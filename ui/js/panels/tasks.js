/**
 * tasks.js — Tasks and Next Actions Panel
 */
const TasksPanel = (() => {

  function statusPill(s) {
    const map   = { created: 'pill-steel', running: 'pill-amber', completed: 'pill-green', failed: 'pill-red' };
    const label = { created: 'נוצר', running: 'רץ', completed: 'הושלם', failed: 'נכשל' };
    return `<span class="pill ${map[s] || ''}">${label[s] || s}</span>`;
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

      <div id="tasksTable">
        <div class="empty-state"><span class="spinner"></span><p style="margin-top:8px">טוען...</p></div>
      </div>
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
    let tasks   = res.success ? (res.data.tasks || []) : [];

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

    const tbody = tasks.length ? tasks.map(t => `
      <tr>
        <td style="font-family:var(--mono);font-size:11px;color:var(--muted)">${(t.id || '').slice(0, 8)}</td>
        <td>${t.type || '—'}</td>
        <td>${t.action || '—'}</td>
        <td>${statusPill(t.status)}</td>
        <td style="font-family:var(--mono);font-size:11px;color:${priorityColor(t.priority || 5)}">${t.priority || 5}</td>
        <td style="font-family:var(--mono);font-size:11px;color:var(--muted)">${(t.created_at || '').slice(0, 16).replace('T', ' ') || '—'}</td>
      </tr>`).join('')
      : '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px">אין משימות</td></tr>';

    document.getElementById('tasksTable').innerHTML = `
      <div class="table-wrap" style="margin-top:0">
        <table>
          <thead>
            <tr>
              <th>ID</th>
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

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  return { render, init };
})();
