"""Tests for category enrichment runtime data behavior."""

from unittest.mock import Mock, patch

from app.services.media.category_enrichment_service import (
    enrich_categories_with_runtime_data,
)


class TestCategoryEnrichmentService:
    """Coverage for optional runtime dependencies in category enrichment."""

    def test_enrichment_skips_thumbnail_status_when_runtime_is_unavailable(self):
        categories = [{'id': 'movies', 'name': 'Movies'}]

        with (
            patch(
                'app.services.media.category_enrichment_service.get_runtime_config_value',
                return_value=False,
            ),
            patch(
                'app.services.media.category_enrichment_service.registry.resolve',
                return_value=None,
            ),
        ):
            enrich_categories_with_runtime_data(categories)

        assert categories[0].get('processingStatus') is None
        assert categories[0].get('processingData') is None

    def test_enrichment_sets_processing_status_when_thumbnail_runtime_reports_pending(self):
        categories = [{'id': 'movies', 'name': 'Movies'}]
        thumbnail_runtime = Mock()
        thumbnail_runtime.get_thumbnail_status.return_value = {
            'status': 'pending',
            'processed': 1,
            'total': 10,
        }

        with (
            patch(
                'app.services.media.category_enrichment_service.get_runtime_config_value',
                return_value=False,
            ),
            patch(
                'app.services.media.category_enrichment_service.registry.resolve',
                return_value=thumbnail_runtime,
            ),
        ):
            enrich_categories_with_runtime_data(categories)

        assert categories[0]['processingStatus'] == 'generating'
        assert categories[0]['processingData']['status'] == 'pending'
