"""
Tests for Rate Limiting Service
--------------------------------
Comprehensive tests for token bucket rate limiting including:
- Token consumption and refill
- Per-client and global limits
- Burst handling
- Stale client cleanup
- Statistics reporting
"""
import pytest
import time
import threading
from unittest.mock import patch, MagicMock

from conftest import register_test_storage_drive


class TestTokenBucket:
    """Tests for TokenBucket algorithm."""

    def test_token_bucket_initialization(self):
        """Test that TokenBucket initializes with correct capacity."""
        from app.services.system.rate_limit_service import TokenBucket

        bucket = TokenBucket(capacity=1000, refill_rate=100)

        assert bucket.capacity == 1000
        assert bucket.refill_rate == 100
        assert bucket.tokens == 1000  # Starts full

    def test_consume_tokens_success(self):
        """Test consuming tokens when enough are available."""
        from app.services.system.rate_limit_service import TokenBucket

        bucket = TokenBucket(capacity=1000, refill_rate=100)

        # Should succeed - enough tokens
        assert bucket.consume(500) is True
        assert bucket.tokens == 500

    def test_consume_tokens_failure(self):
        """Test consuming tokens when not enough are available."""
        from app.services.system.rate_limit_service import TokenBucket

        bucket = TokenBucket(capacity=1000, refill_rate=100)

        # Consume most tokens
        bucket.consume(900)
        tokens_after_first = bucket.tokens

        # Should fail - not enough tokens
        assert bucket.consume(200) is False
        # Tokens should be roughly unchanged (may refill slightly due to time)
        assert 95 <= bucket.tokens <= 105  # Allow for small refill

    def test_token_refill_over_time(self):
        """Test that tokens refill at the correct rate."""
        from app.services.system.rate_limit_service import TokenBucket

        bucket = TokenBucket(capacity=1000, refill_rate=100)  # 100 tokens/sec

        # Consume all tokens
        bucket.consume(1000)
        assert bucket.tokens == 0

        # Wait 0.5 seconds - should refill 50 tokens
        time.sleep(0.5)
        bucket._refill()
        assert 45 <= bucket.tokens <= 55  # Allow some timing variance

    def test_refill_does_not_exceed_capacity(self):
        """Test that refilling never exceeds capacity."""
        from app.services.system.rate_limit_service import TokenBucket

        bucket = TokenBucket(capacity=1000, refill_rate=100)

        # Wait and refill (should stay at capacity)
        time.sleep(0.1)
        bucket._refill()
        assert bucket.tokens == 1000  # Capped at capacity

    def test_get_wait_time_when_tokens_available(self):
        """Test wait time is zero when tokens are available."""
        from app.services.system.rate_limit_service import TokenBucket

        bucket = TokenBucket(capacity=1000, refill_rate=100)

        wait_time = bucket.get_wait_time(500)
        assert wait_time == 0.0

    def test_get_wait_time_when_tokens_needed(self):
        """Test wait time calculation when tokens are needed."""
        from app.services.system.rate_limit_service import TokenBucket

        bucket = TokenBucket(capacity=1000, refill_rate=100)  # 100 tokens/sec
        bucket.consume(1000)  # Empty bucket

        # Need 100 tokens, refill rate is 100/sec, so should wait ~1 second
        wait_time = bucket.get_wait_time(100)
        assert 0.9 <= wait_time <= 1.1  # Allow some variance


class TestRateLimiter:
    """Tests for RateLimiter with per-client and global limits."""

    def test_rate_limiter_initialization(self):
        """Test RateLimiter initializes with correct limits."""
        from app.services.system.rate_limit_service import RateLimiter

        limiter = RateLimiter()
        limiter.init_limits(
            upload_per_client_mbps=50.0,
            upload_global_mbps=100.0,
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )

        assert 'upload' in limiter.global_buckets
        assert 'download' in limiter.global_buckets
        assert len(limiter.client_buckets) == 0  # No clients yet

    def test_check_limit_allows_within_limit(self):
        """Test that requests within limits are allowed."""
        from app.services.system.rate_limit_service import RateLimiter

        limiter = RateLimiter()
        limiter.init_limits(
            upload_per_client_mbps=50.0,  # 50 Mbps = 6.25 MB/s
            upload_global_mbps=100.0,
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )

        # Small request should succeed
        assert limiter.check_limit('192.168.1.100', 'upload', 1024) is True

    def test_check_limit_blocks_over_global_limit(self):
        """Test that global limit is enforced."""
        from app.services.system.rate_limit_service import RateLimiter

        limiter = RateLimiter()
        limiter.init_limits(
            upload_per_client_mbps=0.001,  # Very small limit for testing
            upload_global_mbps=0.001,
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )

        # Huge request should fail global limit
        assert limiter.check_limit('192.168.1.100', 'upload', 10 * 1024 * 1024) is False

    def test_check_limit_blocks_over_client_limit(self):
        """Test that per-client limit is enforced."""
        from app.services.system.rate_limit_service import RateLimiter

        limiter = RateLimiter()
        limiter.init_limits(
            upload_per_client_mbps=0.001,  # Very small limit
            upload_global_mbps=100.0,  # Large global limit
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )

        # Should fail per-client limit (even though global allows it)
        assert limiter.check_limit('192.168.1.100', 'upload', 5 * 1024 * 1024) is False

    def test_multiple_clients_tracked_separately(self):
        """Test that multiple clients have independent limits."""
        from app.services.system.rate_limit_service import RateLimiter

        limiter = RateLimiter()
        limiter.init_limits(
            upload_per_client_mbps=50.0,
            upload_global_mbps=200.0,  # High enough for both clients
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )

        # Client 1 consumes tokens
        limiter.check_limit('192.168.1.100', 'upload', 1024)

        # Client 2 should have independent bucket
        assert limiter.check_limit('192.168.1.101', 'upload', 1024) is True
        assert len(limiter.client_buckets) == 2

    def test_stale_client_cleanup(self):
        """Test that stale clients are cleaned up after idle period."""
        from app.services.system.rate_limit_service import RateLimiter

        limiter = RateLimiter()
        limiter.init_limits(
            upload_per_client_mbps=50.0,
            upload_global_mbps=100.0,
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )
        limiter.cleanup_interval = 0  # Force immediate cleanup check

        # Create client bucket
        limiter.check_limit('192.168.1.100', 'upload', 100)
        assert len(limiter.client_buckets) == 1

        # Simulate staleness by backdating last_refill (>5 min idle)
        for bucket in limiter.client_buckets['192.168.1.100'].values():
            bucket.last_refill = time.time() - 600

        # Trigger cleanup
        limiter._maybe_cleanup()

        # Should be cleaned up (idle for >5 min)
        assert len(limiter.client_buckets) == 0

    def test_get_stats(self):
        """Test rate limiter statistics."""
        from app.services.system.rate_limit_service import RateLimiter

        limiter = RateLimiter()
        limiter.init_limits(
            upload_per_client_mbps=50.0,
            upload_global_mbps=100.0,
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )

        # Create some clients
        limiter.check_limit('192.168.1.100', 'upload', 100)
        limiter.check_limit('192.168.1.101', 'download', 100)

        stats = limiter.get_stats()

        assert 'active_clients' in stats
        assert stats['active_clients'] >= 1  # At least one client
        assert 'global_upload_available' in stats
        assert 'global_download_available' in stats


class TestRateLimiterModule:
    """Tests for rate_limit_service module functions."""

    def test_init_rate_limiter(self):
        """Test module-level init_rate_limiter function."""
        from app.services.system import rate_limit_service

        # Should initialize without error
        rate_limit_service.init_rate_limiter(
            upload_per_client_mbps=50.0,
            upload_global_mbps=100.0,
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )

    def test_check_upload_limit(self):
        """Test check_upload_limit function."""
        from app.services.system import rate_limit_service

        rate_limit_service.init_rate_limiter(
            upload_per_client_mbps=50.0,
            upload_global_mbps=100.0,
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )

        # Small upload should succeed
        assert rate_limit_service.check_upload_limit('192.168.1.100', 1024) is True

    def test_check_download_limit(self):
        """Test check_download_limit function."""
        from app.services.system import rate_limit_service

        rate_limit_service.init_rate_limiter(
            upload_per_client_mbps=50.0,
            upload_global_mbps=100.0,
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )

        # Small download should succeed
        assert rate_limit_service.check_download_limit('192.168.1.100', 1024) is True

    def test_get_rate_limiter_stats(self):
        """Test get_rate_limiter_stats function."""
        from app.services.system import rate_limit_service

        rate_limit_service.init_rate_limiter(
            upload_per_client_mbps=50.0,
            upload_global_mbps=100.0,
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )

        stats = rate_limit_service.get_rate_limiter_stats()

        assert isinstance(stats, dict)
        assert 'active_clients' in stats


class TestStorageCleanupScheduler:
    """Tests for Specter upload-session cleanup scheduler."""

    def test_cleanup_scheduler_starts(self, app_context):
        """Runtime init should enable periodic stale-upload cleanup."""
        from specter import registry

        service = registry.require('upload_session_runtime')
        service.teardown_runtime()

        state = service.initialize_runtime(cleanup_interval_seconds=5)

        assert state['runtime_initialized'] is True
        assert state['cleanup_interval_seconds'] == 5

        service.teardown_runtime()

    def test_cleanup_scheduler_stops(self, app_context):
        """Runtime teardown should disable periodic cleanup scheduling."""
        from specter import registry

        service = registry.require('upload_session_runtime')
        service.initialize_runtime(cleanup_interval_seconds=5)
        state = service.teardown_runtime()

        assert state['runtime_initialized'] is False
        assert state['cleanup_interval_seconds'] == 0

    def test_cleanup_scheduler_does_not_start_twice(self, app_context):
        """Repeated runtime init should stay idempotent."""
        from specter import registry

        service = registry.require('upload_session_runtime')
        service.teardown_runtime()
        service.initialize_runtime(cleanup_interval_seconds=7)
        first_interval_id = service._cleanup_interval_id

        state = service.initialize_runtime(cleanup_interval_seconds=7)

        assert state['runtime_initialized'] is True
        assert service._cleanup_interval_id == first_interval_id
        service.teardown_runtime()

    def test_cleanup_removes_stale_uploads(self, app_context):
        """Stale upload sessions should be pruned by cleanup_stale_uploads()."""
        from specter import registry
        import tempfile

        service = registry.require('upload_session_runtime')

        with tempfile.TemporaryDirectory() as tmpdir:
            register_test_storage_drive(tmpdir, name='Cleanup Temp Drive')
            success, message, upload_id = service.init_chunked_upload(
                filename='test.txt',
                total_chunks=10,
                total_size=1024,
                drive_path=tmpdir
            )
            assert success is True
            assert upload_id is not None

            with service.upload_lock:
                service.active_uploads[upload_id]['last_activity'] = time.time() - 7200

            service.cleanup_stale_uploads()

            with service.upload_lock:
                assert upload_id not in service.active_uploads


class TestRateLimitIntegration:
    """Integration tests for rate limiting in routes."""

    def test_upload_chunk_respects_rate_limit(self, app_context):
        """Test that upload chunk endpoint enforces rate limits."""
        from app.services.system import rate_limit_service
        from specter import registry
        import tempfile

        # Initialize with very low limits for testing
        rate_limit_service.init_rate_limiter(
            upload_per_client_mbps=0.000001,  # Effectively zero
            upload_global_mbps=0.000001,
            download_per_client_mbps=50.0,
            download_global_mbps=100.0
        )

        # Create temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            register_test_storage_drive(tmpdir, name='Rate Limit Temp Drive')
            upload_service = registry.require('upload_session_runtime')
            # Initialize upload with correct signature
            success, message, upload_id = upload_service.init_chunked_upload(
                filename='test.txt',
                total_chunks=2,
                total_size=1024,
                drive_path=tmpdir
            )
            
            assert success is True
            assert upload_id is not None

            # First chunk should exhaust rate limit
            upload_service.upload_chunk(upload_id, 0, b'x' * 1024, chunk_size=1024)

            # Second chunk should fail rate limit check
            # (We can't easily test the route here, but we verify the service would reject it)
            # Use non-loopback IP to avoid bypass
            assert rate_limit_service.check_upload_limit('192.168.1.100', 1024) is False

    def test_download_respects_rate_limit(self):
        """Test that download streaming enforces rate limits."""
        from app.services.system import rate_limit_service

        # Initialize with very low limits
        rate_limit_service.init_rate_limiter(
            upload_per_client_mbps=50.0,
            upload_global_mbps=100.0,
            download_per_client_mbps=0.000001,  # Effectively zero
            download_global_mbps=0.000001
        )

        # Consume all download tokens
        rate_limit_service.check_download_limit('192.168.1.100', 10 * 1024 * 1024)

        # Next download should be blocked
        assert rate_limit_service.check_download_limit('192.168.1.100', 1024) is False


# Run these tests with: pytest tests/test_rate_limit_service.py -v
