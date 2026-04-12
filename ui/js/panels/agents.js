/**
 * agents.js — Agents Operating Surface
 * Shows real agent actors, their status, last work, and suggested next action.
 */
const AgentsPanel = (() => {

  function render() {
    return `
      <div class="panel-widgets">
        <div class="pw-chip">
          <div class="pw-val pv-accent" id="agwTotal">—</div>
          <div class="pw-label">סוכנים</div>
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

      <div id="agInsight" style="margin-bottom:12px"></div>
      <div id="agNextAction" style="margin-bottom:16px"></div>

      <div class="section-head">
        <div>
          <div class="section-title">סוכנים פעילים</div>
          <div class="section-sub" id="agentCount">טוען...</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <select class="form-select" id="agentDeptFilter" style="font-size:11px;padding:5px 10px;width:auto">
            <option value="">כל המחלקות</option>
          </select>
          <button class="btn btn-ghost" id="agRefreshBtn">↻ רענן</button>
        </div>
      </div>

      <!-- Agents grid -->
      <div class="agents-grid" id="agentsGrid">${UI.loading('טוען סוכנים...')}</div>

      <!-- Usage block -->
      <div id="agUsageBlock" style="display:none;margin-top:20px">
        <div class="section-title" style="margin-bottom:10px;font-size:12px">פעילות מערכת היום</div>
        <div id="agUsageContent"></div>
      </div>
    `;
  }

  let _agents = [];

  async function init() {
    await _load();
    document.getElementById('agRefreshBtn')?.addEventListener('click', _load);
  }

  async function _load() {
    const [res, usageRes] = await Promise.all([
      API.agents(),
      API.adminUsage().catch(() => ({ success: false })),
    ]);

    const grid = document.getElementById('agentsGrid');
    const cnt  = document.getElementById('agentCount');

    if (!res.success) {
      grid.innerHTML = _guidedEmpty(
        'לא נמצאו סוכנים',
        '⊙',
        'הפעל גילוי לידים',
        "HomePanel.openDiscover();App.switchTo('home')"
      );
      return;
    }

    _agents = res.data.agents || [];
    cnt.textContent = `${_agents.length} סוכנים רשומים`;

    const totalTasks = _agents.reduce((s, a) => s + (a.tasks_done || 0), 0);
    const depts      = [...new Set(_agents.map(a => a.department).filter(Boolean))];

    _setText('agwTotal',  _agents.length);
    _setText('agwActive', _agents.length);
    _setText('agwTasks',  totalTasks);
    _setText('agwDepts',  depts.length);

    // Insight strip
    const iChips = [];
    if (_agents.length)  iChips.push({ icon: '⊙', text: `${_agents.length} סוכנים פעילים`, cls: 'insight-good' });
    if (totalTasks > 0)  iChips.push({ icon: '✓', text: `${totalTasks} משימות בוצעו`,      cls: 'insight-good' });
    if (!_agents.length) iChips.push({ icon: '○', text: 'אין סוכנים מוגדרים',              cls: 'insight-warn' });
    const iEl = document.getElementById('agInsight');
    if (iEl) iEl.innerHTML = UI.insightStrip(iChips);

    // Next action — highest-task agent
    const topAgent = [..._agents].sort((a, b) => (b.tasks_done || 0) - (a.tasks_done || 0))[0];
    const naEl = document.getElementById('agNextAction');
    if (naEl && topAgent) {
      naEl.innerHTML = UI.nextAction(
        `${topAgent.name} — ${topAgent.department || ''}: ${topAgent.tasks_done || 0} משימות`,
        'הצג לידים שיוצרו',
        "App.switchTo('leads')"
      );
    } else if (naEl) { naEl.innerHTML = ''; }

    // Dept filter
    const select = document.getElementById('agentDeptFilter');
    if (select) {
      // Clear old options except first
      while (select.options.length > 1) select.remove(1);
      depts.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d; opt.textContent = d;
        select.appendChild(opt);
      });
      select.addEventListener('change', _renderGrid);
    }

    _renderGrid();

    // Usage block
    if (usageRes.success) {
      const usage = usageRes.data;
      const acts  = Object.entries(usage.activities || {});
      const outr  = Object.entries(usage.outreach   || {});

      const chips = (entries, colorCls) => entries.map(([k,v]) => `
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:5px 10px;text-align:center">
          <div style="font-family:var(--mono);font-size:13px;font-weight:600" class="${colorCls}">${v}</div>
          <div style="font-size:9px;color:var(--muted)">${k}</div>
        </div>`).join('');

      document.getElementById('agUsageContent').innerHTML = `
        <div style="font-size:11px;color:var(--muted);margin-bottom:8px">
          ${usage.date || ''} · סה"כ פעולות: <strong>${usage.total_actions || 0}</strong>
        </div>
        ${acts.length ? `<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">${chips(acts,'pv-accent')}</div>` : ''}
        ${outr.length ? `<div style="display:flex;gap:8px;flex-wrap:wrap">${chips(outr,'pv-green')}</div>` : ''}
        ${(!acts.length && !outr.length) ? '<div style="font-size:11px;color:var(--muted)">אין פעילות מוקלטת היום</div>' : ''}
      `;
      document.getElementById('agUsageBlock').style.display = '';
    }
  }

  function _renderGrid() {
    const deptFilter = document.getElementById('agentDeptFilter')?.value || '';
    const grid = document.getElementById('agentsGrid');
    const list = deptFilter ? _agents.filter(a => a.department === deptFilter) : _agents;

    if (!list.length) {
      grid.innerHTML = _guidedEmpty(
        'אין סוכנים במחלקה זו',
        '⊙',
        'הצג כל הסוכנים',
        "document.getElementById('agentDeptFilter').value='';AgentsPanel._renderGrid()"
      );
      return;
    }

    grid.innerHTML = list.map(a => {
      const lastActive = a.last_active_at ? UI.relTime(a.last_active_at) : null;
      const tasksCount = a.tasks_done ?? 0;
      const version    = a.active_version ? `v${a.active_version}` : '';

      // Status indicator: if last active within 24h → active, else idle
      const now = Date.now();
      const lastMs = a.last_active_at ? new Date(a.last_active_at).getTime() : 0;
      const isRecent = lastMs && (now - lastMs) < 86400000;
      const statusDot = isRecent
        ? '<span class="live-dot" title="פעיל לאחרונה"></span>'
        : '<span style="width:6px;height:6px;border-radius:50%;background:var(--border2);display:inline-block;margin-right:4px" title="ממתין"></span>';

      return `
        <div class="agent-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
            <div class="agent-dept">${a.department || '—'}</div>
            ${statusDot}
          </div>
          <div class="agent-name">${a.name}</div>
          <div class="agent-role">${a.role || ''}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;border-top:1px solid var(--border);padding-top:6px">
            <div style="font-family:var(--mono);font-size:10px;color:var(--accent)">${tasksCount} משימות</div>
            ${version ? `<span style="font-family:var(--mono);font-size:8px;color:var(--muted)">${version}</span>` : ''}
          </div>
          ${lastActive ? `<div style="font-size:9px;color:var(--muted);margin-top:3px">פעיל: ${lastActive}</div>` : ''}
          ${a.model_preference ? `<div style="font-family:var(--mono);font-size:8px;color:var(--muted);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${a.model_preference.slice(0,30)}</div>` : ''}
          <div style="margin-top:8px;display:flex;gap:6px">
            <button class="btn btn-ghost" style="font-size:10px;padding:3px 8px;flex:1"
              onclick="App.switchTo('tasks')">משימות</button>
            <button class="btn btn-ghost" style="font-size:10px;padding:3px 8px;flex:1"
              onclick="App.switchTo('leads')">לידים</button>
          </div>
        </div>
      `;
    }).join('');
  }

  function _guidedEmpty(msg, icon, ctaLabel, ctaJs) {
    return `<div class="empty-state">
      <div class="empty-state-icon">${icon}</div>
      <div class="empty-state-msg">${msg}</div>
      ${ctaLabel ? `<button class="btn btn-primary" style="margin-top:12px" onclick="${ctaJs}">${ctaLabel}</button>` : ''}
    </div>`;
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  // Expose _renderGrid for onclick
  AgentsPanel = Object.assign(AgentsPanel || {}, { _renderGrid });

  return { render, init, _renderGrid };
})();
