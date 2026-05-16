/**
 * Admin user data export/import section.
 */

import {
    Module,
    Component,
    createElement,
    append,
} from '../../../libs/ragot.esm.min.js';
import { toast, dialog } from '../../../utils/notificationManager.js';
import { refreshAllLayouts } from '../../../utils/liveVisibility.js';
import {
    downloadIcon,
    refreshIcon,
    uploadIcon,
    usbIcon,
    warningIcon,
} from '../../../utils/icons.js';

const INITIAL_STATE = {
    drives: [],
    selectedExportDriveId: '',
    selectedImportDriveId: '',
    exports: [],
    selectedExportFilename: '',
    loadingDrives: false,
    loadingExports: false,
    activeJobId: null,
    activeJobType: null,
    job: null,
    statusMessage: '',
    error: '',
};

function syncComponentFromState(component, state, module) {
    component.setState({
        ...state,
        actions: module.actions,
    });
}

class UserDataTransferModule extends Module {
    constructor() {
        super({ ...INITIAL_STATE });
        this.actions = {
            refreshDrives: () => this.loadDrives(),
            selectExportDrive: (driveId) => this.setState({ selectedExportDriveId: driveId }),
            selectImportDrive: (driveId) => this.selectImportDrive(driveId),
            selectExportFilename: (filename) => this.setState({ selectedExportFilename: filename }),
            startExport: () => this.startExport(),
            startImport: () => this.startImport(),
            refreshExports: () => this.loadExports(),
        };
    }

    onStart() {
        this.loadDrives();
    }

    async loadDrives() {
        this.setState({ loadingDrives: true, error: '', statusMessage: 'Loading USB drives...' });
        try {
            const data = await fetchJson('/api/admin/user-data/drives');
            const drives = Array.isArray(data.drives) ? data.drives : [];
            const firstWritable = drives.find(drive => drive.writable);
            const firstDrive = drives[0] || null;
            const selectedExportDriveId = this.state.selectedExportDriveId ||
                (firstWritable ? firstWritable.id : '');
            const selectedImportDriveId = this.state.selectedImportDriveId ||
                (firstDrive ? firstDrive.id : '');

            this.setState({
                drives,
                selectedExportDriveId,
                selectedImportDriveId,
                loadingDrives: false,
                statusMessage: drives.length ? '' : 'No USB drives detected.',
            });

            if (selectedImportDriveId) {
                await this.loadExports(selectedImportDriveId);
            }
        } catch (error) {
            this.setState({
                loadingDrives: false,
                error: error.message || 'Failed to load USB drives.',
                statusMessage: '',
            });
        }
    }

    async selectImportDrive(driveId) {
        this.setState({
            selectedImportDriveId: driveId,
            selectedExportFilename: '',
            exports: [],
        });
        if (driveId) {
            await this.loadExports(driveId);
        }
    }

    async loadExports(driveId = this.state.selectedImportDriveId) {
        if (!driveId) {
            this.setState({ exports: [], selectedExportFilename: '' });
            return;
        }

        this.setState({ loadingExports: true, error: '', statusMessage: 'Scanning USB exports...' });
        try {
            const url = `/api/admin/user-data/exports?drive_id=${encodeURIComponent(driveId)}`;
            const data = await fetchJson(url);
            const exportsList = Array.isArray(data.exports) ? data.exports : [];
            const selectedExportFilename = exportsList.some(item => item.filename === this.state.selectedExportFilename)
                ? this.state.selectedExportFilename
                : (exportsList[0]?.filename || '');

            this.setState({
                exports: exportsList,
                selectedExportFilename,
                loadingExports: false,
                statusMessage: exportsList.length ? '' : 'No valid GhostHub exports found on this drive.',
            });
        } catch (error) {
            this.setState({
                loadingExports: false,
                error: error.message || 'Failed to list exports.',
                statusMessage: '',
            });
        }
    }

    async startExport() {
        const drive = this.state.drives.find(item => item.id === this.state.selectedExportDriveId);
        if (!drive) {
            this.setState({ error: 'Select a writable USB drive for export.' });
            return;
        }
        if (!drive.writable) {
            this.setState({ error: 'Selected export drive is not writable.' });
            return;
        }

        const confirmed = await dialog.confirm(
            'Export profiles, progress, hidden content, categories, drive labels, app config, and WiFi name/password settings to this USB drive?\n\nMedia files are not exported. Admin, session, and WiFi passwords may be included, so treat the export as sensitive.',
            { type: 'danger', confirmText: 'Export User Data' },
        );
        if (!confirmed) return;

        this.setState({ error: '', statusMessage: 'Starting export...' });
        try {
            const data = await fetchJson('/api/admin/user-data/export', {
                method: 'POST',
                body: JSON.stringify({ drive_id: drive.id }),
            });
            this.beginPolling(data.job_id, 'export');
        } catch (error) {
            this.setState({ error: error.message || 'Failed to start export.', statusMessage: '' });
        }
    }

    async startImport() {
        if (!this.state.selectedImportDriveId || !this.state.selectedExportFilename) {
            this.setState({ error: 'Select a USB drive and GhostHub export zip to import.' });
            return;
        }

        const selectedExport = this.state.exports.find(
            item => item.filename === this.state.selectedExportFilename
        );
        const manifest = selectedExport?.manifest || {};
        const confirmed = await dialog.confirm(
            `Import ${this.state.selectedExportFilename}?\n\nRows are upserted and existing data is not wiped. App config and WiFi name/password settings will be merged/restored.\n\nExported: ${manifest.exported_at || 'unknown'}\nGhostHub: ${manifest.ghosthub_version || 'unknown'}\nSchema: ${manifest.schema_version ?? 'unknown'}`,
            { type: 'danger', confirmText: 'Import User Data' },
        );
        if (!confirmed) return;

        this.setState({ error: '', statusMessage: 'Starting import...' });
        try {
            const data = await fetchJson('/api/admin/user-data/import', {
                method: 'POST',
                body: JSON.stringify({
                    drive_id: this.state.selectedImportDriveId,
                    filename: this.state.selectedExportFilename,
                }),
            });
            this.beginPolling(data.job_id, 'import');
        } catch (error) {
            this.setState({ error: error.message || 'Failed to start import.', statusMessage: '' });
        }
    }

    beginPolling(jobId, jobType) {
        this.clearTimers();
        this.setState({
            activeJobId: jobId,
            activeJobType: jobType,
            job: { id: jobId, type: jobType, status: 'queued', step: 'Queued', progress: 0 },
            statusMessage: 'Queued...',
            error: '',
        });
        this.pollJob();
    }

    async pollJob() {
        const jobId = this.state.activeJobId;
        if (!jobId) return;

        try {
            const data = await fetchJson(`/api/admin/user-data/jobs/${encodeURIComponent(jobId)}`);
            const job = data.job;
            this.setState({
                job,
                statusMessage: job.message || job.step || '',
                error: job.status === 'error' ? (job.error || 'Transfer failed.') : '',
            });

            if (job.status === 'complete') {
                await this.handleJobComplete(job);
                this.setState({ activeJobId: null, activeJobType: null });
                return;
            }
            if (job.status === 'error') {
                this.setState({ activeJobId: null, activeJobType: null });
                return;
            }

            this.timeout(() => this.pollJob(), 1000);
        } catch (error) {
            this.setState({
                activeJobId: null,
                activeJobType: null,
                error: error.message || 'Failed to poll transfer job.',
            });
        }
    }

    async handleJobComplete(job) {
        if (job.type === 'export') {
            const filename = job.result?.filename;
            toast.success(filename ? `Export complete: ${filename}` : 'User data export complete.');
            if (this.state.selectedImportDriveId === this.state.selectedExportDriveId) {
                await this.loadExports(this.state.selectedImportDriveId);
            }
            return;
        }

        if (job.type === 'import') {
            await refreshAllLayouts(true);
            const warnings = job.result?.warnings || [];
            if (warnings.length) {
                toast.warning(warnings.join('\n'));
            } else {
                toast.success('User data import complete.');
            }

            const filename = job.result?.filename || this.state.selectedExportFilename;
            if (!filename) return;
            const shouldDelete = await dialog.confirm(
                `Delete ${filename} from the USB drive now that import is complete?`,
                { type: 'danger', confirmText: 'Delete Export' },
            );
            if (shouldDelete) {
                await this.deleteExport(filename);
            }
        }
    }

    async deleteExport(filename) {
        try {
            await fetchJson('/api/admin/user-data/export', {
                method: 'DELETE',
                body: JSON.stringify({
                    drive_id: this.state.selectedImportDriveId,
                    filename,
                }),
            });
            toast.success('Export zip deleted from USB.');
            await this.loadExports(this.state.selectedImportDriveId);
        } catch (error) {
            this.setState({ error: error.message || 'Failed to delete export zip.' });
        }
    }
}

class UserDataTransferComponent extends Component {
    constructor() {
        super({
            ...INITIAL_STATE,
            actions: {},
        });
    }

    start(parent) {
        if (this._isMounted) return this.element;
        this.element = this.render();
        if (parent && this.element) {
            parent.appendChild(this.element);
        }
        this._isMounted = true;
        this.onStart();
        return this.element;
    }

    render() {
        const root = createElement('section', { className: 'config-user-data-transfer' });
        const title = createElement('h4', {
            className: 'config-user-data-transfer__title',
            innerHTML: `${usbIcon(16)} User Data Backup`,
        });
        const warning = createElement('p', {
            className: 'config-user-data-transfer__warning',
            innerHTML: `${warningIcon(16)} Exports contain admin settings and may include passwords. Treat backup zips as sensitive.`,
        });
        const grid = createElement('div', { className: 'config-user-data-transfer__grid' });

        append(grid, [this.renderExportPanel(), this.renderImportPanel()]);
        append(root, [title, warning, grid, this.renderStatus()]);
        return root;
    }

    renderExportPanel() {
        const drive = this.state.drives.find(item => item.id === this.state.selectedExportDriveId);
        const panel = createElement('div', { className: 'config-user-data-transfer__panel' });
        const heading = createElement('h5', {
            innerHTML: `${downloadIcon(15)} Export to USB`,
        });
        const controls = createElement('div', { className: 'config-user-data-transfer__controls' });
        const select = this.renderDriveSelect({
            value: this.state.selectedExportDriveId,
            onChange: (event) => this.state.actions.selectExportDrive?.(event.target.value),
        });
        const refreshButton = createElement('button', {
            className: 'btn btn--secondary btn--sm',
            title: 'Refresh USB drives',
            innerHTML: refreshIcon(15),
            disabled: this.state.loadingDrives || this.hasActiveJob(),
            onClick: () => this.state.actions.refreshDrives?.(),
        });
        const exportButton = createElement('button', {
            className: 'btn btn--primary btn--sm',
            textContent: this.hasActiveJob('export') ? 'Exporting...' : 'Export User Data',
            disabled: this.hasActiveJob() || !drive || !drive.writable,
            onClick: () => this.state.actions.startExport?.(),
        });

        append(controls, [select, refreshButton, exportButton]);
        const hint = createElement('p', {
            className: 'config-user-data-transfer__hint',
            textContent: drive && !drive.writable
                ? 'Selected drive is read-only.'
                : 'Writes GhostHubBackups/ghosthub-user-data-*.zip',
        });
        append(panel, [heading, controls, hint]);
        return panel;
    }

    renderImportPanel() {
        const selectedExport = this.state.exports.find(
            item => item.filename === this.state.selectedExportFilename
        );
        const panel = createElement('div', { className: 'config-user-data-transfer__panel' });
        const heading = createElement('h5', {
            innerHTML: `${uploadIcon(15)} Import from USB`,
        });
        const controls = createElement('div', { className: 'config-user-data-transfer__controls' });
        const driveSelect = this.renderDriveSelect({
            value: this.state.selectedImportDriveId,
            onChange: (event) => this.state.actions.selectImportDrive?.(event.target.value),
        });
        const exportSelect = this.renderExportSelect();
        const refreshButton = createElement('button', {
            className: 'btn btn--secondary btn--sm',
            title: 'Refresh exports',
            innerHTML: refreshIcon(15),
            disabled: this.state.loadingExports || this.hasActiveJob() || !this.state.selectedImportDriveId,
            onClick: () => this.state.actions.refreshExports?.(),
        });
        const importButton = createElement('button', {
            className: 'btn btn--warning btn--sm',
            textContent: this.hasActiveJob('import') ? 'Importing...' : 'Import User Data',
            disabled: this.hasActiveJob() || !this.state.selectedImportDriveId || !this.state.selectedExportFilename,
            onClick: () => this.state.actions.startImport?.(),
        });

        append(controls, [driveSelect, exportSelect, refreshButton, importButton]);
        const summary = selectedExport
            ? this.renderManifestSummary(selectedExport)
            : createElement('p', {
                className: 'config-user-data-transfer__hint',
                textContent: this.state.loadingExports ? 'Scanning for export zips...' : 'Select a drive containing a GhostHub export zip.',
            });
        append(panel, [heading, controls, summary]);
        return panel;
    }

    renderDriveSelect({ value, onChange }) {
        const select = createElement('select', {
            className: 'config-user-data-transfer__select',
            disabled: this.state.loadingDrives || this.hasActiveJob(),
            onChange,
        });
        const options = [];
        if (!this.state.drives.length) {
            options.push(createElement('option', { value: '', textContent: 'No USB drives detected' }));
        } else {
            for (const drive of this.state.drives) {
                const label = drive.label || drive.name || drive.id;
                const suffix = drive.writable ? drive.free_formatted : 'read-only';
                options.push(createElement('option', {
                    value: drive.id,
                    textContent: `${label} (${suffix})`,
                }));
            }
        }
        append(select, options);
        select.value = value;
        return select;
    }

    renderExportSelect() {
        const select = createElement('select', {
            className: 'config-user-data-transfer__select config-user-data-transfer__select--wide',
            disabled: this.state.loadingExports || this.hasActiveJob() || !this.state.exports.length,
            onChange: (event) => this.state.actions.selectExportFilename?.(event.target.value),
        });
        const options = [];
        if (!this.state.exports.length) {
            options.push(createElement('option', {
                value: '',
                textContent: this.state.loadingExports ? 'Scanning exports...' : 'No exports found',
            }));
        } else {
            for (const item of this.state.exports) {
                options.push(createElement('option', {
                    value: item.filename,
                    textContent: `${item.filename} (${item.size_formatted})`,
                }));
            }
        }
        append(select, options);
        select.value = this.state.selectedExportFilename;
        return select;
    }

    renderManifestSummary(item) {
        const manifest = item.manifest || {};
        return createElement('p', {
            className: 'config-user-data-transfer__manifest',
            textContent: `Exported ${manifest.exported_at || 'unknown'} | GhostHub ${manifest.ghosthub_version || 'unknown'} | schema ${manifest.schema_version ?? 'unknown'}`,
        });
    }

    renderStatus() {
        const job = this.state.job || {};
        const progress = Number.isFinite(job.progress) ? Math.max(0, Math.min(100, job.progress)) : 0;
        const statusClass = [
            'config-user-data-transfer__status',
            this.state.error ? 'config-user-data-transfer__status--error' : '',
            job.status === 'complete' ? 'config-user-data-transfer__status--complete' : '',
        ].filter(Boolean).join(' ');
        const status = createElement('div', { className: statusClass });
        const message = this.state.error || this.state.statusMessage || job.step || '';
        const text = createElement('span', { textContent: message || 'Ready' });
        const progressTrack = createElement('div', { className: 'config-user-data-transfer__progress' });
        const progressFill = createElement('div', { className: 'config-user-data-transfer__progress-fill' });
        progressFill.style.width = `${progress}%`;
        progressTrack.appendChild(progressFill);
        const percent = createElement('span', {
            className: 'config-user-data-transfer__percent',
            textContent: this.hasActiveJob() || job.status === 'complete' ? `${progress}%` : '',
        });
        append(status, [text, progressTrack, percent]);
        return status;
    }

    hasActiveJob(type = null) {
        if (!this.state.activeJobId) return false;
        if (!type) return true;
        return this.state.activeJobType === type;
    }
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
        credentials: 'include',
        cache: 'no-store',
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        },
        ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.success === false) {
        throw new Error(data.error || data.message || `Request failed (${response.status})`);
    }
    return data;
}

export function createUserDataTransferSection() {
    const module = new UserDataTransferModule();
    const component = new UserDataTransferComponent();
    const wrapper = createElement('div');
    module.adoptComponent(component, {
        startMethod: 'start',
        stopMethod: 'unmount',
        startArgs: [wrapper],
        sync: syncComponentFromState,
    });
    module.start();
    wrapper.__cleanup = () => module.stop();
    return wrapper;
}
