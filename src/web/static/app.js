// =============================================================================
// Shipyard — Unified Frontend JavaScript
// =============================================================================

// =============================================================================
// 1. STATE & INITIALIZATION
// =============================================================================

let currentMode = 'decompose';
let agentOpen = false;
let currentProject = null;
let currentJobId = null;
let eventSource = null;

// Decompose state
let allDigs = [];
let selectedDigs = [];
let allDecompResults = [];
let pendingDecompRun = null;

// Model state
let currentModel = null;
let selectedToolMode = 'capella';
let selectedLayers = [];
let parsedRequirements = [];
let _pendingModelSettings = null;
let _stageTimers = {};
let _elapsedInterval = null;

// DOM helper — create element safely (no innerHTML)
function el(tag, attrs, children) {
    var elem = document.createElement(tag);
    if (attrs) {
        Object.keys(attrs).forEach(function (key) {
            if (key === 'textContent') elem.textContent = attrs[key];
            else if (key === 'className') elem.className = attrs[key];
            else if (key === 'onclick') elem.addEventListener('click', attrs[key]);
            else if (key === 'style') elem.setAttribute('style', attrs[key]);
            else if (key.startsWith('data-')) elem.setAttribute(key, attrs[key]);
            else elem.setAttribute(key, attrs[key]);
        });
    }
    if (children) {
        children.forEach(function (child) {
            if (typeof child === 'string') elem.appendChild(document.createTextNode(child));
            else if (child) elem.appendChild(child);
        });
    }
    return elem;
}

// Safe DOM clear
function clearChildren(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
}

// Shorthand getElementById
function $(id) { return document.getElementById(id); }

// =============================================================================
// 2. DOMContentLoaded
// =============================================================================

document.addEventListener('DOMContentLoaded', function () {
    // Load config from template
    var cfg = window.SHIPYARD_CONFIG || {};
    currentProject = cfg.project || null;

    // Initialize mode from settings
    if (cfg.settings && cfg.settings.default_mode) {
        selectedToolMode = cfg.settings.default_mode;
    }

    // Initialize views
    loadProjectList();
    initModeSwitch();
    initDragDrop();
    initTabSwitching();
    initLayerCheckboxes();
    initProviderSelector(cfg.settings);
    initAutoSendToggle(cfg.settings);
    renderSuggestedPrompts(currentMode);
    checkForUpdates();

    // If a project is loaded, refresh everything
    if (currentProject && currentProject.slug) {
        refreshAll();
    }

    // Close dropdowns on outside click
    document.addEventListener('click', function (e) {
        var projDd = $('project-dropdown');
        if (projDd && !projDd.classList.contains('hidden') && !e.target.closest('.project-selector')) {
            projDd.classList.add('hidden');
        }
        var digDd = $('dig-dropdown');
        if (digDd && !digDd.classList.contains('hidden') && !e.target.closest('.dig-picker-wrap')) {
            digDd.classList.add('hidden');
        }
        var exportMenu = $('export-menu');
        if (exportMenu && !exportMenu.classList.contains('hidden') && !e.target.closest('.export-dropdown')) {
            exportMenu.classList.add('hidden');
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
            e.preventDefault();
            performUndo();
        }
        if ((e.ctrlKey || e.metaKey) && (e.key === 'Z' || (e.key === 'z' && e.shiftKey))) {
            e.preventDefault();
            performRedo();
        }
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            forceSave();
        }
    });

    // Model search
    var searchInput = $('model-search');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            filterModelTree(this.value.trim().toLowerCase());
        });
    }
});

// =============================================================================
// 3. MODE SWITCHING (Decompose / Model)
// =============================================================================

function initModeSwitch() {
    // Mode is set via onclick in HTML, just ensure initial state
    switchMode(currentMode);
}

function switchMode(mode) {
    currentMode = mode;

    // Toggle view containers
    var decompView = $('decompose-view');
    var modelView = $('model-view');
    if (decompView) {
        decompView.classList.toggle('active', mode === 'decompose');
        decompView.classList.toggle('hidden', mode !== 'decompose');
    }
    if (modelView) {
        modelView.classList.toggle('active', mode === 'model');
        modelView.classList.toggle('hidden', mode !== 'model');
    }

    // Update tab styling
    document.querySelectorAll('.mode-tab').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
    });

    // Update agent suggested prompts
    renderSuggestedPrompts(mode);
}

// =============================================================================
// 4. PROJECT MANAGEMENT
// =============================================================================

async function loadProjectList() {
    try {
        var res = await fetch('/project/list');
        if (!res.ok) return;
        var data = await res.json();
        var dropdown = $('project-dropdown');
        if (!dropdown) return;
        clearChildren(dropdown);

        // New project button
        var newBtn = el('div', { className: 'dropdown-item dropdown-action', onclick: function () { createProject(); } }, ['+ New Project']);
        dropdown.appendChild(newBtn);

        // Import button
        var importBtn = el('div', { className: 'dropdown-item dropdown-action' });
        importBtn.textContent = 'Import Project...';
        importBtn.addEventListener('click', function () {
            var input = document.createElement('input');
            input.type = 'file';
            input.accept = '.json,.zip';
            input.addEventListener('change', function () {
                if (input.files[0]) importProject(input.files[0]);
            });
            input.click();
        });
        dropdown.appendChild(importBtn);

        if (data.projects && data.projects.length > 0) {
            dropdown.appendChild(el('div', { className: 'dropdown-divider' }));
            data.projects.forEach(function (proj) {
                var item = el('div', { className: 'dropdown-item' + (currentProject && currentProject.slug === proj.slug ? ' active' : '') });

                var nameSpan = el('span', { className: 'dropdown-project-name', textContent: proj.name || proj.slug });
                item.appendChild(nameSpan);

                var delBtn = el('span', { className: 'dropdown-project-delete', textContent: '\u00d7', title: 'Delete project' });
                delBtn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    deleteProject(proj.slug, proj.name || proj.slug);
                });
                item.appendChild(delBtn);

                item.addEventListener('click', function () {
                    selectProject(proj.slug);
                });
                dropdown.appendChild(item);
            });
        }

        // Update header project name
        var nameEl = $('project-name');
        if (nameEl && currentProject) {
            nameEl.textContent = currentProject.name || currentProject.slug || 'No Project';
        }
    } catch (e) {
        console.error('Failed to load project list', e);
    }
}

function toggleProjectDropdown() {
    var dd = $('project-dropdown');
    if (dd) dd.classList.toggle('hidden');
}

async function createProject() {
    var name = prompt('Project name:', 'Untitled Project');
    if (name === null) return;

    try {
        var res = await fetch('/project/new', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name }),
        });
        if (!res.ok) {
            var err = await res.json();
            showToast(err.detail || 'Failed to create project', 'error');
            return;
        }
        var data = await res.json();
        currentProject = data.project || data;
        $('project-name').textContent = currentProject.name || 'Untitled';
        $('project-dropdown').classList.add('hidden');
        showToast('Project created', 'success');
        loadProjectList();
        refreshAll();
    } catch (e) {
        showToast('Failed to create project: ' + e.message, 'error');
    }
}

async function selectProject(slug) {
    try {
        var res = await fetch('/project/select/' + encodeURIComponent(slug), { method: 'POST' });
        if (!res.ok) {
            var err = await res.json();
            showToast(err.detail || 'Failed to select project', 'error');
            return;
        }
        var data = await res.json();
        currentProject = data.project || data;
        $('project-name').textContent = currentProject.name || slug;
        $('project-dropdown').classList.add('hidden');
        showToast('Project loaded', 'success');
        loadProjectList();
        refreshAll();
    } catch (e) {
        showToast('Failed to select project: ' + e.message, 'error');
    }
}

async function renameProject() {
    if (!currentProject) return;
    var newName = prompt('Rename project:', currentProject.name || '');
    if (!newName) return;

    try {
        var res = await fetch('/project/rename', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName }),
        });
        if (res.ok) {
            currentProject.name = newName;
            $('project-name').textContent = newName;
            loadProjectList();
            showToast('Project renamed', 'success');
        }
    } catch (e) {
        showToast('Rename failed', 'error');
    }
}

function deleteProject(slug, name) {
    // Show delete confirmation modal
    var modal = $('delete-modal');
    var nameEl = $('delete-project-name');
    if (nameEl) nameEl.textContent = name || slug;
    modal._deleteSlug = slug;
    modal.classList.remove('hidden');
}

function closeDeleteModal() {
    $('delete-modal').classList.add('hidden');
}

async function confirmDelete() {
    var modal = $('delete-modal');
    var slug = modal._deleteSlug;
    if (!slug) return;
    modal.classList.add('hidden');

    try {
        var res = await fetch('/project/delete/' + encodeURIComponent(slug), { method: 'POST' });
        if (res.ok) {
            if (currentProject && currentProject.slug === slug) {
                currentProject = null;
                $('project-name').textContent = 'No Project';
            }
            loadProjectList();
            showToast('Project deleted', 'success');
        }
    } catch (e) {
        showToast('Delete failed', 'error');
    }
}

async function downloadProject() {
    if (!currentProject) {
        showToast('No project to download', 'error');
        return;
    }
    window.open('/project/download', '_blank');
}

async function importProject(file) {
    var formData = new FormData();
    formData.append('file', file);

    try {
        var res = await fetch('/project/import', { method: 'POST', body: formData });
        if (!res.ok) {
            var err = await res.json();
            showToast(err.detail || 'Import failed', 'error');
            return;
        }
        var data = await res.json();
        currentProject = data.project || data;
        $('project-name').textContent = currentProject.name || 'Imported';
        $('project-dropdown').classList.add('hidden');
        loadProjectList();
        refreshAll();
        showToast('Project imported', 'success');
    } catch (e) {
        showToast('Import failed: ' + e.message, 'error');
    }
}

// =============================================================================
// 5. REFRESH ALL
// =============================================================================

async function refreshAll() {
    // Refresh decompose view
    loadDigs();
    loadDecompResults();

    // Refresh model view
    loadModelData();
}

async function loadModelData() {
    try {
        var res = await fetch('/model/data');
        if (!res.ok) return;
        var data = await res.json();
        currentModel = data;
        renderModelTree(data.layers);
        renderCoverage(data.requirements, data.links);
        // Refresh active tab
        var activeTab = document.querySelector('.tab-btn.active');
        if (activeTab) {
            var tabName = activeTab.getAttribute('data-tab');
            if (tabName === 'links') renderLinksTab();
            if (tabName === 'instructions') renderInstructionsTab();
            if (tabName === 'json') renderJsonTab();
            if (tabName === 'batches') renderBatchesTab();
        }
        populateExportLayerFilters();
    } catch (e) {
        // No model data yet — OK
    }
}

// =============================================================================
// 6. DECOMPOSE MODE
// =============================================================================

// Track uploaded files
let uploadedDecompFiles = [];

// --- Upload ---
async function handleDecompUpload(input) {
    if (!input.files || !input.files[0]) return;
    var file = input.files[0];
    var formData = new FormData();
    formData.append('file', file);

    try {
        var res = await fetch('/decompose/upload', { method: 'POST', body: formData });
        if (!res.ok) {
            var err = await res.json();
            showToast(err.detail || 'Upload failed', 'error');
            return;
        }
        var data = await res.json();
        var uploadText = $('decomp-upload-text');
        if (uploadText) {
            uploadText.textContent = '\ud83d\udcc4 ' + file.name + ' \u2014 ' + (data.digs_loaded || data.dig_count || 0) + ' DIGs';
        }
        var fileActions = $('decomp-file-actions');
        if (fileActions) fileActions.classList.remove('hidden');

        // Track uploaded file
        uploadedDecompFiles.push({ name: file.name, type: 'reference', digs: data.digs_loaded || data.dig_count || 0 });
        renderDecompFileList();

        showToast('Loaded ' + (data.digs_loaded || data.dig_count || 0) + ' DIGs from ' + file.name, 'success');
        loadDigs();
    } catch (e) {
        showToast('Upload failed: ' + e.message, 'error');
    }
}

function triggerUploadAnother() {
    var input = $('decomp-file-input');
    if (input) input.click();
}

function renderDecompFileList() {
    var listEl = $('decomp-file-list');
    if (!listEl) return;
    clearChildren(listEl);
    uploadedDecompFiles.forEach(function (f) {
        var row = el('div', { className: 'file-list-item' });
        row.appendChild(el('span', { className: 'file-list-name', textContent: f.name }));
        row.appendChild(el('span', { className: 'file-list-type', textContent: f.type }));
        if (f.digs) row.appendChild(el('span', { className: 'file-list-count', textContent: f.digs + ' DIGs' }));
        listEl.appendChild(row);
    });
}

function handleDecompDrop(e) {
    e.preventDefault();
    var area = $('decomp-upload-area');
    if (area) area.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        var input = $('decomp-file-input');
        input.files = e.dataTransfer.files;
        handleDecompUpload(input);
    }
}

// --- DIGs ---
async function loadDigs() {
    try {
        var res = await fetch('/decompose/digs');
        if (!res.ok) return;
        var data = await res.json();
        allDigs = data.digs || [];
    } catch (e) {
        // silently ignore
    }
}

function showDigDropdown() {
    filterDigDropdown();
    var dd = $('dig-dropdown');
    if (dd) dd.classList.remove('hidden');
}

function filterDigDropdown() {
    var query = ($('dig-search') || {}).value || '';
    query = query.toLowerCase().trim();
    var dropdown = $('dig-dropdown');
    if (!dropdown) return;
    clearChildren(dropdown);

    var filtered = allDigs.filter(function (d) {
        return d.id.toLowerCase().indexOf(query) !== -1 ||
               (d.text && d.text.toLowerCase().indexOf(query) !== -1);
    });

    if (filtered.length === 0) {
        dropdown.appendChild(el('div', { className: 'dig-dropdown-empty', textContent: query ? 'No matching DIGs' : 'No DIGs loaded' }));
        return;
    }

    filtered.slice(0, 50).forEach(function (d) {
        var isSelected = selectedDigs.indexOf(d.id) !== -1;
        var item = el('div', { className: 'dig-dropdown-item' + (isSelected ? ' selected' : '') });
        item.appendChild(el('span', { className: 'dig-dropdown-id', textContent: d.id }));
        item.appendChild(el('span', { className: 'dig-dropdown-text', textContent: d.text || '' }));
        item.addEventListener('click', function () {
            if (!isSelected) {
                selectedDigs.push(d.id);
                renderDigTags();
                filterDigDropdown();
            }
        });
        dropdown.appendChild(item);
    });

    if (filtered.length > 50) {
        dropdown.appendChild(el('div', { className: 'dig-dropdown-empty', textContent: '...' + (filtered.length - 50) + ' more. Type to filter.' }));
    }
}

function renderDigTags() {
    var container = $('dig-tags');
    if (!container) return;
    clearChildren(container);
    selectedDigs.forEach(function (id) {
        var tag = el('span', { className: 'dig-tag' }, [id]);
        var x = el('span', { className: 'dig-tag-x', textContent: '\u00d7' });
        x.addEventListener('click', function () {
            selectedDigs = selectedDigs.filter(function (d) { return d !== id; });
            renderDigTags();
            filterDigDropdown();
        });
        tag.appendChild(x);
        container.appendChild(tag);
    });
    var searchInput = $('dig-search');
    if (searchInput) searchInput.value = '';
}

function getSelectedDigIds() {
    if (selectedDigs.length > 0) return selectedDigs.join(',');
    var input = $('dig-search');
    return input ? input.value.trim() : '';
}

// --- Run ---
async function startDecompose() {
    var body = {
        dig_ids: getSelectedDigIds(),
        max_depth: parseInt(($('decomp-depth') || {}).value || '3'),
        max_breadth: parseInt(($('decomp-breadth') || {}).value || '2'),
        skip_vv: !($('decomp-vv') || {}).checked,
        skip_judge: !($('decomp-judge') || {}).checked,
    };

    // Get cost estimate first
    try {
        var estRes = await fetch('/decompose/estimate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        var est = await estRes.json();
        pendingDecompRun = body;

        // Populate cost modal
        $('cost-model-name').textContent = est.model || 'Unknown';
        $('cost-calls').textContent = (est.max_total_calls || est.total_calls || 0) + ' API calls';
        var costVal = est.est_cost_usd || est.estimated_cost || 0;
        $('cost-range').textContent = costVal > 0 ? '~' + formatCost(costVal) + ' (worst case)' : 'N/A';
        $('cost-modal').classList.remove('hidden');
    } catch (e) {
        // If estimate fails, run directly
        pendingDecompRun = body;
        proceedAfterCost();
    }
}

async function estimateDecompCost() {
    var body = {
        dig_ids: getSelectedDigIds(),
        max_depth: parseInt(($('decomp-depth') || {}).value || '3'),
        max_breadth: parseInt(($('decomp-breadth') || {}).value || '2'),
        skip_vv: !($('decomp-vv') || {}).checked,
        skip_judge: !($('decomp-judge') || {}).checked,
    };
    try {
        var res = await fetch('/decompose/estimate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        var data = await res.json();
        var costStr = data.est_cost_usd > 0 ? ' \u2248 ~' + formatCost(data.est_cost_usd) : '';
        showToast('Est: ' + (data.digs || 0) + ' DIGs, ' + (data.max_total_calls || 0) + ' max calls' + costStr, 'info');
    } catch (e) {
        showToast('Estimate failed', 'error');
    }
}

function closeCostModal() {
    $('cost-modal').classList.add('hidden');
    pendingDecompRun = null;
    _pendingModelSettings = null;
}

async function proceedAfterCost() {
    $('cost-modal').classList.add('hidden');

    // Check if this is a decompose run or a model run
    if (pendingDecompRun) {
        var body = pendingDecompRun;
        pendingDecompRun = null;
        await executeDecompRun(body);
    } else if (_pendingModelSettings) {
        var settings = _pendingModelSettings;
        _pendingModelSettings = null;
        await executeModelRun(settings);
    }
}

async function executeDecompRun(body) {
    try {
        var res = await fetch('/decompose/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (res.status === 409) {
            var conflict = await res.json();
            var activeType = conflict.job_type || 'unknown';
            if (confirm('A ' + activeType + ' job is already running. Cancel it and start decomposition?')) {
                var cancelUrl = activeType === 'model' ? '/model/cancel/' : '/decompose/cancel/';
                await fetch(cancelUrl + conflict.job_id, { method: 'POST' });
                if (eventSource) { eventSource.close(); eventSource = null; }
                // Retry after cancellation
                setTimeout(function () { executeDecompRun(body); }, 500);
            }
            return;
        }
        if (!res.ok) {
            var err = await res.json();
            showError(err.detail || 'Failed to start decomposition');
            return;
        }
        var data = await res.json();

        // Show orphaned links warning if present (Section 9.1)
        if (data.warning && data.warning.warning === 'orphaned_links') {
            if (!confirm(data.warning.message + '\n\nProceed anyway?')) {
                // Cancel the job that was already started
                await fetch('/decompose/cancel/' + data.job_id, { method: 'POST' });
                return;
            }
        }

        currentJobId = data.job_id;
        showDecompProgress();
        startSSEStream(data.job_id, 'decompose');
    } catch (e) {
        showError('Failed to start: ' + e.message);
    }
}

function showDecompProgress() {
    var section = $('decomp-progress');
    if (section) {
        section.classList.remove('hidden');
        $('decomp-progress-bar').style.width = '0%';
        $('decomp-progress-label').textContent = 'Processing...';
        $('decomp-progress-cost').textContent = '';
        $('decomp-progress-detail').textContent = '';
    }
}

function hideDecompProgress() {
    var section = $('decomp-progress');
    if (section) section.classList.add('hidden');
}

async function cancelDecompJob() {
    if (!currentJobId) return;
    try {
        await fetch('/decompose/cancel/' + currentJobId, { method: 'POST' });
    } catch (e) { /* ignore */ }
    if (eventSource) { eventSource.close(); eventSource = null; }
    hideDecompProgress();
    showToast('Cancelled', 'info');
}

// --- Results ---
async function loadDecompResults() {
    try {
        var res = await fetch('/decompose/results');
        if (!res.ok) return;
        var data = await res.json();
        allDecompResults = data.results || [];
        renderDecompResults(allDecompResults);
    } catch (e) {
        // No results yet
    }
}

function filterDecompResults() {
    var query = ($('decomp-results-search') || {}).value || '';
    query = query.toLowerCase().trim();
    if (!query) {
        renderDecompResults(allDecompResults);
        return;
    }
    var filtered = allDecompResults.filter(function (r) {
        return r.dig_id.toLowerCase().indexOf(query) !== -1 ||
               (r.dig_text && r.dig_text.toLowerCase().indexOf(query) !== -1);
    });
    renderDecompResults(filtered);
}

function renderDecompResults(results) {
    var list = $('decomp-results-list');
    var countEl = $('decomp-results-count');
    if (!list) return;
    clearChildren(list);

    if (!results || results.length === 0) {
        list.appendChild(el('div', { className: 'empty-state', textContent: 'Upload a GTR-SDS workbook to get started, or switch to Model to upload pre-decomposed requirements' }));
        if (countEl) countEl.textContent = 'RESULTS \u2014 0 DIGS, 0 REQUIREMENTS';
        return;
    }

    var totalNodes = results.reduce(function (s, r) { return s + (r.nodes || 0); }, 0);
    if (countEl) countEl.textContent = 'RESULTS \u2014 ' + results.length + ' DIGS, ' + totalNodes + ' REQUIREMENTS';

    results.forEach(function (r) {
        list.appendChild(renderDecompResult(r));
    });
}

function renderDecompResult(r) {
    var card = el('div', { className: 'result-card', id: 'decomp-card-' + r.dig_id });

    // Header
    var header = el('div', { className: 'result-card-header' });
    header.addEventListener('click', function () { expandDecompResult(r.dig_id); });

    var headerLeft = el('div', { className: 'result-card-left' });
    headerLeft.appendChild(el('span', { className: 'result-dig-id', textContent: 'DIG ' + r.dig_id }));
    headerLeft.appendChild(el('span', { className: 'result-dig-text', textContent: r.dig_text || '' }));

    // Queue badge
    var badgeClass = r.queued ? 'badge badge-queued' : 'badge badge-not-sent';
    var badgeText = r.queued ? 'Queued' : 'Not sent';
    headerLeft.appendChild(el('span', { className: badgeClass, textContent: badgeText }));

    var headerRight = el('div', { className: 'result-card-right' });
    headerRight.appendChild(el('span', { className: 'result-levels', textContent: (r.levels || 0) + ' levels' }));
    headerRight.appendChild(el('span', { className: 'result-nodes', textContent: (r.nodes || 0) + ' nodes' }));
    headerRight.appendChild(el('span', { className: 'result-cost', textContent: formatCost(r.cost || 0) }));

    // Expand button
    var expandBtn = el('span', { className: 'result-expand', id: 'expand-' + r.dig_id, textContent: '\u2295' });
    headerRight.appendChild(expandBtn);

    // Delete button
    var deleteBtn = el('span', { className: 'result-delete', title: 'Delete result', textContent: '\u00d7' });
    deleteBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        deleteDecompResult(r.dig_id);
    });
    headerRight.appendChild(deleteBtn);

    header.appendChild(headerLeft);
    header.appendChild(headerRight);
    card.appendChild(header);

    // Body (expanded tree)
    var body = el('div', { className: 'result-card-body', id: 'decomp-body-' + r.dig_id });
    card.appendChild(body);

    return card;
}

async function expandDecompResult(digId) {
    var body = $('decomp-body-' + digId);
    var expandBtn = $('expand-' + digId);
    if (!body) return;

    if (body.classList.contains('open')) {
        body.classList.remove('open');
        if (expandBtn) expandBtn.textContent = '\u2295';
        return;
    }

    if (!body.hasChildNodes()) {
        try {
            var res = await fetch('/decompose/results/' + encodeURIComponent(digId));
            if (!res.ok) throw new Error('Not found');
            var tree = await res.json();
            body.appendChild(renderDecompTreeNode(tree.root || tree));
        } catch (e) {
            body.appendChild(el('div', { className: 'error-text', textContent: 'Failed to load' }));
        }
    }
    body.classList.add('open');
    if (expandBtn) expandBtn.textContent = '\u2296';
}

function renderDecompTreeNode(node) {
    if (!node) return document.createTextNode('');
    var levelClass = 'tree-level tree-level-' + Math.min(node.level || 0, 4);
    var reqText = node.technical_requirement || node.text || '(empty)';
    if (reqText.length > 120) reqText = reqText.slice(0, 120) + '...';
    var nodeId = 'dnode-' + (node.level || 0) + '-' + Math.random().toString(36).slice(2, 8);

    var container = el('div', { className: 'tree-node' });

    // Header row
    var header = el('div', { className: 'tree-node-header' });
    header.addEventListener('click', function () {
        var detail = $(nodeId);
        if (detail) detail.style.display = detail.style.display === 'none' ? 'block' : 'none';
    });
    header.appendChild(el('span', { className: levelClass, textContent: 'L' + (node.level || 0) }));
    header.appendChild(el('span', { className: 'tree-req', textContent: reqText }));
    container.appendChild(header);

    // Detail panel
    var detail = el('div', { className: 'node-detail', id: nodeId, style: 'display:none' });
    var dl = document.createElement('dl');

    function addField(label, value) {
        if (!value) return;
        dl.appendChild(el('dt', { textContent: label }));
        dl.appendChild(el('dd', { textContent: value }));
    }

    if (node.technical_requirement) {
        dl.appendChild(el('dt', { textContent: 'Technical Requirement' }));
        var reqRow = el('dd', { style: 'display:flex; align-items:start; gap:4px;' });
        reqRow.appendChild(el('span', { textContent: node.technical_requirement, style: 'flex:1;' }));
        var copyBtn = el('button', { className: 'btn-copy', textContent: 'Copy' });
        copyBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            copyToClipboard(node.technical_requirement);
        });
        reqRow.appendChild(copyBtn);
        dl.appendChild(reqRow);
    }
    addField('Rationale', node.rationale);
    addField('Allocation', (node.allocation || '-') + ' \u2014 ' + (node.chapter_code || '-'));
    addField('System Hierarchy', node.system_hierarchy_id);
    addField('Acceptance Criteria', node.acceptance_criteria);
    if (node.verification_method && node.verification_method.length) {
        addField('Verification', node.verification_method.join(', ') + ' @ ' + (node.verification_event || []).join(', '));
    }
    addField('Confidence Notes', node.confidence_notes);

    detail.appendChild(dl);
    container.appendChild(detail);

    // Children
    if (node.children && node.children.length) {
        var childrenDiv = el('div', { className: 'tree-children' });
        node.children.forEach(function (child) {
            childrenDiv.appendChild(renderDecompTreeNode(child));
        });
        container.appendChild(childrenDiv);
    }

    return container;
}

async function deleteDecompResult(digId) {
    if (!confirm('Delete result for DIG ' + digId + '?')) return;
    try {
        var res = await fetch('/decompose/results/' + encodeURIComponent(digId), { method: 'DELETE' });
        if (res.ok) {
            var card = $('decomp-card-' + digId);
            if (card) {
                card.style.transition = 'opacity 0.3s, transform 0.3s';
                card.style.opacity = '0';
                card.style.transform = 'translateX(20px)';
                setTimeout(function () { card.remove(); }, 300);
            }
            allDecompResults = allDecompResults.filter(function (r) { return r.dig_id !== digId; });
            showToast('DIG ' + digId + ' deleted', 'success');
        }
    } catch (e) {
        showToast('Failed to delete', 'error');
    }
}

async function sendToModel(digIds) {
    if (!digIds || digIds.length === 0) return;
    try {
        var res = await fetch('/decompose/send-to-model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dig_ids: digIds }),
        });
        if (res.ok) {
            showToast('Sent ' + digIds.length + ' DIG(s) to model queue', 'success');
            loadDecompResults();
            loadModelQueue();
        } else {
            var err = await res.json();
            showToast(err.detail || 'Failed to send', 'error');
        }
    } catch (e) {
        showToast('Failed to send to model', 'error');
    }
}

function downloadDecompXlsx() {
    window.location.href = '/decompose/export';
}

// =============================================================================
// 7. MODEL MODE
// =============================================================================

// --- Layer checkboxes ---
function initLayerCheckboxes() {
    var cfg = window.SHIPYARD_CONFIG || {};
    var container = $('layer-checkboxes');
    if (!container) return;
    clearChildren(container);

    var layers = selectedToolMode === 'capella' ? (cfg.capellaLayers || {}) : (cfg.rhapsodyDiagrams || {});
    Object.keys(layers).forEach(function (key) {
        var label = document.createElement('label');
        label.className = 'layer-checkbox';
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = key;
        cb.checked = true;
        cb.addEventListener('change', readSelectedLayers);
        label.appendChild(cb);
        label.appendChild(document.createTextNode(' ' + layers[key]));
        container.appendChild(label);
    });
    readSelectedLayers();
}

function readSelectedLayers() {
    var container = $('layer-checkboxes');
    if (!container) { selectedLayers = []; return; }
    selectedLayers = [];
    container.querySelectorAll('input[type=checkbox]:checked').forEach(function (cb) {
        selectedLayers.push(cb.value);
    });
    // Enable/disable generate button
    var btn = $('generate-btn');
    if (btn) btn.disabled = selectedLayers.length === 0;
}

// --- Tool mode toggle ---
function setToolMode(mode) {
    // Check if model exists and warn about data loss
    if (currentModel && currentModel.layers && Object.keys(currentModel.layers).length > 0 && mode !== selectedToolMode) {
        // Count elements and links for the warning message
        var elementCount = 0;
        var layers = currentModel.layers || {};
        Object.keys(layers).forEach(function (layerKey) {
            var layer = layers[layerKey];
            if (layer && typeof layer === 'object') {
                Object.keys(layer).forEach(function (collKey) {
                    if (Array.isArray(layer[collKey])) {
                        elementCount += layer[collKey].length;
                    }
                });
            }
        });
        var linkCount = (currentModel.links && currentModel.links.length) || 0;

        // Update the modal text with counts
        var modal = $('mode-switch-modal');
        var modalBody = modal.querySelector('.modal-body p');
        if (modalBody) {
            var currentModeName = selectedToolMode === 'capella' ? 'Capella' : 'Rhapsody';
            var newModeName = mode === 'capella' ? 'Capella' : 'Rhapsody';
            modalBody.textContent = 'Switching to ' + newModeName + ' will clear the existing ' + currentModeName + ' model (' + elementCount + ' elements, ' + linkCount + ' links). Decomposed requirements are preserved. Continue?';
        }

        modal._pendingMode = mode;
        modal.classList.remove('hidden');
        return;
    }
    applyToolMode(mode);
}

function closeModeSwitchModal() {
    $('mode-switch-modal').classList.add('hidden');
}

function confirmModeSwitch() {
    var modal = $('mode-switch-modal');
    var mode = modal._pendingMode;
    modal.classList.add('hidden');
    if (mode) applyToolMode(mode);
}

function applyToolMode(mode) {
    selectedToolMode = mode;
    document.querySelectorAll('#mode-toggle .segment').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
    });
    initLayerCheckboxes();
}

// --- Provider selector ---
function initProviderSelector(settings) {
    var provider = (settings && settings.provider) || 'api';
    setProvider(provider === 'local' ? 'local' : 'api');
}

function setProvider(uiProvider) {
    document.querySelectorAll('#provider-selector .segment').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-provider') === uiProvider);
    });
}

// --- Upload (model) ---
function handleModelFileSelect(input) {
    if (input.files && input.files[0]) handleModelUpload(input.files[0]);
}

function handleModelDrop(e) {
    e.preventDefault();
    var area = $('model-upload-area');
    if (area) area.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleModelUpload(e.dataTransfer.files[0]);
    }
}

async function handleModelUpload(file) {
    var formData = new FormData();
    formData.append('file', file);

    try {
        var res = await fetch('/model/upload', { method: 'POST', body: formData });
        if (!res.ok) {
            var err = await res.json();
            showToast(err.detail || 'Upload failed', 'error');
            return;
        }
        var data = await res.json();
        parsedRequirements = data.requirements || [];

        // Update UI
        var statusEl = $('model-file-status');
        if (statusEl) statusEl.classList.remove('hidden');
        var nameEl = $('model-file-name');
        if (nameEl) nameEl.textContent = file.name;
        var countEl = $('model-req-count');
        if (countEl) countEl.textContent = parsedRequirements.length + ' requirements';

        // Enable generate
        var btn = $('generate-btn');
        if (btn && selectedLayers.length > 0) btn.disabled = false;

        // Populate req preview
        populateReqPreview(parsedRequirements);

        showToast('Loaded ' + parsedRequirements.length + ' requirements', 'success');
    } catch (e) {
        showToast('Upload failed: ' + e.message, 'error');
    }
}

function populateReqPreview(reqs) {
    var section = $('model-req-preview');
    var list = $('req-preview-list');
    if (!section || !list) return;
    clearChildren(list);

    reqs.forEach(function (req) {
        var item = el('div', { className: 'req-preview-item' });
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'req-checkbox';
        cb.value = req.id;
        cb.checked = true;
        cb.addEventListener('change', updateReqSelectedCount);

        item.appendChild(cb);
        item.appendChild(el('span', { className: 'req-preview-id', textContent: req.id }));
        var textSpan = el('span', { className: 'req-preview-text', textContent: req.text || '' });
        if (req.text) textSpan.title = req.text;
        item.appendChild(textSpan);
        list.appendChild(item);
    });

    section.classList.remove('hidden');
    updateReqSelectedCount();
}

function updateReqSelectedCount() {
    var total = document.querySelectorAll('#req-preview-list .req-checkbox').length;
    var checked = document.querySelectorAll('#req-preview-list .req-checkbox:checked').length;
    var countEl = $('req-selected-count');
    if (countEl) countEl.textContent = checked + ' of ' + total + ' selected';
}

function reqSelectAll() {
    document.querySelectorAll('#req-preview-list .req-checkbox').forEach(function (cb) { cb.checked = true; });
    updateReqSelectedCount();
}

function reqDeselectAll() {
    document.querySelectorAll('#req-preview-list .req-checkbox').forEach(function (cb) { cb.checked = false; });
    updateReqSelectedCount();
}

// --- Queue ---
async function loadModelQueue() {
    try {
        var res = await fetch('/model/queue');
        if (!res.ok) return;
        var data = await res.json();
        var countEl = $('req-counts');
        if (countEl && data.queue) {
            countEl.textContent = data.queue.length + ' requirements in queue';
        }
    } catch (e) {
        // ignore
    }
}

async function dismissFromQueue(ids) {
    try {
        await fetch('/model/dismiss', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: ids }),
        });
        loadModelQueue();
    } catch (e) {
        showToast('Failed to dismiss', 'error');
    }
}

async function restoreToQueue(ids) {
    try {
        await fetch('/model/restore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids: ids }),
        });
        loadModelQueue();
    } catch (e) {
        showToast('Failed to restore', 'error');
    }
}

// --- Pipeline ---
async function startModelBatch() {
    readSelectedLayers();

    if (selectedLayers.length === 0) {
        showToast('Select at least one layer', 'error');
        return;
    }

    var settings = gatherModelSettings();

    // Get selected requirement IDs
    var checkedBoxes = document.querySelectorAll('#req-preview-list .req-checkbox:checked');
    if (checkedBoxes.length > 0) {
        var selectedIds = [];
        checkedBoxes.forEach(function (cb) { selectedIds.push(cb.value); });
        settings.selected_requirements = selectedIds;
    }

    // Estimate cost first
    try {
        var estRes = await fetch('/model/estimate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        if (estRes.ok) {
            var estimate = await estRes.json();
            _pendingModelSettings = settings;
            $('cost-model-name').textContent = estimate.model || 'Unknown';
            $('cost-calls').textContent = (estimate.total_calls || 0) + ' API calls';
            var minCost = formatCost(estimate.estimated_min_cost || 0);
            var maxCost = formatCost(estimate.estimated_max_cost || 0);
            $('cost-range').textContent = minCost + ' \u2013 ' + maxCost;
            $('cost-modal').classList.remove('hidden');
            return;
        }
    } catch (e) {
        // Estimate failed, proceed directly
    }

    _pendingModelSettings = settings;
    proceedAfterCost();
}

function gatherModelSettings() {
    var cfg = window.SHIPYARD_CONFIG || {};
    var settings = cfg.settings || {};

    var activeProvider = document.querySelector('#provider-selector .segment.active');
    var provider = activeProvider ? activeProvider.getAttribute('data-provider') : 'api';

    return {
        mode: selectedToolMode,
        selected_layers: selectedLayers.slice(),
        model: settings.mbse_model || settings.model || 'claude-sonnet-4-6',
        provider: provider,
    };
}

async function executeModelRun(settings) {
    try {
        var res = await fetch('/model/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        if (res.status === 409) {
            var conflict = await res.json();
            var activeType = conflict.job_type || 'unknown';
            if (confirm('A ' + activeType + ' job is already running. Cancel it and start model generation?')) {
                var cancelUrl = activeType === 'decompose' ? '/decompose/cancel/' : '/model/cancel/';
                await fetch(cancelUrl + conflict.job_id, { method: 'POST' });
                if (eventSource) { eventSource.close(); eventSource = null; }
                // Retry after cancellation
                setTimeout(function () { executeModelRun(settings); }, 500);
            }
            return;
        }
        if (!res.ok) {
            var err = await res.json();
            showToast(err.detail || 'Failed to start', 'error');
            return;
        }
        var data = await res.json();
        currentJobId = data.job_id;
        showModelProgress(settings);
        startSSEStream(data.job_id, 'model');
    } catch (e) {
        showToast('Failed to start: ' + e.message, 'error');
    }
}

function showModelProgress(settings) {
    var area = $('model-progress');
    if (area) area.classList.remove('hidden');
    var costEl = $('model-running-cost');
    if (costEl) costEl.textContent = '';

    var stagesDiv = $('pipeline-stages');
    if (!stagesDiv) return;
    clearChildren(stagesDiv);

    var stages = [
        { key: 'analyze', label: 'Analyzing Requirements', desc: 'Checking for ambiguity and completeness' },
        { key: 'clarify', label: 'Clarification', desc: 'Resolving any flagged issues' },
        { key: 'generate', label: 'Generating Model Layers', desc: 'Building MBSE elements for each layer' },
        { key: 'link', label: 'Creating Traceability Links', desc: 'Connecting elements across layers' },
        { key: 'instruct', label: 'Writing Recreation Steps', desc: 'Step-by-step instructions for your tool' },
    ];

    stages.forEach(function (s) {
        var row = el('div', { className: 'stage-row stage-pending', id: 'stage-' + s.key });
        var icon = el('div', { className: 'stage-icon', id: 'icon-' + s.key });
        row.appendChild(icon);

        var content = el('div', { className: 'stage-content' });
        var header = el('div', { className: 'stage-header' });
        header.appendChild(el('span', { className: 'stage-label', textContent: s.label }));
        header.appendChild(el('span', { className: 'stage-timer', id: 'timer-' + s.key }));
        header.appendChild(el('span', { className: 'stage-badge', id: 'badge-' + s.key, textContent: 'Waiting' }));
        content.appendChild(header);
        content.appendChild(el('div', { className: 'stage-detail', id: 'detail-' + s.key, textContent: s.desc }));
        var barWrap = el('div', { className: 'stage-bar-wrap' });
        barWrap.appendChild(el('div', { className: 'stage-bar', id: 'bar-' + s.key }));
        content.appendChild(barWrap);

        row.appendChild(content);
        stagesDiv.appendChild(row);
    });
}

function hideModelProgress() {
    var area = $('model-progress');
    if (area) area.classList.add('hidden');
}

async function cancelModelJob() {
    if (!currentJobId) return;
    try {
        await fetch('/model/cancel/' + currentJobId, { method: 'POST' });
    } catch (e) { /* ignore */ }
    if (eventSource) { eventSource.close(); eventSource = null; }
    _stopAllTimers();
    hideModelProgress();
    showToast('Cancellation requested', 'info');
}

// --- Model Tree Rendering ---
function renderModelTree(layers) {
    var container = $('tab-tree');
    if (!container) return;
    clearChildren(container);

    if (!layers || Object.keys(layers).length === 0) {
        container.appendChild(el('div', {
            className: 'empty-state',
            textContent: 'Decompose requirements first, or upload pre-decomposed requirements (XLSX/CSV) directly',
        }));
        return;
    }

    var cfg = window.SHIPYARD_CONFIG || {};
    var layerNames = selectedToolMode === 'capella' ? (cfg.capellaLayers || {}) : (cfg.rhapsodyDiagrams || {});

    Object.keys(layers).forEach(function (layerKey) {
        var layerData = layers[layerKey];
        var displayName = layerNames[layerKey] || layerKey;

        var totalCount = 0;
        if (layerData && typeof layerData === 'object') {
            Object.values(layerData).forEach(function (coll) {
                if (Array.isArray(coll)) totalCount += coll.length;
            });
        }

        var section = el('div', { className: 'layer-section', id: 'layer-section-' + layerKey });
        var header = el('div', { className: 'layer-header' });
        var arrow = el('span', { className: 'layer-arrow open', textContent: '\u25be' });
        var title = el('span', { className: 'layer-title', textContent: displayName });
        var countBadge = el('span', { className: 'layer-count', textContent: totalCount + ' elements' });
        var regenBtn = el('button', { className: 'btn-regen', title: 'Regenerate this layer', textContent: '\u2726 Regen' });
        regenBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            regenLayer(layerKey);
        });

        header.appendChild(arrow);
        header.appendChild(title);
        header.appendChild(countBadge);
        header.appendChild(regenBtn);

        var body = el('div', { className: 'layer-body', id: 'layer-body-' + layerKey });

        header.addEventListener('click', function () {
            var isOpen = body.style.display !== 'none';
            body.style.display = isOpen ? 'none' : '';
            arrow.textContent = isOpen ? '\u25b8' : '\u25be';
            arrow.classList.toggle('open', !isOpen);
        });

        section.appendChild(header);
        section.appendChild(body);

        if (layerData && typeof layerData === 'object') {
            Object.keys(layerData).forEach(function (collKey) {
                var collection = layerData[collKey];
                if (!Array.isArray(collection)) return;
                body.appendChild(renderCollection(layerKey, collKey, collection));
            });
        }

        container.appendChild(section);
    });
}

function renderCollection(layerKey, collKey, elements) {
    var collLabel = collKey.charAt(0).toUpperCase() + collKey.slice(1).replace(/_/g, ' ');
    var section = el('div', { className: 'collection-section', id: 'coll-' + layerKey + '-' + collKey });

    var header = el('div', { className: 'collection-header' });
    var arrow = el('span', { className: 'collection-arrow', textContent: '\u25be' });
    header.appendChild(arrow);
    header.appendChild(el('span', { className: 'collection-name', textContent: collLabel }));
    header.appendChild(el('span', { className: 'collection-count', textContent: '(' + elements.length + ')' }));

    var listDiv = el('div', { className: 'element-list', id: 'list-' + layerKey + '-' + collKey });
    elements.forEach(function (elem) {
        listDiv.appendChild(renderElementRow(layerKey, collKey, elem));
    });

    var addBtn = el('button', { className: 'btn-add-element', textContent: '+ Add' });
    addBtn.addEventListener('click', function () {
        showAddElementForm(layerKey, collKey, listDiv, addBtn);
    });

    header.addEventListener('click', function () {
        var isOpen = listDiv.style.display !== 'none';
        listDiv.style.display = isOpen ? 'none' : '';
        addBtn.style.display = isOpen ? 'none' : '';
        arrow.textContent = isOpen ? '\u25b8' : '\u25be';
    });

    section.appendChild(header);
    section.appendChild(listDiv);
    section.appendChild(addBtn);
    return section;
}

function renderElementRow(layerKey, collKey, elem) {
    var row = el('div', { className: 'element-row', id: 'elem-row-' + (elem.id || '') });

    row.appendChild(el('span', { className: 'element-id', textContent: elem.id || '?' }));
    row.appendChild(el('span', { className: 'element-name', textContent: elem.name || elem.id || '(unnamed)' }));
    if (elem.type) {
        row.appendChild(el('span', { className: 'element-type', textContent: elem.type }));
    }

    var actions = el('div', { className: 'element-actions' });

    var editBtn = el('button', { className: 'btn-icon-small', title: 'Edit', textContent: '\u270e' });
    editBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        startInlineEdit(row, layerKey, collKey, elem);
    });

    var deleteBtn = el('button', { className: 'btn-icon-small btn-delete', title: 'Delete', textContent: '\u2715' });
    deleteBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        deleteElement(elem.id, layerKey, collKey);
    });

    actions.appendChild(editBtn);
    actions.appendChild(deleteBtn);
    row.appendChild(actions);

    // Click to expand details
    row.addEventListener('click', function (e) {
        if (e.target.closest('.element-actions') || e.target.closest('button')) return;
        toggleElementDetails(row, elem);
    });

    return row;
}

function toggleElementDetails(row, elem) {
    var existing = row.nextElementSibling;
    if (existing && existing.classList.contains('element-details')) {
        existing.remove();
        return;
    }

    var details = el('div', { className: 'element-details' });
    var skipKeys = { id: 1, name: 1, type: 1 };

    Object.keys(elem).forEach(function (key) {
        if (skipKeys[key]) return;
        var val = elem[key];
        if (val === null || val === undefined || val === '') return;

        var field = el('div', { className: 'detail-field' });
        var keyEl = el('span', { className: 'detail-key', textContent: key.replace(/_/g, ' ') });
        var valEl = el('span', { className: 'detail-value' });

        if (Array.isArray(val)) {
            if (val.length === 0) return;
            if (typeof val[0] === 'object') {
                val.forEach(function (item, i) {
                    var line = Object.entries(item).map(function (kv) { return kv[0] + ': ' + kv[1]; }).join(', ');
                    valEl.appendChild(el('div', { textContent: (i + 1) + '. ' + line, style: 'padding:1px 0; color:#999;' }));
                });
            } else {
                valEl.textContent = val.join(', ');
            }
        } else if (typeof val === 'object') {
            valEl.textContent = JSON.stringify(val);
        } else {
            valEl.textContent = String(val);
        }

        field.appendChild(keyEl);
        field.appendChild(valEl);
        details.appendChild(field);
    });

    if (details.children.length === 0) {
        var empty = el('div', { className: 'detail-field' });
        empty.appendChild(el('span', { className: 'detail-value', textContent: 'No additional properties' }));
        details.appendChild(empty);
    }

    // Traceability links
    var relatedLinks = (currentModel && currentModel.links || []).filter(function (link) {
        return link.source === elem.id || link.target === elem.id;
    });
    if (relatedLinks.length > 0) {
        details.appendChild(el('div', { className: 'detail-trace-header', textContent: 'Traceability' }));
        relatedLinks.forEach(function (link) {
            var traceRow = el('div', { className: 'detail-trace-row' });
            if (link.source === elem.id) {
                traceRow.textContent = '\u2192 ' + link.type + ' \u2192 ' + link.target;
            } else {
                traceRow.textContent = '\u2190 ' + link.type + ' \u2190 ' + link.source;
            }
            addReqTooltip(traceRow, link.source === elem.id ? link.target : link.source);
            details.appendChild(traceRow);
        });
    }

    row.parentNode.insertBefore(details, row.nextSibling);
}

function addReqTooltip(element, reqId) {
    if (!currentModel || !currentModel.requirements) return;
    var req = currentModel.requirements.find(function (r) { return r.id === reqId; });
    if (req) {
        element.title = req.id + ': ' + req.text;
        element.classList.add('has-tooltip');
    }
}

// --- Inline editing ---
function startInlineEdit(row, layerKey, collKey, elem) {
    if (row.querySelector('.edit-input')) return;
    var nameSpan = row.querySelector('.element-name');
    if (!nameSpan) return;

    var originalName = nameSpan.textContent;
    nameSpan.style.display = 'none';

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'edit-input';
    input.value = originalName;

    var saveBtn = el('button', { className: 'btn-save-edit', textContent: '\u2713' });
    var cancelBtn = el('button', { className: 'btn-cancel-edit', textContent: '\u2715' });

    saveBtn.addEventListener('click', function () {
        saveInlineEdit(row, layerKey, collKey, elem, input.value, nameSpan);
    });
    cancelBtn.addEventListener('click', function () {
        input.remove(); saveBtn.remove(); cancelBtn.remove();
        nameSpan.style.display = '';
    });
    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') saveBtn.click();
        if (e.key === 'Escape') cancelBtn.click();
    });

    row.insertBefore(input, nameSpan.nextSibling);
    row.insertBefore(saveBtn, input.nextSibling);
    row.insertBefore(cancelBtn, saveBtn.nextSibling);
    input.focus();
    input.select();
}

async function saveInlineEdit(row, layerKey, collKey, elem, newName, nameSpan) {
    try {
        var res = await fetch('/model/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: 'Rename element ' + elem.id + ' to "' + newName + '"',
                mode: 'model',
            }),
        });
        var data = await res.json();

        if (currentModel && currentModel.layers && currentModel.layers[layerKey] && currentModel.layers[layerKey][collKey]) {
            var coll = currentModel.layers[layerKey][collKey];
            for (var i = 0; i < coll.length; i++) {
                if (coll[i].id === elem.id) { coll[i].name = newName; break; }
            }
        }

        nameSpan.textContent = newName;
        nameSpan.style.display = '';
        var input = row.querySelector('.edit-input');
        var saveB = row.querySelector('.btn-save-edit');
        var cancelB = row.querySelector('.btn-cancel-edit');
        if (input) input.remove();
        if (saveB) saveB.remove();
        if (cancelB) cancelB.remove();
        showToast('Element updated', 'success');
    } catch (e) {
        showToast('Edit failed: ' + e.message, 'error');
    }
}

async function deleteElement(elementId, layerKey, collKey) {
    if (!elementId) return;
    if (!confirm('Delete element ' + elementId + '?')) return;

    try {
        var res = await fetch('/model/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: 'Remove element ' + elementId,
                mode: 'model',
            }),
        });
        if (res.ok) {
            if (currentModel && currentModel.layers && currentModel.layers[layerKey] && currentModel.layers[layerKey][collKey]) {
                currentModel.layers[layerKey][collKey] = currentModel.layers[layerKey][collKey].filter(
                    function (e) { return e.id !== elementId; }
                );
            }
            renderModelTree(currentModel ? currentModel.layers : null);
            showToast('Element deleted', 'success');
        }
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

function showAddElementForm(layerKey, collKey, listDiv, addBtn) {
    var existing = listDiv.parentNode.querySelector('.add-element-form');
    if (existing) { existing.remove(); return; }

    var form = el('div', { className: 'add-element-form' });

    var idInput = document.createElement('input');
    idInput.type = 'text'; idInput.className = 'edit-input'; idInput.placeholder = 'ID (e.g. OE-99)';

    var nameInput = document.createElement('input');
    nameInput.type = 'text'; nameInput.className = 'edit-input'; nameInput.placeholder = 'Name';

    var typeInput = document.createElement('input');
    typeInput.type = 'text'; typeInput.className = 'edit-input'; typeInput.placeholder = 'Type (optional)';

    var saveBtn = el('button', { className: 'btn-save-edit', textContent: '\u2713 Add' });
    var cancelBtn = el('button', { className: 'btn-cancel-edit', textContent: '\u2715 Cancel' });

    saveBtn.addEventListener('click', async function () {
        var newId = idInput.value.trim();
        var newName = nameInput.value.trim();
        var newType = typeInput.value.trim();
        if (!newId || !newName) { showToast('ID and Name are required', 'error'); return; }

        var newElem = { id: newId, name: newName };
        if (newType) newElem.type = newType;

        await addElement(layerKey, collKey, newElem);
        form.remove();
    });
    cancelBtn.addEventListener('click', function () { form.remove(); });

    form.appendChild(idInput);
    form.appendChild(nameInput);
    form.appendChild(typeInput);
    form.appendChild(saveBtn);
    form.appendChild(cancelBtn);

    addBtn.parentNode.insertBefore(form, addBtn);
    idInput.focus();
}

async function addElement(layerKey, collKey, newElem) {
    try {
        var res = await fetch('/model/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: 'Add element ' + newElem.id + ' "' + newElem.name + '" to ' + layerKey + '/' + collKey,
                mode: 'model',
            }),
        });
        if (res.ok) {
            if (currentModel && currentModel.layers && currentModel.layers[layerKey]) {
                if (!currentModel.layers[layerKey][collKey]) currentModel.layers[layerKey][collKey] = [];
                currentModel.layers[layerKey][collKey].push(newElem);
            }
            renderModelTree(currentModel ? currentModel.layers : null);
            showToast('Element added', 'success');
        }
    } catch (e) {
        showToast('Add failed: ' + e.message, 'error');
    }
}

async function regenLayer(layerKey) {
    showToast('Regenerating layer ' + layerKey + '...', 'info');
    try {
        var res = await fetch('/model/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: 'Regenerate the ' + layerKey + ' layer completely',
                mode: 'model',
            }),
        });
        if (res.ok) {
            var data = await res.json();
            if (data.model) {
                currentModel = data.model;
                renderModelTree(currentModel.layers);
                renderCoverage(currentModel.requirements, currentModel.links);
            }
            showToast('Layer regenerated', 'success');
        }
    } catch (e) {
        showToast('Regen failed: ' + e.message, 'error');
    }
}

// --- Links tab ---
function renderLinksTab() {
    var tbody = $('links-tbody');
    if (!tbody) return;
    clearChildren(tbody);

    if (!currentModel || !currentModel.links || currentModel.links.length === 0) {
        var row = document.createElement('tr');
        var td = document.createElement('td');
        td.colSpan = 3; td.textContent = 'No links in this model.';
        td.style.textAlign = 'center'; td.style.color = '#666';
        row.appendChild(td);
        tbody.appendChild(row);
        return;
    }

    currentModel.links.forEach(function (link) {
        var row = document.createElement('tr');
        var sourceTd = el('td', { textContent: link.source });
        addReqTooltip(sourceTd, link.source);
        row.appendChild(sourceTd);
        row.appendChild(el('td', { className: 'link-type', textContent: link.type }));
        var targetTd = el('td', { textContent: link.target });
        addReqTooltip(targetTd, link.target);
        row.appendChild(targetTd);
        tbody.appendChild(row);
    });
}

// --- Instructions tab ---
function renderInstructionsTab() {
    var list = $('instructions-list');
    if (!list) return;
    clearChildren(list);

    if (!currentModel || !currentModel.instructions) {
        list.appendChild(el('div', { className: 'empty-state', textContent: 'No instructions available.' }));
        return;
    }

    var steps = currentModel.instructions.steps || [];
    var toolName = currentModel.instructions.tool || '';

    if (steps.length === 0) {
        list.appendChild(el('div', { className: 'empty-state', textContent: 'No steps generated.' }));
        return;
    }

    // Header
    var header = el('div', { className: 'instructions-header' });
    if (toolName) header.appendChild(el('span', { className: 'instructions-tool', textContent: toolName }));
    header.appendChild(el('span', { className: 'instructions-count', textContent: steps.length + ' steps' }));
    var copyAllBtn = el('button', { className: 'btn-copy-all', textContent: 'Copy All' });
    copyAllBtn.addEventListener('click', function () {
        var allText = steps.map(function (s) {
            return 'Step ' + (s.step || '') + ': ' + (s.action || '') + '\n' + (s.detail || '');
        }).join('\n\n');
        copyToClipboard(allText);
    });
    header.appendChild(copyAllBtn);
    list.appendChild(header);

    // Group by layer
    var layerGroups = {};
    var layerOrder = [];
    steps.forEach(function (step) {
        var layer = step.layer || 'general';
        if (!layerGroups[layer]) { layerGroups[layer] = []; layerOrder.push(layer); }
        layerGroups[layer].push(step);
    });

    layerOrder.forEach(function (layer) {
        var layerDisplay = layer.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
        var section = el('div', { className: 'instructions-layer-section' });
        var layerHeader = el('div', { className: 'instructions-layer-header' });
        layerHeader.appendChild(el('span', { className: 'instructions-layer-name', textContent: layerDisplay }));
        layerHeader.appendChild(el('span', { className: 'instructions-layer-count', textContent: layerGroups[layer].length + ' steps' }));
        section.appendChild(layerHeader);

        layerGroups[layer].forEach(function (step) {
            var card = el('div', { className: 'instruction-card' });
            var cardHeader = el('div', { className: 'instruction-card-header' });
            cardHeader.appendChild(el('span', { className: 'instruction-step-num', textContent: step.step || '?' }));
            cardHeader.appendChild(el('span', { className: 'instruction-action', textContent: step.action || '' }));
            var copyBtn = el('button', { className: 'instruction-copy', title: 'Copy step', textContent: '\u2398' });
            copyBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                copyToClipboard((step.action || '') + ': ' + (step.detail || ''));
            });
            cardHeader.appendChild(copyBtn);
            card.appendChild(cardHeader);
            if (step.detail) card.appendChild(el('div', { className: 'instruction-detail', textContent: step.detail }));
            section.appendChild(card);
        });

        list.appendChild(section);
    });
}

// --- JSON tab ---
function renderJsonTab() {
    var pre = $('json-output');
    if (!pre) return;
    pre.textContent = currentModel ? JSON.stringify(currentModel, null, 2) : 'No model loaded.';
}

// --- Batches tab ---
function renderBatchesTab() {
    var container = $('batch-list');
    if (!container) return;
    clearChildren(container);

    if (!currentModel || !currentModel.batches || currentModel.batches.length === 0) {
        container.appendChild(el('div', { className: 'empty-state', textContent: 'No batches yet.' }));
        return;
    }

    var reqLookup = {};
    if (currentModel.requirements) {
        currentModel.requirements.forEach(function (r) { reqLookup[r.id] = r; });
    }

    var batches = currentModel.batches.slice().reverse();
    batches.forEach(function (batch) {
        var card = el('div', { className: 'batch-card' });

        var header = el('div', { className: 'batch-card-header' });
        var headerLeft = el('div', { className: 'batch-header-left' });
        headerLeft.appendChild(el('span', { className: 'batch-id', textContent: batch.id }));
        var ts = new Date(batch.timestamp);
        headerLeft.appendChild(el('span', { className: 'batch-time', textContent: ts.toLocaleString() }));
        header.appendChild(headerLeft);
        var expandArrow = el('span', { className: 'batch-expand-arrow', textContent: '\u25b8' });
        header.appendChild(expandArrow);
        card.appendChild(header);

        var meta = el('div', { className: 'batch-card-meta' });
        meta.appendChild(el('span', { className: 'batch-source', textContent: batch.source_file || '' }));
        meta.appendChild(el('span', { className: 'batch-reqs', textContent: (batch.requirement_ids || []).length + ' requirements' }));
        card.appendChild(meta);

        var stats = el('div', { className: 'batch-card-stats' });
        stats.appendChild(el('span', { className: 'batch-layers', textContent: (batch.layers_generated || []).join(', ') }));
        stats.appendChild(el('span', { className: 'batch-model', textContent: batch.model || '' }));
        stats.appendChild(el('span', { className: 'batch-cost', textContent: formatCost(batch.cost || 0) }));
        card.appendChild(stats);

        var detailDiv = el('div', { className: 'batch-detail', style: 'display:none' });
        detailDiv.appendChild(el('div', { className: 'batch-detail-header', textContent: 'Requirements in this batch' }));
        if (batch.requirement_ids && batch.requirement_ids.length > 0) {
            batch.requirement_ids.forEach(function (reqId) {
                var row = el('div', { className: 'batch-req-row' });
                row.appendChild(el('span', { className: 'batch-req-id', textContent: reqId }));
                var req = reqLookup[reqId];
                var text = req ? req.text : '(not available)';
                var textSpan = el('span', { className: 'batch-req-text', textContent: text });
                textSpan.title = text;
                row.appendChild(textSpan);
                detailDiv.appendChild(row);
            });
        }
        card.appendChild(detailDiv);

        header.style.cursor = 'pointer';
        header.addEventListener('click', function () {
            var showing = detailDiv.style.display !== 'none';
            detailDiv.style.display = showing ? 'none' : '';
            expandArrow.textContent = showing ? '\u25b8' : '\u25be';
        });

        container.appendChild(card);
    });
}

// --- Coverage ---
function renderCoverage(reqs, links) {
    var bar = $('coverage-bar');
    if (!bar) return;

    if (!reqs || !links || reqs.length === 0) {
        bar.classList.add('hidden');
        return;
    }

    var totalReqs = reqs.length;
    var linkedReqIds = new Set();
    links.forEach(function (link) {
        reqs.forEach(function (req) {
            if (link.target === req.id || link.source === req.id) linkedReqIds.add(req.id);
        });
    });
    var covered = linkedReqIds.size;
    var pct = Math.round((covered / totalReqs) * 100);

    bar.classList.remove('hidden');
    var countEl = $('coverage-count');
    if (countEl) countEl.textContent = covered + '/' + totalReqs + ' (' + pct + '%)';
    var fill = $('coverage-fill');
    if (fill) fill.style.width = pct + '%';
    var badge = $('uncovered-badge');
    if (badge) badge.textContent = (totalReqs - covered) + ' uncovered';
}

// --- Model search ---
function filterModelTree(query) {
    if (!query) {
        document.querySelectorAll('.element-row, .collection-section, .layer-section').forEach(function (el) {
            el.style.display = '';
        });
        return;
    }
    document.querySelectorAll('.element-row').forEach(function (row) {
        var id = (row.querySelector('.element-id') || {}).textContent || '';
        var name = (row.querySelector('.element-name') || {}).textContent || '';
        row.style.display = (id.toLowerCase().includes(query) || name.toLowerCase().includes(query)) ? '' : 'none';
    });
    document.querySelectorAll('.collection-section').forEach(function (section) {
        var visible = section.querySelectorAll('.element-row:not([style*="display: none"])');
        section.style.display = visible.length > 0 ? '' : 'none';
    });
    document.querySelectorAll('.layer-section').forEach(function (section) {
        var visible = section.querySelectorAll('.collection-section:not([style*="display: none"])');
        section.style.display = visible.length > 0 ? '' : 'none';
    });
}

// =============================================================================
// 8. SSE STREAMING (shared)
// =============================================================================

function startSSEStream(jobId, type) {
    var url = type === 'decompose' ? '/decompose/stream/' + jobId : '/model/stream/' + jobId;
    if (eventSource) { eventSource.close(); eventSource = null; }
    eventSource = new EventSource(url);

    eventSource.onmessage = function (e) {
        try {
            var event = JSON.parse(e.data);
            handleStreamEvent(event, type);
        } catch (err) {
            console.error('SSE parse error', err);
        }
    };

    eventSource.onerror = function () {
        eventSource.close();
        eventSource = null;
    };
}

function handleStreamEvent(event, type) {
    if (type === 'decompose') {
        handleDecompStreamEvent(event);
    } else {
        handleModelStreamEvent(event);
    }
}

function handleDecompStreamEvent(event) {
    var label = $('decomp-progress-label');
    var detail = $('decomp-progress-detail');
    var cost = $('decomp-progress-cost');
    var bar = $('decomp-progress-bar');

    switch (event.type) {
        case 'started':
            if (label) label.textContent = 'Processing ' + (event.total_digs || 0) + ' DIG(s)...';
            break;
        case 'dig_started':
            if (label) label.textContent = 'DIG ' + event.dig_id + ' [' + event.index + '/' + event.total + ']';
            if (detail) detail.textContent = event.dig_text || '';
            if (bar) bar.style.width = ((event.index - 1) / event.total * 100) + '%';
            break;
        case 'phase':
            if (detail) detail.textContent = (event.phase || '') + ' \u2014 ' + (event.detail || '');
            break;
        case 'cost':
            if (cost) cost.textContent = formatCost(event.total_cost || 0);
            break;
        case 'dig_complete':
            if (detail) detail.textContent = 'DIG ' + event.dig_id + ': ' + (event.nodes || 0) + ' nodes, ' + (event.levels || 0) + ' levels';
            break;
        case 'complete':
            if (label) label.textContent = 'Complete \u2014 ' + (event.total_digs || 0) + ' DIGs, ' + (event.total_nodes || 0) + ' requirements';
            if (cost) cost.textContent = formatCost(event.total_cost || 0);
            if (bar) bar.style.width = '100%';
            if (eventSource) { eventSource.close(); eventSource = null; }
            setTimeout(function () {
                hideDecompProgress();
                loadDecompResults();
            }, 1500);
            break;
        case 'error':
            var msg = event.dig_id ? 'DIG ' + event.dig_id + ': ' + event.message : (event.message || 'Unknown error');
            showError(msg);
            if (detail) detail.textContent = 'Error: ' + msg;
            break;
        case 'warning':
            showToast(event.message || 'Warning', 'info');
            break;
        case 'cancelled':
            if (label) label.textContent = 'Cancelled';
            if (eventSource) { eventSource.close(); eventSource = null; }
            setTimeout(hideDecompProgress, 1000);
            break;
    }
}

function handleModelStreamEvent(event) {
    var stage = event.stage;
    var status = event.status;
    var detailText = event.detail || '';
    var costText = event.cost || '';

    if (costText) {
        var costEl = $('model-running-cost');
        if (costEl) costEl.textContent = costText;
    }

    if (stage === 'done') {
        if (eventSource) { eventSource.close(); eventSource = null; }
        _stopAllTimers();
        hideModelProgress();
        loadModelData();
        showToast('Model generated successfully!', 'success');
        return;
    }

    if (stage === 'cancelled') {
        if (eventSource) { eventSource.close(); eventSource = null; }
        _stopAllTimers();
        hideModelProgress();
        showToast('Job cancelled', 'info');
        return;
    }

    if (stage === 'error') {
        if (eventSource) { eventSource.close(); eventSource = null; }
        _stopAllTimers();
        hideModelProgress();
        showError(detailText || 'Pipeline failed');
        return;
    }

    // Check for clarification
    if (stage === 'analyze' && status === 'complete' && event.data) {
        var flagged = (event.data.flagged) || [];
        if (flagged.length > 0) showClarificationModal(flagged);
    }

    var stageRow = $('stage-' + stage);
    var barEl = $('bar-' + stage);
    var detailEl = $('detail-' + stage);
    var badge = $('badge-' + stage);
    var timer = $('timer-' + stage);

    if (!stageRow) return;

    if (status === 'running') {
        stageRow.className = 'stage-row stage-running';
        if (badge) badge.textContent = 'Running';
        if (detailEl) detailEl.textContent = detailText;
        if (!_stageTimers[stage]) {
            _stageTimers[stage] = Date.now();
            _startElapsedUpdater();
        }
    } else if (status === 'complete') {
        stageRow.className = 'stage-row stage-complete';
        if (badge) badge.textContent = 'Done';
        if (detailEl) detailEl.textContent = detailText;
        if (_stageTimers[stage] && timer) {
            var elapsed = Math.round((Date.now() - _stageTimers[stage]) / 1000);
            timer.textContent = _formatElapsed(elapsed);
            timer.classList.add('timer-done');
        }
        delete _stageTimers[stage];
    } else if (status === 'layer_complete') {
        if (detailEl) detailEl.textContent = detailText;
    }
}

function _formatElapsed(seconds) {
    if (seconds < 60) return seconds + 's';
    var m = Math.floor(seconds / 60);
    var s = seconds % 60;
    return m + 'm ' + (s < 10 ? '0' : '') + s + 's';
}

function _startElapsedUpdater() {
    if (_elapsedInterval) return;
    _elapsedInterval = setInterval(function () {
        var anyRunning = false;
        Object.keys(_stageTimers).forEach(function (stage) {
            var timer = $('timer-' + stage);
            if (timer) {
                var elapsed = Math.round((Date.now() - _stageTimers[stage]) / 1000);
                timer.textContent = _formatElapsed(elapsed);
                anyRunning = true;
            }
        });
        if (!anyRunning) { clearInterval(_elapsedInterval); _elapsedInterval = null; }
    }, 1000);
}

function _stopAllTimers() {
    _stageTimers = {};
    if (_elapsedInterval) { clearInterval(_elapsedInterval); _elapsedInterval = null; }
}

// =============================================================================
// 9. AGENT PANEL
// =============================================================================

function toggleAgent() {
    agentOpen = !agentOpen;
    var panel = $('agent-panel');
    var toggle = $('agent-toggle');

    if (panel) panel.classList.toggle('hidden', !agentOpen);
    if (toggle) toggle.classList.toggle('active', agentOpen);

    // Resize main content
    document.body.classList.toggle('agent-open', agentOpen);
}

async function sendAgentMessage() {
    var input = $('agent-input');
    if (!input) return;
    var message = input.value.trim();
    if (!message) return;
    input.value = '';
    appendChatMessage('user', message);

    var sendBtn = document.querySelector('.btn-send');
    if (sendBtn) sendBtn.disabled = true;

    var loadingEl = appendChatMessage('agent', '\u2026', true);

    try {
        var res = await fetch('/model/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, mode: currentMode }),
        });

        if (!res.ok) {
            var err = await res.json();
            loadingEl.remove();
            appendChatMessage('agent', 'Error: ' + (err.detail || 'unknown error'));
        } else {
            var data = await res.json();
            loadingEl.remove();
            appendChatMessage('agent', data.response || '(no response)');

            if (data.model) {
                currentModel = data.model;
                renderModelTree(currentModel.layers);
                renderCoverage(currentModel.requirements, currentModel.links);
                var activeTab = document.querySelector('.tab-btn.active');
                if (activeTab) {
                    var tabName = activeTab.getAttribute('data-tab');
                    if (tabName === 'links') renderLinksTab();
                    if (tabName === 'instructions') renderInstructionsTab();
                    if (tabName === 'json') renderJsonTab();
                }
            }
        }
    } catch (e) {
        loadingEl.remove();
        appendChatMessage('agent', 'Error: ' + e.message);
    }

    if (sendBtn) sendBtn.disabled = false;
    input.focus();
}

function appendChatMessage(role, text, isLoading) {
    var history = $('chat-history');
    if (!history) return document.createElement('div');

    // Remove welcome message on first real message
    var welcome = history.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    var wrapper = el('div', {
        className: 'chat-message chat-' + role + (isLoading ? ' chat-loading' : ''),
    });

    var label = el('div', { className: 'chat-msg-label', textContent: role === 'user' ? 'You' : 'Agent' });
    wrapper.appendChild(label);

    var body = el('div', { className: 'chat-msg-body' });
    if (role === 'agent' && !isLoading) {
        // Render markdown safely: escape HTML first, then apply formatting
        body.appendChild(renderMarkdownSafe(text));
    } else {
        body.textContent = text;
    }
    wrapper.appendChild(body);

    history.appendChild(wrapper);
    history.scrollTop = history.scrollHeight;
    return wrapper;
}

/**
 * Render markdown text into DOM nodes without using innerHTML.
 * Handles: paragraphs, bold, italic, inline code, code blocks, and lists.
 */
function renderMarkdownSafe(text) {
    var container = document.createDocumentFragment();

    // Split into paragraphs on double-newline
    var paragraphs = text.split(/\n\n+/);
    paragraphs.forEach(function (para) {
        para = para.trim();
        if (!para) return;

        // Check for code block
        if (para.startsWith('```')) {
            var codeContent = para.replace(/^```\w*\n?/, '').replace(/```$/, '');
            var pre = document.createElement('pre');
            var code = document.createElement('code');
            code.textContent = codeContent;
            pre.appendChild(code);
            container.appendChild(pre);
            return;
        }

        // Check if it's a list (lines starting with - or *)
        var lines = para.split('\n');
        var allList = lines.every(function (l) { return /^[-*] /.test(l.trim()); });
        if (allList && lines.length > 0) {
            var ul = document.createElement('ul');
            lines.forEach(function (line) {
                var li = document.createElement('li');
                li.textContent = line.replace(/^[-*] /, '');
                ul.appendChild(li);
            });
            container.appendChild(ul);
            return;
        }

        // Regular paragraph
        var p = document.createElement('p');
        // Simple inline formatting via textContent (safe)
        // For bold/italic/code, we use textContent which is safe from XSS
        p.textContent = para.replace(/\n/g, ' ');
        container.appendChild(p);
    });

    return container;
}

// Legacy renderMarkdown kept for reference but not used for innerHTML
function renderMarkdown(text) {
    // Not used - see renderMarkdownSafe
    return text;
}

function renderSuggestedPrompts(mode) {
    var container = $('suggested-prompts');
    if (!container) return;

    // Keep the label, remove old prompt buttons
    var label = container.querySelector('.label');
    clearChildren(container);
    if (label) container.appendChild(label);

    var prompts = mode === 'decompose' ? [
        'Re-run DIG 9694 with depth 4',
        'Show all validation warnings',
        'Which DIGs haven\'t been decomposed?',
        'Send DIG 9694 to modeling',
        'Why was DIG 9584 only 1 level deep?',
        'Edit requirement 9584-3 to use GTR allocation',
    ] : [
        'Show traceability from DIG 9584 to physical components',
        'Which requirements don\'t have traceability links yet?',
        'Add a logical component for ice detection sensors',
        'What\'s the coverage for the propulsion requirements?',
        'Re-decompose requirement 9584-3 with more detail',
        'Regenerate the Operational Analysis layer',
        'Compare the decomposition of DIG 9584 vs DIG 9646',
    ];

    prompts.forEach(function (p) {
        var btn = el('button', { className: 'suggested-prompt', textContent: '"' + p + '"' });
        btn.addEventListener('click', function () {
            var input = $('agent-input');
            if (input) { input.value = p; input.focus(); }
        });
        container.appendChild(btn);
    });
}

async function clearChatHistory() {
    if (!confirm('Clear all chat history?')) return;
    try {
        await fetch('/model/chat/clear', { method: 'POST' });
    } catch (e) { /* ignore */ }

    var history = $('chat-history');
    if (history) {
        clearChildren(history);
        var welcome = el('div', { className: 'chat-welcome' });
        welcome.appendChild(el('div', { className: 'chat-welcome-icon', textContent: '\u2672' }));
        welcome.appendChild(el('div', { className: 'chat-welcome-title', textContent: 'Shipyard Agent' }));
        welcome.appendChild(el('div', { className: 'chat-welcome-text', textContent: 'Ask me about your project. I can modify the model, analyze requirements, add or remove elements, create links, and more.' }));
        history.appendChild(welcome);
    }
    showToast('Chat history cleared', 'info');
}

// =============================================================================
// 10. TAB SWITCHING (Model mode)
// =============================================================================

function initTabSwitching() {
    // Tabs are wired via onclick in HTML; just ensure initial state
    switchTab('tree');
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-tab') === tabName);
    });
    document.querySelectorAll('.tab-pane').forEach(function (pane) {
        pane.style.display = 'none';
        pane.classList.remove('active');
    });
    var activePane = $('tab-' + tabName);
    if (activePane) {
        activePane.style.display = '';
        activePane.classList.add('active');
    }

    // Lazy-render tab content
    if (tabName === 'links') renderLinksTab();
    if (tabName === 'instructions') renderInstructionsTab();
    if (tabName === 'json') renderJsonTab();
    if (tabName === 'batches') renderBatchesTab();
}

// =============================================================================
// 11. SETTINGS
// =============================================================================

async function openSettings() {
    var modal = $('settings-modal');
    if (!modal) return;

    var cfg = window.SHIPYARD_CONFIG || {};
    var settings = cfg.settings || {};

    // Populate fields
    var anthKey = $('settings-anthropic-key');
    var orKey = $('settings-openrouter-key');
    var localUrl = $('settings-local-url');
    if (anthKey) anthKey.value = '';
    if (orKey) orKey.value = '';
    if (localUrl) localUrl.value = settings.local_url || '';

    var anthStatus = $('anthropic-key-status');
    var orStatus = $('openrouter-key-status');
    if (anthStatus) {
        anthStatus.textContent = settings.has_anthropic_key ? 'Key configured' : 'No key set';
        anthStatus.style.color = settings.has_anthropic_key ? '#5a5' : '#c88';
    }
    if (orStatus) {
        orStatus.textContent = settings.has_openrouter_key ? 'Key configured' : 'No key set';
        orStatus.style.color = settings.has_openrouter_key ? '#5a5' : '#888';
    }

    // Populate model selects
    var catalogue = cfg.modelCatalogue || [];
    populateModelSelect('settings-decompose-model', catalogue, settings.decompose_model || settings.model);
    populateModelSelect('settings-mbse-model', catalogue, settings.mbse_model || settings.model);

    // Auto-send checkbox
    var autoSend = $('settings-auto-send');
    if (autoSend) autoSend.checked = settings.auto_send !== false;

    // Mode buttons
    document.querySelectorAll('.modal-settings .segment[data-value]').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-value') === (settings.default_mode || 'capella'));
    });

    // Load cost history
    loadCostHistory();

    modal.classList.remove('hidden');
}

function populateModelSelect(selectId, catalogue, currentValue) {
    var select = $(selectId);
    if (!select) return;
    clearChildren(select);
    catalogue.forEach(function (m) {
        var opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = m.name || m.id;
        select.appendChild(opt);
    });
    if (currentValue) select.value = currentValue;
}

function closeSettings() {
    $('settings-modal').classList.add('hidden');
}

function setSettingsProvider(provider) {
    var btn = event.target;
    var group = btn.closest('.form-group');
    if (!group) return;
    group.querySelectorAll('.segment').forEach(function (b) {
        b.classList.toggle('active', b.getAttribute('data-value') === provider);
    });
}

function setSettingsMode(mode) {
    var btn = event.target;
    var group = btn.closest('.form-group');
    if (!group) return;
    group.querySelectorAll('.segment').forEach(function (b) {
        b.classList.toggle('active', b.getAttribute('data-value') === mode);
    });
}

async function saveSettings() {
    var body = {};

    var anthKey = $('settings-anthropic-key');
    var orKey = $('settings-openrouter-key');
    var localUrl = $('settings-local-url');
    var decompModel = $('settings-decompose-model');
    var mbseModel = $('settings-mbse-model');
    var autoSend = $('settings-auto-send');

    if (anthKey && anthKey.value.trim()) body.anthropic_key = anthKey.value.trim();
    if (orKey && orKey.value.trim()) body.openrouter_key = orKey.value.trim();
    if (localUrl && localUrl.value.trim()) body.local_url = localUrl.value.trim();
    if (decompModel) body.decompose_model = decompModel.value;
    if (mbseModel) body.mbse_model = mbseModel.value;
    if (autoSend) body.auto_send = autoSend.checked;

    var activeModeBtn = document.querySelector('.modal-settings .segment[data-value].active');
    if (activeModeBtn) {
        var val = activeModeBtn.getAttribute('data-value');
        if (val === 'capella' || val === 'rhapsody') body.default_mode = val;
    }

    try {
        var res = await fetch('/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        var data = await res.json();
        if (data.status === 'ok') {
            // Update local config
            var cfg = window.SHIPYARD_CONFIG || {};
            cfg.settings = Object.assign(cfg.settings || {}, body);
            if (body.anthropic_key) cfg.settings.has_anthropic_key = true;
            if (body.openrouter_key) cfg.settings.has_openrouter_key = true;
            closeSettings();
            showToast('Settings saved', 'success');
        } else {
            showToast('Failed to save settings', 'error');
        }
    } catch (e) {
        showToast('Failed to save: ' + e.message, 'error');
    }
}

function initAutoSendToggle(settings) {
    var statusEl = $('auto-send-status');
    if (statusEl && settings) {
        statusEl.textContent = settings.auto_send !== false ? 'ON' : 'OFF';
    }
}

async function toggleAutoSend() {
    var statusEl = $('auto-send-status');
    var isOn = statusEl && statusEl.textContent === 'ON';
    var newValue = !isOn;

    try {
        await fetch('/settings/auto-send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ auto_send: newValue }),
        });
        if (statusEl) statusEl.textContent = newValue ? 'ON' : 'OFF';
        var cfg = window.SHIPYARD_CONFIG || {};
        if (cfg.settings) cfg.settings.auto_send = newValue;
        showToast('Auto-send ' + (newValue ? 'enabled' : 'disabled'), 'info');
    } catch (e) {
        showToast('Failed to toggle auto-send', 'error');
    }
}

async function checkForUpdates() {
    try {
        var res = await fetch('/settings/check-updates');
        if (!res.ok) return;
        var data = await res.json();

        if (data.available) {
            var banner = $('update-banner');
            var versionEl = $('update-version');
            if (banner) banner.classList.remove('hidden');
            if (versionEl) versionEl.textContent = data.version || ('v' + data.behind + ' update(s)');

            // Also update settings modal if open
            var settingsStatus = $('settings-update-status');
            if (settingsStatus) settingsStatus.textContent = data.behind + ' update(s) available';

            // Add update dot to settings gear icon
            var settingsBtn = document.querySelector('[onclick="openSettings()"]');
            if (settingsBtn) settingsBtn.classList.add('has-update');
        }
    } catch (e) {
        // Silently ignore
    }
}

function dismissBanner() {
    var banner = $('update-banner');
    if (banner) banner.classList.add('hidden');
}

async function installUpdate() {
    var btn = $('settings-update-btn');
    if (btn) { btn.textContent = 'Updating...'; btn.disabled = true; }

    try {
        var res = await fetch('/settings/update', { method: 'POST' });
        var data = await res.json();

        if (data.status === 'ok' && data.updated) {
            var status = $('settings-update-status');
            if (status) status.textContent = 'Updated! Restart to apply.';
            showToast('Update applied. Restart server to activate.', 'success');
        } else {
            if (btn) btn.textContent = 'Check for Updates';
            if (btn) btn.disabled = false;
            showToast(data.message || 'Already up to date', 'info');
        }
    } catch (e) {
        if (btn) { btn.textContent = 'Check for Updates'; btn.disabled = false; }
        showToast('Update failed', 'error');
    }
}

async function loadCostHistory() {
    var body = $('cost-history-body');
    if (!body) return;
    clearChildren(body);
    body.appendChild(document.createTextNode('Loading...'));

    try {
        var res = await fetch('/settings/cost-history');
        if (!res.ok) throw new Error('Failed');
        var data = await res.json();
        clearChildren(body);

        var summary = el('div', { className: 'cost-history-summary' });
        summary.appendChild(el('div', { textContent: 'Total runs: ' + (data.total_runs || 0) }));
        summary.appendChild(el('div', { textContent: 'Total spend: ' + formatCost(data.total_spend || 0) }));
        summary.appendChild(el('div', { textContent: 'Average per run: ' + formatCost(data.avg_per_run || 0) }));
        body.appendChild(summary);

        if (data.runs && data.runs.length > 0) {
            body.appendChild(el('div', { className: 'cost-history-subheader', textContent: 'Recent runs:' }));
            data.runs.slice(-5).reverse().forEach(function (run) {
                var row = el('div', { className: 'cost-history-row' });
                var ts = run.timestamp ? new Date(run.timestamp).toLocaleString() : 'Unknown';
                var cost = run.totals ? formatCost(run.totals.cost_usd || 0) : '$0.00';
                row.appendChild(el('span', { className: 'cost-hist-time', textContent: ts }));
                row.appendChild(el('span', { className: 'cost-hist-cost', textContent: cost }));
                body.appendChild(row);
            });
        }
    } catch (e) {
        clearChildren(body);
        body.appendChild(document.createTextNode('Could not load cost history.'));
    }
}

// =============================================================================
// 12. CLARIFICATION MODAL
// =============================================================================

function showClarificationModal(flaggedItems) {
    var container = $('clarify-items');
    if (!container) return;
    clearChildren(container);

    flaggedItems.forEach(function (item) {
        var itemDiv = el('div', { className: 'clarify-item' });
        itemDiv.appendChild(el('span', { className: 'clarify-req-id', textContent: item.id || item.req_id || '' }));
        itemDiv.appendChild(el('p', { className: 'clarify-req-text', textContent: item.text || '' }));
        itemDiv.appendChild(el('p', { className: 'clarify-issue', textContent: 'Issue: ' + (item.issue || item.problem || '') }));
        if (item.suggestion) {
            itemDiv.appendChild(el('p', { className: 'clarify-suggestion', textContent: 'Suggestion: ' + item.suggestion }));
        }
        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'clarify-input';
        input.placeholder = item.suggestion || 'Enter clarification...';
        input.setAttribute('data-req-id', item.id || item.req_id || '');
        itemDiv.appendChild(input);
        container.appendChild(itemDiv);
    });

    $('clarify-modal').classList.remove('hidden');
}

function submitClarifications() {
    var inputs = document.querySelectorAll('#clarify-items .clarify-input');
    var clarifications = {};
    inputs.forEach(function (input) {
        var reqId = input.getAttribute('data-req-id');
        var value = input.value.trim();
        if (reqId && value) clarifications[reqId] = value;
    });
    $('clarify-modal').classList.add('hidden');

    // Re-run model with clarifications
    if (_pendingModelSettings) {
        _pendingModelSettings.clarifications = clarifications;
        executeModelRun(_pendingModelSettings);
        _pendingModelSettings = null;
    }
}

// =============================================================================
// 13. DRAG-DROP HANDLERS
// =============================================================================

function initDragDrop() {
    // Both upload areas share the same dragover/dragleave pattern
    // The specific drop handlers are wired in HTML via ondrop
}

function handleDragOver(e) {
    e.preventDefault();
    var area = e.currentTarget;
    if (area) area.classList.add('dragover');
}

function handleDragLeave(e) {
    var area = e.currentTarget;
    if (area) area.classList.remove('dragover');
}

// =============================================================================
// 14. EXPORT
// =============================================================================

function toggleExportMenu() {
    var menu = $('export-menu');
    if (!menu) return;
    if (menu.classList.contains('hidden')) {
        populateExportLayerFilters();
    }
    menu.classList.toggle('hidden');
}

function populateExportLayerFilters() {
    var container = $('export-layer-filters');
    if (!container) return;
    clearChildren(container);
    if (!currentModel || !currentModel.layers) return;

    var cfg = window.SHIPYARD_CONFIG || {};
    var layerNames = selectedToolMode === 'capella' ? (cfg.capellaLayers || {}) : (cfg.rhapsodyDiagrams || {});

    Object.keys(currentModel.layers).forEach(function (layerKey) {
        var displayName = layerNames[layerKey] || layerKey;
        var label = document.createElement('label');
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = layerKey;
        cb.checked = true;
        label.appendChild(cb);
        label.appendChild(document.createTextNode(' ' + displayName));
        container.appendChild(label);
    });
}

function exportProject(format) {
    if (!currentModel || !currentModel.layers) {
        showToast('No model to export', 'error');
        return;
    }
    var checkedLayers = [];
    document.querySelectorAll('#export-layer-filters input[type=checkbox]:checked').forEach(function (cb) {
        checkedLayers.push(cb.value);
    });
    var queryStr = checkedLayers.length > 0 ? '?layers=' + checkedLayers.join(',') : '';
    window.open('/export/model/' + format + queryStr, '_blank');
    $('export-menu').classList.add('hidden');
}

function openPrintView() {
    window.open('/export/print', '_blank');
    $('export-menu').classList.add('hidden');
}

function exportDecomposition() {
    window.location = '/export/decomposition';
}

function exportFullProject() {
    window.location = '/export/full';
}

// =============================================================================
// 15. UNDO / REDO / SAVE
// =============================================================================

async function performUndo() {
    try {
        var res = await fetch('/model/undo', { method: 'POST' });
        if (res.ok) {
            var data = await res.json();
            currentModel = data;
            renderModelTree(currentModel.layers);
            renderCoverage(currentModel.requirements, currentModel.links);
            showToast('Undone', 'info');
        } else {
            showToast('Nothing to undo', 'info');
        }
    } catch (e) {
        showToast('Undo failed', 'error');
    }
}

async function performRedo() {
    try {
        var res = await fetch('/model/redo', { method: 'POST' });
        if (res.ok) {
            var data = await res.json();
            currentModel = data;
            renderModelTree(currentModel.layers);
            renderCoverage(currentModel.requirements, currentModel.links);
            showToast('Redone', 'info');
        } else {
            showToast('Nothing to redo', 'info');
        }
    } catch (e) {
        showToast('Redo failed', 'error');
    }
}

async function forceSave() {
    if (!currentProject) return;
    try {
        var res = await fetch('/project/save', { method: 'POST' });
        if (res.ok) showToast('Project saved', 'success');
    } catch (e) {
        showToast('Save failed', 'error');
    }
}

// =============================================================================
// 16. UTILITIES
// =============================================================================

function showToast(message, type) {
    type = type || 'info';
    var container = $('toast-container');
    if (!container) return;
    var toast = el('div', { className: 'toast toast-' + type, textContent: message });
    container.appendChild(toast);
    // Animate in
    requestAnimationFrame(function () { toast.classList.add('toast-show'); });
    setTimeout(function () {
        toast.classList.remove('toast-show');
        setTimeout(function () { toast.remove(); }, 300);
    }, 4000);
}

function showError(msg) {
    var banner = $('error-banner');
    var text = $('error-text');
    if (banner && text) {
        text.textContent = msg;
        banner.classList.remove('hidden');
        setTimeout(function () { banner.classList.add('hidden'); }, 10000);
    }
}

function showInfoTip(elem, text) {
    var existing = document.querySelector('.info-tip-bubble');
    if (existing) { existing.remove(); return; }
    var bubble = el('div', { className: 'info-tip-bubble', textContent: text });
    elem.appendChild(bubble);
    setTimeout(function () {
        document.addEventListener('click', function handler(e) {
            if (!elem.contains(e.target)) {
                bubble.remove();
                document.removeEventListener('click', handler);
            }
        });
    }, 10);
}

function formatCost(amount) {
    if (typeof amount !== 'number') amount = parseFloat(amount) || 0;
    if (amount === 0) return '$0.00';
    if (amount < 0.001) return '$' + amount.toFixed(6);
    if (amount < 0.01) return '$' + amount.toFixed(4);
    return '$' + amount.toFixed(4);
}

function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
            showToast('Copied to clipboard', 'success');
        }).catch(function () {
            _fallbackCopy(text);
        });
    } else {
        _fallbackCopy(text);
    }
}

function _fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.top = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand('copy');
        showToast('Copied to clipboard', 'success');
    } catch (e) {
        showToast('Could not copy', 'error');
    }
    ta.remove();
}
