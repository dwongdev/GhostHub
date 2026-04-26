import { describe, it, expect, vi, afterEach } from 'vitest';

import { transitionToSingleCategoryGrid } from '../../../modules/layouts/streaming/index.js';

describe('streaming transitions', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('does not force any scroll behavior for subfolder grid transitions', () => {
    const category = { id: 'movies' };
    const cache = { media: [{ url: '/media/movies/a.mp4' }], subfolders: [] };
    const mountGrid = vi.fn();
    const unmountRows = vi.fn();
    const scrollToTop = vi.fn();

    transitionToSingleCategoryGrid({
      category,
      cache,
      mountGrid,
      unmountRows,
      scrollToTop,
      activeSubfolder: 'Shows/Season 1'
    });

    expect(mountGrid).toHaveBeenCalledWith(category, cache);
    expect(unmountRows).toHaveBeenCalledOnce();
    expect(scrollToTop).not.toHaveBeenCalled();
  });

  it('does not force scroll for non-subfolder grid transitions either', () => {
    const mountGrid = vi.fn();
    const unmountRows = vi.fn();
    const scrollToTop = vi.fn();

    transitionToSingleCategoryGrid({
      category: { id: 'movies' },
      cache: { media: [], subfolders: [] },
      mountGrid,
      unmountRows,
      scrollToTop,
      activeSubfolder: null
    });

    expect(mountGrid).toHaveBeenCalledOnce();
    expect(unmountRows).toHaveBeenCalledOnce();
    expect(scrollToTop).not.toHaveBeenCalled();
  });

  it('uses view transitions for grid swaps when supported', () => {
    const mountGrid = vi.fn();
    const unmountRows = vi.fn();
    document.startViewTransition = vi.fn((cb) => {
      cb();
      return { finished: Promise.resolve() };
    });
    window.matchMedia = vi.fn().mockReturnValue({ matches: false });

    transitionToSingleCategoryGrid({
      category: { id: 'movies' },
      cache: { media: [], subfolders: [] },
      mountGrid,
      unmountRows,
      activeSubfolder: null
    });

    expect(document.startViewTransition).toHaveBeenCalled();
    expect(mountGrid).toHaveBeenCalledOnce();
    expect(unmountRows).toHaveBeenCalledOnce();
  });
});
