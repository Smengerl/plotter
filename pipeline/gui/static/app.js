// Plotter Pipeline Manager — SPA core
'use strict';

// ─── Central State ────────────────────────────────────────────────────────────

let state = {
    images: [],       // from GET /api/input_images
    outputImages: [],       // from GET /api/output_images
    pipelines: [],       // from GET /api/pipelines
    currentJob: null,     // from GET /api/jobs/current
    logs: [],       // max 500 lines
    view: 'library',
    selectedImage: null,
};

/** Merge patch into state and re-render. Never mutate state directly. */
function setState(patch) {
    state = Object.assign({}, state, patch);
    render(state);
}

// ─── API Helpers ──────────────────────────────────────────────────────────────

async function apiFetch(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`${res.status} ${res.statusText}: ${text}`);
    }
    return res;
}

async function apiJSON(url, options = {}) {
    const res = await apiFetch(url, options);
    if (res.status === 204) return null;
    return res.json();
}

async function refreshAll() {
    const [images, outputImages, pipelines, currentJob] = await Promise.all([
        apiJSON('/api/input_images').catch(() => state.images),
        apiJSON('/api/output_images').catch(() => state.outputImages),
        apiJSON('/api/pipelines').catch(() => state.pipelines),
        apiJSON('/api/jobs/current').catch(() => state.currentJob),
    ]);
    setState({ images, outputImages, pipelines, currentJob });
}

// ─── Render Entry Point ───────────────────────────────────────────────────────

function render(s) {
    renderHeader(s);
    renderMainView(s);
    renderLogPanel(s);
}

// ─── Header ───────────────────────────────────────────────────────────────────

function renderHeader(s) {
    const header = document.getElementById('header');
    if (!header) return;

    if (s.view === 'library') {
        header.innerHTML = `
            <h1>🖊 Plotter Pipeline Manager</h1>
            <div class="toolbar__spacer"></div>
            <button class="btn-primary" id="btn-upload">＋ Upload</button>
        `;
        document.getElementById('btn-upload').addEventListener('click', () => {
            document.getElementById('file-input').click();
        });
    } else {
        header.innerHTML = `
            <button class="btn-secondary" id="btn-back">← Back</button>
            <h1 class="text-muted" style="font-size:14px;font-weight:normal;">
                ${escHtml(s.selectedImage || '')}
            </h1>
        `;
        document.getElementById('btn-back').addEventListener('click', () => {
            setState({ view: 'library', selectedImage: null });
        });
    }
}

// ─── Main View ────────────────────────────────────────────────────────────────

function renderMainView(s) {
    const main = document.getElementById('main');
    if (!main) return;
    if (s.view === 'library') {
        renderLibrary(s, main);
    } else {
        renderDetail(s, main);
    }
}

// ─── Library View ─────────────────────────────────────────────────────────────

function renderLibrary(s, container) {
    const sorted = [...s.images].sort((a, b) => a.name.localeCompare(b.name));

    let html = `
        <div class="upload-zone" id="upload-zone" tabindex="0" role="button"
             aria-label="Drop images here or click to upload">
            <span>📂 Drop images here or <u>click to upload</u></span>
            <div class="upload-progress" id="upload-progress"></div>
        </div>
        <input type="file" id="file-input" class="sr-only"
               accept="image/jpeg,image/png,image/tiff" multiple>
    `;

    if (sorted.length === 0) {
        html += `
            <div class="empty-state">
                <div class="empty-state__icon">🖼</div>
                <div class="empty-state__label">No images yet — upload one to get started</div>
            </div>
        `;
    } else {
        html += `<div class="image-grid" id="image-grid">`;
        for (const img of sorted) {
            const badge = badgeForImage(img, s);
            html += `
                <div class="image-card" data-name="${escAttr(img.name)}" role="button" tabindex="0">
                    <img class="image-card__thumb"
                         src="/api/input_images/${encodeURIComponent(img.name)}/thumbnail"
                         alt="${escAttr(img.name)}"
                         loading="lazy"
                         onerror="this.style.display='none'">
                    <div class="image-card__body">
                        <div class="image-card__name">${escHtml(stem(img.name))}</div>
                        ${badge}
                    </div>
                </div>
            `;
        }
        html += `</div>`;
    }

    container.innerHTML = html;
    bindUploadZone(container);
    bindImageCards(container);
}

function badgeForImage(img, s) {
    // Running priority: check currentJob
    if (s.currentJob && s.currentJob.image_name === img.name && s.currentJob.status === 'running') {
        return badge('running', 'Running');
    }
    if (img.status === 'running') return badge('running', 'Running');
    if (img.status === 'error') return badge('error', 'Error');
    if (img.done_count > 0) return badge('done', `${img.done_count} done`);
    return badge('new', 'New');
}

function badge(type, label) {
    // type is one of: new, done, error, running → CSS: badge--new badge--done badge--error badge--running
    return `<span class="badge badge--${type}"><span class="badge__dot"></span>${escHtml(label)}</span>`;
}

function bindImageCards(container) {
    container.querySelectorAll('.image-card').forEach(card => {
        const name = card.dataset.name;
        const activate = () => setState({ view: 'detail', selectedImage: name });
        card.addEventListener('click', activate);
        card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') activate(); });
    });
}

// ─── Upload ───────────────────────────────────────────────────────────────────

function bindUploadZone(container) {
    const zone = container.querySelector('#upload-zone');
    const fileInput = container.querySelector('#file-input');
    if (!zone || !fileInput) return;

    zone.addEventListener('click', () => fileInput.click());
    zone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('upload-zone--dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('upload-zone--dragover'));
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('upload-zone--dragover');
        uploadFiles(Array.from(e.dataTransfer.files), container);
    });
    fileInput.addEventListener('change', () => {
        uploadFiles(Array.from(fileInput.files), container);
        fileInput.value = '';
    });
}

async function uploadFiles(files, container) {
    const progressEl = container.querySelector('#upload-progress');
    const valid = files.filter(f => /image\/(jpeg|png|tiff)/.test(f.type));
    if (!valid.length) return;

    for (const file of valid) {
        const itemId = `up-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        if (progressEl) {
            progressEl.insertAdjacentHTML('beforeend', `
                <div class="upload-progress__item" id="${itemId}">
                    <span>${escHtml(file.name)}</span>
                    <div class="progress-bar"><div class="progress-bar__fill" style="width:0%"></div></div>
                </div>
            `);
        }

        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/input_images/upload');
        xhr.upload.addEventListener('progress', e => {
            if (e.lengthComputable) {
                const pct = Math.round(e.loaded / e.total * 100);
                const fill = progressEl && progressEl.querySelector(`#${itemId} .progress-bar__fill`);
                if (fill) fill.style.width = pct + '%';
            }
        });
        await new Promise(resolve => {
            xhr.addEventListener('loadend', async () => {
                const el = progressEl && progressEl.querySelector(`#${itemId}`);
                if (el) setTimeout(() => el.remove(), 1500);
                await refreshAll();
                resolve();
            });
            xhr.send(formData);
        });
    }
}

// ─── Detail View ──────────────────────────────────────────────────────────────

function renderDetail(s, container) {
    const img = s.images.find(i => i.name === s.selectedImage);
    if (!img) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state__label">Image not found.</div></div>`;
        return;
    }

    const outputCount = s.outputImages.filter(o => o.source_image === img.name).length;

    container.innerHTML = `
        <div class="detail-view">
            <div>
                <div class="detail-preview">
                    <img src="/api/input_images/${encodeURIComponent(img.name)}/full"
                         alt="${escAttr(img.name)}">
                    <div class="detail-meta">
                        <strong>${escHtml(img.name)}</strong>
                        <span>${img.width} × ${img.height} px · ${img.format} · ${formatBytes(img.size_bytes)}</span>
                        <div class="detail-actions">
                            <a href="/api/input_images/${encodeURIComponent(img.name)}/download"
                               class="btn-secondary" style="display:inline-block;padding:6px 14px;border-radius:6px;border:1px solid var(--color-border);">
                               ↓ Download
                            </a>
                            <button class="btn-danger" id="btn-delete">🗑 Delete</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="pipeline-list" id="pipeline-list">
                ${renderPipelineList(img, s)}
            </div>
        </div>
    `;

    document.getElementById('btn-delete').addEventListener('click', () => confirmDelete(img, outputCount));
    bindPipelineActions(container, img, s);
}

function renderPipelineList(img, s) {
    if (!s.pipelines.length) {
        return `<div class="empty-state"><div class="empty-state__label">No pipelines found in tools directory.</div></div>`;
    }

    let html = '';
    for (const pipeline of s.pipelines) {
        html += renderPipelineCard(pipeline, img, s);
    }
    return html;
}

function renderPipelineCard(pipeline, img, s) {
    const output = s.outputImages.find(
        o => o.source_image === img.name && o.pipeline_stem === pipeline.stem
    );
    const jobIsRunning = s.currentJob && s.currentJob.status === 'running';
    const thisJobRunning = jobIsRunning &&
        s.currentJob.image_name === img.name &&
        s.currentJob.pipeline_stem === pipeline.stem;

    let statusBadge, extraHtml = '', actionsHtml = '';

    if (thisJobRunning) {
        const cur = s.currentJob.step_current || 0;
        const tot = s.currentJob.step_total || 0;
        const lbl = s.currentJob.step_label || '';
        statusBadge = badge('running', 'Running');
        extraHtml = `<div class="text-muted" style="font-size:11px;">Step ${cur}/${tot}${lbl ? ': ' + escHtml(lbl) : ''}</div>`;
        actionsHtml = `<button class="btn-secondary btn-cancel-job" data-stem="${escAttr(pipeline.stem)}">✕ Cancel</button>`;
    } else if (output) {
        statusBadge = badge('done', 'Done');
        extraHtml = `
            <div class="pipeline-card__output">
                <img src="/api/output_images/${encodeURIComponent(output.name)}/thumbnail"
                     alt="${escAttr(output.name)}"
                     data-lightbox="${escAttr(output.name)}"
                     title="${escAttr(output.name)}">
                <div style="display:flex;flex-direction:column;gap:6px;">
                    <span class="text-muted" style="font-size:11px;">${escHtml(output.name)}</span>
                    <a href="/api/output_images/${encodeURIComponent(output.name)}/download"
                       class="btn-secondary" style="display:inline-block;padding:4px 10px;border-radius:6px;border:1px solid var(--color-border);font-size:12px;">
                       ↓ Download
                    </a>
                </div>
            </div>
        `;
        actionsHtml = `
            <button class="btn-primary btn-run-pipeline"
                    data-stem="${escAttr(pipeline.stem)}"
                    ${jobIsRunning ? 'disabled' : ''}>▶ Re-run</button>
            <button class="btn-secondary btn-send-plotter"
                    data-output="${escAttr(output.name)}"
                    ${jobIsRunning ? 'disabled' : ''}>🖊 Send to Plotter</button>
        `;
    } else if (img.status === 'error' || (s.currentJob && s.currentJob.image_name === img.name &&
        s.currentJob.pipeline_stem === pipeline.stem && s.currentJob.status === 'error')) {
        statusBadge = badge('error', 'Error');
        const reason = s.currentJob && s.currentJob.pipeline_stem === pipeline.stem
            ? s.currentJob.error_reason : img.error_reason;
        if (reason) {
            extraHtml = `<div class="pipeline-card__error">${escHtml(reason)}</div>`;
        }
        actionsHtml = `
            <button class="btn-primary btn-run-pipeline"
                    data-stem="${escAttr(pipeline.stem)}"
                    ${jobIsRunning ? 'disabled' : ''}>▶ Run</button>
        `;
    } else {
        statusBadge = badge('new', 'Not run');
        actionsHtml = `
            <button class="btn-primary btn-run-pipeline"
                    data-stem="${escAttr(pipeline.stem)}"
                    ${jobIsRunning ? 'disabled' : ''}>▶ Run</button>
        `;
    }

    const descHtml = pipeline.description
        ? `<div class="pipeline-card__description">${escHtml(pipeline.description)}</div>`
        : '';
    const invalidHtml = !pipeline.valid
        ? `<div class="pipeline-card__error">⚠ Invalid pipeline: ${escHtml(pipeline.error || '')}</div>`
        : '';

    return `
        <div class="pipeline-card">
            <div class="pipeline-card__header">
                <div>
                    <div class="pipeline-card__name">${escHtml(pipeline.name)}</div>
                    ${descHtml}
                </div>
                ${statusBadge}
            </div>
            ${invalidHtml}
            ${extraHtml}
            <div class="pipeline-card__actions">${actionsHtml}</div>
        </div>
    `;
}

function bindPipelineActions(container, img, s) {
    // Run pipeline
    container.querySelectorAll('.btn-run-pipeline').forEach(btn => {
        btn.addEventListener('click', async () => {
            const stem = btn.dataset.stem;
            try {
                await apiFetch('/api/jobs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image_name: img.name, pipeline_stem: stem }),
                });
                await refreshAll();
            } catch (e) {
                console.error('Run job failed:', e);
            }
        });
    });

    // Cancel job
    container.querySelectorAll('.btn-cancel-job').forEach(btn => {
        btn.addEventListener('click', async () => {
            try {
                await apiFetch('/api/jobs/current', { method: 'DELETE' });
            } catch (e) {
                console.error('Cancel failed:', e);
            }
        });
    });

    // Send to plotter
    container.querySelectorAll('.btn-send-plotter').forEach(btn => {
        btn.addEventListener('click', async () => {
            const outputName = btn.dataset.output;
            try {
                await apiFetch('/api/plotter/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ output_image_name: outputName }),
                });
                await refreshAll();
            } catch (e) {
                console.error('Plotter send failed:', e);
            }
        });
    });

    // Lightbox
    container.querySelectorAll('[data-lightbox]').forEach(img => {
        img.addEventListener('click', e => {
            e.stopPropagation();
            openLightbox(`/api/output_images/${encodeURIComponent(img.dataset.lightbox)}`);
        });
    });
}

async function confirmDelete(img, outputCount) {
    const msg = `Delete "${img.name}" and all ${outputCount} pipeline result(s)? This cannot be undone.`;
    if (!confirm(msg)) return;
    try {
        await apiFetch(`/api/input_images/${encodeURIComponent(img.name)}`, { method: 'DELETE' });
        await refreshAll();
        setState({ view: 'library', selectedImage: null });
    } catch (e) {
        console.error('Delete failed:', e);
    }
}

// ─── Log Panel ────────────────────────────────────────────────────────────────

let _logPanelExpanded = false;
let _logUserScrolled = false;

function renderLogPanel(s) {
    const panel = document.getElementById('log-panel');
    if (!panel) return;

    if (!s.currentJob) {
        panel.className = 'log-panel log-panel--hidden';
        return;
    }

    const job = s.currentJob;
    const isRunning = job.status === 'running';
    const statusIcon = isRunning ? '⟳' : job.status === 'done' ? '✓' : '✗';
    const statusColour = isRunning ? 'var(--color-warning)'
        : job.status === 'done' ? 'var(--color-success)' : 'var(--color-error)';

    const stepInfo = isRunning && job.step_total
        ? `Step ${job.step_current}/${job.step_total}${job.step_label ? ': ' + job.step_label : ''}`
        : '';

    panel.className = `log-panel ${_logPanelExpanded ? 'log-panel--expanded' : 'log-panel--collapsed'}`;

    const cancelBtn = isRunning
        ? `<button class="btn-danger" id="btn-log-cancel" style="font-size:11px;padding:3px 10px;">✕ Cancel</button>`
        : '';
    const expandBtn = `<button class="btn-icon" id="btn-log-toggle" title="${_logPanelExpanded ? 'Collapse' : 'Expand'}">
        ${_logPanelExpanded ? '▼' : '▲'}
    </button>`;

    panel.innerHTML = `
        <div class="log-panel__header" id="log-header">
            <span class="log-panel__status-icon" style="color:${statusColour}">${statusIcon}</span>
            <span class="log-panel__title">
                ${escHtml(job.image_name)} — ${escHtml(job.pipeline_name || job.pipeline_stem)}
            </span>
            ${stepInfo ? `<span class="log-panel__progress">${escHtml(stepInfo)}</span>` : ''}
            <div class="log-panel__actions">
                ${cancelBtn}
                ${expandBtn}
            </div>
        </div>
        <div class="log-panel__body" id="log-body">
            ${renderLogLines(s.logs)}
        </div>
    `;

    // Toggle expand
    document.getElementById('log-header').addEventListener('click', e => {
        if (e.target.closest('button')) return;
        _logPanelExpanded = !_logPanelExpanded;
        renderLogPanel(state);
    });
    document.getElementById('btn-log-toggle').addEventListener('click', () => {
        _logPanelExpanded = !_logPanelExpanded;
        renderLogPanel(state);
    });

    const cancelEl = document.getElementById('btn-log-cancel');
    if (cancelEl) {
        cancelEl.addEventListener('click', async () => {
            try { await apiFetch('/api/jobs/current', { method: 'DELETE' }); }
            catch (e) { console.error('Cancel failed:', e); }
        });
    }

    // Auto-scroll
    const body = document.getElementById('log-body');
    if (body) {
        body.addEventListener('scroll', () => {
            _logUserScrolled = body.scrollHeight - body.scrollTop - body.clientHeight > 30;
        });
        if (isRunning && !_logUserScrolled) {
            body.scrollTop = body.scrollHeight;
        }
        if (!isRunning) {
            _logUserScrolled = false;
        }
    }
}

function renderLogLines(logs) {
    return logs.map(line => {
        const lvl = (line.level || 'info').toLowerCase();
        const cls = lvl === 'debug' ? 'log-line--debug'
            : lvl === 'warning' ? 'log-line--warning'
                : lvl === 'error' || lvl === 'critical' ? 'log-line--error'
                    : 'log-line--info';
        return `<div class="log-line ${cls}">${escHtml(line.text || '')}</div>`;
    }).join('');
}

// ─── Lightbox ─────────────────────────────────────────────────────────────────

function openLightbox(src) {
    const lb = document.getElementById('lightbox');
    if (!lb) return;
    lb.querySelector('img').src = src;
    lb.classList.remove('lightbox--hidden');
}

function closeLightbox() {
    const lb = document.getElementById('lightbox');
    if (lb) lb.classList.add('lightbox--hidden');
}

// ─── SSE Client ───────────────────────────────────────────────────────────────

let _sseSource = null;
let _pollInterval = null;

function connectSSE() {
    if (_sseSource) {
        _sseSource.close();
        _sseSource = null;
    }
    clearInterval(_pollInterval);

    _sseSource = new EventSource('/api/events');

    _sseSource.addEventListener('refresh', async () => {
        await refreshAll();
    });

    _sseSource.addEventListener('log', e => {
        try {
            const line = JSON.parse(e.data);
            const newLogs = [...state.logs.slice(-499), line];
            setState({ logs: newLogs });
            // Auto-scroll
            const body = document.getElementById('log-body');
            if (body && !_logUserScrolled) {
                body.scrollTop = body.scrollHeight;
            }
        } catch (_) { }
    });

    _sseSource.addEventListener('progress', e => {
        try {
            const data = JSON.parse(e.data);
            if (state.currentJob) {
                const updated = Object.assign({}, state.currentJob, {
                    step_current: data.step_current,
                    step_total: data.step_total,
                    step_label: data.step_label,
                });
                // Update without full re-render — just patch log panel header
                state = Object.assign({}, state, { currentJob: updated });
                renderLogPanel(state);
            }
        } catch (_) { }
    });

    _sseSource.onerror = () => {
        _sseSource.close();
        _sseSource = null;
        // Fallback: poll every 5 seconds
        if (!_pollInterval) {
            _pollInterval = setInterval(async () => {
                await refreshAll();
                // Try to reconnect SSE
                if (!_sseSource) {
                    clearInterval(_pollInterval);
                    _pollInterval = null;
                    setTimeout(connectSSE, 1000);
                }
            }, 5000);
        }
    };
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escAttr(str) {
    return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function stem(filename) {
    return filename.replace(/\.[^.]+$/, '');
}

function formatBytes(bytes) {
    if (bytes == null) return '?';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// ─── Bootstrap ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    // Lightbox close
    const lb = document.getElementById('lightbox');
    if (lb) {
        lb.addEventListener('click', closeLightbox);
        lb.querySelector('img').addEventListener('click', e => e.stopPropagation());
    }
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeLightbox();
    });

    // Initial data load
    await refreshAll();

    // Connect SSE
    connectSSE();
});
