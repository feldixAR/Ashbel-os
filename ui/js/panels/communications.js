/**
 * communications.js — Communications Panel
 * Sources: GET /api/outreach/queue, GET /api/outreach/followups
 * Shows pending outreach, due today, overdue items with send actions.
 */
const CommunicationsPanel = (() => {

  function render() {
    return `
      <!-- Widget bar -->
      <div class="panel-widgets">
        <div class="pw-chip">
          <div class="pw-val" id="comwTotal">—</div>
          <div class="pw-label">ממתינים לשליחה</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-amber" id="comwToday">—</div>
          <div class="pw-label">לביצוע היום</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-red" id="comwOverdue">—</div>
          <div class="pw-label">באיחור</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-green" id="comwFollowups">—</div>
          <div class="pw-label">Follow-up ממתינים</div>
        </div>
      </div>

      <div class="section-head">
        <div>
          <div class="section-title">תקשורת ופניות יוצאות</div>
          <div class="section-sub" id="comSub">טוען...</div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-ghost" id="comRefresh">↻ רענן</button>
          <button class="btn btn-primary" id="comSendAll">📤 שלח הכל</button>
        </div>
      </div>

      <!-- Tab bar -->
      <div class="leads-filter" id="comTabs">
        <button class="filter-pill active" data-tab="queue">תור שליחה</button>
        <button class="filter-pill" data-tab="followups">Follow-up</button>
      </div>

      <div id="comInsight"></div>
      <div id="comNextAction" style="margin-bottom:16px"></div>

      <!-- Queue list -->
      <div id="comQueueView">${UI.loading('טוען תור שליחה...')}</div>

      <!-- Followup list (hidden) -->
      <div id="comFollowupView" style="display:none">${UI.loading('טוען follow-ups...')}</div>
    `;
  }

  let _activeTab = 'queue';

  async function init() {
    _activeTab = 'queue';
    await loadAll();

    document.getElementById('comRefresh')?.addEventListener('click', loadAll);
    document.getElementById('comSendAll')?.addEventListener('click', sendAll);

    document.querySelectorAll('#comTabs .filter-pill').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#comTabs .filter-pill').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _activeTab = btn.dataset.tab;
        document.getElementById('comQueueView').style.display    = _activeTab === 'queue'     ? '' : 'none';
        document.getElementById('comFollowupView').style.display = _activeTab === 'followups' ? '' : 'none';
      });
    });
  }

  async function loadAll() {
    const [qRes, fRes] = await Promise.all([
      API.outreachQueue(),
      API.outreachFollowups(),
    ]);

    const tasks     = qRes.success ? (qRes.data?.daily_tasks || qRes.data?.tasks || []) : [];
    const followups = fRes.success ? (fRes.data?.records || fRes.data?.followups || []) : [];

    const today     = new Date().toISOString().slice(0, 10);
    const todayTasks   = tasks.filter(t => (t.due_date || t.scheduled_at || '').slice(0, 10) <= today);
    const overdueTasks = tasks.filter(t => {
      const d = (t.due_date || t.scheduled_at || '').slice(0, 10);
      return d && d < today;
    });

    _setText('comwTotal',     tasks.length);
    _setText('comwToday',     todayTasks.length);
    _setText('comwOverdue',   overdueTasks.length);
    _setText('comwFollowups', followups.length);
    document.getElementById('comSub').textContent =
      `${tasks.length} פניות · ${followups.length} follow-ups`;

    // Insight strip
    const iChips = [];
    if (overdueTasks.length)  iChips.push({ icon: '⚠',  text: `${overdueTasks.length} פניות באיחור`,      cls: 'insight-alert' });
    if (todayTasks.length)    iChips.push({ icon: '⏰', text: `${todayTasks.length} לביצוע היום`,          cls: 'insight-warn'  });
    if (followups.length)     iChips.push({ icon: '↩',  text: `${followups.length} follow-ups ממתינים`,   cls: 'insight-good'  });
    if (!iChips.length)       iChips.push({ icon: '✓',  text: 'אין פניות פעילות',                         cls: 'insight-good'  });
    const iEl = document.getElementById('comInsight');
    if (iEl) iEl.innerHTML = UI.insightStrip(iChips);

    // Next-action
    const firstOverdue = overdueTasks[0] || todayTasks[0];
    const naEl = document.getElementById('comNextAction');
    if (naEl && firstOverdue) {
      naEl.innerHTML = UI.nextAction(
        `שלח פנייה ל‑${firstOverdue.lead_name || firstOverdue.contact_name || '—'} — ${firstOverdue.channel || 'whatsapp'}`
      );
    } else if (naEl) { naEl.innerHTML = ''; }

    renderQueue(tasks);
    renderFollowups(followups);
  }

  function renderQueue(tasks) {
    const el  = document.getElementById('comQueueView');
    const now = new Date().toISOString().slice(0, 10);

    if (!tasks.length) { el.innerHTML = UI.empty('אין פניות ממתינות', '📭'); return; }

    el.innerHTML = tasks.map(t => {
      const dueDate   = (t.due_date || t.scheduled_at || '').slice(0, 10);
      const isOverdue = dueDate && dueDate < now;
      const channel   = t.channel || 'whatsapp';

      return `
        <div class="comm-item ${isOverdue ? 'overdue' : ''}">
          <div style="font-size:16px;flex-shrink:0">${channel === 'whatsapp' ? '📱' : channel === 'email' ? '📧' : '📤'}</div>
          <div class="comm-info">
            <div class="comm-name">${t.lead_name || t.contact_name || '—'}</div>
            <div class="comm-action">${(t.message || t.action || '—').slice(0, 80)}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0">
            <div class="comm-due ${isOverdue ? 'overdue' : ''}">${dueDate || '—'}</div>
            ${t.deep_link
              ? `<a href="${t.deep_link}" target="_blank" class="btn btn-primary" style="font-size:10px;padding:4px 10px;text-decoration:none">📱 שלח</a>`
              : `<button class="btn btn-primary" style="font-size:10px;padding:4px 10px"
                         onclick="CommunicationsPanel.executeOutreach('${t.lead_id || t.id || ''}')">שלח</button>`}
          </div>
        </div>
      `;
    }).join('');
  }

  function renderFollowups(followups) {
    const el  = document.getElementById('comFollowupView');
    const now = new Date().toISOString().slice(0, 10);

    if (!followups.length) { el.innerHTML = UI.empty('אין follow-ups ממתינים', '✓'); return; }

    el.innerHTML = followups.map(f => {
      const nextDate  = (f.next_action_at || f.next_followup || '').slice(0, 10);
      const isOverdue = nextDate && nextDate < now;

      return `
        <div class="comm-item ${isOverdue ? 'overdue' : ''}">
          <div style="font-size:16px;flex-shrink:0">⏰</div>
          <div class="comm-info">
            <div class="comm-name">${f.contact_name || f.lead_name || '—'}</div>
            <div class="comm-action">${f.channel || 'whatsapp'} · ניסיון ${f.attempt || 1}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0">
            <div class="comm-due ${isOverdue ? 'overdue' : ''}">${nextDate || '—'}</div>
            ${f.deep_link
              ? `<a href="${f.deep_link}" target="_blank" class="btn btn-ghost" style="font-size:10px;padding:4px 10px;text-decoration:none">📱 פתח</a>`
              : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  async function executeOutreach(leadId) {
    if (!leadId) return;
    const res = await API.post('/outreach/execute', { lead_id: leadId });
    if (res.success) {
      Toast.success('פניה נשלחה בהצלחה');
      await loadAll();
    } else {
      Toast.error(res.error || 'שגיאה בשליחת פניה');
    }
  }

  async function sendAll() {
    const btn = document.getElementById('comSendAll');
    btn.disabled = true;
    btn.textContent = '...שולח';
    const res = await API.post('/command', { command: 'שלח פניות' });
    btn.disabled = false;
    btn.textContent = '📤 שלח הכל';
    Toast.show(
      res.success ? `✅ ${res.data?.message || 'פניות נשלחו'}` : `❌ ${res.error || 'שגיאה'}`,
      res.success ? 'success' : 'error'
    );
    await loadAll();
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  return { render, init, executeOutreach };
})();
