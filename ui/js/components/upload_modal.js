/**
 * upload_modal.js — File Upload + Lead Import Review Modal
 *
 * Stages:
 *   1. drop-zone / file picker
 *   2. parsing / loading
 *   3. review — grouped records, per-row actions
 *   4. committing
 *   5. results
 */
const UploadModal = (() => {

  const GROUP_LABELS = {
    relevant_now:     { label: 'דחוף — פעולה מיידית', cls: 'ug-relevant-now' },
    relevant_waiting: { label: 'רלוונטי — ממתין לתיעדוף', cls: 'ug-relevant' },
    missing_info:     { label: 'חסר מידע', cls: 'ug-missing' },
    not_relevant:     { label: 'לא רלוונטי', cls: 'ug-irrelevant' },
    duplicate:        { label: 'כפולות / קיים', cls: 'ug-dup' },
  };

  let _records = [];
  let _sourceFile = '';

  // ── Public API ────────────────────────────────────────────────────────────

  function open() {
    document.getElementById('uploadModal').classList.remove('hidden');
    _showStage('drop');
  }

  function close() {
    document.getElementById('uploadModal').classList.add('hidden');
    _records = [];
    _sourceFile = '';
  }

  // ── Init (called once on page load) ──────────────────────────────────────

  function init() {
    const modal = document.getElementById('uploadModal');
    if (!modal) return;

    // Close on overlay click
    modal.addEventListener('click', e => {
      if (e.target === modal) close();
    });

    // File input change
    document.getElementById('umFileInput').addEventListener('change', e => {
      const file = e.target.files?.[0];
      if (file) _handleFile(file);
    });

    // Drop zone
    const dz = document.getElementById('umDropZone');
    dz.addEventListener('click', () => document.getElementById('umFileInput').click());
    dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('um-drag'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('um-drag'));
    dz.addEventListener('drop', e => {
      e.preventDefault();
      dz.classList.remove('um-drag');
      const file = e.dataTransfer?.files?.[0];
      if (file) _handleFile(file);
    });

    // Commit button
    document.getElementById('umCommitBtn').addEventListener('click', _commit);

    // Batch approve all "review" and "relevant_waiting"
    document.getElementById('umApproveAllBtn')?.addEventListener('click', () => {
      _records.forEach(r => {
        if (r.group !== 'not_relevant' && r.group !== 'duplicate') r.action = 'approve';
      });
      _renderReview();
    });
  }

  // ── File handling ─────────────────────────────────────────────────────────

  async function _handleFile(file) {
    const allowed = ['csv','xlsx','xls','docx','doc','pdf','txt'];
    const ext = file.name.rsplit ? file.name.rsplit('.',1)[1] : file.name.split('.').pop();
    if (!allowed.includes((ext||'').toLowerCase())) {
      _showError(`סוג קובץ לא נתמך: .${ext}. נתמך: CSV, Excel, Word, PDF, TXT`);
      return;
    }
    _sourceFile = file.name;
    _showStage('parsing');
    document.getElementById('umParsingName').textContent = file.name;

    try {
      const fd = new FormData();
      fd.append('file', file);

      const res = await API.postForm('/intake/upload', fd);
      if (!res.success) {
        _showError(res.data?.message || res.message || 'שגיאת ניתוח');
        return;
      }

      _records = res.data?.records || [];
      _showStage('review');
      _renderReview();
      _renderGroupSummary(res.data?.groups || {});

      // Update status message
      const cnt = _records.length;
      document.getElementById('umReviewTitle').textContent =
        `נמצאו ${cnt} רשומות מתוך "${file.name}"`;
    } catch(e) {
      _showError(`שגיאה: ${e.message || e}`);
    }
  }

  // ── Review rendering ──────────────────────────────────────────────────────

  function _renderGroupSummary(groups) {
    const el = document.getElementById('umGroupSummary');
    if (!el) return;
    el.innerHTML = Object.entries(GROUP_LABELS).map(([key, meta]) => {
      const count = groups[key] || 0;
      if (!count) return '';
      return `<div class="um-gs-chip ${meta.cls}">
        <span class="um-gs-count">${count}</span>
        <span class="um-gs-label">${meta.label}</span>
      </div>`;
    }).join('');
  }

  function _renderReview() {
    const container = document.getElementById('umRecordsContainer');
    if (!container) return;

    // Group records
    const grouped = {};
    _records.forEach(r => {
      const g = r.group || 'not_relevant';
      if (!grouped[g]) grouped[g] = [];
      grouped[g].push(r);
    });

    const approvedCount = _records.filter(r => r.action === 'approve').length;
    document.getElementById('umApprovedCount').textContent = `${approvedCount} אושרו`;

    // Render each group
    const ORDER = ['relevant_now','relevant_waiting','missing_info','not_relevant','duplicate'];
    container.innerHTML = ORDER.map(key => {
      const items = grouped[key];
      if (!items?.length) return '';
      const meta = GROUP_LABELS[key];
      return `
        <div class="um-group">
          <div class="um-group-hd ${meta.cls}">
            <span>${meta.label}</span>
            <span class="um-group-count">${items.length}</span>
          </div>
          ${items.map(r => _renderRow(r)).join('')}
        </div>`;
    }).join('');
  }

  function _renderRow(rec) {
    const idx  = rec._idx;
    const name  = rec.name  || '—';
    const phone = rec.phone || '';
    const email = rec.email || '';
    const city  = rec.city  || '';
    const score = rec.score || 0;
    const reason = rec.reason || '';
    const action = rec.action || 'skip';
    const isDup  = rec.group === 'duplicate';

    return `
      <div class="um-row ${action === 'approve' ? 'um-row-approved' : ''}" id="umrow-${idx}">
        <div class="um-row-info">
          <div class="um-row-name">${name}</div>
          <div class="um-row-meta">
            ${phone ? `<span>📱 ${phone}</span>` : ''}
            ${email ? `<span>✉ ${email}</span>` : ''}
            ${city  ? `<span>📍 ${city}</span>`  : ''}
          </div>
          <div class="um-row-reason">${reason}</div>
          ${isDup ? `<div class="um-row-dup">⚠ כבר קיים: ${rec.dup_name||'—'}</div>` : ''}
          ${rec.next_action ? `<div class="um-row-next">→ ${rec.next_action}</div>` : ''}
        </div>
        <div class="um-row-score">
          <span class="score ${score>=70?'score-hot':score>=40?'score-warm':'score-cold'}" style="font-size:11px">${score}</span>
        </div>
        <div class="um-row-actions">
          <button class="um-act-btn ${action==='approve'?'um-act-active':''}"
            onclick="UploadModal.setAction(${idx},'approve')">✓ ייבא</button>
          <button class="um-act-btn ${action==='review'?'um-act-active':''}"
            onclick="UploadModal.setAction(${idx},'review')">? בדוק</button>
          <button class="um-act-btn um-act-skip ${action==='skip'?'um-act-skip-active':''}"
            onclick="UploadModal.setAction(${idx},'skip')">✕ דלג</button>
        </div>
      </div>`;
  }

  function setAction(idx, action) {
    const rec = _records.find(r => r._idx === idx);
    if (!rec) return;
    rec.action = action;
    // Update row visually
    const rowEl = document.getElementById(`umrow-${idx}`);
    if (rowEl) rowEl.outerHTML = _renderRow(rec);
    // Update approved count
    const approvedCount = _records.filter(r => r.action === 'approve').length;
    document.getElementById('umApprovedCount').textContent = `${approvedCount} אושרו`;
  }

  // ── Commit ────────────────────────────────────────────────────────────────

  async function _commit() {
    const toImport = _records.filter(r => r.action === 'approve');
    if (!toImport.length) {
      Toast.show('לא נבחרו רשומות לייבוא', 'warning');
      return;
    }

    _showStage('committing');
    document.getElementById('umCommittingCount').textContent = `מייבא ${toImport.length} רשומות...`;

    try {
      const res = await API.post('/intake/commit', {
        records: toImport,
        source_file: _sourceFile,
      });

      _showStage('results');
      const data = res.success ? (res.data || {}) : {};
      document.getElementById('umResultMsg').innerHTML = res.success
        ? `<div class="um-success">
            ✅ ${data.message || `יובאו ${data.created||0} לידים`}
            ${data.created ? `<br><button class="btn btn-primary" style="margin-top:8px" onclick="UploadModal.close();App.switchTo('leads')">הצג לידים שיובאו →</button>` : ''}
          </div>`
        : `<div class="um-error">❌ ${res.data?.message || res.message || 'שגיאת ייבוא'}</div>`;

      // Refresh home panel if visible
      if (typeof HomePanel !== 'undefined') {
        setTimeout(() => App.rerender('home'), 500);
      }
    } catch(e) {
      _showStage('results');
      document.getElementById('umResultMsg').innerHTML =
        `<div class="um-error">❌ שגיאה: ${e.message||e}</div>`;
    }
  }

  // ── Stage management ──────────────────────────────────────────────────────

  function _showStage(stage) {
    ['drop','parsing','review','committing','results'].forEach(s => {
      const el = document.getElementById(`umStage-${s}`);
      if (el) el.style.display = s === stage ? '' : 'none';
    });
  }

  function _showError(msg) {
    _showStage('drop');
    document.getElementById('umDropError').textContent = msg;
  }

  return { open, close, init, setAction };
})();

// Extend API to support FormData posts
if (typeof API !== 'undefined') {
  API.postForm = async (path, formData) => {
    try {
      const key  = API._getKey ? API._getKey() : (localStorage.getItem('os_api_key') || sessionStorage.getItem('os_api_key') || '');
      const resp = await fetch('/api' + path, {
        method: 'POST',
        headers: { 'X-API-Key': key },
        body: formData,
      });
      return await resp.json();
    } catch(e) {
      return { success: false, message: e.message || 'network error' };
    }
  };
}
