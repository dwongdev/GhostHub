/**
 * Gallery Layout - Data Fetching
 * Handles API calls and data management for timeline view
 */

import {
    getAllMedia,
    setAllMedia,
    clearAllMedia,
    setCategoriesData,
    getCategoriesData,
    getMediaFilter,
    getCategoryIdFilter,
    getCategoryIdsFilter,
    getParentNameFilter,
    getMediaByDate,
    setDateTotals,
    mergeDateTotals,
    getDateTotal,
    getDatesPage,
    setDatesPage,
    getHasMoreDates,
    setHasMoreDates,
    setIsLoading,
    groupMediaByDate,
    setAllYearsData
} from './state.js';

import { getShowHiddenHeaders } from '../../../utils/showHiddenManager.js';
import { cachedFetch } from '../../../utils/requestCache.js';

/**
 * Fetch hardware tier from backend
 * Returns: 'LITE' (2GB), 'STANDARD' (4GB), or 'PRO' (8GB+)
 */
export async function fetchHardwareTier() {
    try {
        const response = await fetch('/api/storage/upload/negotiate');
        if (response.ok) {
            const data = await response.json();
            return data.hardware_tier || 'LITE';
        }
    } catch (error) {
        console.warn('[GalleryData] Failed to fetch hardware tier:', error);
    }
    return 'LITE'; // Default to base tier
}

/**
 * Fetch all categories
 * @param {boolean} forceRefresh - If true, bypass server cache
 */
export async function fetchCategories(forceRefresh = false) {
    try {
        const params = new URLSearchParams();
        if (forceRefresh) params.append('force_refresh', 'true');
        const categoryIdFilter = getCategoryIdFilter();
        const categoryIdsFilter = getCategoryIdsFilter();
        const parentNameFilter = getParentNameFilter();

        if (categoryIdFilter) {
            params.append('category_id', categoryIdFilter);
        }

        // Prioritize specific category IDs over parent name
        if (categoryIdsFilter && categoryIdsFilter.length > 0) {
            params.append('category_ids', categoryIdsFilter.join(','));
        } else if (parentNameFilter) {
            params.append('parent_name', parentNameFilter);
        }

        const url = `/api/categories?${params}`;
        const response = await cachedFetch(url, {
            headers: getShowHiddenHeaders()
        });
        if (!response.ok) throw new Error('Failed to fetch categories');

        const data = await response.json();
        const categories = data.categories || [];
        setCategoriesData(categories);
        return categories;
    } catch (e) {
        console.error('[GalleryLayout] Error fetching categories:', e);
        return [];
    }
}

/**
 * Fetch media grouped by date with pagination
 * @param {number} page - Page of dates to load (default 1)
 */
export async function fetchTimelineMedia(page = 1) {
    const filter = getMediaFilter();
    const categoryId = getCategoryIdFilter();
    const categoryIdsFilter = getCategoryIdsFilter();

    try {
        const params = new URLSearchParams({
            filter: filter,
            items_per_date: 9,
            dates_page: page,
            dates_limit: 15
        });

        if (categoryId) {
            params.append('category_id', categoryId);
        }

        if (categoryIdsFilter && categoryIdsFilter.length > 0) {
            params.append('category_ids', categoryIdsFilter.join(','));
        }

        const response = await cachedFetch(`/api/media/timeline?${params}`, {
            headers: getShowHiddenHeaders()
        });

        if (!response.ok) {
            throw new Error('Failed to fetch timeline');
        }

        const data = await response.json();
        return {
            media: data.media || [],
            dateTotals: data.date_totals || {},
            hasMoreDates: data.has_more_dates || false
        };
    } catch (e) {
        console.error('[GalleryLayout] Error fetching timeline media:', e);
        return { media: [], dateTotals: {}, hasMoreDates: false };
    }
}

/**
 * Fetch more items for a specific date
 * Used by "Show more" button per date group
 */
export async function fetchMoreForDate(dateKey, offset) {
    const filter = getMediaFilter();
    const categoryId = getCategoryIdFilter();
    const categoryIdsFilter = getCategoryIdsFilter();

    try {
        const params = new URLSearchParams({
            filter: filter,
            date: dateKey,
            date_offset: offset,
            items_per_date: 9
        });

        if (categoryId) {
            params.append('category_id', categoryId);
        }

        if (categoryIdsFilter && categoryIdsFilter.length > 0) {
            params.append('category_ids', categoryIdsFilter.join(','));
        }

        const response = await fetch(`/api/media/timeline?${params}`, {
            headers: getShowHiddenHeaders()
        });

        if (!response.ok) {
            throw new Error('Failed to fetch more for date');
        }

        const data = await response.json();
        return {
            media: data.media || [],
            hasMore: data.has_more_for_date || false,
            totalForDate: data.total_for_date || 0
        };
    } catch (e) {
        console.error('[GalleryLayout] Error fetching more for date:', e);
        return { media: [], hasMore: false, totalForDate: 0 };
    }
}

/**
 * Fetch all available years for timeline navigation
 * This allows the timeline to show all years even before they're paginated
 */
export async function fetchAllYears() {
    const filter = getMediaFilter();
    const categoryId = getCategoryIdFilter();
    const categoryIdsFilter = getCategoryIdsFilter();

    try {
        const params = new URLSearchParams({ filter });

        if (categoryId) {
            params.append('category_id', categoryId);
        }

        if (categoryIdsFilter && categoryIdsFilter.length > 0) {
            params.append('category_ids', categoryIdsFilter.join(','));
        }

        const response = await fetch(`/api/media/timeline/years?${params}`, {
            headers: getShowHiddenHeaders()
        });

        if (!response.ok) {
            throw new Error('Failed to fetch timeline years');
        }

        const data = await response.json();
        setAllYearsData(data.years || []);
        return data.years || [];
    } catch (e) {
        console.error('[GalleryLayout] Error fetching timeline years:', e);
        return [];
    }
}

/**
 * Load initial media for gallery
 * Fetches first page of dates with limited items per date
 * @param {boolean} forceRefresh - If true, bypass server cache
 */
export async function loadInitialMedia(forceRefresh = false) {
    setIsLoading(true);
    clearAllMedia();

    try {
        await fetchCategories(forceRefresh);

        // Fetch all years for timeline navigation (parallel with media)
        const [yearsResult, mediaResult] = await Promise.all([
            fetchAllYears(),
            fetchTimelineMedia(1)
        ]);

        setAllMedia(mediaResult.media);
        setDateTotals(mediaResult.dateTotals);
        setDatesPage(1);
        setHasMoreDates(mediaResult.hasMoreDates);
        groupMediaByDate();

        return mediaResult.media;
    } catch (e) {
        console.error('[GalleryLayout] Error loading initial media:', e);
        return [];
    } finally {
        setIsLoading(false);
    }
}

/**
 * Jump to a specific date by loading the page containing that date
 * @param {string} dateKey - The date key to jump to (e.g., "2024-05-31")
 * @returns {Promise<boolean>} - True if successful
 */
export async function jumpToDate(dateKey) {
    if (!dateKey) return false;

    const filter = getMediaFilter();
    const categoryId = getCategoryIdFilter();
    const categoryIdsFilter = getCategoryIdsFilter();

    try {
        const params = new URLSearchParams({
            filter: filter,
            items_per_date: 9,
            jump_to_date: dateKey,
            dates_limit: 15
        });

        if (categoryId) {
            params.append('category_id', categoryId);
        }

        if (categoryIdsFilter && categoryIdsFilter.length > 0) {
            params.append('category_ids', categoryIdsFilter.join(','));
        }

        const response = await cachedFetch(`/api/media/timeline?${params}`, {
            headers: getShowHiddenHeaders()
        });

        if (!response.ok) {
            throw new Error('Failed to jump to date');
        }

        const data = await response.json();

        if (data.media && data.media.length > 0) {
            // Append new media to existing
            const currentMedia = getAllMedia();
            const existingUrls = new Set(currentMedia.map(m => m.url));
            const newMedia = data.media.filter(m => !existingUrls.has(m.url));

            if (newMedia.length > 0) {
                setAllMedia([...currentMedia, ...newMedia]);
            }

            // Merge date totals
            mergeDateTotals(data.date_totals || {});

            // IMPORTANT: Update datesPage to the page we just loaded
            if (data.dates_page) {
                setDatesPage(data.dates_page);
            }

            setHasMoreDates(data.has_more_dates || false);
            groupMediaByDate();

            return true;
        }

        return false;
    } catch (e) {
        console.error('[GalleryLayout] Error jumping to date:', e);
        return false;
    }
}

/**
 * Jump to a specific year by loading pages until we have data for that year
 * @param {number} targetYear - The year to jump to (e.g., 2022)
 * @returns {Promise<string|null>} - The first date key found for that year, or null
 */
export async function jumpToYear(targetYear) {
    const mediaByDate = getMediaByDate();
    const yearPrefix = `${targetYear}-`;

    // Check if we already have data for this year
    const existingDate = Object.keys(mediaByDate).find(d => d.startsWith(yearPrefix));
    if (existingDate) {
        return existingDate;
    }

    // Need to load more pages until we find this year
    // Force load even if hasMoreDates is false - the API might have more data
    let maxAttempts = 50; // Increased limit for large libraries
    let currentPage = getDatesPage();

    while (maxAttempts > 0) {
        // Force fetch next page directly (bypass hasMoreDates check)
        currentPage++;
        const result = await fetchTimelineMedia(currentPage);

        if (result.media.length === 0) {
            // No more data from server
            break;
        }

        // Append new media to existing
        const currentMedia = getAllMedia();
        const existingUrls = new Set(currentMedia.map(m => m.url));
        const newMedia = result.media.filter(m => !existingUrls.has(m.url));

        if (newMedia.length > 0) {
            setAllMedia([...currentMedia, ...newMedia]);
        }

        mergeDateTotals(result.dateTotals);
        setDatesPage(currentPage);
        setHasMoreDates(result.hasMoreDates);
        groupMediaByDate();

        // Check if we now have data for the target year
        const newMediaByDate = getMediaByDate();
        const foundDate = Object.keys(newMediaByDate).find(d => d.startsWith(yearPrefix));
        if (foundDate) {
            return foundDate;
        }

        // Check if we've gone past the target year (dates are sorted newest first)
        const allDates = Object.keys(newMediaByDate).sort();
        const oldestLoadedDate = allDates[0];
        if (oldestLoadedDate && parseInt(oldestLoadedDate.split('-')[0]) < targetYear) {
            // We've loaded past this year, it doesn't exist
            return null;
        }

        // Stop if server says no more
        if (!result.hasMoreDates) {
            break;
        }

        maxAttempts--;
    }

    return null;
}

/**
 * Load more dates (next page of dates)
 * Called by "Load more" button at bottom
 */
export async function loadMoreDates() {
    if (!getHasMoreDates()) return { media: [], hasMore: false };

    const nextPage = getDatesPage() + 1;
    console.log(`[GalleryData] Loading more dates, page: ${nextPage}`);

    try {
        const result = await fetchTimelineMedia(nextPage);

        if (result.media && result.media.length > 0) {
            // Append new media to existing, avoiding duplicates
            const currentMedia = getAllMedia();
            const existingUrls = new Set(currentMedia.map(m => m.url));
            const newMedia = result.media.filter(m => !existingUrls.has(m.url));

            if (newMedia.length > 0) {
                setAllMedia([...currentMedia, ...newMedia]);
            }

            // Merge date totals (preserves existing totals)
            mergeDateTotals(result.dateTotals);

            setDatesPage(nextPage);
            setHasMoreDates(result.hasMoreDates);
            groupMediaByDate();

            console.log(`[GalleryData] Successfully loaded page ${nextPage}. media: ${result.media.length}, new: ${newMedia.length}, hasMore: ${result.hasMoreDates}`);
        } else {
            // Only set to false if the server explicitly says no more or we reached the end
            // Otherwise we might want to allow a retry
            console.warn(`[GalleryData] Page ${nextPage} returned no media.`);
            setHasMoreDates(result.hasMoreDates || false);
        }

        return {
            media: result.media,
            hasMore: result.hasMoreDates
        };
    } catch (e) {
        console.error('[GalleryLayout] Error loading more dates:', e);
        return { media: [], hasMore: false };
    }
}

/**
 * Load more items for a specific date
 * Called by "Show more" button per date group
 */
export async function loadMoreForDate(dateKey) {
    const mediaByDate = getMediaByDate();
    const currentItems = mediaByDate[dateKey] || [];
    const offset = currentItems.length;

    try {
        const result = await fetchMoreForDate(dateKey, offset);

        if (result.media.length > 0) {
            // Avoid duplicates by checking existing URLs
            const existingUrls = new Set(currentItems.map(m => m.url));
            const newMedia = result.media.filter(m => !existingUrls.has(m.url));

            if (newMedia.length > 0) {
                // Append to existing date group (direct mutation is intentional here
                // as mediaByDate is the state object reference)
                mediaByDate[dateKey] = [...currentItems, ...newMedia];

                // Also update allMedia to keep state in sync
                const currentAllMedia = getAllMedia();
                const allMediaUrls = new Set(currentAllMedia.map(m => m.url));
                const trulyNewMedia = newMedia.filter(m => !allMediaUrls.has(m.url));
                if (trulyNewMedia.length > 0) {
                    setAllMedia([...currentAllMedia, ...trulyNewMedia]);
                }
            }
        }

        return {
            media: result.media,
            hasMore: result.hasMore
        };
    } catch (e) {
        console.error('[GalleryLayout] Error loading more for date:', e);
        return { media: [], hasMore: false };
    }
}

/**
 * Get "On This Day" memories
 * Returns media from previous years on today's date
 */
export async function fetchOnThisDayMedia() {
    const today = new Date();
    const month = today.getMonth() + 1;
    const day = today.getDate();

    try {
        const response = await fetch(`/api/media/on-this-day?month=${month}&day=${day}&limit=20`, {
            headers: getShowHiddenHeaders()
        });

        if (!response.ok) {
            // Endpoint might not exist - return empty
            return [];
        }

        const data = await response.json();
        return data.media || [];
    } catch (e) {
        // Silently fail - this is an optional feature
        return [];
    }
}

/**
 * Fetch all media for a specific year/month (used by the month overlay).
 * @param {number} year
 * @param {number} month - 1-12
 * @param {Object} [options]
 * @param {AbortSignal} [options.signal]
 * @returns {Promise<{media: Array, dateTotals: Object, error: string|null, aborted?: boolean}>}
 */
export async function fetchMonthMedia(year, month, options = {}) {
    const filter = getMediaFilter();
    const categoryId = getCategoryIdFilter();
    const categoryIdsFilter = getCategoryIdsFilter();
    const monthStr = `${year}-${String(month).padStart(2, '0')}`;

    try {
        const params = new URLSearchParams({
            filter,
            month_filter: monthStr,
            items_per_date: 300,
            dates_limit: 31,
            dates_page: 1,
        });

        if (categoryId) params.append('category_id', categoryId);
        if (categoryIdsFilter && categoryIdsFilter.length > 0) {
            params.append('category_ids', categoryIdsFilter.join(','));
        }

        const response = await fetch(`/api/media/timeline?${params}`, {
            headers: getShowHiddenHeaders(),
            signal: options.signal
        });
        if (!response.ok) throw new Error('Failed to fetch month media');

        const data = await response.json();
        return { media: data.media || [], dateTotals: data.date_totals || {}, error: null };
    } catch (e) {
        if (e?.name === 'AbortError') {
            return { media: [], dateTotals: {}, error: null, aborted: true };
        }
        console.error('[GalleryData] Error fetching month media:', e);
        return {
            media: [],
            dateTotals: {},
            error: `Couldn't load ${monthStr}. Please try again.`
        };
    }
}
