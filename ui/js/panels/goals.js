/**
 * goals.js — Goals & Deals panel (Batch 6)
 */
const GoalsPanel = (() => {

  function statusPill(s) {
    const map = { active: 'pill-green', paused: 'pill-amber', completed: 'pill-steel' };
    const label = { active: 'פעיל', paused: 'מושהה', completed: 'הושלם' };
    return `<span class="pill ${map[s] || ''}">${label[s] || s}</span>`;
  }

  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">יעדים עסקיים</div>
          <div class="section-sub" id="goalCount">טוען...</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <input class="modal-input" id="newGoalInput" placeholder="הגדר יעד חדש... (למשל: הגדל מכירות אדריכלים)" style="width:320px" />
          <button class="btn btn-primary" id="addGoalBtn">+ יעד</button>
        </div>
      </div>
      <div id="goalsGrid"></div>
      <div class="section-head" style="margin-top:24px">
        <div class="section-title">תוכנית צמיחה אחרונה</div>
      </div>
      <div id="growthPlanOutput"></div>
    `;
  }

  async function init() {
    await loadGoals();
    document.getElementById('addGoalBtn')?.addEventListener('click', addGoal);
    document.getElementById('newGoalInput')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') addGoal();
    });
  }

  async function loadGoals() {
    const res = await API.post('/command', { command: 'הצג יעדים' });
    const goals = res.success ? (res.data?.output?.goals || res.data?.output?.goals || res.data?.goals || []) : [];
    document.getElementById('goalCount').textContent = `${goals.length} יעדים פעילים`;
    document.getElementById('goalsGrid').innerHTML = goals.length
      ? goals.map(g => `
          <div class="card" style="margin-bottom:12px">
            <div style="display:flex;justify-content:space-between;align-items:center">
              <div>
                <div style="font-weight:600">${g.raw_goal || '—'}</div>
                <div style="font-size:12px;color:var(--text-muted);margin-top:4px">תחום: ${g.domain || '—'} | מדד: ${g.primary_metric || '—'}</div>
              </div>
              <div style="display:flex;gap:8px;align-items:center">
                ${statusPill(g.status)}
                <button class="btn btn-xs" onclick="GoalsPanel.buildPlan('${g.raw_goal}')">📊 תוכנית</button>
              </div>
            </div>
            ${g.tracks?.length ? `<div style="margin-top:10px;font-size:12px;color:var(--text-muted)">מסלולים: ${g.tracks.map(t => t.name || t).join(' | ')}</div>` : ''}
          </div>`)
        .join('')
      : '<div class="empty-state"><span>🎯</span><p>אין יעדים פעילים. הגדר יעד ראשון.</p></div>';
  }

  async function addGoal() {
    const input = document.getElementById('newGoalInput');
    const goal  = (input?.value || '').trim();
    if (!goal) return;
    input.value = '';
    const res = await API.post('/command', { command: goal });
    Toast.show(res.success ? `✅ ${res.data?.message || res.message}` : `❌ ${res.data?.message || res.message || 'שגיאה'}`, res.success ? 'success' : 'error');
    if (res.success) await loadGoals();
  }

  async function buildPlan(goalText) {
    document.getElementById('growthPlanOutput').innerHTML = '<div style="color:var(--text-muted);padding:12px">בונה תוכנית...</div>';
    const res = await API.post('/command', { command: `תוכנית צמיחה ${goalText}` });
    if (!res.success) {
      document.getElementById('growthPlanOutput').innerHTML = `<div style="color:var(--danger)">${res.data?.message || res.message || 'שגיאה'}</div>`;
      return;
    }
    const tracks = res.data?.output?.tracks || res.data?.output?.tracks || res.data?.tracks || [];
    document.getElementById('growthPlanOutput').innerHTML = tracks.length
      ? tracks.map(t => `
          <div class="card" style="margin-bottom:8px">
            <div style="font-weight:600">📍 ${t.track}</div>
            <div style="font-size:12px;margin-top:6px;color:var(--text-muted)">ערוץ: ${t.channel} | פעולות: ${(t.actions || []).join(' → ')}</div>
          </div>`).join('')
      : '<div style="color:var(--text-muted)">אין מסלולים</div>';
  }

  return { render, init, buildPlan };
})();
