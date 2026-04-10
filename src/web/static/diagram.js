// =============================================================================
// Shipyard — Mermaid Diagram Module
// Loaded after app.js. Reads: currentModel, selectedToolMode, el(), $(), clearChildren()
// =============================================================================

// --- State ---
var _diagramCurrentLayer = null;
var _diagramRenderCounter = 0;
var _mermaidInitialized = false;
var _diagramAbortCtrl = null;

function _ensureMermaid() {
    if (_mermaidInitialized || !window.mermaid) return !!window.mermaid;
    mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });
    _mermaidInitialized = true;
    return true;
}

// =============================================================================
// Sanitization
// =============================================================================

var MERMAID_KEYWORDS = ['end', 'graph', 'subgraph', 'classDef', 'click', 'style',
    'linkStyle', 'direction', 'participant', 'actor', 'note',
    'loop', 'alt', 'opt', 'par', 'rect', 'left', 'right', 'state',
    'class', 'default', 'section', 'title'];

function sanitizeId(raw) {
    if (!raw) return 'nd_unknown';
    var s = String(raw).replace(/[^a-zA-Z0-9_]/g, '_');
    if (/^[0-9]/.test(s) || MERMAID_KEYWORDS.indexOf(s.toLowerCase()) !== -1) s = 'nd_' + s;
    return s || 'nd_empty';
}

function sanitizeLabel(text, maxLen) {
    if (!text) return '';
    maxLen = maxLen || 55;
    var s = String(text).replace(/[\r\n]+/g, ' ');
    if (s.length > maxLen) s = s.slice(0, maxLen - 1) + '\u2026';
    return s.replace(/"/g, "'").replace(/</g, '').replace(/>/g, '')
            .replace(/[{}]/g, '').replace(/\|/g, '\u2758')
            .replace(/;/g, ',').replace(/:/g, '\u2236');
}

// =============================================================================
// Entry Point
// =============================================================================

function renderDiagramTab() {
    var pane = $('tab-diagram');
    if (!pane) return;
    clearChildren(pane);

    if (!currentModel || !currentModel.layers || Object.keys(currentModel.layers).length === 0) {
        pane.appendChild(el('div', { className: 'empty-state', textContent: 'Generate a model to see diagrams.' }));
        return;
    }

    // Build toolbar
    var toolbar = el('div', { className: 'diagram-toolbar' });

    // Layer picker
    var select = document.createElement('select');
    select.className = 'model-select';
    select.id = 'diagram-layer-select';
    select.style.minWidth = '220px';

    var cfg = window.SHIPYARD_CONFIG || {};
    var nameMap = selectedToolMode === 'rhapsody' ? (cfg.rhapsodyDiagrams || {}) : (cfg.capellaLayers || {});

    var layerKeys = [];
    Object.keys(currentModel.layers).forEach(function (key) {
        var layer = currentModel.layers[key];
        var hasData = layer && Object.keys(layer).some(function (k) {
            return Array.isArray(layer[k]) && layer[k].length > 0;
        });
        if (!hasData) return;
        layerKeys.push(key);
        var opt = document.createElement('option');
        opt.value = key;
        opt.textContent = nameMap[key] || key.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
        select.appendChild(opt);
    });

    if (layerKeys.length === 0) {
        pane.appendChild(el('div', { className: 'empty-state', textContent: 'No layers with data to diagram.' }));
        return;
    }

    // Restore previous selection
    if (_diagramCurrentLayer && layerKeys.indexOf(_diagramCurrentLayer) !== -1) {
        select.value = _diagramCurrentLayer;
    } else {
        _diagramCurrentLayer = layerKeys[0];
    }

    select.addEventListener('change', function () {
        _diagramCurrentLayer = select.value;
        renderDiagramContent(pane);
    });

    toolbar.appendChild(select);

    // Export buttons
    var svgBtn = el('button', { className: 'btn-secondary', textContent: '\u2913 SVG' });
    svgBtn.addEventListener('click', exportDiagramSVG);
    var pngBtn = el('button', { className: 'btn-secondary', textContent: '\u2913 PNG' });
    pngBtn.addEventListener('click', exportDiagramPNG);
    toolbar.appendChild(svgBtn);
    toolbar.appendChild(pngBtn);

    pane.appendChild(toolbar);

    // Diagram container
    var container = el('div', { className: 'diagram-container', id: 'diagram-container' });
    pane.appendChild(container);

    // Tooltip
    var tooltip = el('div', { className: 'diagram-tooltip hidden', id: 'diagram-tooltip' });
    pane.appendChild(tooltip);

    renderDiagramContent(pane);
}

async function renderDiagramContent(pane) {
    var container = $('diagram-container');
    if (!container) return;
    clearChildren(container);

    var layerKey = _diagramCurrentLayer;
    if (!layerKey || !currentModel || !currentModel.layers || !currentModel.layers[layerKey]) {
        container.appendChild(el('div', { className: 'empty-state', textContent: 'Select a layer to diagram.' }));
        return;
    }

    var layerData = currentModel.layers[layerKey];
    var links = currentModel.links || [];
    var diagramResult = buildMermaidDefinition(layerKey, layerData, links);
    var definition = diagramResult ? diagramResult.definition : null;
    var warning = diagramResult ? diagramResult.warning : null;

    if (!definition) {
        container.appendChild(el('div', { className: 'empty-state', textContent: 'This layer has no elements to diagram. Try regenerating it or running a new batch.' }));
        return;
    }

    // Show rendering indicator
    container.appendChild(el('div', { className: 'empty-state', textContent: 'Rendering diagram...' }));

    if (!_ensureMermaid()) {
        clearChildren(container);
        container.appendChild(el('div', { className: 'empty-state', textContent: 'Mermaid library not loaded. Check your internet connection.' }));
        return;
    }

    var myRender = ++_diagramRenderCounter;

    try {
        var id = 'dgm_' + myRender;
        var result = await mermaid.render(id, definition);
        if (_diagramRenderCounter !== myRender) return;
        clearChildren(container);

        // Show partial data warning if applicable
        if (warning) {
            var warn = el('div', { className: 'diagram-warning', textContent: warning });
            container.appendChild(warn);
        }

        var svgString = (typeof result === 'object' && result.svg) ? result.svg : result;
        var wrapper = document.createElement('div');
        wrapper.insertAdjacentHTML('afterbegin', svgString);
        while (wrapper.firstChild) container.appendChild(wrapper.firstChild);
        wireDiagramClickHandlers(container, layerKey, layerData);
    } catch (err) {
        clearChildren(container);
        var errDiv = el('div', { className: 'empty-state' });
        errDiv.appendChild(el('div', { textContent: 'Diagram render error: ' + err.message }));
        var pre = document.createElement('pre');
        pre.style.cssText = 'text-align:left;font-size:10px;color:#666;max-height:200px;overflow:auto;margin-top:10px;';
        pre.textContent = definition;
        errDiv.appendChild(pre);
        container.appendChild(errDiv);
    }
}

function _diagramResult(lines, warning) {
    if (lines.length <= 1) return null; // only header, no nodes
    return { definition: lines.join('\n'), warning: warning || null };
}

// =============================================================================
// Generator Dispatch
// =============================================================================

function buildMermaidDefinition(layerKey, layerData, links) {
    if (selectedToolMode === 'capella') {
        if (layerKey === 'operational_analysis') return buildOADiagram(layerData, links);
        if (layerKey === 'system_needs_analysis') return buildSADiagram(layerData, links);
        if (layerKey === 'logical_architecture') return buildArchDiagram(layerData, links, 'logical');
        if (layerKey === 'physical_architecture') return buildArchDiagram(layerData, links, 'physical');
        if (layerKey === 'epbs') return buildEPBSDiagram(layerData);
    }
    if (selectedToolMode === 'rhapsody') {
        if (layerKey === 'sequence_diagram') return buildSequenceDiagram(layerData);
        if (layerKey === 'state_machine') return buildStateDiagram(layerData);
        if (layerKey === 'block_definition') return buildBDDDiagram(layerData, links);
    }
    return null;
}

// =============================================================================
// Capella Generators
// =============================================================================

// --- Operational Analysis: entities + interactions ---
function buildOADiagram(layer, links) {
    var entities = layer.entities || [];
    var interactions = layer.operational_interactions || [];
    var comms = layer.communication_means || [];
    if (entities.length === 0) return null;

    var lines = ['graph LR'];
    var warning = null;

    var idMap = {};
    entities.forEach(function (e) {
        var nid = sanitizeId(e.id);
        idMap[e.id] = nid;
        idMap[e.name] = nid;
        lines.push('    ' + nid + '["' + sanitizeLabel(e.name) + '"]');
    });

    interactions.forEach(function (i) {
        var src = idMap[i.source_entity] || sanitizeId(i.source_entity);
        var tgt = idMap[i.target_entity] || sanitizeId(i.target_entity);
        if (src && tgt && src !== tgt) {
            lines.push('    ' + src + ' -->|"' + sanitizeLabel(i.name, 30) + '"| ' + tgt);
        }
    });

    comms.forEach(function (c) {
        var src = idMap[c.source_entity] || sanitizeId(c.source_entity);
        var tgt = idMap[c.target_entity] || sanitizeId(c.target_entity);
        if (src && tgt && src !== tgt) {
            lines.push('    ' + src + ' -.-|"' + sanitizeLabel(c.name, 30) + '"| ' + tgt);
        }
    });

    if (interactions.length === 0 && comms.length === 0) {
        warning = 'Partial diagram: entities found but no interactions or communication means were generated. The model run may not have produced sufficient relationship data for this layer.';
    }

    return _diagramResult(lines, warning);
}

// --- System Needs Analysis: functions + exchanges + actors ---
function buildSADiagram(layer, links) {
    var functions = layer.functions || [];
    var exchanges = layer.exchanges || [];
    var actors = layer.external_actors || [];
    var sysDefs = layer.system_definitions || [];
    if (functions.length === 0 && actors.length === 0 && sysDefs.length === 0) return null;

    var lines = ['graph TB'];
    var idMap = {};
    var warning = null;
    var missing = [];

    sysDefs.forEach(function (s) {
        var nid = sanitizeId(s.id);
        idMap[s.id] = nid;
        lines.push('    ' + nid + '["' + sanitizeLabel(s.name) + '"]');
    });

    actors.forEach(function (a) {
        var nid = sanitizeId(a.id);
        idMap[a.id] = nid;
        lines.push('    ' + nid + '(["' + sanitizeLabel(a.name) + '"])');
    });

    functions.forEach(function (f) {
        var nid = sanitizeId(f.id);
        idMap[f.id] = nid;
        lines.push('    ' + nid + '("' + sanitizeLabel(f.name) + '")');
    });

    exchanges.forEach(function (ex) {
        var src = idMap[ex.source] || sanitizeId(ex.source);
        var tgt = idMap[ex.target] || sanitizeId(ex.target);
        if (src && tgt && src !== tgt) {
            lines.push('    ' + src + ' -->|"' + sanitizeLabel(ex.name, 30) + '"| ' + tgt);
        }
    });

    if (functions.length === 0) missing.push('functions');
    if (actors.length === 0) missing.push('external actors');
    if (exchanges.length === 0) missing.push('exchanges');
    if (missing.length > 0) {
        warning = 'Partial diagram: no ' + missing.join(', ') + ' were generated. The model run produced limited data for this layer.';
    }

    return _diagramResult(lines, warning);
}

// --- Logical/Physical Architecture: components + exchanges ---
function buildArchDiagram(layer, links, variant) {
    var components = layer.components || [];
    var compExchanges = layer.component_exchanges || [];
    var functions = layer.functions || [];
    if (components.length === 0) return null;

    var lines = ['graph TB'];
    var compIdMap = {};
    var fnIdMap = {};
    var warning = null;

    // Components as subgraphs containing their functions
    var fnByComponent = {};
    functions.forEach(function (f) {
        var compRef = f.component || f.physical_component;
        if (compRef) {
            if (!fnByComponent[compRef]) fnByComponent[compRef] = [];
            fnByComponent[compRef].push(f);
        }
    });

    components.forEach(function (c) {
        var cid = sanitizeId(c.id);
        compIdMap[c.id] = cid;
        compIdMap[c.name] = cid;
        var fns = fnByComponent[c.id] || [];

        if (fns.length > 0) {
            lines.push('    subgraph ' + cid + '["' + sanitizeLabel(c.name) + '"]');
            fns.forEach(function (f) {
                var fid = sanitizeId(f.id);
                fnIdMap[f.id] = fid;
                lines.push('        ' + fid + '("' + sanitizeLabel(f.name, 30) + '")');
            });
            lines.push('    end');
        } else {
            lines.push('    ' + cid + '["' + sanitizeLabel(c.name) + '"]');
        }
    });

    // Unallocated functions
    functions.forEach(function (f) {
        if (!fnIdMap[f.id]) {
            var fid = sanitizeId(f.id);
            fnIdMap[f.id] = fid;
            lines.push('    ' + fid + '("' + sanitizeLabel(f.name, 30) + '")');
        }
    });

    compExchanges.forEach(function (ex) {
        var src = compIdMap[ex.source_component] || sanitizeId(ex.source_component);
        var tgt = compIdMap[ex.target_component] || sanitizeId(ex.target_component);
        if (src && tgt && src !== tgt) {
            lines.push('    ' + src + ' <-->|"' + sanitizeLabel(ex.name, 30) + '"| ' + tgt);
        }
    });

    if (compExchanges.length === 0 && functions.length === 0) {
        warning = 'Partial diagram: components found but no functions or exchanges were generated.';
    } else if (compExchanges.length === 0) {
        warning = 'Partial diagram: no component exchanges were generated. Components are shown without connections.';
    }

    return _diagramResult(lines, warning);
}

// --- EPBS: PBS tree ---
function buildEPBSDiagram(layer) {
    var nodes = layer.pbs_structure || [];
    var cis = layer.configuration_items || [];
    if (nodes.length === 0 && cis.length === 0) return null;

    var lines = ['graph TD'];
    var idMap = {};

    // Build CI type lookup
    var ciTypes = {};
    cis.forEach(function (ci) { ciTypes[ci.id] = ci.type || ''; });

    if (nodes.length > 0) {
        // PBS tree
        nodes.forEach(function (n) {
            var nid = sanitizeId(n.id);
            idMap[n.id] = nid;
            var typeTag = n.ci_ref && ciTypes[n.ci_ref] ? ' [' + ciTypes[n.ci_ref] + ']' : '';
            lines.push('    ' + nid + '["' + sanitizeLabel(n.name + typeTag) + '"]');
        });
        nodes.forEach(function (n) {
            if (n.parent_id && idMap[n.parent_id]) {
                lines.push('    ' + idMap[n.parent_id] + ' --> ' + idMap[n.id]);
            }
        });
    } else {
        // Fallback: just show CIs as flat nodes
        cis.forEach(function (ci) {
            var nid = sanitizeId(ci.id);
            lines.push('    ' + nid + '["' + sanitizeLabel(ci.name + ' [' + (ci.type || '') + ']') + '"]');
        });
    }

    return _diagramResult(lines);
}

// =============================================================================
// Rhapsody Generators
// =============================================================================

// --- Block Definition Diagram ---
function buildBDDDiagram(layer, links) {
    var blocks = layer.blocks || [];
    if (blocks.length === 0) return null;

    var lines = ['classDiagram'];

    blocks.forEach(function (b) {
        var bid = sanitizeId(b.id);
        var props = b.properties || [];
        var ports = b.ports || [];

        if (props.length > 0 || ports.length > 0) {
            lines.push('    class ' + bid + ' {');
            lines.push('        <<Block>>');
            props.forEach(function (p) { lines.push('        +' + sanitizeLabel(p, 40)); });
            ports.forEach(function (p) { lines.push('        ~' + sanitizeLabel(p, 40)); });
            lines.push('    }');
        } else {
            lines.push('    class ' + bid);
        }
        // Add display name annotation
        lines.push('    ' + bid + ' : ' + sanitizeLabel(b.name, 40));
    });

    // Add links between blocks if any
    var blockIds = {};
    blocks.forEach(function (b) { blockIds[b.id] = sanitizeId(b.id); });
    (links || []).forEach(function (lnk) {
        var src = blockIds[lnk.source];
        var tgt = blockIds[lnk.target];
        if (src && tgt) {
            lines.push('    ' + src + ' --> ' + tgt + ' : ' + sanitizeLabel(lnk.type, 20));
        }
    });

    return _diagramResult(lines);
}

// --- Sequence Diagram ---
function buildSequenceDiagram(layer) {
    var lifelines = layer.lifelines || [];
    var messages = (layer.messages || []).slice().sort(function (a, b) {
        return (a.sequence || 0) - (b.sequence || 0);
    });
    if (lifelines.length === 0) return null;

    var lines = ['sequenceDiagram'];

    // Participants
    lifelines.forEach(function (ll) {
        var pid = sanitizeId(ll.id);
        lines.push('    participant ' + pid + ' as "' + sanitizeLabel(ll.name) + '"');
    });

    // Build lifeline ID lookup
    var llMap = {};
    lifelines.forEach(function (ll) {
        llMap[ll.id] = sanitizeId(ll.id);
        llMap[ll.name] = sanitizeId(ll.id);
    });

    // Messages
    messages.forEach(function (m) {
        var from = llMap[m.from_lifeline] || sanitizeId(m.from_lifeline);
        var to = llMap[m.to_lifeline] || sanitizeId(m.to_lifeline);
        var msg = sanitizeLabel(m.message, 40);
        // Use -->> for return-style messages
        var arrow = '->>';
        var msgLower = (m.message || '').toLowerCase();
        if (msgLower.indexOf('return') === 0 || msgLower.indexOf('reply') === 0 ||
            msgLower.indexOf('response') === 0 || msgLower.indexOf('ack') === 0) {
            arrow = '-->>';
        }
        lines.push('    ' + from + arrow + to + ': ' + msg);
    });

    return _diagramResult(lines);
}

// --- State Machine ---
function buildStateDiagram(layer) {
    var states = layer.states || [];
    var transitions = layer.transitions || [];
    if (states.length === 0) return null;

    var lines = ['stateDiagram-v2'];

    var stateMap = {};
    states.forEach(function (s) { stateMap[s.id] = s; });

    // Declare non-special states
    states.forEach(function (s) {
        if (s.type !== 'Initial' && s.type !== 'Final') {
            var sid = sanitizeId(s.id);
            lines.push('    ' + sid + ' : ' + sanitizeLabel(s.name));
        }
    });

    // Transitions
    transitions.forEach(function (t) {
        var srcState = stateMap[t.source];
        var tgtState = stateMap[t.target];
        // Skip transitions from Final states (invalid in state diagrams)
        if (srcState && srcState.type === 'Final') return;
        var src = srcState && srcState.type === 'Initial' ? '[*]' : sanitizeId(t.source);
        var tgt = tgtState && tgtState.type === 'Final' ? '[*]' : sanitizeId(t.target);

        var label = '';
        if (t.trigger) label = sanitizeLabel(t.trigger, 30);
        if (t.guard) label += (label ? ' ' : '') + '[' + sanitizeLabel(t.guard, 20) + ']';

        lines.push('    ' + src + ' --> ' + tgt + (label ? ' : ' + label : ''));
    });

    return _diagramResult(lines);
}

// =============================================================================
// Click Handlers & Tooltip
// =============================================================================

function wireDiagramClickHandlers(container, layerKey, layerData) {
    // Build lookup: sanitized ID -> raw element data
    var lookup = {};
    Object.keys(layerData).forEach(function (k) {
        var arr = layerData[k];
        if (!Array.isArray(arr)) return;
        arr.forEach(function (item) {
            if (item && item.id) {
                lookup[sanitizeId(item.id)] = item;
            }
            if (item && item.name) {
                lookup[sanitizeId(item.name)] = item;
            }
        });
    });

    // Walk SVG nodes — Mermaid assigns IDs and classes to <g> groups
    container.querySelectorAll('.node, .actor, .statediagram-state').forEach(function (nodeEl) {
        // Try to find matching element by node ID attribute
        var nodeId = nodeEl.getAttribute('id') || '';
        // Mermaid prefixes node IDs with various strings; extract the meaningful part
        var cleanId = nodeId.replace(/^flowchart-/, '').replace(/^classId-/, '').replace(/-\d+$/, '');
        var data = lookup[cleanId];

        // Fallback: match by text content
        if (!data) {
            var textEl = nodeEl.querySelector('text, span');
            if (textEl) {
                var label = textEl.textContent.trim();
                Object.keys(lookup).forEach(function (k) {
                    if (lookup[k].name && sanitizeLabel(lookup[k].name, 55) === label) {
                        data = lookup[k];
                    }
                });
            }
        }

        if (!data) return;
        nodeEl.style.cursor = 'pointer';
        nodeEl.addEventListener('click', function (e) {
            e.stopPropagation();
            showDiagramTooltip(e, data);
        });
    });

    // Click container to dismiss tooltip — use AbortController to prevent listener accumulation
    if (_diagramAbortCtrl) _diagramAbortCtrl.abort();
    _diagramAbortCtrl = new AbortController();
    container.addEventListener('click', function (e) {
        if (!e.target.closest('.node, .actor, .statediagram-state')) {
            hideDiagramTooltip();
        }
    }, { signal: _diagramAbortCtrl.signal });
}

function showDiagramTooltip(evt, data) {
    var tip = $('diagram-tooltip');
    if (!tip) return;
    clearChildren(tip);

    var title = el('div', { className: 'diagram-tooltip-title', textContent: data.name || data.id || 'Element' });
    tip.appendChild(title);

    Object.keys(data).forEach(function (k) {
        if (k === 'name') return;
        var val = data[k];
        if (Array.isArray(val)) {
            if (val.length === 0) return;
            val = val.map(function (v) {
                return typeof v === 'object' ? JSON.stringify(v) : String(v);
            }).join(', ');
        }
        if (val === null || val === undefined || val === '') return;

        var row = el('div', { className: 'diagram-tooltip-field' });
        row.appendChild(el('span', { className: 'diagram-tooltip-key', textContent: k.replace(/_/g, ' ') }));
        row.appendChild(el('span', { className: 'diagram-tooltip-val', textContent: String(val) }));
        tip.appendChild(row);
    });

    // Position relative to click, clamped to viewport
    var pane = $('tab-diagram');
    if (!pane) return;
    var paneRect = pane.getBoundingClientRect();
    var x = evt.clientX - paneRect.left + 12;
    var y = evt.clientY - paneRect.top + 12;
    if (x + 320 > paneRect.width) x = paneRect.width - 330;
    if (x < 0) x = 10;
    if (y + 200 > paneRect.height) y = paneRect.height - 210;
    if (y < 0) y = 10;
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
    tip.classList.remove('hidden');
}

function hideDiagramTooltip() {
    var tip = $('diagram-tooltip');
    if (tip) tip.classList.add('hidden');
}

// Dismiss tooltip on Escape
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') hideDiagramTooltip();
});

// =============================================================================
// Export
// =============================================================================

function exportDiagramSVG() {
    var svg = document.querySelector('#diagram-container svg');
    if (!svg) { showToast('No diagram to export', 'error'); return; }
    var serializer = new XMLSerializer();
    var svgStr = serializer.serializeToString(svg);
    var blob = new Blob([svgStr], { type: 'image/svg+xml' });
    triggerDiagramDownload(blob, 'shipyard-diagram.svg');
}

function exportDiagramPNG() {
    var svg = document.querySelector('#diagram-container svg');
    if (!svg) { showToast('No diagram to export', 'error'); return; }
    var serializer = new XMLSerializer();
    var svgStr = serializer.serializeToString(svg);
    var bbox = svg.getBoundingClientRect();
    var w = svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.width ? svg.viewBox.baseVal.width : bbox.width;
    var h = svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.height ? svg.viewBox.baseVal.height : bbox.height;
    w = Math.max(w, 100);
    h = Math.max(h, 100);

    var canvas = document.createElement('canvas');
    canvas.width = w * 2;
    canvas.height = h * 2;
    var ctx = canvas.getContext('2d');
    ctx.scale(2, 2);
    // Fill background
    ctx.fillStyle = '#0d0d1a';
    ctx.fillRect(0, 0, w, h);

    var img = new Image();
    var url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgStr);
    img.onload = function () {
        ctx.drawImage(img, 0, 0, w, h);
        try {
            canvas.toBlob(function (blob) {
                triggerDiagramDownload(blob, 'shipyard-diagram.png');
            });
        } catch (e) {
            showToast('PNG export failed \u2014 try SVG instead', 'error');
        }
    };
    img.onerror = function () {
        showToast('PNG export failed \u2014 try SVG instead', 'error');
    };
    img.src = url;
}

function triggerDiagramDownload(blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 100);
}
