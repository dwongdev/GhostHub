"""
Tests for tunnel domain services.
"""

import os
from unittest.mock import Mock, patch

import pytest


class TestTunnelService:
    @pytest.fixture(autouse=True)
    def reset_tunnel_state(self):
        from app.services.system.tunnel.state_service import replace_active_tunnel_info

        replace_active_tunnel_info()
        yield
        replace_active_tunnel_info()

    def test_find_cloudflared_path_from_env(self):
        from app.services.system.tunnel.binary_service import find_cloudflared_path

        with patch.dict(os.environ, {'CLOUDFLARED_PATH': '/usr/local/bin/cloudflared'}), \
             patch('os.path.exists', return_value=True):
            assert find_cloudflared_path() == '/usr/local/bin/cloudflared'

    def test_find_cloudflared_path_from_which(self):
        from app.services.system.tunnel.binary_service import find_cloudflared_path

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('CLOUDFLARED_PATH', None)
            with patch('shutil.which', return_value='/usr/bin/cloudflared'):
                assert find_cloudflared_path() == '/usr/bin/cloudflared'

    def test_find_cloudflared_path_not_found(self):
        from app.services.system.tunnel.binary_service import find_cloudflared_path

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('CLOUDFLARED_PATH', None)
            with patch('shutil.which', return_value=None), \
                 patch('os.path.exists', return_value=False):
                assert find_cloudflared_path() is None

    def test_get_active_tunnel_status_stopped(self):
        from app.services.system.tunnel.process_service import get_process_tunnel_status

        status = get_process_tunnel_status()
        assert status['status'] == 'stopped'
        assert status['provider'] is None
        assert status['url'] is None

    def test_get_active_tunnel_status_running(self):
        from app.services.system.tunnel.process_service import get_process_tunnel_status
        from app.services.system.tunnel.state_service import replace_active_tunnel_info

        mock_process = Mock()
        mock_process.poll.return_value = None

        replace_active_tunnel_info({
            "provider": "cloudflare",
            "url": "https://test.trycloudflare.com",
            "process": mock_process,
            "local_port": 5000,
        })

        status = get_process_tunnel_status()
        assert status['status'] == 'running'
        assert status['provider'] == 'cloudflare'
        assert status['url'] == 'https://test.trycloudflare.com'
        assert status['local_port'] == 5000

    def test_stop_active_tunnel_no_process(self):
        from app.services.system.tunnel.process_service import stop_process_tunnel

        result = stop_process_tunnel()
        assert result['status'] == 'success'
        assert 'No active tunnel' in result['message']

    def test_stop_active_tunnel_running_process(self):
        from app.services.system.tunnel.process_service import stop_process_tunnel
        from app.services.system.tunnel.state_service import replace_active_tunnel_info

        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.pid = 12345

        replace_active_tunnel_info({
            "provider": "cloudflare",
            "url": "https://test.trycloudflare.com",
            "process": mock_process,
            "local_port": 5000,
        })

        result = stop_process_tunnel()
        assert result['status'] == 'success'
        mock_process.terminate.assert_called_once()

    def test_stop_active_tunnel_already_stopped(self):
        from app.services.system.tunnel.process_service import stop_process_tunnel
        from app.services.system.tunnel.state_service import replace_active_tunnel_info

        mock_process = Mock()
        mock_process.poll.return_value = 0

        replace_active_tunnel_info({
            "provider": "pinggy",
            "process": mock_process,
            "local_port": 5000,
        })

        result = stop_process_tunnel()
        assert result['status'] == 'success'

    def test_start_cloudflare_tunnel_no_executable(self):
        from app.services.system.tunnel.provider_service import start_cloudflare_tunnel

        result = start_cloudflare_tunnel(None, 5000)
        assert result['status'] == 'error'
        assert 'not found' in result['message']

    def test_start_cloudflare_tunnel_already_running(self):
        from app.services.system.tunnel.provider_service import start_cloudflare_tunnel
        from app.services.system.tunnel.state_service import replace_active_tunnel_info

        mock_process = Mock()
        mock_process.poll.return_value = None
        replace_active_tunnel_info({'provider': 'pinggy', 'process': mock_process})

        result = start_cloudflare_tunnel('/usr/bin/cloudflared', 5000)
        assert result['status'] == 'error'
        assert 'already running' in result['message']

    @patch('subprocess.Popen')
    @patch('app.services.system.tunnel.provider_service.collect_process_output_lines')
    @patch('app.services.system.tunnel.provider_service.gevent.sleep')
    @patch('app.services.system.tunnel.provider_service.register_process_tunnel')
    def test_start_cloudflare_tunnel_success(
        self,
        mock_register,
        mock_sleep,
        mock_collect_output,
        mock_popen,
    ):
        from app.services.system.tunnel.provider_service import start_cloudflare_tunnel

        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        result = start_cloudflare_tunnel('/usr/bin/cloudflared', 5000)

        assert result['status'] == 'success'
        mock_popen.assert_called_once()
        mock_register.assert_called_once_with("cloudflare", mock_process, 5000)
        mock_collect_output.assert_called_once_with(
            mock_process,
            [],
            label_prefix='Cloudflare',
        )
        mock_sleep.assert_called_once_with(2)

    @patch('subprocess.Popen')
    @patch('app.services.system.tunnel.provider_service.collect_process_output_lines')
    @patch('app.services.system.tunnel.provider_service.gevent.sleep')
    def test_start_cloudflare_tunnel_surfaces_startup_exit(
        self,
        mock_sleep,
        mock_collect_output,
        mock_popen,
    ):
        from app.services.system.tunnel.provider_service import start_cloudflare_tunnel

        mock_process = Mock()
        mock_process.poll.return_value = 1
        mock_process.communicate.return_value = ('', '')
        mock_popen.return_value = mock_process

        def collect_output(_process, output_lines, *, label_prefix):
            assert label_prefix == 'Cloudflare'
            output_lines.append('Cannot use Quick Tunnel with an existing configuration file')

        mock_collect_output.side_effect = collect_output

        result = start_cloudflare_tunnel('/usr/bin/cloudflared', 5000)

        assert result['status'] == 'error'
        assert 'existing configuration file' in result['message']

    @patch('subprocess.Popen')
    @patch('app.services.system.tunnel.provider_service.collect_process_output_lines')
    @patch('app.services.system.tunnel.provider_service.gevent.sleep')
    def test_start_cloudflare_tunnel_reads_final_process_output_on_fast_exit(
        self,
        mock_sleep,
        mock_collect_output,
        mock_popen,
    ):
        from app.services.system.tunnel.provider_service import start_cloudflare_tunnel

        mock_process = Mock()
        mock_process.poll.return_value = 1
        mock_process.communicate.return_value = ('', 'failed to reach edge')
        mock_popen.return_value = mock_process

        result = start_cloudflare_tunnel('/usr/bin/cloudflared', 5000)

        assert result['status'] == 'error'
        assert 'failed to reach edge' in result['message']

    def test_start_pinggy_tunnel_no_token(self):
        from app.services.system.tunnel.provider_service import start_pinggy_tunnel

        result = start_pinggy_tunnel(5000, None)
        assert result['status'] == 'error'
        assert 'token' in result['message'].lower()

    def test_start_pinggy_tunnel_empty_token(self):
        from app.services.system.tunnel.provider_service import start_pinggy_tunnel

        result = start_pinggy_tunnel(5000, '')
        assert result['status'] == 'error'

    def test_start_pinggy_tunnel_already_running(self):
        from app.services.system.tunnel.provider_service import start_pinggy_tunnel
        from app.services.system.tunnel.state_service import replace_active_tunnel_info

        mock_process = Mock()
        mock_process.poll.return_value = None
        replace_active_tunnel_info({'provider': 'cloudflare', 'process': mock_process})

        result = start_pinggy_tunnel(5000, 'test-token')
        assert result['status'] == 'error'
        assert 'already running' in result['message']

    @patch('subprocess.Popen')
    @patch('app.services.system.tunnel.provider_service.ensure_pinggy_ssh_key')
    def test_start_pinggy_tunnel_ssh_not_found(self, mock_ensure_key, mock_popen):
        from app.services.system.tunnel.provider_service import start_pinggy_tunnel

        mock_popen.side_effect = FileNotFoundError("ssh not found")

        result = start_pinggy_tunnel(5000, 'test-token')
        assert result['status'] == 'error'
        assert 'ssh' in result['message'].lower()

    @patch('app.services.system.tunnel.mesh_service.generate_tailscale_qr_code', return_value='qr')
    @patch('app.services.system.tunnel.mesh_service.generate_client_preauth_key', return_value=('remote', 'preauth-key'))
    @patch('app.services.system.tunnel.mesh_service.start_mesh_watchdog')
    @patch('app.services.system.tunnel.mesh_service.manual_dns_update', return_value=True)
    @patch('app.services.system.tunnel.mesh_service.start_hs', return_value=(True, 'ok'))
    @patch('app.services.system.tunnel.mesh_service.generate_config', return_value=True)
    @patch('app.services.system.tunnel.mesh_service.network_detection_service.get_interface_ips', return_value={'eth0': '10.0.0.5'})
    @patch('app.services.system.tunnel.mesh_service.os.path.exists', return_value=False)
    def test_start_mesh_tunnel_bootstraps_with_local_headscale_url(
        self,
        mock_exists,
        mock_get_interfaces,
        mock_generate_config,
        mock_start_hs,
        mock_manual_dns_update,
        mock_start_watchdog,
        mock_generate_client_key,
        mock_generate_qr,
    ):
        from app.services.system.tunnel.mesh_service import start_mesh_tunnel
        from app.services.system.tunnel.state_service import get_active_tunnel_info

        result = start_mesh_tunnel()

        mock_generate_config.assert_called_once_with('http://10.0.0.5:8080')
        assert result['status'] == 'starting'
        assert get_active_tunnel_info()['url'] == 'http://10.0.0.5:8080'
