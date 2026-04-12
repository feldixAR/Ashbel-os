/**
 * tasks.js — Tasks and Next Actions Panel
 */
const TasksPanel = (() => {

  // Delegate to shared UI primitives
  function statusPill(s) {
    const map   = { created: 'pill-steel', running: 'pill-amber', completed: 'pill-green', failed: 'pill-red' };
    const label = { created: 'נוצר', running: 'רץ', completed: 'הושלם', failed: 'נכשל' };
    return UI.pill(label[s] || s, map[s] || '');
  }
  function priorityColor(p) {
    if (p <= 2) return 'var(--red)';
    if (p <= 4) return 'var(--amber)';
    return 'var(--muted)';
  }

  function render() {
    return `
      <!-- Widget bar -->
      <div class="panel-widgets">
        <div class="pw-chip">
          <div class="pw-val" id="twTotal">—</div>
          <div class="pw-label">סה"כ משימות</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-amber" id="twRunning">—</div>
          <div class="pw-label">בריצה</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-green" id="twDone">—</div>
          <div class="pw-label">הושלמו</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-red" id="twFailed">—</div>
          <div class="pw-label">נכשלו</div>
        </div>
      </div>

      <div id="taskInsight"></div>
      <div id="taskNextAction" style="margin-bottom:16px"></div>

      <div class="section-head">
        <div>
          <div class="section-title">משימות ופעולות הבאות</div>
          <div class="section-sub" id="taskCount">טוען...</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <select class="form-select" id="taskStatusFilter" style="font-size:11px;padding:5px 10px">
            <option value="">כל הסטטוסים</option>
            <option value="created">נוצר</option>
            <option value="running">רץ</option>
            <option value="completed">הושלם</option>
            <option value="failed">נכשל</option>
          </select>
          <button class="btn btn-secondary" id="refreshTasksBtn">↻ רענן</button>
        </div>
      </div>

      <div id="tasksTable">${UI.loading('טוען משימות...')}</div>
    `;
  }

  async function init() {
    await loadTasks();
    document.getElementById('refreshTasksBtn')?.addEventListener('click', loadTasks);
    document.getElementById('taskStatusFilter')?.addEventListener('change', loadTasks);
  }

  async function loadTasks() {
    const statusFilter = document.getElementById('taskStatusFilter')?.value || '';
    const res   = await API.get('/tasks');
    if (!res.success) {
      document.getElementById('tasksTable').innerHTML = UI.error('שגיאה בטעינת משימות');
      return;
    }
    let tasks   = res.data.tasks || [];

    if (statusFilter) tasks = tasks.filter(t => t.status === statusFilter);

    // Sort: running first, then created, then failed, then completed; by priority asc within groups
    const order = { running: 0, created: 1, failed: 2, completed: 3 };
    tasks = [...tasks].sort((a, b) => {
      const og = (order[a.status] ?? 9) - (order[b.status] ?? 9);
      if (og !== 0) return og;
      return (a.priority ?? 5) - (b.priority ?? 5);
    });

    const total   = tasks.length;
    const running = tasks.filter(t => t.status === 'running').length;
    const done    = tasks.filter(t => t.status === 'completed').length;
    const failed  = tasks.filter(t => t.status === 'failed').length;

    _setText('twTotal',   total);
    _setText('twRunning', running);
    _setText('twDone',    done);
    _setText('twFailed',  failed);
    document.getElementById('taskCount').textContent = `${total} משימות`;

    // Insight strip
    const iChips = [];
    if (running > 0) iChips.push({ icon: '◌', text: `${running} משימות בריצה`,  cls: 'insight-good' });
    if (failed > 0)  iChips.push({ icon: '⚠', text: `${failed} משימות נכשלו`,  cls: 'insight-alert' });
    if (!iChips.length) iChips.push({ icon: '✓', text: 'אין משימות פעילות',    cls: 'insight-good' });
    const iEl = document.getElementById('taskInsight');
    if (iEl) iEl.innerHTML = UI.insightStrip(iChips);

    // Next-action: highest priority open task
    const nextTask = tasks.filter(t => t.status === 'created' || t.status === 'running')
      .sort((a, b) => (a.priority ?? 9) - (b.priority ?? 9))[0];
    const naEl = document.getElementById('taskNextAction');
    if (naEl && nextTask) {
      naEl.innerHTML = UI.nextAction(
        `${nextTask.type || 'משימה'}: ${nextTask.action || nextTask.id?.slice(0,8)} — עדיפות ${nextTask.priority ?? '—'}`
      );
    } else if (naEl) {
      naEl.innerHTML = '';
    }

    const tbody = tasks.length ? tasks.map(t => {
      const relCreated = t.created_at ? UI.relTime(t.created_at) : '—';
      return `
      <tr style="cursor:pointer" onclick="TasksPanel.openTask('${t.id}','${t.lead_id||''}')" title="פתח הקשר">
        <td style="font-family:var(--mono);font-size:11px;color:var(--muted)">${(t.id || '').slice(0, 8)}</td>
        <td>${t.type || '—'}</td>
        <td>${t.action || '—'}</td>
        <td>${statusPill(t.status)}</td>
        <td style="font-family:var(--mono);font-size:11px;color:${priorityColor(t.priority || 5)}">${t.priority || 5}</td>
        <td style="font-family:var(--mono);font-size:11px;color:var(--muted)" title="${(t.created_at||'').slice(0,16).replace('T',' ')}">${relCreated}</td>
      </tr>`;}).join('')
      : `<tr><td colspan="6">
          <div class="empty-state">
            <div class="empty-state-icon">◫</div>
            <div class="empty-state-msg">אין משימות פעילות</div>
            <div style="display:flex;gap:8px;justify-content:center;margin-top:12px;flex-wrap:wrap">
              <button class="btn btn-ghost" onclick="HomePanel.openDiscover();App.switchTo('home')">🔍 גלה לידים חדשים</button>
              <button class="btn btn-ghost" onclick="App.switchTo('leads')">◎ ראה לידים</button>
            </div>
          </div>
        </td></tr>`;

    document.getElementById('tasksTable').innerHTML = `
      <div class="table-wrap" style="margin-top:0">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>סוג</th>
              <th>פעולה</th>
              <th>סטטוס</th>
              <th>עדיפות</th>
              <th>נוצר</th>
            </tr>
          </thead>
          <tbody>${tbody}</tbody>
        </table>
      </div>`;
  }

  function openTask(id, leadId) {
    if (leadId) {
      App.switchTo('briefing');
      setTimeout(() => {
        if (typeof BriefingPanel !== 'undefined') BriefingPanel.prefillLead(leadId);
      }, 200);
    } else {
      App.switchTo('leads');
    }
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  return { render, init, openTask };
})();
