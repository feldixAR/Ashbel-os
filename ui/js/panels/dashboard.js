/**
 * dashboard.js — לוח בקרה Dashboard (Batch 10)
 * מסמך היסוד: "תוך 5–10 שניות להבין מה קורה, איפה הכסף, מה תקוע, מה הפעולה הבאה"
 */
const DashboardPanel = (() => {

  function statusColor(s) {
    return { green: '#22c55e', yellow: '#f59e0b', red: '#ef4444' }[s] || 'var(--text-muted)';
  }

  function severityIcon(s) {
    return { critical: '🔴', warning: '🟡', info: '🔵' }[s] || '⚪';
  }

  function render() {
    return `
      <div class="section-head" style="margin-bottom:0">
        <div>
          <div class="section-title">לוח בקרה</div>
          <div class="section-sub" id="dashTs">טוען...</div>
        </div>
        <button class="btn btn-secondary" id="dashRefreshBtn" title="רענן">↻ רענן</button>
      </div>

      <!-- KPI Row -->
      <div id="dashKpiRow" style="display:flex;gap:10px;flex-wrap:wrap;margin:16px 0 20px">
        ${[1,2,3,4,5,6].map(() => `<div class="kpi-skeleton" style="flex:1;min-width:120px;height:72px;background:var(--surface-2);border-radius:10px;animation:pulse 1.2s infinite"></div>`).join('')}
      </div>

      <!-- Two-column: Alerts + Today Queue -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
        <div>
          <div style="font-weight:600;font-size:13px;margin-bottom:10px;color:var(--text-muted)">⚠️ התראות פעילות</div>
          <div id="dashAlerts"><div style="color:var(--text-muted);font-size:13px">טוען...</div></div>
        </div>
        <div>
          <div style="font-weight:600;font-size:13px;margin-bottom:10px;color:var(--text-muted)">📋 תור היום</div>
          <div id="dashTodayQueue"><div style="color:var(--text-muted);font-size:13px">טוען...</div></div>
        </div>
      </div>

      <!-- Pipeline snapshot -->
      <div style="font-weight:600;font-size:13px;margin-bottom:10px;color:var(--text-muted)">📊 Pipeline Snapshot</div>
      <div id="dashPipeline"></div>

      <!-- Quick actions -->
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:20px">
        <button class="btn btn-primary"    onclick="DashboardPanel.quickCmd('מה הצעד הבא')">🎯 Next Action</button>
        <button class="btn btn-secondary"  onclick="DashboardPanel.quickCmd('מה תקוע')">🔍 Bottlenecks</button>
        <button class="btn btn-secondary"  onclick="DashboardPanel.quickCmd('תכנן לי את היום')">📅 Daily Plan</button>
        <button class="btn btn-secondary"  onclick="DashboardPanel.quickCmd('לידים חמים')">🔥 Hot Leads</button>
        <button class="btn btn-secondary"  onclick="DashboardPanel.quickCmd('דוח יומי')">📄 Daily Report</button>
      </div>
      <div id="dashQuickOut" style="margin-top:12px"></div>
    `;
  }

  async function init() {
    await load();
    document.getElementById('dashRefreshBtn')?.addEventListener('click', load);
  }

  async function load() {
    const [dashRes, outRes] = await Promise.all([
      API.get('/dashboard'),
      API.get('/outreach/summary'),
    ]);

    // Timestamp
    if (dashRes.success) {
      const ts = (dashRes.data.generated_at || '').slice(0, 16).replace('T', ' ');
      document.getElementById('dashTs').textContent = `עודכן: ${ts} UTC`;
    }

    // KPIs
    const kpis = dashRes.success ? (dashRes.data.kpis || []) : [];
    document.getElementById('dashKpiRow').innerHTML = kpis.length
      ? kpis.map(k => `
          <div class="card" style="flex:1;min-width:120px;text-align:center;padding:12px 8px">
            <div style="font-size:22px;font-weight:700;color:${statusColor(k.status)}">${k.value}<span style="font-size:12px;font-weight:400;margin-right:3px">${k.unit}</span></div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:3px">${k.label}</div>
            <div style="font-size:10px;color:${statusColor(k.status)};margin-top:2px">${k.trend === 'up' ? '↑' : k.trend === 'down' ? '↓' : '→'} יעד: ${k.target}</div>
          </div>`).join('')
      : '<div style="color:var(--text-muted);font-size:13px">אין KPI נתונים</div>';

    // Alerts
    const alerts = dashRes.success ? (dashRes.data.alerts || []) : [];
    document.getElementById('dashAlerts').innerHTML = alerts.length
      ? alerts.slice(0, 5).map(a => `
          <div style="display:flex;gap:8px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--border)">
            <span>${severityIcon(a.severity)}</span>
            <div>
              <div style="font-size:13px">${a.message}</div>
              <div style="font-size:11px;color:var(--text-muted);margin-top:2px">${a.action}</div>
            </div>
          </div>`).join('')
      : '<div style="color:var(--text-muted);font-size:13px">אין התראות 🟢</div>';

    // Today queue from outreach summary
    const top = outRes.success ? (outRes.data.top_priorities || []) : [];
    document.getElementById('dashTodayQueue').innerHTML = top.length
      ? top.slice(0, 5).map(t => `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--border)">
            <div>
              <div style="font-size:13px;font-weight:500">${t.lead_name}</div>
              <div style="font-size:11px;color:var(--text-muted)">${t.reason}</div>
            </div>
            ${t.deep_link ? `<a href="${t.deep_link}" target="_blank" class="btn btn-xs" style="flex-shrink:0">📱</a>` : ''}
          </div>`).join('')
      : '<div style="color:var(--text-muted);font-size:13px">תור ריק</div>';

    // Pipeline snapshot
    const rev = dashRes.success ? (dashRes.data.revenue_summary || {}) : {};
    const pipe = dashRes.success ? (dashRes.data.pipeline_summary || {}) : {};
    document.getElementById('dashPipeline').innerHTML = `
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        ${_snapCard('סה"כ לידים', rev.total_leads ?? '—', '')}
        ${_snapCard('לידים חמים', rev.hot_leads ?? '—', '🔥')}
        ${_snapCard('שווי צנרת', rev.pipeline_value ? '₪' + Number(rev.pipeline_value).toLocaleString() : '—', '💰')}
        ${_snapCard('outreach שנשלחו', pipe.total_sent ?? outRes.data?.total_due ?? '—', '📤')}
        ${_snapCard('ענו', pipe.total_replied ?? '—', '💬')}
      </div>`;
  }

  function _snapCard(label, value, icon) {
    return `
      <div class="card" style="flex:1;min-width:110px;padding:10px 12px">
        <div style="font-size:18px;font-weight:700">${icon} ${value}</div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:3px">${label}</div>
      </div>`;
  }

  async function quickCmd(cmd) {
    const out = document.getElementById('dashQuickOut');
    out.innerHTML = `<div style="color:var(--text-muted);font-size:13px;padding:8px">מריץ: ${cmd}...</div>`;
    const res = await API.post('/command', { command: cmd });
    out.innerHTML = `
      <div class="card" style="margin-top:4px">
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:6px">${cmd}</div>
        <div style="white-space:pre-wrap;font-size:13px">${res.data?.message || res.data?.message || res.message || JSON.stringify(res.data, null, 2)}</div>
      </div>`;
  }

  return { render, init, quickCmd };
})();
