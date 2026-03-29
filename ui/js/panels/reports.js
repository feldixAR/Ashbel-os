/**
 * reports.js — Reports and Analytics Panel
 * Sources: GET /api/reports/daily, /api/analytics/daily-learning, /api/analytics/metrics
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

      <!-- Tab bar -->
      <div class="leads-filter" id="rpTabs">
        <button class="filter-pill active" data-tab="daily">דוח יומי</button>
        <button class="filter-pill" data-tab="analytics">ביצועים</button>
        <button class="filter-pill" data-tab="metrics">מדדי ערוצים</button>
      </div>

      <!-- Daily report tab -->
      <div id="rpDailyView">
        <div class="stats-row" id="statsRow" style="margin:16px 0"></div>
        <div class="cmd-box" style="margin-bottom:16px" id="reportPipeSection" style="display:none">
          <div class="cmd-label">pipeline לפי שלב</div>
          <div id="reportPipeBars"></div>
        </div>
        <div class="cmd-label" style="margin-bottom:8px">דוח מפורט</div>
        <div id="rpInsight" style="margin-bottom:12px"></div>
        <div class="output-box" id="reportText"
             style="font-family:var(--mono);font-size:12px;direction:rtl;min-height:180px;">
          ${UI.loading('טוען דוח...')}
        </div>
      </div>

      <!-- Analytics drill-down tab -->
      <div id="rpAnalyticsView" style="display:none">
        <div id="rpAnalyticsContent">${UI.loading('טוען ניתוח ביצועים...')}</div>
      </div>

      <!-- Metrics table tab -->
      <div id="rpMetricsView" style="display:none">
        <div style="display:flex;gap:8px;margin:12px 0" id="rpMetricsTabs">
          <button class="filter-pill active" onclick="ReportsPanel.loadMetrics('channel')">ערוץ</button>
          <button class="filter-pill" onclick="ReportsPanel.loadMetrics('audience')">קהל</button>
          <button class="filter-pill" onclick="ReportsPanel.loadMetrics('opp_type')">סוג הזדמנות</button>
        </div>
        <div id="rpMetricsContent">${UI.loading('טוען מדדים...')}</div>
      </div>
    `;
  }

  let _activeTab = 'daily';

  async function init() {
    _activeTab = 'daily';
    await loadAll();

    document.querySelectorAll('#rpTabs .filter-pill').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#rpTabs .filter-pill').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _activeTab = btn.dataset.tab;
        document.getElementById('rpDailyView').style.display     = _activeTab === 'daily'     ? '' : 'none';
        document.getElementById('rpAnalyticsView').style.display = _activeTab === 'analytics' ? '' : 'none';
        document.getElementById('rpMetricsView').style.display   = _activeTab === 'metrics'   ? '' : 'none';
        if (_activeTab === 'analytics') loadAnalytics();
        if (_activeTab === 'metrics')   loadMetrics('channel');
      });
    });
  }

  async function loadAll() {
    const [reportRes, dealsRes] = await Promise.all([
      API.dailyReport(),
      API.deals(),
    ]);

    const txt = document.getElementById('reportText');
    const ts  = document.getElementById('reportTs');
    const row = document.getElementById('statsRow');

    if (!reportRes.success) {
      txt.innerHTML = UI.error('שגיאה בטעינת הדוח');
      return;
    }
    const { summary, report_text } = reportRes.data;
    ts.textContent = 'נוצר: ' + (summary?.generated_at || '').slice(0,19).replace('T',' ');
    txt.textContent = report_text || '—';

    const leads = summary?.leads || {};
    const tasks = summary?.tasks || {};

    _setText('rpwLeads', leads.total || 0);
    _setText('rpwHot',   leads.hot   || 0);
    _setText('rpwScore', leads.avg_score || 0);
    _setText('rpwDone',  tasks.done  || 0);

    // Insight strip
    const iChips = [];
    if (leads.hot > 0)    iChips.push({ icon: '🔥', text: `${leads.hot} לידים חמים`,      cls: 'insight-alert' });
    if (tasks.failed > 0) iChips.push({ icon: '⚠',  text: `${tasks.failed} משימות נכשלו`, cls: 'insight-warn'  });
    if (!iChips.length)   iChips.push({ icon: '✓',  text: 'מצב מערכת תקין',               cls: 'insight-good'  });
    const iEl = document.getElementById('rpInsight');
    if (iEl) iEl.innerHTML = UI.insightStrip(iChips);

    row.innerHTML = [
      { num: leads.total  || 0,  label: 'סה"כ לידים',    cls: '' },
      { num: leads.hot    || 0,  label: 'לידים חמים',     cls: 'pv-red' },
      { num: leads.avg_score||0, label: 'ציון ממוצע',     cls: 'pv-accent' },
      { num: tasks.done   || 0,  label: 'משימות הושלמו', cls: 'pv-green' },
      { num: tasks.failed || 0,  label: 'משימות נכשלו',  cls: 'pv-red' },
    ].map(s => `
      <div class="stat-card">
        <div class="stat-num ${s.cls}">${s.num}</div>
        <div class="stat-label">${s.label}</div>
      </div>
    `).join('');

    // Pipeline bars
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

  async function loadAnalytics() {
    const el  = document.getElementById('rpAnalyticsContent');
    el.innerHTML = UI.loading('טוען...');
    const res = await API.analyticsLearning();
    if (!res.success) { el.innerHTML = UI.error('שגיאה בטעינת ביצועים'); return; }
    const d = res.data;
    const rev24h = UI.ils(d.revenue?.last_24h || 0);
    const rev7d  = UI.ils(d.revenue?.last_7d  || 0);

    const metricBlock = (title, m) => {
      if (!m) return `<div class="ap-row"><span class="ap-key">${title}</span><span class="ap-val" style="color:var(--muted)">אין נתונים</span></div>`;
      const conv = ((m.conversion_rate || 0) * 100).toFixed(1);
      const avg  = UI.ils(m.avg_revenue || 0);
      return `
        <div class="health-card" style="margin-bottom:0">
          <div class="health-icon">📊</div>
          <div class="health-label">${title}</div>
          <div class="health-val hv-ok">${m.dim_value || '—'}</div>
          <div style="font-size:9px;color:var(--muted);margin-top:4px">
            המרה: ${conv}% · הכנסה ממוצעת: ${avg} · דגימות: ${m.sample_size || 0}
          </div>
        </div>
      `;
    };

    el.innerHTML = `
      <!-- Revenue windows -->
      <div class="cmd-box" style="margin-bottom:16px">
        <div class="cmd-label">הכנסות — חלונות זמן</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:8px">
          <div class="stat-card">
            <div class="stat-num pv-green">${rev24h}</div>
            <div class="stat-label">24 שעות אחרונות</div>
          </div>
          <div class="stat-card">
            <div class="stat-num pv-accent">${rev7d}</div>
            <div class="stat-label">7 ימים אחרונים</div>
          </div>
        </div>
      </div>

      <!-- Top performers -->
      <div class="cmd-label" style="margin-bottom:8px">ביצועי שיא</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
        ${metricBlock('ערוץ מוביל', d.top_channel)}
        ${metricBlock('קהל מוביל', d.top_audience)}
      </div>

      <div class="cmd-box">
        <div class="cmd-label">מדדים כוללים</div>
        <div style="padding:8px 0;font-size:11px;color:var(--muted)">
          סה"כ מדדים פעילים: <strong style="color:var(--text)">${d.all_metrics_count || 0}</strong>
          · מקור: performance_metrics + live_outreach_records
        </div>
      </div>
    `;
  }

  async function loadMetrics(dimType) {
    // Update active pill
    document.querySelectorAll('#rpMetricsTabs .filter-pill').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#rpMetricsTabs .filter-pill').forEach(b => {
      const map = { channel:'ערוץ', audience:'קהל', opp_type:'סוג הזדמנות' };
      if (b.textContent === (map[dimType] || dimType)) b.classList.add('active');
    });

    const el = document.getElementById('rpMetricsContent');
    el.innerHTML = UI.loading('טוען מדדים...');
    const res = await API.analyticsMetrics(dimType);
    if (!res.success) { el.innerHTML = UI.error('שגיאה בטעינת מדדים'); return; }
    const metrics = res.data.metrics || [];
    if (!metrics.length) { el.innerHTML = UI.empty('אין מדדים — נדרשות לפחות 3 דגימות', '○'); return; }

    const max = Math.max(...metrics.map(m => m.conversion_rate || 0), 0.01);
    el.innerHTML = `
      <table style="width:100%;border-collapse:collapse;font-size:11px">
        <thead>
          <tr style="color:var(--muted);border-bottom:1px solid var(--border)">
            <th style="text-align:right;padding:6px 4px">ערך</th>
            <th style="text-align:center;padding:6px 4px">המרה %</th>
            <th style="text-align:center;padding:6px 4px">הכנסה ממוצעת</th>
            <th style="text-align:center;padding:6px 4px">דגימות</th>
            <th style="padding:6px 4px;min-width:80px"></th>
          </tr>
        </thead>
        <tbody>
          ${metrics.map(m => {
            const conv = ((m.conversion_rate || 0) * 100).toFixed(1);
            const bar  = Math.round((m.conversion_rate || 0) / max * 100);
            return `
              <tr style="border-bottom:1px solid rgba(34,39,49,.3)">
                <td style="padding:7px 4px;font-family:var(--mono);color:var(--accent)">${m.dim_value || '—'}</td>
                <td style="padding:7px 4px;text-align:center;color:var(--green)">${conv}%</td>
                <td style="padding:7px 4px;text-align:center;color:var(--ils)">${UI.ils(m.avg_revenue || 0)}</td>
                <td style="padding:7px 4px;text-align:center;color:var(--muted)">${m.sample_size || 0}</td>
                <td style="padding:7px 4px">
                  <div style="height:4px;background:rgba(255,255,255,.06);border-radius:2px">
                    <div style="height:4px;background:var(--accent);border-radius:2px;width:${bar}%"></div>
                  </div>
                </td>
              </tr>`;
          }).join('')}
        </tbody>
      </table>
    `;
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  return { render, init: loadAll, reload: loadAll, loadMetrics };
})();
