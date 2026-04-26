import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockCaches = {};

vi.mock('../../../utils/layoutUtils.js', () => ({
  calculateProgress: vi.fn(() => 0)
}));

vi.mock('../../../utils/icons.js', () => ({
  videoIcon: vi.fn(() => '<svg></svg>'),
  imageIcon: vi.fn(() => '<svg></svg>'),
  tvIcon: vi.fn(() => '<svg></svg>'),
  sparkleIcon: vi.fn(() => '<svg></svg>'),
  userIcon: vi.fn(() => '<svg></svg>'),
  usersIcon: vi.fn(() => '<svg></svg>'),
  folderFilledIcon: vi.fn(() => '<svg></svg>')
}));

vi.mock('../../../utils/mediaUtils.js', () => ({
  buildThumbnailPlaceholderLayerAttrs: vi.fn(({ className = '', state = 'pending' } = {}) => ({
    className: `gh-thumbnail-placeholder-layer ${className}`.trim(),
    dataset: { thumbnailState: state }
  }))
}));

vi.mock('../../../modules/layouts/streaming/state.js', () => ({
  getCategoryCache: vi.fn((categoryId, subfolder = null, mediaFilter = 'all') =>
    mockCaches[`${categoryId}|sf:${subfolder || ''}|mf:${mediaFilter || 'all'}`] || null),
  getMediaFilter: vi.fn(() => 'all'),
  getSubfolderFilter: vi.fn(() => null),
  getCategoryIdFilter: vi.fn(() => null)
}));

vi.mock('../../../modules/layouts/streaming/data.js', () => ({
  loadMoreMedia: vi.fn(async () => [])
}));

vi.mock('../../../modules/layouts/streaming/lazyLoad.js', () => ({
  observeLazyImage: vi.fn(),
  primeLazyImage: vi.fn()
}));

vi.mock('../../../modules/layouts/streaming/cards.js', () => ({
  createContinueWatchingCard: vi.fn(() => document.createElement('div')),
  createMediaItemCard: vi.fn(() => document.createElement('div')),
  createSubfolderCard: vi.fn(() => document.createElement('div')),
  updateCardProgress: vi.fn(),
  updateContinueWatchingCard: vi.fn()
}));

vi.mock('../../../utils/subfolderUtils.js', () => ({
  isSubfolderFile: vi.fn(() => false)
}));

vi.mock('../../../modules/layouts/shared/subfolderNavigation.js', () => ({
  handleSubfolderClick: vi.fn()
}));

import { StreamingRowsComponent } from '../../../modules/layouts/streaming/rows.js';
import * as streamingCards from '../../../modules/layouts/streaming/cards.js';

describe('StreamingRowsComponent loading states', () => {
  beforeEach(() => {
    Object.keys(mockCaches).forEach((key) => delete mockCaches[key]);
    document.body.innerHTML = '<div id="host"></div>';
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('renders a Continue Watching placeholder row while the data is still loading', () => {
    const host = document.getElementById('host');
    const rows = new StreamingRowsComponent();

    rows.mount(host);
    rows.setState({
      categoriesData: [],
      continueWatchingData: [],
      continueWatchingLoading: true,
      whatsNewData: [],
      whatsNewLoading: false,
      isLoading: false
    });

    expect(host.querySelector('#row-continue-watching')).not.toBeNull();
  });

  it('patches existing Continue Watching cards when progress changes for the same video', () => {
    const host = document.getElementById('host');
    const rows = new StreamingRowsComponent();

    rows.mount(host);
    rows.setState({
      categoriesData: [],
      continueWatchingData: [{
        videoUrl: '/media/cat-1/movie.mp4',
        categoryId: 'cat-1',
        videoTimestamp: 60,
        videoDuration: 600
      }],
      continueWatchingLoading: false,
      whatsNewData: [],
      whatsNewLoading: false,
      isLoading: false
    });

    vi.mocked(streamingCards.updateContinueWatchingCard).mockClear();

    rows.setState({
      continueWatchingData: [{
        videoUrl: '/media/cat-1/movie.mp4',
        categoryId: 'cat-1',
        videoTimestamp: 120,
        videoDuration: 600
      }]
    });

    expect(streamingCards.updateContinueWatchingCard).toHaveBeenCalledTimes(1);
    expect(streamingCards.updateContinueWatchingCard).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({
        videoUrl: '/media/cat-1/movie.mp4',
        videoTimestamp: 120
      })
    );
  });

  it("renders a What's New placeholder row while the row is explicitly loading", () => {
    const host = document.getElementById('host');
    const rows = new StreamingRowsComponent();

    rows.mount(host);
    rows.setState({
      categoriesData: [],
      continueWatchingData: [],
      continueWatchingLoading: false,
      whatsNewData: [],
      whatsNewLoading: true,
      isLoading: false
    });

    expect(host.querySelector('#row-whats-new')).not.toBeNull();
  });

  it("keeps a What's New placeholder row visible while category indexing is still in progress", () => {
    const host = document.getElementById('host');
    const rows = new StreamingRowsComponent();

    mockCaches['cat-1|sf:|mf:all'] = {
      media: [],
      page: 1,
      hasMore: false,
      loading: false,
      subfolders: [],
      asyncIndexing: true,
      indexingProgress: 42
    };

    rows.mount(host);
    rows.setState({
      categoriesData: [{ id: 'cat-1', name: 'Movies', containsVideo: true }],
      categoryMediaCache: { ...mockCaches },
      continueWatchingData: [],
      continueWatchingLoading: false,
      whatsNewData: [],
      whatsNewLoading: false,
      mediaFilter: 'all',
      categoryIdFilter: null,
      subfolderFilter: null,
      isLoading: false
    });

    expect(host.querySelector('#row-whats-new')).not.toBeNull();
  });
});
