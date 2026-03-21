/**
 * agents.js — agents panel
 */
const AgentsPanel = (() => {
  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">סוכנים</div>
          <div class="section-sub" id="agentCount">טוען...</div>
        </div>
      </div>
      <div class="agents-grid" id="agentsGrid">
        <div style="color:var(--muted);"><span class="spinner"></span> טוען...</div>
      </div>
    `;
  }

  async function init() {
    const res  = await API.agents();
    const grid = document.getElementById('agentsGrid');
    const cnt  = document.getElementById('agentCount');

    if (!res.success) {
      grid.innerHTML = `<div style="color:var(--red);">שגיאה בטעינת סוכנים</div>`;
      return;
    }
    const agents = res.data.agents || [];
    cnt.textContent = `${agents.length} סוכנים פעילים`;

    if (!agents.length) {
      grid.innerHTML = `<div style="color:var(--muted);">אין סוכנים פעילים עדיין</div>`;
      return;
    }
    grid.innerHTML = agents.map(a => `
      <div class="agent-card">
        <div class="agent-dept">${a.department || '—'}</div>
        <div class="agent-name">${a.name}</div>
        <div class="agent-role">${a.role || a.model_preference || ''}</div>
        <div class="agent-tasks">משימות: ${a.tasks_done ?? 0}</div>
      </div>
    `).join('');
  }

  return { render, init };
})();