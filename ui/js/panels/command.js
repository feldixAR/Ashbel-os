/**
 * command.js — Conversational Command Center (Batch 1+2)
 * Full natural language interface with draft approval flow.
 */
const CommandPanel = (() => {

  const QUICK = [
    { label: '📊 סטטוס',              cmd: 'סטטוס' },
    { label: '🔥 לידים חמים',          cmd: 'לידים חמים' },
    { label: '💡 מה יקדם הכנסות',      cmd: 'מה הכי יקדם הכנסות היום' },
    { label: '🚧 מה תקוע',             cmd: 'למה לא סוגרים' },
    { label: '📋 הצעד הבא',            cmd: 'מה הצעד הבא' },
    { label: '📈 דוח יומי',             cmd: 'דוח יומי' },
    { label: '❓ עזרה',                cmd: 'עזרה' },
  ];

  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">מרכז פקודות</div>
          <div class="section-sub">כתוב בחופשיות — עברית או אנגלית</div>
        </div>
      </div>

      <div class="cmd-box">
        <div class="cmd-label">פקודה</div>
        <div class="cmd-row">
          <input class="cmd-input" id="cmdInput"
            placeholder='למשל: שלחי הודעה לשרי / הוסף ליד יוסי כהן תל אביב 0501234567 / תקבעי פגישה עם דוד ביום חמישי'
            autocomplete="off" spellcheck="false" />
          <button class="btn btn-primary" id="cmdSubmit">שלח ↵</button>
        </div>
        <div class="quick-cmds" id="quickCmds"></div>
      </div>

      <!-- Draft approval card (hidden by default) -->
      <div class="draft-card hidden" id="draftCard">
        <div class="draft-header">
          <span id="draftTitle">טיוטה מוכנה</span>
          <span class="draft-badge" id="draftBadge">ממתין לאישור</span>
        </div>
        <div class="draft-body" id="draftBody"></div>
        <div class="draft-actions">
          <button class="btn btn-primary" id="draftApprove">✅ אשר ושלח</button>
          <button class="btn btn-ghost" id="draftEdit">✏️ ערוך</button>
          <button class="btn btn-ghost" id="draftCancel">✕ בטל</button>
        </div>
      </div>

      <div class="cmd-label" style="margin-bottom:8px;">תוצאה</div>
      <div class="output-box" id="cmdOutput" dir="rtl">ממתין לפקודה...</div>
      <div class="output-meta hidden" id="cmdMeta"></div>

      <!-- Conversation history -->
      <div id="convHistory" class="conv-history"></div>
    `;
  }

  // Conversation history (in-memory)
  const history = [];

  function init() {
    const input   = document.getElementById('cmdInput');
    const submit  = document.getElementById('cmdSubmit');
    const output  = document.getElementById('cmdOutput');
    const meta    = document.getElementById('cmdMeta');
    const quickEl = document.getElementById('quickCmds');

    // Quick buttons
    QUICK.forEach(q => {
      const btn = document.createElement('button');
      btn.className   = 'qcmd';
      btn.textContent = q.label;
      btn.onclick = () => { input.value = q.cmd; runCommand(); };
      quickEl.appendChild(btn);
    });

    submit.onclick = runCommand;
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) runCommand();
    });

    // Draft action buttons
    document.getElementById('draftApprove').onclick = approveDraft;
    document.getElementById('draftEdit').onclick    = editDraft;
    document.getElementById('draftCancel').onclick  = cancelDraft;

    let currentDraft = null;

    async function runCommand() {
      const cmd = input.value.trim();
      if (!cmd) return;

      input.value = '';
      output.textContent = '⏳ מעבד...';
      output.classList.add('loading');
      meta.classList.add('hidden');
      submit.disabled = true;
      hideDraft();

      const res = await API.command(cmd);

      output.classList.remove('loading');
      submit.disabled = false;

      if (!res.success && res.error === 'unauthorized') {
        output.textContent = '⛔ מפתח API שגוי. רענן את הדף.';
        return;
      }

      const d = res.data || {};

      // --- Needs approval (task gating) ---
      if (d.needs_approval) {
        output.textContent = `⏸ הפעולה דורשת אישור.\n${d.message || ''}`;
        Toast.info('הפעולה ממתינה לאישור');
        App.refreshBadge();
        addToHistory(cmd, d.message || 'ממתין לאישור', 'pending');
        return;
      }

      // --- Error ---
      if (!res.success) {
        const msg = d.message || res.error || 'שגיאה לא ידועה';
        output.textContent = `❌ ${msg}`;
        Toast.error('הפקודה נכשלה');
        addToHistory(cmd, msg, 'error');
        return;
      }

      const out = d.output || {};

      // --- Draft flow (Batch 2) ---
      if (out.action_type && out.needs_approval) {
        currentDraft = { cmd, out, task_id: d.task_id };
        output.textContent = d.message || '📋 טיוטה מוכנה לאישורך';
        showDraft(out);
        addToHistory(cmd, d.message || 'טיוטה מוכנה', 'draft');
        return;
      }

      // --- Hot leads list ---
      if (out.hot_leads) {
        const lines = (out.hot_leads || []).map(l =>
          `🔥 ${l.name} (${l.city || '—'}) | ${l.phone || '—'} | ציון: ${l.score}`
        );
        output.textContent = d.message + (lines.length ? '\n\n' + lines.join('\n') : '');
        Toast.success(d.message);
        addToHistory(cmd, d.message, 'success');
        return;
      }

      // --- Leads list ---
      if (out.leads_list) {
        const lines = (out.leads_list || []).map(l =>
          `• ${l.name} | ${l.status} | ציון ${l.score ?? '—'}`
        );
        output.textContent = d.message + (lines.length ? '\n\n' + lines.join('\n') : '');
        Toast.success('נטענו לידים');
        addToHistory(cmd, d.message, 'success');
        return;
      }

      // --- Revenue insights ---
      if (out.insights) {
        output.textContent = (out.insights || []).join('\n') || d.message;
        Toast.success('תובנות הכנסות');
        addToHistory(cmd, d.message, 'success');
        return;
      }

      // --- Next actions ---
      if (out.next_actions) {
        const lines = (out.next_actions || []).map(a =>
          `• ${a.name} — ${a.status}, ציון ${a.score}`
        );
        output.textContent = d.message + '\n\n' + lines.join('\n');
        Toast.success('הצעד הבא');
        addToHistory(cmd, d.message, 'success');
        return;
      }

      // --- Report ---
      if (out.report) {
        output.textContent = out.report;
        Toast.success('דוח נוצר');
        addToHistory(cmd, 'דוח יומי נוצר', 'success');
        return;
      }

      // --- Generic success ---
      let text = d.message || '✅ בוצע';
      if (Object.keys(out).length) {
        const lines = [];
        for (const [k, v] of Object.entries(out)) {
          if (typeof v !== 'object' && v !== null && v !== undefined && v !== '') {
            lines.push(`${k}: ${v}`);
          }
        }
        if (lines.length) text += '\n\n' + lines.join('\n');
      }
      output.textContent = text;
      Toast.success('בוצע בהצלחה');
      addToHistory(cmd, d.message || '✅ בוצע', 'success');

      meta.classList.remove('hidden');
      meta.textContent = `intent: ${d.intent}  |  task: ${d.task_id?.slice(0,8) || '—'}  |  trace: ${d.trace_id?.slice(0,8) || '—'}`;

      App.refreshBadge();
    }

    // ── Draft flow ─────────────────────────────────────────────────────────

    function showDraft(out) {
      const card  = document.getElementById('draftCard');
      const title = document.getElementById('draftTitle');
      const body  = document.getElementById('draftBody');

      card.classList.remove('hidden');

      if (out.action_type === 'whatsapp_draft') {
        title.textContent = `💬 הודעת WhatsApp ל${out.contact_name}`;
        body.innerHTML = `
          <div class="draft-field"><b>נמען:</b> ${out.contact_name}</div>
          <div class="draft-field"><b>הודעה:</b></div>
          <textarea class="draft-textarea" id="draftText">${out.draft_message || ''}</textarea>
        `;
      } else if (out.action_type === 'calendar_draft') {
        title.textContent = `📅 פגישה עם ${out.contact_name}`;
        body.innerHTML = `
          <div class="draft-field"><b>איש קשר:</b> ${out.contact_name}</div>
          <div class="draft-field"><b>כותרת:</b> ${out.meeting_title}</div>
          <div class="draft-field"><b>תאריך:</b> ${out.meeting_date || 'לקביעה'}</div>
          <div class="draft-field"><b>הערות:</b> ${out.notes || '—'}</div>
        `;
      } else if (out.action_type === 'reminder') {
        title.textContent = `⏰ תזכורת`;
        body.innerHTML = `
          <div class="draft-field"><b>תזכורת:</b> ${out.reminder_text}</div>
          <div class="draft-field"><b>תאריך:</b> ${out.date || 'מחר'}</div>
        `;
      } else {
        title.textContent = '📋 טיוטה';
        body.innerHTML = `<pre class="draft-raw">${JSON.stringify(out, null, 2)}</pre>`;
      }
    }

    function hideDraft() {
      document.getElementById('draftCard').classList.add('hidden');
      currentDraft = null;
    }

    function approveDraft() {
      if (!currentDraft) return;
      const textarea = document.getElementById('draftText');
      const msg = textarea ? textarea.value : '';
      Toast.success('הפעולה אושרה — בשלב הבא תישלח בפועל');
      output.textContent = `✅ אושר!\n\nבשלב הבא (Batch 5 — Integrations), ההודעה תישלח ישירות דרך WhatsApp/Calendar.`;
      hideDraft();
    }

    function editDraft() {
      const textarea = document.getElementById('draftText');
      if (textarea) textarea.focus();
    }

    function cancelDraft() {
      hideDraft();
      output.textContent = '❌ הפעולה בוטלה.';
    }
  }

  // ── Conversation history ──────────────────────────────────────────────────

  function addToHistory(cmd, response, type) {
    history.unshift({ cmd, response, type, time: new Date().toLocaleTimeString('he-IL') });
    if (history.length > 10) history.pop();
    renderHistory();
  }

  function renderHistory() {
    const el = document.getElementById('convHistory');
    if (!el || history.length === 0) return;
    el.innerHTML = `
      <div class="conv-header">היסטוריית שיחה</div>
      ${history.map(h => `
        <div class="conv-item conv-${h.type}">
          <div class="conv-time">${h.time}</div>
          <div class="conv-cmd">↗ ${h.cmd}</div>
          <div class="conv-resp">← ${h.response}</div>
        </div>
      `).join('')}
    `;
  }

  return { render, init };
})();
