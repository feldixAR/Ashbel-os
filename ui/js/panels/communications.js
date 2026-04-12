/**
 * communications.js — Communications Panel
 * Sources: GET /api/outreach/queue, /api/outreach/followups,
 *          GET /api/outreach/summary, GET /api/outreach/pipeline
 */
const CommunicationsPanel = (() => {

  const LIFECYCLE_HE = {
    sent:               'נשלח',
    awaiting_response:  'ממתין לתגובה',
    followup_due:       'Follow-up נדרש',
    followup_sent:      'Follow-up נשלח',
    closed_won:         'נסגר — עסקה',
    closed_lost:        'נסגר — ללא עסקה',
  };
  const LIFECYCLE_CLS = {
    sent:              '',
    awaiting_response: 'pv-amber',
    followup_due:      'pv-red',
    followup_sent:     'pv-accent',
    closed_won:        'pv-green',
    closed_lost:       'pv-red',
  };

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
        <button class="filter-pill" data-tab="pipeline">מצב שוטף</button>
      </div>

      <div id="comInsight"></div>
      <div id="comNextAction" style="margin-bottom:16px"></div>

      <!-- Queue list -->
      <div id="comQueueView">${UI.loading('טוען תור שליחה...')}</div>

      <!-- Followup list (hidden) -->
      <div id="comFollowupView" style="display:none">${UI.loading('טוען follow-ups...')}</div>

      <!-- Pipeline list (hidden) -->
      <div id="comPipelineView" style="display:none">${UI.loading('טוען pipeline...')}</div>
    `;
  }

  let _activeTab = 'queue';
  let _pipeline  = [];

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
        document.getElementById('comQueueView').style.display    = _activeTab === 'queue'    ? '' : 'none';
        document.getElementById('comFollowupView').style.display = _activeTab === 'followups'? '' : 'none';
        document.getElementById('comPipelineView').style.display = _activeTab === 'pipeline' ? '' : 'none';
      });
    });
  }

  async function loadAll() {
    const [qRes, fRes, sumRes, pipeRes] = await Promise.all([
      API.outreachQueue(),
      API.outreachFollowups(),
      API.outreachSummary().catch(() => ({ success: false })),
      API.outreachPipeline().catch(() => ({ success: false })),
    ]);

    const tasks     = qRes.success  ? (qRes.data?.daily_tasks || qRes.data?.tasks || []) : [];
    const followups = fRes.success  ? (fRes.data?.records || fRes.data?.followups || [])  : [];
    _pipeline       = pipeRes.success ? (pipeRes.data?.pipeline || []) : [];

    // Prefer server-side aggregate counts from /summary if available
    const sum = sumRes.success ? sumRes.data : null;
    const today = new Date().toISOString().slice(0, 10);
    const todayTasks   = tasks.filter(t => (t.due_date || t.scheduled_at || '').slice(0, 10) <= today);
    const overdueTasks = tasks.filter(t => {
      const d = (t.due_date || t.scheduled_at || '').slice(0, 10);
      return d && d < today;
    });

    _setText('comwTotal',     sum ? sum.total_due : tasks.length);
    _setText('comwToday',     sum ? sum.pending   : todayTasks.length);
    _setText('comwOverdue',   sum ? sum.overdue   : overdueTasks.length);
    _setText('comwFollowups', followups.length);
    document.getElementById('comSub').textContent =
      `${sum ? sum.total_due : tasks.length} פניות · ${followups.length} follow-ups · ${_pipeline.length} ב-pipeline`;

    // Insight strip
    const overdueCount = sum ? sum.overdue : overdueTasks.length;
    const todayCount   = sum ? sum.pending : todayTasks.length;
    const iChips = [];
    if (overdueCount)      iChips.push({ icon: '⚠',  text: `${overdueCount} פניות באיחור`,    cls: 'insight-alert' });
    if (todayCount)        iChips.push({ icon: '⏰', text: `${todayCount} לביצוע היום`,        cls: 'insight-warn'  });
    if (followups.length)  iChips.push({ icon: '↩',  text: `${followups.length} follow-ups`,  cls: 'insight-good'  });
    if (!iChips.length)    iChips.push({ icon: '✓',  text: 'אין פניות פעילות',                cls: 'insight-good'  });
    const iEl = document.getElementById('comInsight');
    if (iEl) iEl.innerHTML = UI.insightStrip(iChips);

    // Next-action — prefer top_priorities from summary, else fall back to queue
    const naEl = document.getElementById('comNextAction');
    const topPriority = sum?.top_priorities?.[0];
    const firstOverdue = overdueTasks[0] || todayTasks[0];
    if (naEl && topPriority) {
      naEl.innerHTML = UI.nextAction(
        `שלח פנייה ל‑${topPriority.lead_name || '—'} — ${topPriority.reason || topPriority.urgency || ''}`
      );
    } else if (naEl && firstOverdue) {
      naEl.innerHTML = UI.nextAction(
        `שלח פנייה ל‑${firstOverdue.lead_name || firstOverdue.contact_name || '—'} — ${firstOverdue.channel || 'whatsapp'}`
      );
    } else if (naEl) { naEl.innerHTML = ''; }

    renderQueue(tasks);
    renderFollowups(followups);
    renderPipeline(_pipeline);
  }

  function renderQueue(tasks) {
    const el  = document.getElementById('comQueueView');
    const now = new Date().toISOString().slice(0, 10);
    if (!tasks.length) {
      el.innerHTML = UI.guidedEmpty(
        'אין פניות ממתינות בתור',
        '◁',
        [
          { label: '🔍 גלה לידים', onclick: "HomePanel.openDiscover();App.switchTo('home')", primary: false },
          { label: '◎ ראה לידים', onclick: "App.switchTo('leads')", primary: false },
        ],
        'כשיש לידים עם טיוטות מאושרות הם יופיעו כאן'
      );
      return;
    }

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
            <div style="display:flex;gap:5px">
              <button class="btn btn-ghost" style="font-size:10px;padding:4px 8px"
                onclick="CommunicationsPanel.draftFor('${t.lead_id || ''}','${t.contact_name || t.lead_name || ''}')">✉ טיוטה</button>
              ${t.deep_link
                ? `<a href="${t.deep_link}" target="_blank" class="btn btn-primary" style="font-size:10px;padding:4px 10px;text-decoration:none">📱 שלח</a>`
                : `<button class="btn btn-primary" style="font-size:10px;padding:4px 10px"
                           onclick="CommunicationsPanel.executeOutreach('${t.lead_id || t.id || ''}')">שלח</button>`}
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  function renderFollowups(followups) {
    const el  = document.getElementById('comFollowupView');
    const now = new Date().toISOString().slice(0, 10);
    if (!followups.length) {
      el.innerHTML = UI.guidedEmpty('אין follow-ups ממתינים', '✓',
        [{ label: '◎ לידים פעילים', onclick: "App.switchTo('leads')", primary: false }]);
      return;
    }

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

  function renderPipeline(records, filterStatus = '') {
    const el  = document.getElementById('comPipelineView');
    const now = new Date().toISOString().slice(0, 10);
    const list = filterStatus ? records.filter(r => (r.status || r.lifecycle_status) === filterStatus) : records;

    // Build lifecycle filter pills
    const allStatuses = [...new Set(records.map(r => r.status || r.lifecycle_status).filter(Boolean))];
    const pillsHtml = allStatuses.length > 1 ? `
      <div class="leads-filter" style="margin-bottom:10px">
        <button class="filter-pill ${!filterStatus ? 'active' : ''}"
                onclick="CommunicationsPanel.filterPipeline('')">הכל</button>
        ${allStatuses.map(s => `
          <button class="filter-pill ${filterStatus === s ? 'active' : ''}"
                  onclick="CommunicationsPanel.filterPipeline('${s}')">
            ${LIFECYCLE_HE[s] || s}
          </button>`).join('')}
      </div>` : '';

    if (!list.length) {
      el.innerHTML = pillsHtml + UI.guidedEmpty('אין רשומות pipeline', '○',
        [{ label: '◁ תור שליחה', onclick: "document.querySelector('[data-tab=queue]')?.click()", primary: false }]);
      return;
    }

    el.innerHTML = pillsHtml + list.map(r => {
      const status   = r.status || r.lifecycle_status || 'sent';
      const nextDate = (r.next_followup || '').slice(0, 10);
      const isOverdue = nextDate && nextDate < now;
      const cls      = LIFECYCLE_CLS[status] || '';

      return `
        <div class="comm-item">
          <div style="font-size:16px;flex-shrink:0">📋</div>
          <div class="comm-info">
            <div class="comm-name">${r.lead_name || '—'}</div>
            <div class="comm-action">ניסיון ${r.attempt || 1} · ${nextDate ? `follow-up: ${nextDate}` : 'ללא תאריך'}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0">
            <span style="font-family:var(--mono);font-size:10px" class="${cls}">${LIFECYCLE_HE[status] || status}</span>
            ${nextDate && isOverdue ? `<div class="comm-due overdue">${nextDate}</div>` : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  function filterPipeline(status) {
    renderPipeline(_pipeline, status);
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

  function draftFor(leadId, leadName) {
    if (typeof DraftModal !== 'undefined') {
      DraftModal.openForAction({ id: leadId, name: leadName }, 'follow_up');
    }
  }

  return { render, init, executeOutreach, filterPipeline, draftFor };
})();
