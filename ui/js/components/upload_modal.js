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
    hot_now:          { label: 'חם עכשיו — פעולה היום', cls: 'ug-relevant-now' },
    clarify_aluminum: { label: 'לברר אלומיניום', cls: 'ug-relevant' },
    follow_up_future: { label: 'מעקב עתידי', cls: 'ug-relevant' },
    relevant_now:     { label: 'דחוף — פעולה מיידית', cls: 'ug-relevant-now' },
    relevant_waiting: { label: 'רלוונטי — ממתין לתיעדוף', cls: 'ug-relevant' },
    missing_info:     { label: 'חסר מידע', cls: 'ug-missing' },
    not_relevant:     { label: 'לא רלוונטי', cls: 'ug-irrelevant' },
    duplicate:        { label: 'כפולות / קיים', cls: 'ug-dup' },
  };

  let _records = [];
  let _sourceFile = '';
  let _importRunId = '';
  let _approvalId = '';

  function open() {
    document.getElementById('uploadModal').classList.remove('hidden');
    _resetFileInput();
    _showStage('drop');
  }

  function close() {
    document.getElementById('uploadModal').classList.add('hidden');
    _records = [];
    _sourceFile = '';
    _importRunId = '';
    _approvalId = '';
    _resetFileInput();
    const err = document.getElementById('umDropError');
    if (err) err.textContent = '';
  }

  function init() {
    const modal = document.getElementById('uploadModal');
    if (!modal) return;

    modal.addEventListener('click', e => {
      if (e.target === modal) close();
    });

    document.getElementById('umFileInput').addEventListener('change', e => {
      const file = e.target.files?.[0];
      if (file) _handleFile(file);
    });

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

    document.getElementById('umCommitBtn').addEventListener('click', _commit);

    const approveAll = document.getElementById('umApproveAllBtn');
    if (approveAll) {
      approveAll.textContent = 'אשר לידים מומלצים בלבד';
      approveAll.addEventListener('click', () => {
        _records.forEach(r => {
          if (['hot_now','relevant_now','relevant_waiting'].includes(r.group)) r.action = 'approve';
          else if (r.group !== 'duplicate' && r.group !== 'not_relevant') r.action = 'review';
        });
        _renderReview();
      });
    }
  }

  async function _handleFile(file) {
    const allowed = ['csv','xlsx','xls','docx','doc','pdf','txt'];
    const ext = file.name.split('.').pop();
    const err = document.getElementById('umDropError');
    if (err) err.textContent = '';
    if (!allowed.includes((ext||'').toLowerCase())) {
      _showError(`סוג קובץ לא נתמך: .${ext}. נתמך: CSV, Excel, Word, PDF, TXT`);
      _resetFileInput();
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
        _showError(_extractError(res, 'שגיאת ניתוח'));
        return;
      }

      _records = res.data?.records || [];
      _importRunId = res.data?.import_run_id || '';
      _approvalId = '';
      _showStage('review');
      _renderReview();
      _renderGroupSummary(res.data?.groups || {});

      const cnt = _records.length;
      document.getElementById('umReviewTitle').textContent =
        `נמצאו ${cnt} רשומות מתוך "${file.name}"`;
    } catch(e) {
      _showError(`שגיאה: ${e.message || e}`);
    } finally {
      _resetFileInput();
    }
  }

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

    const grouped = {};
    _records.forEach(r => {
      const g = r.group || 'not_relevant';
      if (!grouped[g]) grouped[g] = [];
      grouped[g].push(r);
    });

    const approvedCount = _records.filter(r => r.action === 'approve').length;
    document.getElementById('umApprovedCount').textContent = `${approvedCount} אושרו`;

    const commitBtn = document.getElementById('umCommitBtn');
    if (commitBtn) commitBtn.textContent = 'העבר לאישור ייבוא';

    const ORDER = ['hot_now','clarify_aluminum','follow_up_future','relevant_now','relevant_waiting','missing_info','not_relevant','duplicate'];
    container.innerHTML = ORDER.map(key => {
      const items = grouped[key];
      if (!items?.length) return '';
      const meta = GROUP_LABELS[key] || GROUP_LABELS.not_relevant;
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
    const name  = _esc(rec.name  || '—');
    const phone = _esc(rec.phone || '');
    const email = _esc(rec.email || '');
    const city  = _esc(rec.city  || '');
    const score = rec.score_total || rec.score || 0;
    const reason = _esc(rec.business_reason || rec.reason || '');
    const action = rec.action || 'skip';
    const isDup  = rec.group === 'duplicate';
    const intent = _esc(rec.aluminum_intent_label || 'לא זוהתה כוונת אלומיניום');
    const stage = _esc(rec.construction_stage_label || 'שלב לא מזוהה');
    const timing = _esc(rec.timing_window || 'בדיקה ידנית');
    const recommended = _esc(rec.recommended_action || rec.next_action || 'בדיקה ידנית');
    const missing = Array.isArray(rec.missing_fields) ? rec.missing_fields.filter(Boolean) : [];
    const breakdown = rec.score_breakdown || {};

    return `
      <div class="um-row ${action === 'approve' ? 'um-row-approved' : ''}" id="umrow-${idx}">
        <div class="um-row-info">
          <div class="um-row-name">${name}</div>
          <div class="um-row-meta">
            ${phone ? `<span>📱 ${phone}</span>` : ''}
            ${email ? `<span>✉ ${email}</span>` : ''}
            ${city  ? `<span>📍 ${city}</span>`  : ''}
          </div>
          <div class="um-business-badges">
            <span>${intent}</span>
            <span>שלב: ${stage}</span>
            <span>חלון פעולה: ${timing}</span>
          </div>
          <div class="um-row-reason">${reason}</div>
          <div class="um-row-next">→ ${recommended}</div>
          ${missing.length ? `<div class="um-row-missing">חסר להצעה: ${missing.map(_esc).join(', ')}</div>` : ''}
          <div class="um-score-breakdown">
            ניקוד: כוונה ${breakdown.intent ?? 0}, תזמון ${breakdown.timing ?? 0}, קשר ${breakdown.contactability ?? 0}, היקף ${breakdown.scope ?? 0}, מיקום ${breakdown.geography ?? 0}, מוכנות ${breakdown.readiness ?? 0}
          </div>
          ${isDup ? `<div class="um-row-dup">⚠ כבר קיים: ${_esc(rec.dup_name||'—')}</div>` : ''}
        </div>
        <div class="um-row-score">
          <span class="score ${score>=70?'score-hot':score>=40?'score-warm':'score-cold'}" style="font-size:11px">${score}</span>
        </div>
        <div class="um-row-actions">
          <button class="um-act-btn ${action==='approve'?'um-act-active':''}"
            onclick="UploadModal.setAction(${idx},'approve')">✓ סמן לייבוא</button>
          <button class="um-act-btn ${action==='review'?'um-act-active':''}"
            onclick="UploadModal.setAction(${idx},'review')">? דורש בדיקה</button>
          <button class="um-act-btn um-act-skip ${action==='skip'?'um-act-skip-active':''}"
            onclick="UploadModal.setAction(${idx},'skip')">✕ דלג</button>
        </div>
      </div>`;
  }

  function setAction(idx, action) {
    const rec = _records.find(r => r._idx === idx);
    if (!rec) return;
    rec.action = action;
    const rowEl = document.getElementById(`umrow-${idx}`);
    if (rowEl) rowEl.outerHTML = _renderRow(rec);
    const approvedCount = _records.filter(r => r.action === 'approve').length;
    document.getElementById('umApprovedCount').textContent = `${approvedCount} אושרו`;
  }

  async function _commit() {
    const toImport = _records.filter(r => r.action === 'approve');
    if (!toImport.length) {
      Toast.show('לא נבחרו רשומות לייבוא', 'warning');
      return;
    }

    _showStage('committing');
    document.getElementById('umCommittingCount').textContent = _approvalId
      ? `בודק אישור ומייבא ${toImport.length} רשומות...`
      : `מעביר ${toImport.length} רשומות לאישור ייבוא...`;

    try {
      if (_approvalId) {
        const approved = await _isApprovalApproved(_approvalId);
        if (!approved) {
          _showStage('results');
          _renderApprovalPending(_approvalId);
          return;
        }
      }

      const res = await API.post('/intake/commit', {
        records: toImport,
        source_file: _sourceFile,
        import_run_id: _importRunId,
        approval_id: _approvalId,
      });

      _showStage('results');
      const data = res.success ? (res.data || {}) : {};
      if (res.success && data.approval_required && data.approval_id) {
        _approvalId = data.approval_id;
        _renderApprovalPending(data.approval_id);
        return;
      }
      document.getElementById('umResultMsg').innerHTML = res.success
        ? `<div class="um-success">
            ✅ ${data.message || `יובאו ${data.created||0} לידים`}
            ${data.created ? `<br><button class="btn btn-primary" style="margin-top:8px" onclick="UploadModal.close();Shell.switchTab('leads')">הצג לידים שיובאו →</button>` : ''}
          </div>`
        : `<div class="um-error">❌ ${_humanError(res, 'שגיאת ייבוא')}</div>`;

      if (typeof HomePanel !== 'undefined') {
        setTimeout(() => App.rerender('home'), 500);
      }
    } catch(e) {
      _showStage('results');
      document.getElementById('umResultMsg').innerHTML =
        `<div class="um-error">❌ שגיאה: ${e.message||e}</div>`;
    }
  }

  async function _isApprovalApproved(id) {
    try {
      const [pending, history] = await Promise.all([
        API.approvals ? API.approvals() : API.get('/approvals'),
        API.approvalHistory ? API.approvalHistory(100) : API.get('/approvals/history?limit=100'),
      ]);
      const pendingItem = (pending?.data?.approvals || []).find(a => a.id === id);
      if (pendingItem) return false;
      const resolvedItem = (history?.data?.history || []).find(a => a.id === id);
      return resolvedItem?.status === 'approved';
    } catch (_) {
      return false;
    }
  }

  function _renderApprovalPending(id) {
    document.getElementById('umResultMsg').innerHTML = `<div class="um-warning">
      נוצרה בקשת אישור ייבוא. עדיין לא נכתבו לידים למערכת ולא נשלחה שום הודעה ללקוחות.<br>
      אישור: <code>${_esc(id)}</code><br>
      <div style="margin-top:8px;color:var(--muted);font-size:12px">
        יש לפתוח את מסך האישורים, לאשר את בקשת הייבוא הזו ואז לחזור לכאן וללחוץ שוב על השלמת הייבוא.
      </div>
      <button class="btn btn-primary" style="margin-top:8px" onclick="Shell.switchTab('approvals')">פתח אישורים</button>
      <button class="btn btn-ghost" style="margin-top:8px" onclick="UploadModal.retryCommit()">בדוק שוב והשלם ייבוא</button>
    </div>`;
  }

  function _humanError(res, fallback) {
    const msg = _extractError(res, fallback);
    if (msg === 'import approval is not approved') {
      return 'בקשת הייבוא עדיין לא אושרה. פתח את מסך האישורים, אשר את בקשת import_commit ואז לחץ שוב על השלמת הייבוא.';
    }
    if (msg === 'approval_id not found') return 'בקשת האישור לא נמצאה. יש ליצור בקשת ייבוא חדשה.';
    if (msg === 'approval_id is not an import approval') return 'האישור שנבחר אינו אישור ייבוא.';
    if (msg === 'approval_id does not match source_file') return 'האישור אינו שייך לקובץ הזה. יש ליצור בקשת ייבוא חדשה.';
    return msg;
  }

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

  function _extractError(res, fallback) {
    return res?.error || res?.data?.message || res?.message || fallback;
  }

  function _resetFileInput() {
    const input = document.getElementById('umFileInput');
    if (input) input.value = '';
  }

  function _esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
  }

  function retryCommit() {
    if (!_approvalId) {
      Toast.show('אין approval_id לייבוא הזה', 'warning');
      return;
    }
    _commit();
  }

  return { open, close, init, setAction, retryCommit };
})();

if (typeof API !== 'undefined') {
  API.postForm = async (path, formData) => {
    try {
      const key  = API._getKey ? API._getKey() : (
        sessionStorage.getItem('ashbal_api_key') ||
        localStorage.getItem('ashbal_api_key_r') ||
        ''
      );
      const resp = await fetch('/api' + path, {
        method: 'POST',
        headers: { 'X-API-Key': key },
        body: formData,
      });
      return await resp.json();
    } catch(e) {
      return { success: false, data: null, error: e.message || 'network error' };
    }
  };
}

(function loadQAConsole() {
  if (document.getElementById('qaConsoleScript')) return;
  const s = document.createElement('script');
  s.id = 'qaConsoleScript';
  s.src = '/ui/js/panels/qa_console.js?v=qa1';
  document.head.appendChild(s);
})();
