"""GhostHub media discovery controller built on Specter."""

from flask import request

from app.services.media.sort_service import SortService
from specter import Controller, registry
from app.utils.auth import get_show_hidden_flag

from app.controllers._media_support import MediaVisibilitySupport


class MediaDiscoveryController(MediaVisibilitySupport, Controller):
    """Newest-media and timeline queries for gallery-style browsing."""

    name = 'media_discovery'
    url_prefix = '/api'

    def build_routes(self, router):
        @router.route(
            '/media/newest',
            methods=['GET'],
            json_errors='Failed to get newest media',
        )
        def get_newest_media():
            limit = request.args.get('limit', 10, type=int)
            media = self.get_newest_media(
                limit=limit,
                show_hidden=get_show_hidden_flag(),
            )
            return {'media': media}

        @router.route(
            '/media/timeline/years',
            methods=['GET'],
            json_errors='Failed to get timeline years',
        )
        def get_timeline_years():
            result = self.get_timeline_years(
                media_filter=request.args.get('filter', 'all', type=str).lower(),
                category_id=request.args.get('category_id'),
                show_hidden=get_show_hidden_flag(),
            )
            return {
                'years': result,
                'total_years': len(result),
            }

        @router.route(
            '/media/timeline',
            methods=['GET'],
            json_errors='Failed to get media timeline',
        )
        def get_media_timeline():
            return self.get_media_timeline(
                media_filter=request.args.get('filter', 'all', type=str).lower(),
                items_per_date=request.args.get('items_per_date', 24, type=int),
                dates_page=request.args.get('dates_page', 1, type=int),
                dates_limit=request.args.get('dates_limit', 15, type=int),
                specific_date=request.args.get('date', type=str),
                date_offset=request.args.get('date_offset', 0, type=int),
                category_id=request.args.get('category_id'),
                jump_to_date=request.args.get('jump_to_date'),
                month_filter=request.args.get('month_filter', type=str),
                show_hidden=get_show_hidden_flag(),
            )

    def get_newest_media(self, *, limit=10, show_hidden=False):
        newest_media = SortService.get_sorted_media(
            category_id=None,
            sort_by='mtime',
            sort_order='DESC',
            page=1,
            limit=limit,
            show_hidden=show_hidden,
        )
        return self._filter_hidden_media_items(newest_media, show_hidden)

    def get_timeline_years(
        self,
        *,
        media_filter='all',
        category_id=None,
        show_hidden=False,
    ):
        date_counts = SortService.get_timeline_dates(
            category_id=category_id,
            filter_type=media_filter,
            show_hidden=show_hidden,
        )

        years_data = {}
        for date_key, count in date_counts.items():
            try:
                year = int(date_key.split('-')[0])
                month = int(date_key.split('-')[1])
            except (ValueError, IndexError):
                continue

            if year not in years_data:
                years_data[year] = {
                    'months': set(),
                    'count': 0,
                    'first_date': date_key,
                    'month_dates': {},
                    'month_counts': {},
                }

            years_data[year]['months'].add(month)
            years_data[year]['count'] += count
            years_data[year]['month_counts'][month] = (
                years_data[year]['month_counts'].get(month, 0) + count
            )
            if (
                month not in years_data[year]['month_dates'] or
                date_key > years_data[year]['month_dates'][month]
            ):
                years_data[year]['month_dates'][month] = date_key
            if date_key < years_data[year]['first_date']:
                years_data[year]['first_date'] = date_key

        result = []
        for year in sorted(years_data.keys(), reverse=True):
            data = years_data[year]
            months = [{
                'month': month,
                'dateKey': data['month_dates'].get(month),
                'media_count': data['month_counts'].get(month, 0),
            } for month in sorted(list(data['months']), reverse=True)]
            result.append({
                'year': year,
                'month_count': len(data['months']),
                'media_count': data['count'],
                'first_date': data['first_date'],
                'months': months,
            })

        return result

    def get_media_timeline(
        self,
        *,
        media_filter='all',
        items_per_date=24,
        dates_page=1,
        dates_limit=15,
        specific_date=None,
        date_offset=0,
        category_id=None,
        jump_to_date=None,
        month_filter=None,
        show_hidden=False,
    ):
        if specific_date:
            collected = []
            offset = date_offset
            exhausted = False
            while len(collected) < items_per_date:
                batch = SortService.get_media_for_date(
                    specific_date,
                    category_id=category_id,
                    filter_type=media_filter,
                    limit=items_per_date,
                    offset=offset,
                    show_hidden=show_hidden,
                )
                if not batch:
                    exhausted = True
                    break
                filtered = self._filter_hidden_media_items(batch, show_hidden)
                collected.extend(filtered)
                offset += len(batch)
                if len(batch) < items_per_date:
                    exhausted = True
                    break
            items = collected[:items_per_date]
            self._prioritize_thumbnail_generation(items)
            return {
                'media': items,
                'date': specific_date,
                'offset': offset,
                'has_more_for_date': not exhausted and len(collected) >= items_per_date,
            }

        date_counts = SortService.get_timeline_dates(
            category_id=category_id,
            filter_type=media_filter,
            show_hidden=show_hidden,
        )
        all_dates = sorted(date_counts.keys(), reverse=True)

        if month_filter:
            prefix = month_filter + '-'
            all_dates = [d for d in all_dates if d.startswith(prefix)]

        total_dates = len(all_dates)

        if jump_to_date and jump_to_date in all_dates:
            dates_page = (all_dates.index(jump_to_date) // dates_limit) + 1

        start_idx = (dates_page - 1) * dates_limit
        page_dates = all_dates[start_idx:start_idx + dates_limit]

        result_media = []
        date_totals = {}

        for date_key in page_dates:
            collected = []
            offset = 0
            exhausted = False
            while len(collected) < items_per_date:
                batch = SortService.get_media_for_date(
                    date_key,
                    category_id=category_id,
                    filter_type=media_filter,
                    limit=items_per_date,
                    offset=offset,
                    show_hidden=show_hidden,
                )
                if not batch:
                    exhausted = True
                    break
                filtered = self._filter_hidden_media_items(batch, show_hidden)
                collected.extend(filtered)
                offset += len(batch)
                if len(batch) < items_per_date:
                    exhausted = True
                    break

            if exhausted:
                date_totals[date_key] = len(collected)
            else:
                date_totals[date_key] = date_counts.get(date_key, len(collected))
            result_media.extend(collected[:items_per_date])

        self._prioritize_thumbnail_generation(result_media)

        return {
            'media': result_media,
            'date_totals': date_totals,
            'items_per_date': items_per_date,
            'dates_page': dates_page,
            'total_dates': total_dates,
            'has_more_dates': (start_idx + dates_limit) < total_dates,
        }

    def _prioritize_thumbnail_generation(self, media_items):
        """Promote thumbnails for timeline slices the client is actively viewing."""
        if not media_items:
            return

        try:
            registry.require('thumbnail_runtime').prioritize_media_slice(media_items)
        except Exception:
            return
