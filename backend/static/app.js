/**
 * FalconEYE AI Music Generator — Frontend Application
 * Supports three generation modes: Melodic Arpeggio, Drum Loop, Chord Progression
 * Full-featured: prompt UI, piano roll, MIDI preview, pattern library,
 * tab navigation, settings management, pattern modification.
 * (c) 2026 FalconEYE Software Dev
 */

// ============================================================
// DOM References
// ============================================================
const DOM = {
    promptInput: document.getElementById('promptInput'),
    promptTypeLabel: document.getElementById('promptTypeLabel'),
    btnGenerate: document.getElementById('btnGenerate'),
    generateBtnText: document.getElementById('generateBtnText'),
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),
    pianoRoll: document.getElementById('pianoRoll'),
    pianoRollPlaceholder: document.getElementById('pianoRollPlaceholder'),
    patternInfo: document.getElementById('patternInfo'),
    previewMeta: document.getElementById('previewMeta'),
    previewControls: document.getElementById('previewControls'),
    reaperHint: document.getElementById('reaperHint'),
    // Mode
    modeToggle: document.getElementById('modeToggle'),
    melodicParams: document.getElementById('melodicParams'),
    melodicStyles: document.getElementById('melodicStyles'),
    drumStyles: document.getElementById('drumStyles'),
    chordStyles: document.getElementById('chordStyles'),
    // Info
    infoName: document.getElementById('infoName'),
    infoEvents: document.getElementById('infoEvents'),
    infoLength: document.getElementById('infoLength'),
    infoTimeSig: document.getElementById('infoTimeSig'),
    infoScale: document.getElementById('infoScale'),
    infoScaleCard: document.getElementById('infoScaleCard'),
    infoBPM: document.getElementById('infoBPM'),
    infoKit: document.getElementById('infoKit'),
    infoKitCard: document.getElementById('infoKitCard'),
    infoType: document.getElementById('infoType'),
    infoTypeCard: document.getElementById('infoTypeCard'),
    // Params
    paramKey: document.getElementById('paramKey'),
    paramScale: document.getElementById('paramScale'),
    paramTimeSig: document.getElementById('paramTimeSig'),
    paramBars: document.getElementById('paramBars'),
    paramSubdivision: document.getElementById('paramSubdivision'),
    paramOctave: document.getElementById('paramOctave'),
    paramCategory: document.getElementById('paramCategory'),
    // Preview
    btnPreviewPlay: document.getElementById('btnPreviewPlay'),
    btnPreviewStop: document.getElementById('btnPreviewStop'),
    previewLoop: document.getElementById('previewLoop'),
    previewInstrument: document.getElementById('previewInstrument'),
    // Modify
    modifyPanel: document.getElementById('modifyPanel'),
    btnModifyToggle: document.getElementById('btnModifyToggle'),
    modifyBody: document.getElementById('modifyBody'),
    modifyPrompt: document.getElementById('modifyPrompt'),
    modBPM: document.getElementById('modBPM'),
    modBars: document.getElementById('modBars'),
    modKey: document.getElementById('modKey'),
    modScale: document.getElementById('modScale'),
    modKeyGroup: document.getElementById('modKeyGroup'),
    modScaleGroup: document.getElementById('modScaleGroup'),
    btnApplyModify: document.getElementById('btnApplyModify'),
    btnRevert: document.getElementById('btnRevert'),
    versionDots: document.getElementById('versionDots'),
    modifyOverrides: document.getElementById('modifyOverrides'),
    // Settings
    btnSettings: document.getElementById('btnSettings'),
    settingsModal: document.getElementById('settingsModal'),
    btnCloseSettings: document.getElementById('btnCloseSettings'),
    btnSaveSettings: document.getElementById('btnSaveSettings'),
    settingProvider: document.getElementById('settingProvider'),
    settingGeminiKey: document.getElementById('settingGeminiKey'),
    settingOpenAIKey: document.getElementById('settingOpenAIKey'),
    settingClaudeKey: document.getElementById('settingClaudeKey'),
    // Library
    libraryGrid: document.getElementById('libraryGrid'),
    libFilterCategory: document.getElementById('libFilterCategory'),
    libFilterFavorites: document.getElementById('libFilterFavorites'),
    // Rename modal
    renameModal: document.getElementById('renameModal'),
    renameInput: document.getElementById('renameInput'),
    renamePatternId: document.getElementById('renamePatternId'),
    btnCloseRename: document.getElementById('btnCloseRename'),
    btnSaveRename: document.getElementById('btnSaveRename'),
    // Category modal
    categoryModal: document.getElementById('categoryModal'),
    categorySelect: document.getElementById('categorySelect'),
    categoryNewInput: document.getElementById('categoryNewInput'),
    categoryPatternId: document.getElementById('categoryPatternId'),
    btnCloseCategory: document.getElementById('btnCloseCategory'),
    btnSaveCategory: document.getElementById('btnSaveCategory'),
    // Tabs
    tabCompose: document.getElementById('tabCompose'),
    tabLibrary: document.getElementById('tabLibrary'),
    // Provider toggles
    provGemini: document.getElementById('provGemini'),
    provOpenAI: document.getElementById('provOpenAI'),
    provClaude: document.getElementById('provClaude'),
    paramIterations: document.getElementById('paramIterations'),
    // Result carousel
    resultCarousel: document.getElementById('resultCarousel'),
    carouselCounter: document.getElementById('carouselCounter'),
    carouselProvider: document.getElementById('carouselProvider'),
    btnPrevResult: document.getElementById('btnPrevResult'),
    btnNextResult: document.getElementById('btnNextResult'),
};

let pollInterval = null;
let currentPattern = null;
let currentPatternRaw = null;
let isPreviewPlaying = false;
let generationMode = 'melodic'; // 'melodic', 'drums', 'chords'
let allResults = [];     // multi-provider/multi-iteration results
let resultIndex = 0;     // current result index

// GM Drum name map (loaded from server, fallback here)
const GM_DRUM_NAMES = {
    35:"Kick 2",36:"Kick 1",37:"Side Stick",38:"Snare",39:"Clap",40:"E.Snare",
    41:"Lo Floor Tom",42:"Closed HH",43:"Hi Floor Tom",44:"Pedal HH",45:"Low Tom",
    46:"Open HH",47:"Lo-Mid Tom",48:"Hi-Mid Tom",49:"Crash 1",50:"High Tom",
    51:"Ride 1",52:"Chinese Cym",53:"Ride Bell",54:"Tambourine",55:"Splash",
    56:"Cowbell",57:"Crash 2",69:"Cabasa",70:"Maracas",75:"Claves",76:"Hi Woodblock"
};

// Version history for modify workflow (max 5)
let versionHistory = [];
let versionIndex = -1;

// Placeholder texts per mode
const PLACEHOLDERS = {
    melodic: 'e.g. Dark ambient C minor arpeggio, ascending then descending with ghost notes, triplet feel, 2 bars...',
    drums: 'e.g. Tight trap beat with rapid hi-hat rolls, punchy 808 kick, snare on 2 and 4, 2 bars...',
    chords: 'e.g. Dreamy neo-soul chord progression in Eb major, jazzy extensions with 7ths and 9ths, 4 bars...'
};
const TYPE_LABELS = { melodic: 'arpeggio', drums: 'drum loop', chords: 'chord progression' };
const BTN_LABELS = { melodic: 'Generate Pattern', drums: 'Generate Drum Loop', chords: 'Generate Chords' };

// ============================================================
// API Helpers
// ============================================================
async function apiGet(path) { const r = await fetch(path); return r.json(); }
async function apiPost(path, body) {
    const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    return r.json();
}
async function apiDelete(path) { const r = await fetch(path, { method: 'DELETE' }); return r.json(); }
function escapeHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ============================================================
// Mode Toggle
// ============================================================
function setMode(mode) {
    generationMode = mode;
    // Update toggle buttons
    document.querySelectorAll('.mode-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.mode === mode);
    });
    // Show/hide mode-specific sections
    const isMelodic = mode === 'melodic';
    const isDrums = mode === 'drums';
    const isChords = mode === 'chords';

    if (DOM.melodicParams) DOM.melodicParams.style.display = (isMelodic || isChords) ? 'grid' : 'none';
    if (DOM.melodicStyles) DOM.melodicStyles.style.display = isMelodic ? '' : 'none';
    if (DOM.drumStyles) DOM.drumStyles.style.display = isDrums ? '' : 'none';
    if (DOM.chordStyles) DOM.chordStyles.style.display = isChords ? '' : 'none';

    // Update labels
    if (DOM.promptTypeLabel) DOM.promptTypeLabel.textContent = TYPE_LABELS[mode] || 'pattern';
    if (DOM.promptInput) DOM.promptInput.placeholder = PLACEHOLDERS[mode] || '';
    if (DOM.generateBtnText) DOM.generateBtnText.textContent = BTN_LABELS[mode] || 'Generate';

    // Hide instrument selector for drums (channel 10 is always percussion)
    if (DOM.previewInstrument) DOM.previewInstrument.style.display = isDrums ? 'none' : '';

    // Hide key/scale in modify overrides for drums
    if (DOM.modKeyGroup) DOM.modKeyGroup.style.display = isDrums ? 'none' : '';
    if (DOM.modScaleGroup) DOM.modScaleGroup.style.display = isDrums ? 'none' : '';

    // Clear active style chips when switching modes
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    updateSelectedStylesSummary();
}

document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => setMode(btn.dataset.mode));
});

// ============================================================
// Multi-Select Style Chips
// ============================================================
function getActiveStylesText() {
    const active = document.querySelectorAll('.chip.active');
    if (!active.length) return '';
    return Array.from(active).map(c => c.dataset.style).join(', ');
}

function updateSelectedStylesSummary() {
    let container = document.getElementById('selectedStylesSummary');
    if (!container) {
        container = document.createElement('div');
        container.id = 'selectedStylesSummary';
        container.className = 'selected-styles-summary';
        // Insert after the active styles section
        const stylesSection = DOM.melodicStyles || DOM.drumStyles || DOM.chordStyles;
        if (stylesSection && stylesSection.parentNode) {
            stylesSection.parentNode.insertBefore(container, DOM.btnGenerate || stylesSection.nextSibling);
        }
    }
    const active = document.querySelectorAll('.chip.active');
    if (!active.length) { container.style.display = 'none'; return; }
    container.style.display = '';
    container.innerHTML = '<span class="styles-label">Selected: </span>' +
        Array.from(active).map(c =>
            `<span class="style-tag">${c.textContent}<button class="style-tag-x" data-remove="${c.textContent}">×</button></span>`
        ).join('');
    // Wire remove buttons
    container.querySelectorAll('.style-tag-x').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            const name = btn.dataset.remove;
            document.querySelectorAll('.chip.active').forEach(c => {
                if (c.textContent === name) c.classList.remove('active');
            });
            updateSelectedStylesSummary();
        });
    });
}

// Delegate chip clicks for multi-select toggle
document.addEventListener('click', e => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    e.preventDefault();
    chip.classList.toggle('active');
    updateSelectedStylesSummary();
});

// ============================================================
// Custom Param Handlers
// ============================================================
function setupCustomSelect(selectId, customInputId) {
    const sel = document.getElementById(selectId);
    const inp = document.getElementById(customInputId);
    if (!sel || !inp) return;
    sel.addEventListener('change', () => {
        inp.style.display = sel.value === '__custom' ? '' : 'none';
        if (sel.value === '__custom') inp.focus();
    });
}
setupCustomSelect('paramScale', 'paramScaleCustom');
setupCustomSelect('paramTimeSig', 'paramTimeSigCustom');
setupCustomSelect('paramBars', 'paramBarsCustom');

function getParamValue(selectId, customInputId) {
    const sel = document.getElementById(selectId);
    if (!sel) return '';
    if (sel.value === '__custom') {
        const inp = document.getElementById(customInputId);
        return inp ? inp.value.trim() : '';
    }
    return sel.value;
}

// ============================================================
// Piano Roll Renderer
// ============================================================
class PianoRollRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.dpr = window.devicePixelRatio || 1;
        this.resize();
        window.addEventListener('resize', () => this.resize());
    }
    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width * this.dpr;
        this.canvas.height = 250 * this.dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = '250px';
        this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
        this.w = rect.width;
        this.h = 250;
        if (currentPattern) this.render(currentPattern);
    }
    render(pattern) {
        const ctx = this.ctx;
        const w = this.w, h = this.h;
        const events = pattern.events || [];
        const loopLen = pattern.loop_length_beats || 4;
        const isDrums = pattern.type === 'drums';
        ctx.clearRect(0, 0, w, h);
        if (!events.length) return;
        const padL = isDrums ? 80 : 50, padR = 16, padT = 20, padB = 24;
        const rollW = w - padL - padR, rollH = h - padT - padB;
        let minNote = 127, maxNote = 0;
        for (const e of events) { if (e.note < minNote) minNote = e.note; if (e.note > maxNote) maxNote = e.note; }
        const noteRange = Math.max(maxNote - minNote + 1, 1);
        const noteH = Math.min(Math.max(rollH / noteRange, 3), 14);
        ctx.fillStyle = 'rgba(10,10,20,0.8)';
        ctx.beginPath(); ctx.roundRect(0, 0, w, h, 8); ctx.fill();
        // Beat grid
        ctx.strokeStyle = 'rgba(80,80,130,0.2)'; ctx.lineWidth = 1;
        for (let b = 0; b <= loopLen; b++) {
            const x = padL + (b / loopLen) * rollW;
            ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, padT + rollH); ctx.stroke();
            if (b < loopLen) { ctx.fillStyle = 'rgba(150,140,180,0.5)'; ctx.font = '10px "JetBrains Mono",monospace'; ctx.textAlign = 'center'; ctx.fillText(`${b + 1}`, x + (rollW / loopLen) / 2, h - 6); }
        }
        // Sub-beat grid
        ctx.strokeStyle = 'rgba(60,60,100,0.12)';
        for (let b = 0; b < loopLen * 4; b++) { if (b % 4 !== 0) { const x = padL + (b / (loopLen * 4)) * rollW; ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, padT + rollH); ctx.stroke(); } }
        // Note labels
        const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
        ctx.font = isDrums ? '8px "JetBrains Mono",monospace' : '9px "JetBrains Mono",monospace';
        ctx.textAlign = 'right';
        for (let n = minNote; n <= maxNote; n++) {
            const y = padT + rollH - ((n - minNote + 0.5) / noteRange) * rollH;
            const isBlack = [1, 3, 6, 8, 10].includes(n % 12);
            if (!isDrums && isBlack) { const yT = padT + rollH - ((n - minNote + 1) / noteRange) * rollH; const yB = padT + rollH - ((n - minNote) / noteRange) * rollH; ctx.fillStyle = 'rgba(0,0,0,0.15)'; ctx.fillRect(padL, yT, rollW, yB - yT); }
            if (isDrums) {
                // Label every drum note
                ctx.fillStyle = 'rgba(245,158,11,0.7)';
                ctx.fillText(GM_DRUM_NAMES[n] || `P${n}`, padL - 6, y + 3);
            } else if (n % 12 === 0 || n === minNote || n === maxNote) {
                ctx.fillStyle = 'rgba(150,140,180,0.6)';
                ctx.fillText(NOTE_NAMES[n % 12] + (Math.floor(n / 12) - 1), padL - 6, y + 3);
            }
        }
        // Notes — color by mode
        for (const e of events) {
            const x = padL + (e.beat / loopLen) * rollW;
            const nw = Math.max((e.duration / loopLen) * rollW, 3);
            const y = padT + rollH - ((e.note - minNote + 0.5) / noteRange) * rollH - noteH / 2;
            const vR = (e.velocity || 100) / 127;
            let hue, sat, light;
            if (isDrums) { hue = 30 + (1 - vR) * 20; sat = 70 + vR * 25; light = 45 + vR * 20; }
            else if (pattern.type === 'chords') { hue = 160 + (1 - vR) * 40; sat = 55 + vR * 30; light = 40 + vR * 25; }
            else { hue = 260 + (1 - vR) * 40; sat = 60 + vR * 30; light = 45 + vR * 20; }
            ctx.shadowColor = `hsla(${hue},${sat}%,${light}%,0.5)`; ctx.shadowBlur = 6;
            ctx.fillStyle = `hsla(${hue},${sat}%,${light}%,0.9)`;
            ctx.beginPath(); ctx.roundRect(x, y, nw, noteH, 2); ctx.fill();
            ctx.shadowBlur = 0;
            ctx.fillStyle = `hsla(${hue},80%,${60 + vR * 15}%,0.6)`;
            ctx.fillRect(x, y, 2, noteH);
        }
        ctx.strokeStyle = 'rgba(80,80,130,0.3)'; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.roundRect(0, 0, w, h, 8); ctx.stroke();
    }
}
const renderer = new PianoRollRenderer(DOM.pianoRoll);

// ============================================================
// Tabs
// ============================================================
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const target = tab.dataset.tab === 'library' ? DOM.tabLibrary : DOM.tabCompose;
        target.classList.add('active');
        target.style.display = '';
        (tab.dataset.tab === 'library' ? DOM.tabCompose : DOM.tabLibrary).style.display = 'none';
        if (tab.dataset.tab === 'library') loadLibrary();
    });
});

// ============================================================
// Generation
// ============================================================
async function generatePattern() {
    const prompt = DOM.promptInput.value.trim();
    if (!prompt) { setStatus('error', 'Please enter a prompt'); return; }
    const params = {
        prompt, mode: generationMode,
        time_sig: getParamValue('paramTimeSig', 'paramTimeSigCustom'),
        bars: getParamValue('paramBars', 'paramBarsCustom'),
        subdivision: DOM.paramSubdivision.value,
        category: DOM.paramCategory.value, auto_save: true
    };
    // Melodic/chord-only params
    if (generationMode !== 'drums') {
        params.key = DOM.paramKey.value;
        params.scale = getParamValue('paramScale', 'paramScaleCustom');
        params.octave_range = DOM.paramOctave.value;
    }
    // Combine all active style chips
    const combinedStyles = getActiveStylesText();
    if (combinedStyles) params.style = combinedStyles;

    // Multi-provider: collect checked providers
    const providers = [];
    if (DOM.provGemini?.checked) providers.push('gemini');
    if (DOM.provOpenAI?.checked) providers.push('openai');
    if (DOM.provClaude?.checked) providers.push('claude');
    if (providers.length) params.providers = providers;

    // Multi-iteration: how many variations
    const iterations = parseInt(DOM.paramIterations?.value || '1', 10);
    if (iterations > 1) params.iterations = iterations;

    // Reset results
    allResults = [];
    resultIndex = 0;
    if (DOM.resultCarousel) DOM.resultCarousel.style.display = 'none';

    DOM.btnGenerate.classList.add('loading');
    setStatus('generating', 'Starting generation...');
    try {
        const r = await apiPost('/api/generate', params);
        if (r.error) { setStatus('error', r.error); DOM.btnGenerate.classList.remove('loading'); return; }
        startPolling();
    } catch (e) { setStatus('error', `Network error: ${e.message}`); DOM.btnGenerate.classList.remove('loading'); }
}

function startPolling() {
    stopPolling();
    pollInterval = setInterval(async () => {
        try {
            const s = await apiGet('/api/status');
            setStatus(s.status, s.message);
            if (s.status === 'done') {
                stopPolling(); DOM.btnGenerate.classList.remove('loading');
                DOM.btnApplyModify?.classList.remove('loading');
                // Store all results for carousel
                if (s.results && s.results.length > 0) {
                    allResults = s.results;
                    resultIndex = s.result_index || 0;
                    displayPattern(allResults[resultIndex]);
                    updateCarousel();
                } else if (s.pattern) {
                    allResults = [s.pattern];
                    resultIndex = 0;
                    displayPattern(s.pattern);
                    updateCarousel();
                }
            } else if (s.status === 'error') {
                stopPolling(); DOM.btnGenerate.classList.remove('loading');
                DOM.btnApplyModify?.classList.remove('loading');
            }
        } catch (_) { }
    }, 800);
}
function stopPolling() { if (pollInterval) { clearInterval(pollInterval); pollInterval = null; } }
function setStatus(s, msg) { DOM.statusDot.className = 'status-dot ' + s; DOM.statusText.textContent = msg || s; }

// ============================================================
// Result Carousel Navigation
// ============================================================
function updateCarousel() {
    if (!DOM.resultCarousel) return;
    if (allResults.length <= 1) {
        DOM.resultCarousel.style.display = 'none';
        return;
    }
    DOM.resultCarousel.style.display = 'flex';
    DOM.carouselCounter.textContent = `${resultIndex + 1} / ${allResults.length}`;
    const r = allResults[resultIndex];
    let provLabel = '';
    if (r.provider) provLabel = r.provider.charAt(0).toUpperCase() + r.provider.slice(1);
    if (r.iteration) provLabel += ` v${r.iteration}`;
    DOM.carouselProvider.textContent = provLabel ? `via ${provLabel}` : '';
}

async function navigateResult(direction) {
    if (allResults.length <= 1) return;
    try {
        const r = await apiPost('/api/results/navigate', { direction });
        if (r.ok && r.pattern) {
            resultIndex = r.result_index;
            displayPattern(r.pattern);
            updateCarousel();
        }
    } catch (e) {
        // Fallback: navigate locally
        if (direction === 'next') resultIndex = (resultIndex + 1) % allResults.length;
        else if (direction === 'prev') resultIndex = (resultIndex - 1 + allResults.length) % allResults.length;
        displayPattern(allResults[resultIndex]);
        updateCarousel();
    }
}

DOM.btnPrevResult?.addEventListener('click', () => navigateResult('prev'));
DOM.btnNextResult?.addEventListener('click', () => navigateResult('next'));

// ============================================================
// Pattern Display
// ============================================================
function displayPattern(pattern) {
    currentPattern = pattern;
    const isDrums = pattern.type === 'drums';
    const isChords = pattern.type === 'chords';

    // Auto-set mode to match displayed pattern
    if (pattern.type && pattern.type !== generationMode) setMode(pattern.type);

    DOM.pianoRollPlaceholder.classList.add('hidden');
    renderer.render(pattern);
    DOM.patternInfo.style.display = 'grid';
    DOM.previewControls.style.display = 'flex';
    DOM.modifyPanel.style.display = 'block';
    DOM.infoName.textContent = pattern.pattern_name || 'AI Pattern';
    DOM.infoEvents.textContent = pattern.num_events || '—';
    DOM.infoLength.textContent = `${pattern.loop_length_beats} beats`;
    DOM.infoTimeSig.textContent = pattern.time_sig || '4/4';
    DOM.infoBPM.textContent = pattern.bpm_suggestion || '—';
    DOM.previewMeta.textContent = `${pattern.num_events} events • ${pattern.loop_length_beats} beats`;
    DOM.reaperHint.style.display = 'flex';

    // Mode-specific info cards
    if (DOM.infoScaleCard) DOM.infoScaleCard.style.display = isDrums ? 'none' : '';
    if (DOM.infoScale) DOM.infoScale.textContent = pattern.scale_name || '—';
    if (DOM.infoKitCard) DOM.infoKitCard.style.display = isDrums ? '' : 'none';
    if (DOM.infoKit) DOM.infoKit.textContent = pattern.kit_name || 'Standard Kit';
    if (DOM.infoTypeCard) {
        DOM.infoTypeCard.style.display = '';
        DOM.infoType.textContent = isDrums ? '🥁 Drums' : isChords ? '🎶 Chords' : '🎹 Melodic';
    }

    // Hide instrument select for drums
    if (DOM.previewInstrument) DOM.previewInstrument.style.display = isDrums ? 'none' : '';

    DOM.modBPM.placeholder = pattern.bpm_suggestion || 120;
    DOM.modBPM.value = '';

    if (pattern.library_id) {
        apiGet(`/api/library/${pattern.library_id}`).then(d => {
            if (d.pattern) { currentPatternRaw = d.pattern; pushVersion(d.pattern, pattern); }
        });
    }
}

// ============================================================
// Modify This Beat
// ============================================================
DOM.btnModifyToggle.addEventListener('click', () => {
    const body = DOM.modifyBody;
    const isExpanded = body.style.display !== 'none';
    body.style.display = isExpanded ? 'none' : 'flex';
    DOM.btnModifyToggle.classList.toggle('expanded', !isExpanded);
});

async function applyModification() {
    if (!currentPatternRaw) { setStatus('error', 'No pattern to modify'); return; }
    const modPrompt = DOM.modifyPrompt.value.trim();
    const overrides = {};
    if (DOM.modBPM.value) overrides.bpm = DOM.modBPM.value;
    if (DOM.modBars.value) overrides.bars = DOM.modBars.value;
    if (generationMode !== 'drums') {
        if (DOM.modKey.value) overrides.key = DOM.modKey.value;
        if (DOM.modScale.value) overrides.scale = DOM.modScale.value;
    }
    if (!modPrompt && Object.keys(overrides).length === 0) {
        setStatus('error', 'Describe a change or adjust a parameter'); return;
    }
    DOM.btnApplyModify.classList.add('loading');
    setStatus('generating', 'Modifying pattern...');
    try {
        const r = await apiPost('/api/modify', {
            original_pattern: currentPatternRaw, modification_prompt: modPrompt,
            overrides, mode: generationMode, category: DOM.paramCategory.value, auto_save: true
        });
        if (r.error) { setStatus('error', r.error); DOM.btnApplyModify.classList.remove('loading'); return; }
        startPolling();
    } catch (e) { setStatus('error', `Network error: ${e.message}`); DOM.btnApplyModify.classList.remove('loading'); }
}
DOM.btnApplyModify.addEventListener('click', applyModification);

// Version history
function pushVersion(rawPattern, displayPattern) {
    if (versionHistory.length > 0) {
        const last = versionHistory[versionHistory.length - 1];
        if (last.display.pattern_name === displayPattern.pattern_name &&
            last.display.num_events === displayPattern.num_events) return;
    }
    versionHistory.push({ raw: rawPattern, display: displayPattern });
    if (versionHistory.length > 5) versionHistory.shift();
    versionIndex = versionHistory.length - 1;
    renderVersionDots();
    DOM.btnRevert.style.display = versionHistory.length > 1 ? 'flex' : 'none';
}
function renderVersionDots() {
    if (versionHistory.length < 2) { DOM.versionDots.style.display = 'none'; return; }
    DOM.versionDots.style.display = 'flex';
    DOM.versionDots.innerHTML = versionHistory.map((v, i) => {
        const cls = ['version-dot']; if (i === versionIndex) cls.push('active'); if (i === 0) cls.push('original');
        return `<button class="${cls.join(' ')}" data-idx="${i}" title="V${i + 1}: ${escapeHtml(v.display.pattern_name || 'Pattern')}"></button>`;
    }).join('');
    DOM.versionDots.querySelectorAll('.version-dot').forEach(dot => { dot.addEventListener('click', () => loadVersion(parseInt(dot.dataset.idx))); });
}
function loadVersion(idx) {
    if (idx < 0 || idx >= versionHistory.length) return;
    versionIndex = idx; const v = versionHistory[idx];
    currentPatternRaw = v.raw; currentPattern = v.display;
    renderer.render(v.display);
    DOM.infoName.textContent = v.display.pattern_name || 'AI Pattern';
    DOM.infoEvents.textContent = v.display.num_events || '—';
    DOM.infoLength.textContent = `${v.display.loop_length_beats} beats`;
    DOM.infoBPM.textContent = v.display.bpm_suggestion || '—';
    DOM.modBPM.placeholder = v.display.bpm_suggestion || 120;
    renderVersionDots();
}
DOM.btnRevert.addEventListener('click', () => { if (versionIndex > 0) loadVersion(versionIndex - 1); });

// ============================================================
// MIDI Preview
// ============================================================
async function loadInstruments() {
    try { const d = await apiGet('/api/preview/instruments'); DOM.previewInstrument.innerHTML = (d.instruments || []).map((n, i) => `<option value="${i}">${i}: ${escapeHtml(n)}</option>`).join(''); } catch (_) { }
}
DOM.btnPreviewPlay.addEventListener('click', async () => {
    if (!currentPatternRaw && !currentPattern) return;
    const pattern = currentPatternRaw || currentPattern;
    const bpm = parseFloat(currentPattern?.bpm_suggestion || 120);
    const program = parseInt(DOM.previewInstrument.value || 0);
    const loop = DOM.previewLoop.checked;
    try { const r = await apiPost('/api/preview/play', { pattern, bpm, program, loop }); if (r.ok) { isPreviewPlaying = true; DOM.btnPreviewPlay.classList.add('playing'); } } catch (_) { }
});
DOM.btnPreviewStop.addEventListener('click', async () => {
    try { await apiPost('/api/preview/stop', {}); isPreviewPlaying = false; DOM.btnPreviewPlay.classList.remove('playing'); } catch (_) { }
});

// ============================================================
// Library
// ============================================================
async function loadLibrary() {
    const cat = DOM.libFilterCategory.value; const favs = DOM.libFilterFavorites.checked;
    try {
        const d = await apiGet(`/api/library/list?category=${encodeURIComponent(cat || 'All')}&favorites=${favs}`);
        renderLibrary(d.patterns || []); updateCategorySelects(d.categories || []);
    } catch (_) { DOM.libraryGrid.innerHTML = '<div class="library-empty">Failed to load library</div>'; }
}
function updateCategorySelects(categories) {
    const currentFilter = DOM.libFilterCategory.value;
    DOM.libFilterCategory.innerHTML = '<option value="All">All Categories</option>' + categories.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
    DOM.libFilterCategory.value = currentFilter;
    DOM.paramCategory.innerHTML = categories.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
    DOM.categorySelect.innerHTML = categories.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
}
function renderLibrary(patterns) {
    if (!patterns.length) { DOM.libraryGrid.innerHTML = '<div class="library-empty">No patterns saved yet. Generate a pattern to get started!</div>'; return; }
    DOM.libraryGrid.innerHTML = patterns.map(p => {
        const date = new Date(p.created_at * 1000).toLocaleDateString();
        const typeIcon = p.type === 'drums' ? '🥁' : p.type === 'chords' ? '🎶' : '🎹';
        const typeClass = p.type === 'drums' ? 'drum-type' : p.type === 'chords' ? 'chord-type' : '';
        return `<div class="lib-card ${typeClass}" data-id="${p.id}">
            <div class="lib-card-header">
                <span class="lib-card-name">${typeIcon} ${escapeHtml(p.name)}</span>
                <button class="lib-card-fav ${p.favorite ? 'active' : ''}" data-action="favorite" data-id="${p.id}" title="Toggle favorite">${p.favorite ? '★' : '☆'}</button>
            </div>
            <div class="lib-card-meta">
                <span class="lib-card-tag category">${escapeHtml(p.category || 'Uncategorized')}</span>
                <span class="lib-card-tag">${p.num_events} events</span>
                <span class="lib-card-tag">${p.loop_length_beats}b</span>
                <span class="lib-card-tag">${escapeHtml(p.time_sig || '4/4')}</span>
                ${p.type !== 'drums' ? `<span class="lib-card-tag">${escapeHtml(p.scale_name || '')}</span>` : ''}
                ${p.kit_name ? `<span class="lib-card-tag">${escapeHtml(p.kit_name)}</span>` : ''}
            </div>
            ${p.prompt ? `<div class="lib-card-prompt" title="${escapeHtml(p.prompt)}">${escapeHtml(p.prompt)}</div>` : ''}
            <div class="lib-card-actions">
                <button class="lib-btn primary" data-action="load" data-id="${p.id}">Load to REAPER</button>
                <button class="lib-btn" data-action="preview" data-id="${p.id}">Preview</button>
                <button class="lib-btn" data-action="rename" data-id="${p.id}" data-name="${escapeHtml(p.name)}">Rename</button>
                <button class="lib-btn" data-action="categorize" data-id="${p.id}" data-cat="${escapeHtml(p.category)}">Category</button>
                <button class="lib-btn danger" data-action="delete" data-id="${p.id}">Delete</button>
            </div>
        </div>`;
    }).join('');
    DOM.libraryGrid.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', e => { e.stopPropagation(); handleLibAction(btn.dataset.action, btn.dataset.id, btn.dataset); });
    });
}
async function handleLibAction(action, id, data) {
    switch (action) {
        case 'load':
            try {
                const r = await apiPost(`/api/library/${id}/load`, {});
                if (r.pattern) {
                    currentPatternRaw = null;
                    document.querySelector('.tab[data-tab="compose"]').click();
                    displayPattern(r.pattern);
                    setStatus('done', `Loaded: ${r.pattern.pattern_name}`);
                    const full = await apiGet(`/api/library/${id}`);
                    if (full.pattern) { currentPatternRaw = full.pattern; versionHistory = []; versionIndex = -1; pushVersion(full.pattern, r.pattern); }
                }
            } catch (_) { } break;
        case 'preview':
            try {
                const full = await apiGet(`/api/library/${id}`);
                if (full.pattern) { currentPatternRaw = full.pattern; const bpm = full.pattern.bpm_suggestion || 120; const program = parseInt(DOM.previewInstrument.value || 0); await apiPost('/api/preview/play', { pattern: full.pattern, bpm, program, loop: false }); isPreviewPlaying = true; }
            } catch (_) { } break;
        case 'favorite': try { await apiPost(`/api/library/${id}/favorite`, {}); loadLibrary(); } catch (_) { } break;
        case 'rename': DOM.renamePatternId.value = id; DOM.renameInput.value = data.name || ''; DOM.renameModal.classList.add('active'); DOM.renameInput.focus(); DOM.renameInput.select(); break;
        case 'categorize': DOM.categoryPatternId.value = id; DOM.categorySelect.value = data.cat || 'Uncategorized'; DOM.categoryNewInput.value = ''; DOM.categoryModal.classList.add('active'); break;
        case 'delete': if (confirm('Delete this pattern permanently?')) { try { await apiDelete(`/api/library/${id}`); loadLibrary(); } catch (_) { } } break;
    }
}

// Rename/Category saves
DOM.btnSaveRename.addEventListener('click', async () => { const id = DOM.renamePatternId.value; const name = DOM.renameInput.value.trim(); if (!name) return; await apiPost(`/api/library/${id}/rename`, { name }); DOM.renameModal.classList.remove('active'); loadLibrary(); });
DOM.btnCloseRename.addEventListener('click', () => DOM.renameModal.classList.remove('active'));
DOM.btnSaveCategory.addEventListener('click', async () => { const id = DOM.categoryPatternId.value; let cat = DOM.categoryNewInput.value.trim() || DOM.categorySelect.value; if (DOM.categoryNewInput.value.trim()) await apiPost('/api/library/categories', { name: cat }); await apiPost(`/api/library/${id}/category`, { category: cat }); DOM.categoryModal.classList.remove('active'); loadLibrary(); });
DOM.btnCloseCategory.addEventListener('click', () => DOM.categoryModal.classList.remove('active'));
DOM.libFilterCategory.addEventListener('change', loadLibrary);
DOM.libFilterFavorites.addEventListener('change', loadLibrary);

// ============================================================
// Style Chips
// ============================================================
// (Chip multi-select is handled by delegated click handler above)

// ============================================================
// Settings
// ============================================================
DOM.btnSettings.addEventListener('click', () => DOM.settingsModal.classList.add('active'));
DOM.btnCloseSettings.addEventListener('click', () => DOM.settingsModal.classList.remove('active'));
DOM.settingsModal.addEventListener('click', e => { if (e.target === DOM.settingsModal) DOM.settingsModal.classList.remove('active'); });
DOM.renameModal.addEventListener('click', e => { if (e.target === DOM.renameModal) DOM.renameModal.classList.remove('active'); });
DOM.categoryModal.addEventListener('click', e => { if (e.target === DOM.categoryModal) DOM.categoryModal.classList.remove('active'); });
DOM.btnSaveSettings.addEventListener('click', async () => {
    const d = { llm_provider: DOM.settingProvider.value };
    if (DOM.settingGeminiKey.value) d.gemini_api_key = DOM.settingGeminiKey.value;
    if (DOM.settingOpenAIKey.value) d.openai_api_key = DOM.settingOpenAIKey.value;
    if (DOM.settingClaudeKey && DOM.settingClaudeKey.value) d.claude_api_key = DOM.settingClaudeKey.value;
    // Default providers
    const defProviders = [];
    const defGem = document.getElementById('settingDefGemini');
    const defOai = document.getElementById('settingDefOpenAI');
    const defCla = document.getElementById('settingDefClaude');
    if (defGem?.checked) defProviders.push('gemini');
    if (defOai?.checked) defProviders.push('openai');
    if (defCla?.checked) defProviders.push('claude');
    if (defProviders.length) d.default_providers = defProviders;
    // Default iterations
    const defIter = document.getElementById('settingDefIterations');
    if (defIter) d.default_iterations = parseInt(defIter.value, 10);
    await apiPost('/api/config', d); DOM.settingsModal.classList.remove('active'); setStatus('idle', 'Settings saved');
});

// Open folder buttons
document.getElementById('btnOpenDataFolder')?.addEventListener('click', () => apiPost('/api/open-folder/data', {}));
document.getElementById('btnOpenLibFolder')?.addEventListener('click', () => apiPost('/api/open-folder/library', {}));

// Stop server button
document.getElementById('btnStopServer')?.addEventListener('click', async () => {
    if (!confirm('Stop the background server? You will need to run build_and_run.bat again to restart.')) return;
    try { await apiPost('/api/shutdown', {}); } catch (e) { /* expected — server dies */ }
    document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;color:#888;font-family:Inter,sans-serif;font-size:1.2rem;text-align:center;flex-direction:column;gap:12px;"><div style="font-size:2rem;">⏹</div>Server stopped.<br><small style="opacity:0.5">Run build_and_run.bat to restart.</small></div>';
});

// Ctrl+Enter
DOM.promptInput.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); generatePattern(); } });
DOM.btnGenerate.addEventListener('click', generatePattern);

// ============================================================
// Init — load config and set provider defaults
// ============================================================
async function initApp() {
    loadInstruments();
    apiGet('/api/library/list?category=All').then(d => { if (d.categories) updateCategorySelects(d.categories); }).catch(() => { });

    // Load config and set provider toggles
    try {
        const cfg = await apiGet('/api/config');
        // Settings modal
        DOM.settingProvider.value = cfg.llm_provider || 'gemini';
        // Provider availability checkboxes in compose panel
        const defProvs = cfg.default_providers || [cfg.llm_provider || 'gemini'];
        if (DOM.provGemini) { DOM.provGemini.checked = defProvs.includes('gemini'); DOM.provGemini.disabled = !cfg.has_gemini_key; }
        if (DOM.provOpenAI) { DOM.provOpenAI.checked = defProvs.includes('openai'); DOM.provOpenAI.disabled = !cfg.has_openai_key; }
        if (DOM.provClaude) { DOM.provClaude.checked = defProvs.includes('claude'); DOM.provClaude.disabled = !cfg.has_claude_key; }
        // Settings default checkboxes
        const defGem = document.getElementById('settingDefGemini');
        const defOai = document.getElementById('settingDefOpenAI');
        const defCla = document.getElementById('settingDefClaude');
        if (defGem) defGem.checked = defProvs.includes('gemini');
        if (defOai) defOai.checked = defProvs.includes('openai');
        if (defCla) defCla.checked = defProvs.includes('claude');
        // Default iterations
        const defIterSel = document.getElementById('settingDefIterations');
        if (defIterSel) defIterSel.value = String(cfg.default_iterations || 1);
        if (DOM.paramIterations) DOM.paramIterations.value = String(cfg.default_iterations || 1);
        // Dim unavailable providers
        document.querySelectorAll('.provider-toggle').forEach(tog => {
            const cb = tog.querySelector('input[type="checkbox"]');
            if (cb && cb.disabled) tog.classList.add('unavailable');
            else tog.classList.remove('unavailable');
        });
    } catch (_) { }

    setStatus('idle', 'Ready — describe your pattern and click Generate');
    setMode('melodic');
}
initApp();

// ============================================================
// Console Drawer
// ============================================================
(function() {
    const drawer = document.getElementById('consoleDrawer');
    const output = document.getElementById('consoleOutput');
    const logFileEl = document.getElementById('consoleLogFile');
    const btnToggle = document.getElementById('btnToggleConsole');
    const btnClose = document.getElementById('btnConsoleClose');
    const btnClear = document.getElementById('btnConsoleClear');
    const body = document.getElementById('consoleBody');

    if (!drawer || !output) return;

    let consolePollId = null;
    let isOpen = false;
    let autoScroll = true;

    function classifyLine(line) {
        if (line.includes('[ERROR]')) return 'log-error';
        if (line.includes('[WARNING]')) return 'log-warning';
        if (line.includes('[INFO]')) return 'log-info';
        if (line.includes('[DEBUG]')) return 'log-debug';
        if (line.includes('werkzeug') || line.includes('* Running') || line.includes('Press CTRL')) return 'log-server';
        return '';
    }

    function renderLogs(lines) {
        const wasAtBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 30;
        output.innerHTML = '';
        const frag = document.createDocumentFragment();
        for (const line of lines) {
            const span = document.createElement('span');
            span.className = 'log-line ' + classifyLine(line);
            span.textContent = line;
            frag.appendChild(span);
            frag.appendChild(document.createTextNode('\n'));
        }
        output.appendChild(frag);
        if (autoScroll && wasAtBottom) {
            body.scrollTop = body.scrollHeight;
        }
    }

    async function fetchLogs() {
        try {
            const data = await apiGet('/api/logs?lines=200');
            if (data.ok !== false) {
                if (logFileEl) logFileEl.textContent = data.log_file || '';
                renderLogs(data.lines || []);
            }
        } catch (_) { }
    }

    function openConsole() {
        isOpen = true;
        drawer.classList.add('open');
        document.body.classList.add('console-open');
        btnToggle.classList.add('active');
        fetchLogs();
        consolePollId = setInterval(fetchLogs, 2000);
    }

    function closeConsole() {
        isOpen = false;
        drawer.classList.remove('open');
        document.body.classList.remove('console-open');
        btnToggle.classList.remove('active');
        if (consolePollId) { clearInterval(consolePollId); consolePollId = null; }
    }

    function toggleConsole() {
        if (isOpen) closeConsole(); else openConsole();
    }

    btnToggle.addEventListener('click', toggleConsole);
    btnClose.addEventListener('click', closeConsole);
    btnClear.addEventListener('click', () => {
        output.innerHTML = '';
    });

    // Track scroll — disable auto-scroll if user scrolls up
    body.addEventListener('scroll', () => {
        autoScroll = body.scrollHeight - body.scrollTop - body.clientHeight < 30;
    });

    // Keyboard shortcut: backtick (`) to toggle console
    document.addEventListener('keydown', (e) => {
        if (e.key === '`' && !e.ctrlKey && !e.altKey && !e.metaKey) {
            // Don't trigger when typing in inputs
            const t = e.target.tagName;
            if (t === 'INPUT' || t === 'TEXTAREA' || t === 'SELECT') return;
            e.preventDefault();
            toggleConsole();
        }
    });
})();
