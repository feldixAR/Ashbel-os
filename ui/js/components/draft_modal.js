/**
 * draft_modal.js — AI Drafting Studio
 * Governed flow: Lead context → action type → generate → tone/refine → approve
 */
const DraftModal = (() => {

  let _lead       = null;
  let _actionType = 'first_contact';
  let _draft      = null;
  let _initialized = false;

  const ACTION_LABELS = {
    first_contact:    'פנייה ראשונה',
    follow_up:        'Follow-up',
    meeting_request:  'בקשת פגישה',
    inbound_response: 'מענה לפנייה',
  };

  const TONE_ACTIONS = [
    { label: 'קצר יותר',    instruction: 'קצר את הטיוטה לחצי מהגודל המקורי, שמור על הנקודות החשובות' },
    { label: 'פורמלי',      instruction: 'הפוך את הטון לפורמלי ומקצועי יותר' },
    { label: 'ישיר יותר',   instruction: 'הפוך את הטון לישיר ועסקי יותר, ללא הקדמות מיותרות' },
    { label: 'חמותי יותר',  instruction: 'הפוך את הטון לחמותי ואישי יותר, יצירת חיבור אנושי' },
    { label: 'מכירתי יותר', instruction: 'הוסף ערך מכירתי ברור וקריאה לפעולה חזקה' },
  ];

  // ── Inject modal HTML once ─────────────────────────────────────────────────
  function _ensure() {
    if (_initialized) return;
    _initialized = true;

    const el = document.createElement('div');
    el.id = 'draftModalOverlay';
    el.className = 'dm-overlay hidden';
    el.innerHTML = `
      <div class="dm-modal" role="dialog" aria-modal="true">
        <div class="dm-header">
          <div class="dm-title" id="dmTitle">טיוטת פנייה</div>
          <button class="btn btn-ghost dm-close" id="dmClose">✕</button>
        </div>
        <div class="dm-body">
          <div class="dm-lead-row" id="dmLeadInfo"></div>

          <div class="dm-tabs" id="dmTabs">
            <button class="dm-tab active" data-action="first_contact">פנייה ראשונה</button>
            <button class="dm-tab" data-action="follow_up">Follow-up</button>
            <button class="dm-tab" data-action="meeting_request">בקשת פגישה</button>
          </div>

          <button class="btn btn-primary dm-gen-btn" id="dmGenerate">✦ צור טיוטה</button>

          <div id="dmSpinner" style="display:none;text-align:center;padding:16px">
            <div class="wl-spinner"></div>
            <div style="font-size:11px;color:var(--muted);margin-top:6px">מייצר טיוטה...</div>
          </div>

          <div id="dmError" style="display:none;color:var(--red);font-size:12px;padding:8px 0"></div>

          <div id="dmResult" style="display:none">
            <div class="dm-draft-meta" id="dmMeta"></div>
            <div class="dm-draft-subject" id="dmSubject" style="display:none"></div>
            <textarea class="dm-draft-body" id="dmBody" dir="rtl" spellcheck="false"></textarea>

            <!-- Tone controls -->
            <div class="dm-tone-bar">
              <span class="dm-tone-lbl">שנה טון:</span>
              ${TONE_ACTIONS.map(t =>
                `<button class="dm-tone-btn" onclick="DraftModal._refineWith('${t.instruction.replace(/'/g,"\\'")}')">${t.label}</button>`
              ).join('')}
            </div>

            <!-- Custom refine -->
            <div class="dm-refine-row">
              <input class="dm-refine-input" id="dmRefineInput" dir="rtl"
                placeholder="הנחיה מותאמת: למשל — הדגש מחיר, הזכר ניסיון, קצר ל-3 שורות..." />
              <button class="btn btn-ghost btn-sm" id="dmRefineBtn">שפר ↻</button>
            </div>

            <div class="dm-approval-notice">
              <span style="color:var(--amber);font-weight:600">⚑ דרוש אישור</span>
              — הטיוטה תשלח רק לאחר אישור מפורש.
            </div>

            <div class="dm-actions">
              <button class="btn btn-ghost btn-sm" id="dmCopy">📋 העתק</button>
              <button class="btn btn-ghost btn-sm" id="dmWhatsApp" style="display:none">💬 WhatsApp</button>
              <button class="btn btn-ghost btn-sm" id="dmRegenerate">↺ נסח מחדש</button>
              <button class="btn btn-primary btn-sm" id="dmApprove">✓ שלח לאישור</button>
            </div>
          </div>
        </div>
      </div>`;
    document.body.appendChild(el);

    el.addEventListener('click', e => { if (e.target === el) close(); });
    document.getElementById('dmClose').addEventListener('click', close);

    document.getElementById('dmTabs').addEventListener('click', e => {
      const tab = e.target.closest('[data-action]');
      if (!tab) return;
      document.querySelectorAll('.dm-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      _actionType = tab.dataset.action;
      document.getElementById('dmResult').style.display = 'none';
      document.getElementById('dmError').style.display  = 'none';
    });

    document.getElementById('dmGenerate').addEventListener('click', _generate);
    document.getElementById('dmRegenerate').addEventListener('click', _generate);
    document.getElementById('dmCopy').addEventListener('click', _copy);
    document.getElementById('dmWhatsApp').addEventListener('click', _openWhatsApp);
    document.getElementById('dmApprove').addEventListener('click', _submitApproval);
    document.getElementById('dmRefineBtn').addEventListener('click', () => {
      const instr = document.getElementById('dmRefineInput')?.value?.trim();
      if (instr) _refineWith(instr);
    });
    document.getElementById('dmRefineInput')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        const instr = e.target.value.trim();
        if (instr) _refineWith(instr);
      }
    });
  }

  // ── Open ───────────────────────────────────────────────────────────────────
  function open(lead, actionType) {
    _ensure();
    _lead       = lead || {};
    _actionType = actionType || 'first_contact';
    _draft      = null;

    document.querySelectorAll('.dm-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.action === _actionType));

    document.getElementById('dmTitle').textContent    = `טיוטה — ${_lead.name || 'ליד'}`;
    document.getElementById('dmLeadInfo').innerHTML   = _leadInfoHtml(_lead);
    document.getElementById('dmResult').style.display  = 'none';
    document.getElementById('dmSpinner').style.display = 'none';
    document.getElementById('dmError').style.display   = 'none';

    document.getElementById('draftModalOverlay').classList.remove('hidden');
  }

  function close() {
    document.getElementById('draftModalOverlay')?.classList.add('hidden');
  }

  // ── Generate ───────────────────────────────────────────────────────────────
  async function _generate() {
    if (!_lead) return;
    _setLoading(true);
    try {
      const res = await API.post('/lead_ops/draft', {
        lead: _lead, action_type: _actionType, extra: {},
      });
      if (!res.success) {
        _showError(`שגיאה: ${res.error || 'לא ניתן ליצור טיוטה'}`);
        return;
      }
      _draft = res;
      _showDraft(res);
    } catch (e) {
      _showError(`שגיאה: ${e.message || e}`);
    } finally {
      _setLoading(false);
    }
  }

  // ── Refine with instruction ────────────────────────────────────────────────
  async function _refineWith(instruction) {
    const bodyEl = document.getElementById('dmBody');
    if (!bodyEl) return;
    const currentBody = bodyEl.value.trim();
    if (!currentBody) return;

    _setLoading(true);
    try {
      const res = await API.draftRefine(currentBody, instruction, _lead);
      if (res.success && res.body) {
        bodyEl.value = res.body;
        Toast.success('הטיוטה עודכנה');
        // Clear refine input
        const ri = document.getElementById('dmRefineInput');
        if (ri) ri.value = '';
      } else {
        Toast.error(res.error || 'לא ניתן לשפר כרגע');
      }
    } catch (e) {
      Toast.error(`שגיאה: ${e.message || e}`);
    } finally {
      _setLoading(false);
    }
  }

  // ── Show draft result ──────────────────────────────────────────────────────
  function _showDraft(res) {
    document.getElementById('dmError').style.display  = 'none';
    const metaEl = document.getElementById('dmMeta');
    metaEl.innerHTML = [
      res.channel  ? `ערוץ: <strong>${_chanLabel(res.channel)}</strong>`   : '',
      res.tone     ? `טון: <strong>${res.tone}</strong>`                    : '',
      res.language ? `שפה: <strong>${res.language === 'he' ? 'עברית' : res.language}</strong>` : '',
    ].filter(Boolean).join(' · ');

    const subEl = document.getElementById('dmSubject');
    if (res.subject) { subEl.textContent = `נושא: ${res.subject}`; subEl.style.display = ''; }
    else { subEl.style.display = 'none'; }

    document.getElementById('dmBody').value = res.body || '';

    // WhatsApp button — show only if we have a phone number
    const waBtn = document.getElementById('dmWhatsApp');
    if (waBtn) waBtn.style.display = _lead.phone ? '' : 'none';

    document.getElementById('dmResult').style.display = '';
  }

  // ── Copy ───────────────────────────────────────────────────────────────────
  function _copy() {
    const bodyEl = document.getElementById('dmBody');
    if (!bodyEl) return;
    const subjEl = document.getElementById('dmSubject');
    const text = [
      subjEl?.style.display !== 'none' ? subjEl.textContent + '\n' : '',
      bodyEl.value,
    ].join('');
    navigator.clipboard?.writeText(text).then(() => {
      const btn = document.getElementById('dmCopy');
      btn.textContent = '✓ הועתק!';
      setTimeout(() => { btn.textContent = '📋 העתק'; }, 2000);
    }).catch(() => { bodyEl.select(); });
  }

  // ── WhatsApp deeplink ──────────────────────────────────────────────────────
  function _openWhatsApp() {
    const bodyEl = document.getElementById('dmBody');
    if (!bodyEl || !_lead?.phone) return;
    const phone = _lead.phone.replace(/\D/g, '');
    const intl  = phone.startsWith('0') ? '972' + phone.slice(1) : phone;
    const text  = encodeURIComponent(bodyEl.value);
    window.open(`https://wa.me/${intl}?text=${text}`, '_blank');
  }

  // ── Submit for approval ────────────────────────────────────────────────────
  async function _submitApproval() {
    const bodyEl = document.getElementById('dmBody');
    if (!bodyEl || !_lead) return;
    const currentBody = bodyEl.value.trim();
    if (!currentBody) { Toast.error('הטיוטה ריקה'); return; }

    const btn = document.getElementById('dmApprove');
    btn.disabled = true;
    btn.textContent = 'שולח...';

    try {
      const res = await API.approvalCreate({
        action:        'send_outreach',
        action_type:   _actionType,
        risk_level:    2,
        lead_id:       _lead.id || _lead.lead_id || '',
        lead_name:     _lead.name || '',
        draft_body:    currentBody,
        draft_subject: _draft?.subject || '',
        channel:       _draft?.channel || '',
        rationale:     `טיוטה ל${_lead.name} — ${ACTION_LABELS[_actionType] || _actionType}`,
      });

      if (res.success) {
        Toast.success('הטיוטה נשלחה לאישור — בדוק לשונית אישורים');
        setTimeout(close, 1200);
        // Refresh approval badge
        try { Shell.switchTab && Shell.currentTab() === 'approvals' && Shell.switchTab('approvals'); } catch(_) {}
      } else {
        Toast.info('העתק את הטיוטה ושלח ידנית לאחר אישור');
      }
    } catch (e) {
      Toast.error('שגיאה בשליחה לאישור');
    } finally {
      btn.disabled = false;
      btn.textContent = '✓ שלח לאישור';
    }
  }

  // ── Internal helpers ───────────────────────────────────────────────────────
  function _setLoading(on) {
    const spinner = document.getElementById('dmSpinner');
    const genBtn  = document.getElementById('dmGenerate');
    const refBtn  = document.getElementById('dmRefineBtn');
    if (spinner) spinner.style.display = on ? '' : 'none';
    if (genBtn)  genBtn.disabled = on;
    if (refBtn)  refBtn.disabled = on;
  }

  function _showError(msg) {
    const errEl = document.getElementById('dmError');
    if (errEl) { errEl.textContent = msg; errEl.style.display = ''; }
  }

  function _leadInfoHtml(l) {
    const score = l.priority_score || l.score || 0;
    const scCls = score >= 70 ? 'score-hot' : score >= 40 ? 'score-warm' : 'score-cold';
    return `
      <strong style="font-size:13px">${l.name || '—'}</strong>
      <span style="font-size:11px;color:var(--muted);margin-right:8px">
        ${[l.city, l.source, l.phone].filter(Boolean).join(' · ')}
        ${score ? ` · <span class="score ${scCls}" style="font-family:var(--mono)">${Math.round(score)}</span>` : ''}
      </span>`;
  }

  function _chanLabel(ch) {
    const m = { whatsapp:'WhatsApp', phone:'טלפון', email:'מייל',
                sms:'SMS', linkedin:'LinkedIn', facebook:'Facebook' };
    return m[ch] || ch;
  }

  return { open, close, _refineWith };
})();
