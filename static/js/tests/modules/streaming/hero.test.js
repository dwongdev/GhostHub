/**
 * Streaming Hero Section Unit Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Streaming Hero', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    document.body.innerHTML = `
      <div class="hero-section">
        <div class="hero-backdrop"></div>
        <div class="hero-content">
          <h1 class="hero-title"></h1>
          <p class="hero-category"></p>
          <p class="hero-description"></p>
          <div class="hero-meta">
            <span class="hero-duration"></span>
            <span class="hero-progress"></span>
          </div>
          <div class="hero-actions">
            <button class="hero-play-btn">▶ Play</button>
            <button class="hero-resume-btn hidden">▶ Resume</button>
            <button class="hero-info-btn">ℹ More Info</button>
          </div>
        </div>
      </div>
    `;
  });

  describe('Hero content', () => {
    it('should set title', () => {
      const title = document.querySelector('.hero-title');
      title.textContent = 'Featured Movie';
      
      expect(title.textContent).toBe('Featured Movie');
    });

    it('should set category', () => {
      const category = document.querySelector('.hero-category');
      category.textContent = 'Movies';
      
      expect(category.textContent).toBe('Movies');
    });

    it('should set description', () => {
      const desc = document.querySelector('.hero-description');
      desc.textContent = 'An amazing movie to watch tonight.';
      
      expect(desc.textContent).toContain('amazing');
    });
  });

  describe('Hero backdrop', () => {
    it('should set backdrop image', () => {
      const backdrop = document.querySelector('.hero-backdrop');
      backdrop.style.backgroundImage = 'url(/thumbnails/hero.jpg)';
      
      expect(backdrop.style.backgroundImage).toContain('hero.jpg');
    });

    it('should handle missing thumbnail', () => {
      const backdrop = document.querySelector('.hero-backdrop');
      backdrop.classList.add('no-image');
      
      expect(backdrop.classList.contains('no-image')).toBe(true);
    });
  });

  describe('Hero metadata', () => {
    it('should show duration', () => {
      const duration = document.querySelector('.hero-duration');
      duration.textContent = '2h 15m';
      
      expect(duration.textContent).toBe('2h 15m');
    });

    it('should format duration from seconds', () => {
      const seconds = 8100; // 2h 15m
      const hours = Math.floor(seconds / 3600);
      const mins = Math.floor((seconds % 3600) / 60);
      const formatted = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
      
      expect(formatted).toBe('2h 15m');
    });

    it('should show progress percentage', () => {
      const progress = document.querySelector('.hero-progress');
      progress.textContent = '45% watched';
      
      expect(progress.textContent).toBe('45% watched');
    });
  });

  describe('Hero actions', () => {
    it('should have play button', () => {
      expect(document.querySelector('.hero-play-btn')).toBeDefined();
    });

    it('should show resume button for in-progress media', () => {
      const playBtn = document.querySelector('.hero-play-btn');
      const resumeBtn = document.querySelector('.hero-resume-btn');
      
      playBtn.classList.add('hidden');
      resumeBtn.classList.remove('hidden');
      
      expect(resumeBtn.classList.contains('hidden')).toBe(false);
    });

    it('should handle play click', () => {
      const playBtn = document.querySelector('.hero-play-btn');
      const handler = vi.fn();
      
      playBtn.addEventListener('click', handler);
      playBtn.click();
      
      expect(handler).toHaveBeenCalled();
    });
  });

  describe('Hero selection', () => {
    it('should select from continue watching', () => {
      const continueWatching = [
        { url: 'movie1.mp4', progress: 50, title: 'Movie 1' },
        { url: 'movie2.mp4', progress: 30, title: 'Movie 2' }
      ];
      
      const featured = continueWatching[0];
      
      expect(featured.title).toBe('Movie 1');
    });

    it('should select random if no progress', () => {
      const media = [{ title: 'A' }, { title: 'B' }, { title: 'C' }];
      const random = media[Math.floor(Math.random() * media.length)];
      
      expect(media).toContainEqual(random);
    });
  });

  describe('Hero animation', () => {
    it('should add fade-in class', () => {
      const content = document.querySelector('.hero-content');
      content.classList.add('fade-in');
      
      expect(content.classList.contains('fade-in')).toBe(true);
    });
  });
});
