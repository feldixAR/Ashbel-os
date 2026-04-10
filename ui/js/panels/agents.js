/**
 * agents.js — Automations and Agents Panel
 * Sources: GET /api/agents, GET /api/admin/usage
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

      <!-- Chief of Staff quick card -->
      <div style="background:linear-gradient(135deg,rgba(99,102,241,.12),rgba(139,92,246,.08));border:1px solid rgba(99,102,241,.3);border-radius:10px;padding:14px;margin-bottom:14px;direction:rtl">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <div style="font-weight:600;font-size:13px">🧠 Chief of Staff</div>
          <span class="live-dot"></span>
        </div>
        <div style="font-size:11px;color:var(--muted);margin-bottom:10px">תכנון אסטרטגי · מדיניות · תיאום צוות</div>
        <div id="cosLastDecision" style="font-size:10px;color:var(--muted);margin-bottom:10px;min-height:16px">—</div>
        <button class="btn btn-primary" style="font-size:11px;padding:6px 14px"
                onclick="App.switchTo('command');setTimeout(()=>{const i=document.getElementById('cmdInput');if(i){i.value='מה הצעד הבא?';document.getElementById('cmdSend')?.click();}},300)">
          שאל את Chief of Staff
        </button>
      </div>

      <div class="agents-grid" id="agentsGrid">${UI.loading('טוען סוכנים...')}</div>

      <!-- Today's system activity -->
      <div class="cmd-box" id="agUsageBlock" style="display:none;margin-top:20px">
        <div class="cmd-label">פעילות מערכת היום</div>
        <div id="agUsageContent"></div>
      </div>
    `;
  }

  let _agents = [];

  async function init() {
    const [res, usageRes] = await Promise.all([
      API.agents(),
      API.adminUsage().catch(() => ({ success: false })),
    ]);

    const grid = document.getElementById('agentsGrid');
    const cnt  = document.getElementById('agentCount');

    if (!res.success) {
      grid.innerHTML = UI.error('שגיאה בטעינת סוכנים');
    } else {
      _agents = res.data.agents || [];
      cnt.textContent = `${_agents.length} סוכנים`;

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

      // Dept filter
      const select = document.getElementById('agentDeptFilter');
      depts.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d; opt.textContent = d;
        select.appendChild(opt);
      });
      select.addEventListener('change', renderGrid);

      renderGrid();
    }

    // ── Today's usage ─────────────────────────────────────────────────────────
    if (usageRes.success) {
      const usage = usageRes.data;
      const acts  = Object.entries(usage.activities || {});
      const outr  = Object.entries(usage.outreach   || {});

      const chips = (entries, colorCls) => entries.map(([k,v]) => `
        <div style="background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:6px;padding:5px 10px;text-align:center">
          <div style="font-family:var(--mono);font-size:13px;font-weight:600" class="${colorCls}">${v}</div>
          <div style="font-size:9px;color:var(--muted)">${k}</div>
        </div>`).join('');

      document.getElementById('agUsageContent').innerHTML = `
        <div style="font-size:11px;color:var(--muted);margin-bottom:8px">
          ${usage.date} · סה"כ פעולות: <strong style="color:var(--text)">${usage.total_actions || 0}</strong>
        </div>
        ${acts.length ? `<div style="font-size:10px;color:var(--muted);margin-bottom:6px">פעילויות</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">${chips(acts, 'pv-accent')}</div>` : ''}
        ${outr.length ? `<div style="font-size:10px;color:var(--muted);margin-bottom:6px">פניות לפי ערוץ</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">${chips(outr, 'pv-green')}</div>` : ''}
        ${(!acts.length && !outr.length)
          ? '<div style="font-size:11px;color:var(--muted)">אין פעילות מוקלטת היום</div>' : ''}
      `;
      document.getElementById('agUsageBlock').style.display = '';
    }
  }

  function renderGrid() {
    const deptFilter = document.getElementById('agentDeptFilter')?.value || '';
    const grid = document.getElementById('agentsGrid');
    const list = deptFilter ? _agents.filter(a => a.department === deptFilter) : _agents;

    if (!list.length) { grid.innerHTML = UI.empty('אין סוכנים פעילים עדיין', '⊙'); return; }
    grid.innerHTML = list.map(a => {
      const lastActive = a.last_active_at ? UI.relTime(a.last_active_at) : null;
      const version    = a.active_version  ? `v${a.active_version}` : null;
      return `
        <div class="agent-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
            <div class="agent-dept">${a.department || '—'}</div>
            <span class="live-dot" title="פעיל"></span>
          </div>
          <div class="agent-name">${a.name}</div>
          <div class="agent-role">${a.role || a.model_preference || ''}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
            <div class="agent-tasks">משימות: ${a.tasks_done ?? 0}</div>
            ${version ? `<span style="font-family:var(--mono);font-size:8px;color:var(--muted)">${version}</span>` : ''}
          </div>
          ${lastActive ? `<div style="font-size:9px;color:var(--muted);margin-top:4px">פעיל אחרון: ${lastActive}</div>` : ''}
          ${a.model_preference ? `<div style="font-family:var(--mono);font-size:8px;color:var(--muted);margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${a.model_preference.slice(0,28)}</div>` : ''}
        </div>
      `;
    }).join('');
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  return { render, init };
})();
