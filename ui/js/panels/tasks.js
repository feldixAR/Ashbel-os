/**
 * tasks.js — Tasks panel
 */
const TasksPanel = (() => {

  function statusPill(s) {
    const map = { created: 'pill-steel', running: 'pill-amber', completed: 'pill-green', failed: 'pill-red' };
    const label = { created: 'נוצר', running: 'רץ', completed: 'הושלם', failed: 'נכשל' };
    return `<span class="pill ${map[s] || ''}">${label[s] || s}</span>`;
  }

  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">משימות מערכת</div>
          <div class="section-sub" id="taskCount">טוען...</div>
        </div>
        <button class="btn btn-secondary" id="refreshTasksBtn">🔄 רענן</button>
      </div>
      <div id="tasksTable"><div class="empty-state"><span>⏳</span><p>טוען...</p></div></div>
    `;
  }

  async function init() {
    await loadTasks();
    document.getElementById('refreshTasksBtn')?.addEventListener('click', loadTasks);
  }

  async function loadTasks() {
    const res = await API.get('/tasks');
    const tasks = res.success ? (res.data.tasks || []) : [];
    document.getElementById('taskCount').textContent = `${tasks.length} משימות`;
    const tbody = tasks.length ? tasks.map(t => `
      <tr>
        <td style="font-family:monospace;font-size:11px">${(t.id || '').slice(0, 8)}</td>
        <td>${t.type || '—'}</td>
        <td>${t.action || '—'}</td>
        <td>${statusPill(t.status)}</td>
        <td>${t.priority || 5}</td>
        <td>${(t.created_at || '').slice(0, 16) || '—'}</td>
      </tr>`).join('') : '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">אין משימות</td></tr>';
    document.getElementById('tasksTable').innerHTML = `
      <table class="data-table">
        <thead><tr><th>ID</th><th>סוג</th><th>פעולה</th><th>סטטוס</th><th>עדיפות</th><th>נוצר</th></tr></thead>
        <tbody>${tbody}</tbody>
      </table>`;
  }

  return { render, init };
})();
