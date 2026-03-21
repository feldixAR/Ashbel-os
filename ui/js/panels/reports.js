/**
 * reports.js— reports panel
 */
const ReportsPanel = (() => {
  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">דוח יומי</div>
          <div class="section-sub" id="reportTs">טוען...</div>
        </div>
        <button class="btn btn-ghost" onclick="ReportsPanel.reload()">רענן</button>
      </div>
      <div id="statsRow" class="stats-row"></div>
      <div class="cmd-label" style="margin-bottom:8px;">דוח מפורט</div>
      <div class="output-box" id="reportText" style="font-family:var(--mono);font-size:12px;direction:rtl;">
        <span class="spinner"></span> טוען...
      </div>
    `;
  }

  async function load() {
    const res = await API.dailyReport();
    const txt = document.getElementById('reportText');
    const ts  = document.getElementById('reportTs');
    const row = document.getElementById('statsRow');

    if (!res.success) {
      txt.textContent = 'שגיאה בטעינת הדוח';
      return;
    }
    const { summary, report_text } = res.data;
    ts.textContent = 'נוצר: ' + (summary?.generated_at || '').slice(0,19).replace('T',' ');
    txt.textContent = report_text || '—';

    const leads = summary?.leads || {};
    const tasks = summary?.tasks || {};
    row.innerHTML = [
      { num: leads.total  || 0,  label: 'סה"כ לידים' },
      { num: leads.hot    || 0,  label: 'לידים חמים' },
      { num: leads.avg_score || 0, label: 'ציון ממוצע' },
      { num: tasks.done   || 0,  label: 'משימות הושלמו' },
      { num: tasks.failed || 0,  label: 'משימות נכשלו' },
    ].map(s => `
      <div class="stat-card">
        <div class="stat-num">${s.num}</div>
        <div class="stat-label">${s.label}</div>
      </div>
    `).join('');
  }

  return { render, init: load, reload: load };
})();