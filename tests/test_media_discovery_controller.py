"""Tests for media discovery controller timeline helpers."""

from unittest.mock import patch


class TestMediaDiscoveryController:
    def test_get_timeline_years_includes_full_month_media_counts(self):
        """Month metadata should carry the full month total for gallery headers."""
        from app.controllers.media.media_discovery_controller import MediaDiscoveryController

        controller = MediaDiscoveryController()

        with patch(
            'app.controllers.media.media_discovery_controller.SortService.get_timeline_dates',
            return_value={
                '2024-09-11': 5,
                '2024-09-08': 18,
                '2024-08-30': 7,
            }
        ):
            result = controller.get_timeline_years()

        assert result == [{
            'year': 2024,
            'month_count': 2,
            'media_count': 30,
            'first_date': '2024-08-30',
            'months': [
                {
                    'month': 9,
                    'dateKey': '2024-09-11',
                    'media_count': 23,
                },
                {
                    'month': 8,
                    'dateKey': '2024-08-30',
                    'media_count': 7,
                },
            ],
        }]
