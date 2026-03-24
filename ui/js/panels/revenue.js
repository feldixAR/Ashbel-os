/**
 * revenue.js — מודיעין הכנסות & Daily Plan panel (Batch 4/9)
 */
const RevenuePanel = (() => {

  function kpiCard(label, value, unit, status) {
    const color = { green: 'var(--green)', yellow: 'var(--amber)', red: 'var(--danger)' }[status] || 'var(--text-muted)';
    return `
      <div class="card" style="text-align:center;flex:1;min-width:120px">
        <div style="font-size:22px;font-weight:700;color:${color}">${value}<span style="font-size:13px;font-weight:400;margin-right:4px">${unit}</span></div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:4px">${label}</div>
      </div>`;
  }

  function render() {
    return `
      <div class="section-head">
        <div class="section-title">מודיעין הכנסות</div>
      </div>

      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px" id="kpiRow">
        <div style="color:var(--text-muted);padding:12px">טוען KPIs...</div>
      </div>

      <div style="display:flex;gap:12px;margin-bottom:20px">
        <button class="btn btn-primary" id="dailyPlanBtn">📅 תוכנית יומית</button>
        <button class="btn btn-secondary" id="nextActionBtn">🎯 הצעד הבא</button>
        <button class="btn btn-secondary" id="bottleneckBtn">🔍 זיהוי חסמים</button>
        <button class="btn btn-secondary" id="learningBtn">🧠 מחזור למידה</button>
      </div>

      <div id="revenueOutput"></div>
    `;
  }

  async function init() {
    await loadKPIs();
    document.getElementById('dailyPlanBtn')?.addEventListener('click',   () => runCommand('תכנן לי את היום'));
    document.getElementById('nextActionBtn')?.addEventListener('click',  () => runCommand('מה הצעד הבא'));
    document.getElementById('bottleneckBtn')?.addEventListener('click',  () => runCommand('מה תקוע'));
    document.getElementById('learningBtn')?.addEventListener('click',    () => runCommand('מחזור למידה'));
  }

  async function loadKPIs() {
    const res = await API.get('/dashboard/kpis');
    if (!res.success) return;
    const kpis = res.data?.kpis || [];
    document.getElementById('kpiRow').innerHTML = kpis.map(k =>
      kpiCard(k.label, k.value, k.unit, k.status)
    ).join('') || '<div style="color:var(--text-muted)">אין נתונים</div>';
  }

  async function runCommand(cmd) {
    const out = document.getElementById('revenueOutput');
    out.innerHTML = '<div style="color:var(--text-muted);padding:12px">מריץ...</div>';
    const res = await API.post('/command', { command: cmd });
    out.innerHTML = `
      <div class="card">
        <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px">${cmd}</div>
        <div style="white-space:pre-wrap">${res.data?.message || res.data?.output?.message || res.message || '✅ בוצע'}</div>
      </div>`;
  }

  return { render, init };
})();
