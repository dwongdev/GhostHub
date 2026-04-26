"""
Tests for SPECTER runtime and HTTP primitives.
"""

from unittest.mock import patch

import gevent
import pytest
from flask import Flask

from specter import (
    Controller,
    Field,
    HTTPError,
    ManagedProcess,
    QueueService,
    Router,
    Schema,
    Service,
    ServiceManager,
    SocketIngress,
    expect_json,
    json_endpoint,
    registry,
    route,
)
from specter.core.registry import SPECTERRegistry


@pytest.fixture(autouse=True)
def mock_gevent_spawn():
    """
    Override the global conftest gevent mock for this module.
    These primitive lifecycle tests need real gevent scheduling semantics.
    """
    yield


@pytest.fixture(autouse=True)
def preserve_registry_state():
    """Prevent registry mutations in this module from leaking into later tests."""
    snapshot = {key: registry.resolve(key) for key in registry.list()}
    yield
    registry.clear()
    for key, value in snapshot.items():
        registry.provide(key, value, replace=True)


class _FakeSocketIO:
    def __init__(self):
        self.handlers = {}
        self.default_error_handler = None

    def on(self, event_name):
        def decorator(fn):
            self.handlers[event_name] = fn
            return fn

        return decorator

    def on_event(self, event_name, callback):
        self.handlers[event_name] = callback
        return callback

    def on_error_default(self, callback):
        self.default_error_handler = callback
        return callback


class _DemoRouter(Router):
    name = 'demo_router'
    url_prefix = '/router'

    @route('/status')
    def status(self):
        return {'ok': True}


class _DemoController(Controller):
    schemas = {
        'ping': Schema('ping', {
            'message': Field(str, required=True),
        }),
    }

    def __init__(self):
        super().__init__('demo_controller')

    def on_start(self):
        self.set_state({'started': True})

    def build_routes(self, router):
        @router.route('/status')
        def get_status():
            return self.get_state()

    def build_events(self, handler):
        handler.on('ping', self.handle_ping)

    def handle_ping(self, data):
        clean = self.schema('ping').require(data)
        return {'echo': clean['message']}


class TestServiceGreenlets:
    def test_spawn_tracks_and_runs_owned_greenlets(self):
        service = Service('runner').start()
        seen = []

        greenlet = service.spawn(lambda: seen.append('ran'))
        greenlet.join(timeout=1)

        assert seen == ['ran']
        assert not service._greenlets

        service.stop()

    def test_spawn_later_is_cancelled_on_stop(self):
        service = Service('runner').start()
        seen = []

        service.spawn_later(0.2, lambda: seen.append('late'))
        service.stop()
        gevent.sleep(0.3)

        assert seen == []

    def test_spawn_requires_started_service(self):
        service = Service('runner')

        with pytest.raises(RuntimeError):
            service.spawn(lambda: None)

    def test_interval_requires_started_service(self):
        service = Service('runner')

        with pytest.raises(RuntimeError):
            service.interval(lambda: None, 1.0)

    def test_timeout_requires_started_service(self):
        service = Service('runner')

        with pytest.raises(RuntimeError):
            service.timeout(lambda: None, 1.0)


class _RecordingQueueService(QueueService):
    def __init__(self, *, delay=0):
        super().__init__('queue', worker_count=1, maxsize=2)
        self.items = []
        self.delay = delay

    def handle_item(self, item):
        if self.delay:
            gevent.sleep(self.delay)
        self.items.append(item)


class TestQueueService:
    def test_enqueue_processes_items_and_updates_state(self):
        service = _RecordingQueueService().start()

        assert service.enqueue('a') is True
        gevent.sleep(0.1)

        assert service.items == ['a']
        assert service.pending_count() == 0
        assert service.get_state()['queue_size'] == 0

        service.stop()

    def test_enqueue_returns_false_when_full(self):
        service = _RecordingQueueService(delay=0.25).start()

        assert service.enqueue('a') is True
        assert service.enqueue('b') is True
        assert service.enqueue('c', block=False) is False

        service.stop()


class TestHttpHelpers:
    def test_json_endpoint_auto_jsonifies_payloads(self):
        app = Flask(__name__)

        @app.route('/ok', methods=['GET'])
        @json_endpoint('Failed')
        def ok_route():
            return {'ok': True}, 201

        with app.test_client() as client:
            response = client.get('/ok')

        assert response.status_code == 201
        assert response.get_json() == {'ok': True}

    def test_json_endpoint_handles_http_error(self):
        app = Flask(__name__)

        @app.route('/fail', methods=['GET'])
        @json_endpoint('Failed')
        def fail_route():
            raise HTTPError('Bad request', 400, payload={'field': 'name'})

        with app.test_client() as client:
            response = client.get('/fail')

        assert response.status_code == 400
        assert response.get_json() == {'error': 'Bad request', 'field': 'name'}

    def test_expect_json_validates_required_fields(self):
        app = Flask(__name__)

        @app.route('/payload', methods=['POST'])
        @json_endpoint('Failed')
        def payload_route():
            data = expect_json(required=['name'])
            return {'name': data['name']}

        with app.test_client() as client:
            bad_response = client.post('/payload', json={'other': 'value'})
            good_response = client.post('/payload', json={'name': 'ghosthub'})

        assert bad_response.status_code == 400
        assert bad_response.get_json()['missing'] == ['name']
        assert 'error' in bad_response.get_json()
        assert good_response.status_code == 200
        assert good_response.get_json() == {'name': 'ghosthub'}

    def test_json_endpoint_supports_no_arg_decorator(self):
        app = Flask(__name__)

        @app.route('/no-arg', methods=['GET'])
        @json_endpoint
        def no_arg_route():
            raise HTTPError('Teapot', status=418)

        with app.test_client() as client:
            response = client.get('/no-arg')

        assert response.status_code == 418
        assert response.get_json() == {'error': 'Teapot'}


class TestRouterAndController:
    def test_router_class_routes_mount(self):
        app = Flask(__name__)
        router = _DemoRouter()
        router.register(app)

        with app.test_client() as client:
            response = client.get('/router/status')

        assert response.status_code == 200
        assert response.get_json() == {'ok': True}

    def test_controller_build_blueprint_supports_instance_routes(self):
        app = Flask(__name__)
        controller = _DemoController()
        app.register_blueprint(controller.build_blueprint(), url_prefix='/controller')

        with app.test_client() as client:
            response = client.get('/controller/status')

        assert response.status_code == 200
        assert response.get_json() == {}


class TestServiceManager:
    def test_register_controller_boots_routes_and_handlers(self):
        app = Flask(__name__)
        socketio = _FakeSocketIO()
        controller = _DemoController()
        manager = ServiceManager(app, socketio)

        manager.register_controller(controller, url_prefix='/managed')
        manager.boot()

        with app.test_client() as client:
            response = client.get('/managed/status')

        assert response.status_code == 200
        assert response.get_json() == {'started': True}
        assert 'ping' in socketio.handlers
        assert socketio.handlers['ping']({'message': 'hello'}) == {'echo': 'hello'}

        manager.shutdown()
        assert not controller.running

    def test_shared_socket_ingress_fans_out_in_priority_order(self):
        app = Flask(__name__)
        socketio = _FakeSocketIO()
        controller = _DemoController()
        seen = []
        manager = ServiceManager(app, socketio)

        manager.register_controller(controller, url_prefix='/managed')
        manager.boot()

        registry.require('socket_ingress').subscribe(
            'ping',
            lambda data: seen.append(('legacy', data['message'])),
            priority=50,
        )

        result = socketio.handlers['ping']({'message': 'hello'})

        assert seen == [('legacy', 'hello')]
        assert result == {'echo': 'hello'}

        manager.shutdown()


class TestSocketIngress:
    def test_dispatches_multiple_subscribers_in_priority_order(self):
        socketio = _FakeSocketIO()
        ingress = SocketIngress(socketio)
        seen = []

        ingress.subscribe(
            'shared',
            lambda data: seen.append(('late', data['value'])),
            priority=200,
        )
        ingress.subscribe(
            'shared',
            lambda data: seen.append(('early', data['value'])),
            priority=50,
        )

        socketio.handlers['shared']({'value': 3})

        assert seen == [('early', 3), ('late', 3)]

    def test_dispatches_default_error_subscribers_in_priority_order(self):
        socketio = _FakeSocketIO()
        ingress = SocketIngress(socketio)
        seen = []

        ingress.subscribe_error_default(
            lambda exc: seen.append(('late', str(exc))),
            priority=200,
        )
        ingress.subscribe_error_default(
            lambda exc: seen.append(('early', str(exc))),
            priority=50,
        )

        socketio.default_error_handler(RuntimeError('boom'))

        assert seen == [('early', 'boom'), ('late', 'boom')]

    def test_clear_resets_dispatchers_for_future_attach(self):
        first_socketio = _FakeSocketIO()
        second_socketio = _FakeSocketIO()
        ingress = SocketIngress(first_socketio)
        seen = []

        ingress.subscribe('ping', lambda data: seen.append(('first', data['value'])))
        assert 'ping' in first_socketio.handlers

        ingress.clear()
        ingress.attach(second_socketio)
        ingress.subscribe('ping', lambda data: seen.append(('second', data['value'])))

        assert 'ping' in second_socketio.handlers
        second_socketio.handlers['ping']({'value': 7})
        assert seen == [('second', 7)]


class TestSchemaAndRegistry:
    def test_schema_require_raises_http_error_with_field_errors(self):
        schema = Schema('payload', {
            'count': Field(lambda value: int(value), required=True),
        })

        assert schema.require({'count': '3'}) == {'count': 3}

        with pytest.raises(HTTPError) as exc:
            schema.require({})

        assert exc.value.status_code == 400
        assert exc.value.payload['errors']['count'] == "'count' is required"

    def test_registry_rejects_invalid_owner_without_registering(self):
        with pytest.raises(TypeError):
            registry.provide('bad-owner', object(), owner=object())

        assert registry.resolve('bad-owner') is None

    def test_wait_for_timeout_raises_timeouterror_and_cleans_waiter(self):
        local_registry = SPECTERRegistry()

        with pytest.raises(TimeoutError):
            local_registry.wait_for('missing', timeout=0.01)

        assert local_registry._waiters == {}


class TestManagedProcess:
    def test_start_validates_owner_before_spawning(self):
        process = ManagedProcess('demo')

        with patch('specter.core.process.subprocess.Popen') as popen:
            with pytest.raises(TypeError):
                process.start(['echo', 'hello'], owner=object())

        popen.assert_not_called()
