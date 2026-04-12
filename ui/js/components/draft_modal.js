/**
 * draft_modal.js — Governed Outreach Drafting Surface
 *
 * Flow: Lead context → select action type → POST /api/lead_ops/draft
 *   → preview draft → requires_approval gate → copy / submit for approval
 *
 * Usage:
 *   DraftModal.open({ id, name, city, phone, source, status, score })
 *   DraftModal.openForAction(lead, actionType)
 */
const DraftModal = (() => {

  let _lead       = null;
  let _actionType = 'first_contact';
  let _draft      = null;

  const ACTION_LABELS = {
    first_contact:    'פנייה ראשונה',
    follow_up:        'Follow-up',
    meeting_request:  'בקשת פגישה',
  };

  // ── Inject modal HTML once ─────────────────────────────────────────────────
  function _ensure() {
    if (document.getElementById('draftModalOverlay')) return;
    const el = document.createElement('div');
    el.id = 'draftModalOverlay';
    el.className = 'dm-overlay hidden';
    el.innerHTML = `
      <div class="dm-modal" role="dialog" aria-modal="true" dir="rtl">
        <div class="dm-header">
          <div class="dm-title" id="dmTitle">טיוטת פנייה</div>
          <button class="btn btn-ghost dm-close" id="dmClose" style="padding:4px 10px;font-size:14px">✕</button>
        </div>
        <div class="dm-body">
          <!-- Lead info -->
          <div class="dm-lead-row" id="dmLeadInfo"></div>

          <!-- Action type tabs -->
          <div class="dm-tabs" id="dmTabs">
            <button class="dm-tab active" data-action="first_contact">פנייה ראשונה</button>
            <button class="dm-tab" data-action="follow_up">Follow-up</button>
            <button class="dm-tab" data-action="meeting_request">בקשת פגישה</button>
          </div>

          <!-- Generate button -->
          <button class="btn btn-primary dm-gen-btn" id="dmGenerate">צור טיוטה →</button>

          <!-- Draft result -->
          <div id="dmResult" style="display:none">
            <div class="dm-draft-meta" id="dmMeta"></div>
            <div class="dm-draft-subject" id="dmSubject" style="display:none"></div>
            <div class="dm-draft-body" id="dmBody"></div>
            <div class="dm-approval-notice">
              <span style="color:var(--amber);font-weight:600">⚑ דרוש אישור</span>
              — הטיוטה מוכנה לשליחה רק לאחר אישור מפורש.
            </div>
            <div class="dm-actions">
              <button class="btn btn-ghost" id="dmCopy">📋 העתק טיוטה</button>
              <button class="btn btn-primary" id="dmApprove">✓ שלח לאישור</button>
            </div>
          </div>

          <!-- Spinner -->
          <div id="dmSpinner" style="display:none;text-align:center;padding:20px 0">
            <span style="display:inline-block;animation:spin 1s linear infinite;font-size:20px">◌</span>
            <div style="font-size:11px;color:var(--muted);margin-top:8px">מייצר טיוטה...</div>
          </div>

          <!-- Error -->
          <div id="dmError" style="display:none;color:var(--red);font-size:12px;padding:10px 0"></div>
        </div>
      </div>`;
    document.body.appendChild(el);

    el.addEventListener('click', e => {
      if (e.target === el) close();
    });
    document.getElementById('dmClose').addEventListener('click', close);

    document.getElementById('dmTabs').addEventListener('click', e => {
      const tab = e.target.closest('[data-action]');
      if (!tab) return;
      document.querySelectorAll('.dm-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      _actionType = tab.dataset.action;
      // Reset draft state when tab changes
      document.getElementById('dmResult').style.display = 'none';
      document.getElementById('dmError').style.display = 'none';
    });

    document.getElementById('dmGenerate').addEventListener('click', _generate);
    document.getElementById('dmCopy').addEventListener('click', _copy);
    document.getElementById('dmApprove').addEventListener('click', _submitApproval);
  }

  // ── Open ───────────────────────────────────────────────────────────────────
  function open(lead) {
    _ensure();
    _lead       = lead || {};
    _actionType = 'first_contact';
    _draft      = null;

    // Reset tabs
    document.querySelectorAll('.dm-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.action === 'first_contact'));

    document.getElementById('dmTitle').textContent = `טיוטה — ${_lead.name || 'ליד'}`;
    document.getElementById('dmLeadInfo').innerHTML = _leadInfoHtml(_lead);
    document.getElementById('dmResult').style.display  = 'none';
    document.getElementById('dmSpinner').style.display = 'none';
    document.getElementById('dmError').style.display   = 'none';

    document.getElementById('draftModalOverlay').classList.remove('hidden');
  }

  function openForAction(lead, actionType) {
    open(lead);
    _actionType = actionType || 'first_contact';
    document.querySelectorAll('.dm-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.action === _actionType));
  }

  function close() {
    document.getElementById('draftModalOverlay')?.classList.add('hidden');
  }

  // ── Generate ───────────────────────────────────────────────────────────────
  async function _generate() {
    if (!_lead) return;
    const genBtn = document.getElementById('dmGenerate');
    const spinner = document.getElementById('dmSpinner');
    const result  = document.getElementById('dmResult');
    const errEl   = document.getElementById('dmError');

    genBtn.disabled = true;
    spinner.style.display = '';
    result.style.display  = 'none';
    errEl.style.display   = 'none';

    try {
      const res = await API.post('/lead_ops/draft', {
        lead:        _lead,
        action_type: _actionType,
        extra:       {},
      });

      if (!res.success) {
        errEl.textContent   = `שגיאה: ${res.error || 'לא ניתן ליצור טיוטה'}`;
        errEl.style.display = '';
        return;
      }

      _draft = res;

      // Channel + tone meta
      const metaEl = document.getElementById('dmMeta');
      metaEl.innerHTML = [
        res.channel   ? `ערוץ: <strong>${_chanLabel(res.channel)}</strong>` : '',
        res.tone      ? `טון: <strong>${res.tone}</strong>` : '',
        res.language  ? `שפה: <strong>${res.language === 'he' ? 'עברית' : res.language}</strong>` : '',
      ].filter(Boolean).join(' · ');

      // Subject (if present)
      const subEl = document.getElementById('dmSubject');
      if (res.subject) {
        subEl.textContent   = `נושא: ${res.subject}`;
        subEl.style.display = '';
      } else {
        subEl.style.display = 'none';
      }

      // Body
      document.getElementById('dmBody').textContent = res.body || '';
      result.style.display = '';

    } catch(e) {
      errEl.textContent   = `שגיאה: ${e.message || e}`;
      errEl.style.display = '';
    } finally {
      genBtn.disabled       = false;
      spinner.style.display = 'none';
    }
  }

  // ── Copy ───────────────────────────────────────────────────────────────────
  function _copy() {
    if (!_draft?.body) return;
    const text = [_draft.subject ? `נושא: ${_draft.subject}\n` : '', _draft.body].join('');
    navigator.clipboard?.writeText(text).then(() => {
      const btn = document.getElementById('dmCopy');
      btn.textContent = '✓ הועתק!';
      setTimeout(() => { btn.textContent = '📋 העתק טיוטה'; }, 2000);
    }).catch(() => {
      // Fallback: select text in body element
      const sel = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(document.getElementById('dmBody'));
      sel.removeAllRanges();
      sel.addRange(range);
    });
  }

  // ── Submit for approval ────────────────────────────────────────────────────
  async function _submitApproval() {
    if (!_draft || !_lead) return;
    const btn = document.getElementById('dmApprove');
    btn.disabled = true;
    btn.textContent = 'שולח...';

    try {
      const res = await API.approvalCreate({
        action:       'send_outreach',
        action_type:  _actionType,
        risk_level:   2,
        lead_id:      _lead.id || '',
        lead_name:    _lead.name || '',
        draft_body:   _draft.body,
        draft_subject: _draft.subject || '',
        channel:      _draft.channel || '',
        rationale:    `טיוטה ל${_lead.name} — ${ACTION_LABELS[_actionType] || _actionType}`,
      });

      if (res.success) {
        Toast.success('הטיוטה נשלחה לאישור — בדוק לשונית אישורים');
        setTimeout(close, 1500);
        App.refreshBadge?.();
      } else {
        // Fallback: show copy prompt if approval endpoint missing
        Toast.info('העתק את הטיוטה ושלח ידנית לאחר אישור');
        btn.textContent = '✓ שלח לאישור';
      }
    } catch(e) {
      Toast.error('שגיאה בשליחה לאישור');
    } finally {
      btn.disabled = false;
      btn.textContent = '✓ שלח לאישור';
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────────────
  function _leadInfoHtml(l) {
    const score = l.priority_score || l.score || 0;
    const scCls = score >= 70 ? 'score-hot' : score >= 40 ? 'score-warm' : 'score-cold';
    return `
      <div style="font-weight:600;font-size:13px">${l.name || '—'}</div>
      <div style="font-size:11px;color:var(--muted);margin-top:2px">
        ${[l.city, l.source].filter(Boolean).join(' · ')}
        ${score ? ` · <span class="${scCls}" style="font-family:var(--mono)">${Math.round(score)}</span>` : ''}
      </div>`;
  }

  function _chanLabel(ch) {
    const m = { whatsapp: 'WhatsApp', phone: 'טלפון', email: 'מייל',
                sms: 'SMS', linkedin: 'LinkedIn', facebook: 'Facebook' };
    return m[ch] || ch;
  }

  return { open, openForAction, close };
})();
