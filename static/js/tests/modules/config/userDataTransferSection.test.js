import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../../utils/notificationManager.js', () => ({
  toast: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
  dialog: {
    confirm: vi.fn(() => Promise.resolve(true)),
  },
}));

vi.mock('../../../utils/liveVisibility.js', () => ({
  refreshAllLayouts: vi.fn(() => Promise.resolve()),
}));

import { dialog } from '../../../utils/notificationManager.js';
import { refreshAllLayouts } from '../../../utils/liveVisibility.js';
import { createUserDataTransferSection } from '../../../modules/config/sections/userDataTransferSection.js';

function jsonResponse(data, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(data),
  });
}

async function flushDom() {
  await new Promise(resolve => setTimeout(resolve, 0));
  await new Promise(resolve => requestAnimationFrame(resolve));
}

function setupFetch(handler) {
  global.fetch = vi.fn((url, options = {}) => handler(String(url), options));
}

describe('userDataTransferSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupFetch((url) => {
      if (url === '/api/admin/user-data/drives') {
        return jsonResponse({
          drives: [{
            id: 'drive-1',
            name: 'USB',
            label: 'Backup USB',
            writable: true,
            free_formatted: '10 GB',
            total_formatted: '16 GB',
          }],
        });
      }
      if (url.startsWith('/api/admin/user-data/exports')) {
        return jsonResponse({ exports: [] });
      }
      return jsonResponse({});
    });
  });

  it('renders export and import controls after loading drives', async () => {
    const section = createUserDataTransferSection();
    document.body.appendChild(section);

    await flushDom();

    expect(section.textContent).toContain('User Data Backup');
    expect(section.textContent).toContain('Export User Data');
    expect(section.textContent).toContain('Import User Data');
    expect(section.textContent).toContain('Backup USB');

    section.__cleanup();
  });

  it('starts export and polls job status', async () => {
    setupFetch((url, options = {}) => {
      if (url === '/api/admin/user-data/drives') {
        return jsonResponse({
          drives: [{
            id: 'drive-1',
            name: 'USB',
            writable: true,
            free_formatted: '10 GB',
          }],
        });
      }
      if (url.startsWith('/api/admin/user-data/exports')) {
        return jsonResponse({ exports: [] });
      }
      if (url === '/api/admin/user-data/export' && options.method === 'POST') {
        return jsonResponse({ success: true, job_id: 'job-export' });
      }
      if (url === '/api/admin/user-data/jobs/job-export') {
        return jsonResponse({
          job: {
            id: 'job-export',
            type: 'export',
            status: 'complete',
            progress: 100,
            result: { filename: 'ghosthub-user-data-20260514-130000.zip' },
          },
        });
      }
      return jsonResponse({});
    });
    const section = createUserDataTransferSection();
    document.body.appendChild(section);
    await flushDom();

    const exportButton = [...section.querySelectorAll('button')]
      .find(button => button.textContent === 'Export User Data');
    exportButton.click();
    await flushDom();

    expect(dialog.confirm).toHaveBeenCalled();
    expect(global.fetch).toHaveBeenCalledWith('/api/admin/user-data/export', expect.objectContaining({
      method: 'POST',
    }));
    expect(global.fetch).toHaveBeenCalledWith('/api/admin/user-data/jobs/job-export', expect.any(Object));

    section.__cleanup();
  });

  it('imports an export and deletes it after confirmation', async () => {
    setupFetch((url, options = {}) => {
      if (url === '/api/admin/user-data/drives') {
        return jsonResponse({
          drives: [{
            id: 'drive-1',
            name: 'USB',
            writable: true,
            free_formatted: '10 GB',
          }],
        });
      }
      if (url.startsWith('/api/admin/user-data/exports')) {
        return jsonResponse({
          exports: [{
            filename: 'ghosthub-user-data-20260514-130000.zip',
            size_formatted: '2 KB',
            manifest: {
              exported_at: '2026-05-14T20:00:00Z',
              ghosthub_version: '5.1.1',
              schema_version: 15,
            },
          }],
        });
      }
      if (url === '/api/admin/user-data/import' && options.method === 'POST') {
        return jsonResponse({ success: true, job_id: 'job-import' });
      }
      if (url === '/api/admin/user-data/jobs/job-import') {
        return jsonResponse({
          job: {
            id: 'job-import',
            type: 'import',
            status: 'complete',
            progress: 100,
            result: {
              filename: 'ghosthub-user-data-20260514-130000.zip',
              warnings: [],
            },
          },
        });
      }
      if (url === '/api/admin/user-data/export' && options.method === 'DELETE') {
        return jsonResponse({ success: true });
      }
      return jsonResponse({});
    });
    const section = createUserDataTransferSection();
    document.body.appendChild(section);
    await flushDom();

    const importButton = [...section.querySelectorAll('button')]
      .find(button => button.textContent === 'Import User Data');
    importButton.click();
    await flushDom();

    expect(global.fetch).toHaveBeenCalledWith('/api/admin/user-data/import', expect.objectContaining({
      method: 'POST',
    }));
    expect(refreshAllLayouts).toHaveBeenCalledWith(true);
    expect(global.fetch).toHaveBeenCalledWith('/api/admin/user-data/export', expect.objectContaining({
      method: 'DELETE',
    }));

    section.__cleanup();
  });
});
