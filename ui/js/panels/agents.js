/**
 * agents.js — Automations and Agents Panel
 */
const AgentsPanel = (() => {

  function render() {
    return `
      <!-- Widget bar -->
      <div class="panel-widgets">
        <div class="pw-chip">
          <div class="pw-val pv-accent" id="agwTotal">—</div>
          <div class="pw-label">סה"כ סוכנים</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-green" id="agwActive">—</div>
          <div class="pw-label">פעילים</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val" id="agwTasks">—</div>
          <div class="pw-label">משימות בוצעו</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val" id="agwDepts">—</div>
          <div class="pw-label">מחלקות</div>
        </div>
      </div>

      <div class="section-head">
        <div>
          <div class="section-title">סוכנים ואוטומציות</div>
          <div class="section-sub" id="agentCount">טוען...</div>
        </div>
        <select class="form-select" id="agentDeptFilter" style="font-size:11px;padding:5px 10px;width:auto">
          <option value="">כל המחלקות</option>
        </select>
      </div>
      <div id="agInsight" style="margin-bottom:12px"></div>
      <div class="agents-grid" id="agentsGrid">${UI.loading('טוען סוכנים...')}</div>
    `;
  }

  let _agents = [];

  async function init() {
    const res  = await API.agents();
    const grid = document.getElementById('agentsGrid');
    const cnt  = document.getElementById('agentCount');

    if (!res.success) {
      grid.innerHTML = UI.error('שגיאה בטעינת סוכנים');
      return;
    }
    _agents = res.data.agents || [];
    cnt.textContent = `${_agents.length} סוכנים`;

    // Compute widgets
    const totalTasks = _agents.reduce((s, a) => s + (a.tasks_done || 0), 0);
    const depts      = [...new Set(_agents.map(a => a.department).filter(Boolean))];
    _setText('agwTotal',  _agents.length);
    _setText('agwActive', _agents.length);
    _setText('agwTasks',  totalTasks);
    _setText('agwDepts',  depts.length);

    // Insight strip
    const iChips = [];
    if (_agents.length)       iChips.push({ icon: '⊙', text: `${_agents.length} סוכנים פעילים`, cls: 'insight-good' });
    if (totalTasks > 0)       iChips.push({ icon: '✓', text: `${totalTasks} משימות בוצעו`,      cls: 'insight-good' });
    if (!_agents.length)      iChips.push({ icon: '○', text: 'אין סוכנים מוגדרים',              cls: 'insight-warn' });
    const iEl = document.getElementById('agInsight');
    if (iEl) iEl.innerHTML = UI.insightStrip(iChips);

    // Populate dept filter
    const select = document.getElementById('agentDeptFilter');
    depts.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d; opt.textContent = d;
      select.appendChild(opt);
    });
    select.addEventListener('change', renderGrid);

    renderGrid();
  }

  function renderGrid() {
    const deptFilter = document.getElementById('agentDeptFilter')?.value || '';
    const grid = document.getElementById('agentsGrid');
    const list = deptFilter ? _agents.filter(a => a.department === deptFilter) : _agents;

    if (!list.length) { grid.innerHTML = UI.empty('אין סוכנים פעילים עדיין', '⊙'); return; }
    grid.innerHTML = list.map(a => `
      <div class="agent-card">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
          <div class="agent-dept">${a.department || '—'}</div>
          <span class="live-dot" title="פעיל"></span>
        </div>
        <div class="agent-name">${a.name}</div>
        <div class="agent-role">${a.role || a.model_preference || ''}</div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
          <div class="agent-tasks">משימות: ${a.tasks_done ?? 0}</div>
          ${a.model_preference ? `<span style="font-family:var(--mono);font-size:8px;color:var(--muted)">${a.model_preference.slice(0,20)}</span>` : ''}
        </div>
      </div>
    `).join('');
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  return { render, init };
})();
