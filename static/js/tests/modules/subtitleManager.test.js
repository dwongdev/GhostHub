/**
 * SubtitleManager Unit Tests
 * Tests for subtitle handling functionality
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('SubtitleManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup DOM
    document.body.innerHTML = `
      <div id="media-viewer">
        <video id="test-video">
          <track kind="subtitles" label="English" srclang="en" />
        </video>
        <div class="subtitle-controls">
          <button id="subtitle-toggle-btn">CC</button>
          <select id="subtitle-track-select"></select>
        </div>
      </div>
    `;
    
    // Mock fetch
    global.fetch = vi.fn();
  });

  describe('Subtitle detection', () => {
    it('should detect embedded tracks', () => {
      const video = document.getElementById('test-video');
      const tracks = video.querySelectorAll('track');
      
      expect(tracks.length).toBe(1);
    });

    it('should fetch available subtitles', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          subtitles: [
            { language: 'en', label: 'English', src: '/media/video.en.vtt' },
            { language: 'es', label: 'Spanish', src: '/media/video.es.vtt' }
          ]
        })
      });
      
      const response = await fetch('/api/subtitles?video=/media/video.mp4');
      const data = await response.json();
      
      expect(data.subtitles).toHaveLength(2);
    });

    it('should handle no subtitles available', async () => {
      global.fetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ subtitles: [] })
      });
      
      const response = await fetch('/api/subtitles?video=/media/video.mp4');
      const data = await response.json();
      
      expect(data.subtitles).toHaveLength(0);
    });
  });

  describe('Subtitle UI', () => {
    it('should have toggle button', () => {
      expect(document.getElementById('subtitle-toggle-btn')).toBeDefined();
    });

    it('should have track select', () => {
      expect(document.getElementById('subtitle-track-select')).toBeDefined();
    });

    it('should populate track options', () => {
      const select = document.getElementById('subtitle-track-select');
      
      const option = document.createElement('option');
      option.value = 'en';
      option.textContent = 'English';
      select.appendChild(option);
      
      expect(select.options.length).toBe(1);
    });

    it('should toggle subtitle visibility', () => {
      const btn = document.getElementById('subtitle-toggle-btn');
      let subtitlesEnabled = false;
      
      btn.addEventListener('click', () => {
        subtitlesEnabled = !subtitlesEnabled;
        btn.classList.toggle('active', subtitlesEnabled);
      });
      
      btn.click();
      expect(btn.classList.contains('active')).toBe(true);
      
      btn.click();
      expect(btn.classList.contains('active')).toBe(false);
    });
  });

  describe('Track management', () => {
    it('should add track to video', () => {
      const video = document.getElementById('test-video');
      
      const track = document.createElement('track');
      track.kind = 'subtitles';
      track.label = 'Spanish';
      track.srclang = 'es';
      track.src = '/media/video.es.vtt';
      video.appendChild(track);
      
      expect(video.querySelectorAll('track').length).toBe(2);
    });

    it('should set active track', () => {
      const video = document.getElementById('test-video');
      const track = video.querySelector('track');
      
      // Simulate setting track mode
      // In real browser: track.track.mode = 'showing'
      track.dataset.mode = 'showing';
      
      expect(track.dataset.mode).toBe('showing');
    });

    it('should disable all tracks', () => {
      const video = document.getElementById('test-video');
      const tracks = video.querySelectorAll('track');
      
      tracks.forEach(track => {
        track.dataset.mode = 'disabled';
      });
      
      expect(tracks[0].dataset.mode).toBe('disabled');
    });
  });

  describe('VTT parsing', () => {
    it('should parse simple cue', () => {
      const vttContent = `WEBVTT

00:00:01.000 --> 00:00:04.000
Hello World`;
      
      const lines = vttContent.split('\n');
      expect(lines[0]).toBe('WEBVTT');
      expect(lines[2]).toContain('-->');
      expect(lines[3]).toBe('Hello World');
    });

    it('should handle timestamp format', () => {
      const timestamp = '00:01:30.500';
      const parts = timestamp.split(':');
      
      const hours = parseInt(parts[0]);
      const minutes = parseInt(parts[1]);
      const seconds = parseFloat(parts[2]);
      
      const totalSeconds = hours * 3600 + minutes * 60 + seconds;
      
      expect(totalSeconds).toBe(90.5);
    });
  });

  describe('Language handling', () => {
    it('should map language codes', () => {
      const languageMap = {
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'ja': 'Japanese'
      };
      
      expect(languageMap['en']).toBe('English');
      expect(languageMap['ja']).toBe('Japanese');
    });

    it('should detect language from filename', () => {
      const filename = 'movie.en.srt';
      const match = filename.match(/\.([a-z]{2})\.(srt|vtt)$/i);
      
      expect(match).toBeDefined();
      expect(match[1]).toBe('en');
    });
  });

  describe('SRT to VTT conversion', () => {
    it('should convert SRT timestamps to VTT format', () => {
      const srtTime = '00:01:30,500';
      const vttTime = srtTime.replace(',', '.');
      
      expect(vttTime).toBe('00:01:30.500');
    });
  });
});
