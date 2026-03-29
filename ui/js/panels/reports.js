/**
 * reports.js — Reports and Analytics Panel
 */
const ReportsPanel = (() => {

  function render() {
    return `
      <!-- Widget bar -->
      <div class="panel-widgets">
        <div class="pw-chip">
          <div class="pw-val" id="rpwLeads">—</div>
          <div class="pw-label">סה"כ לידים</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-red" id="rpwHot">—</div>
          <div class="pw-label">לידים חמים</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-accent" id="rpwScore">—</div>
          <div class="pw-label">ציון ממוצע</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-green" id="rpwDone">—</div>
          <div class="pw-label">משימות הושלמו</div>
        </div>
      </div>

      <div class="section-head">
        <div>
          <div class="section-title">דוחות ואנליטיקה</div>
          <div class="section-sub" id="reportTs">טוען...</div>
        </div>
        <button class="btn btn-ghost" onclick="ReportsPanel.reload()">↻ רענן</button>
      </div>

      <!-- Metrics grid (CSS-only bars — no chart libs) -->
      <div class="stats-row" id="statsRow" style="margin-bottom:24px"></div>

      <!-- Pipeline visual bar -->
      <div class="cmd-box" style="margin-bottom:16px" id="reportPipeSection" style="display:none">
        <div class="cmd-label">pipeline לפי שלב</div>
        <div id="reportPipeBars"></div>
      </div>

      <div class="cmd-label" style="margin-bottom:8px;">דוח מפורט</div>
      <div class="output-box" id="reportText" style="font-family:var(--mono);font-size:12px;direction:rtl;min-height:180px;">
        <span class="spinner"></span> טוען...
      </div>
    `;
  }

  async function load() {
    const [reportRes, dealsRes] = await Promise.all([
      API.dailyReport(),
      API.deals(),
    ]);

    const txt = document.getElementById('reportText');
    const ts  = document.getElementById('reportTs');
    const row = document.getElementById('statsRow');

    if (!reportRes.success) {
      txt.textContent = 'שגיאה בטעינת הדוח';
      return;
    }
    const { summary, report_text } = reportRes.data;
    ts.textContent = 'נוצר: ' + (summary?.generated_at || '').slice(0,19).replace('T',' ');
    txt.textContent = report_text || '—';

    const leads = summary?.leads || {};
    const tasks = summary?.tasks || {};

    // Update widgets
    _setText('rpwLeads', leads.total || 0);
    _setText('rpwHot',   leads.hot   || 0);
    _setText('rpwScore', leads.avg_score || 0);
    _setText('rpwDone',  tasks.done  || 0);

    row.innerHTML = [
      { num: leads.total  || 0,  label: 'סה"כ לידים',       cls: '' },
      { num: leads.hot    || 0,  label: 'לידים חמים',        cls: 'pv-red' },
      { num: leads.avg_score || 0, label: 'ציון ממוצע',      cls: 'pv-accent' },
      { num: tasks.done   || 0,  label: 'משימות הושלמו',    cls: 'pv-green' },
      { num: tasks.failed || 0,  label: 'משימות נכשלו',     cls: 'pv-red' },
    ].map(s => `
      <div class="stat-card">
        <div class="stat-num ${s.cls}">${s.num}</div>
        <div class="stat-label">${s.label}</div>
      </div>
    `).join('');

    // Pipeline breakdown
    if (dealsRes.success) {
      const deals  = dealsRes.data?.deals || [];
      const stages = ['new','qualified','proposal','negotiation','won'];
      const heMap  = { new:'חדש', qualified:'כשיר', proposal:'הצעה', negotiation:'משא ומתן', won:'זכה' };
      const totals = stages.map(s => deals.filter(d=>d.stage===s).reduce((sum,d)=>sum+(d.value_ils||0),0));
      const max    = Math.max(...totals, 1);
      document.getElementById('reportPipeBars').innerHTML = stages.map((s,i) => `
        <div class="pipe-row">
          <span class="pipe-label" style="font-size:10px;width:90px">${heMap[s]}</span>
          <div class="pipe-track">
            <div class="pipe-fill" style="width:${Math.round(totals[i]/max*100)}%"></div>
          </div>
          <span class="pipe-val" style="font-size:10px;color:var(--amber)">
            ₪${Math.round(totals[i]/1000)}K
          </span>
        </div>
      `).join('');
      document.getElementById('reportPipeSection').style.display = '';
    }
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  return { render, init: load, reload: load };
})();
