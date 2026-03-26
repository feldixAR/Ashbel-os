/**
 * dashboard.js — Command Center
 * "תוך 5 שניות: איפה הכסף, מה חם, מה הפעולה הבאה"
 *
 * Widgets: KPI bar · Pipeline snapshot · Today queue · Hot leads ·
 *          Pending approvals · Unified activity timeline · Revenue pulse
 */
const DashboardPanel = (() => {

  const STAGE_HE = { new:'חדש', qualified:'כשיר', proposal:'הצעה', negotiation:'משא ומתן', won:'זכה', lost:'הפסיד' };
  const EV_ICON  = { message:'💬', whatsapp:'📱', email:'📧', call:'📞', meeting:'🤝', note:'📝', stage_change:'🔄', calendar:'📅' };

  function ils(n)    { return '₪' + (Number(n)||0).toLocaleString('he-IL'); }
  function initials(name) { return (name||'?').trim().split(/\s+/).map(w=>w[0]).join('').slice(0,2).toUpperCase(); }
  function relTime(s) {
    if (!s) return '';
    const diff = Math.floor((Date.now() - new Date(s)) / 60000);
    if (diff < 2)    return 'כעת';
    if (diff < 60)   return `לפני ${diff} דק'`;
    if (diff < 1440) return `לפני ${Math.floor(diff/60)} שע'`;
    return `לפני ${Math.floor(diff/1440)} ימ'`;
  }
  function stagePill(stage) {
    const cls = { new:'pill-steel', qualified:'pill-amber', proposal:'pill-amber', negotiation:'pill-steel', won:'pill-green', lost:'pill-red' };
    return `<span class="pill ${cls[stage]||''}">${STAGE_HE[stage]||stage}</span>`;
  }

  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">מרכז פיקוד</div>
          <div class="section-sub" id="dashDate">טוען...</div>
        </div>
        <button class="btn btn-ghost" id="dashRefresh" style="font-size:12px">↻ רענן</button>
      </div>

      <!-- KPI BAR -->
      <div class="kpi-bar" id="kpiBar">
        ${[0,1,2,3].map(()=>`<div class="kpi-card"><span class="skel skel-h20 skel-w80"></span><span class="skel skel-h12 skel-w60"></span></div>`).join('')}
      </div>

      <!-- 3-COL GRID -->
      <div class="dash-grid">
        <!-- Today Queue -->
        <div class="dash-cell">
          <div class="cell-title">תור היום<span class="live-dot"></span></div>
          <ul class="priority-list" id="todayQueue">
            ${skelItems(4)}
          </ul>
        </div>

        <!-- Revenue Pulse + Pipeline -->
        <div class="dash-cell">
          <div class="cell-title">דופק הכנסות</div>
          <div id="revPulse" style="margin-bottom:14px">
            <span class="skel skel-h60 skel-w80" style="display:block;margin: 0 auto"></span>
          </div>
          <div class="cell-title" style="margin-top:8px">Pipeline לפי שלב</div>
          <div id="pipeSnap">${skelItems(3, 'pipe')}</div>
        </div>

        <!-- Hot Leads + Approvals -->
        <div class="dash-cell">
          <div class="cell-title">לידים חמים 🔥</div>
          <div id="hotLeads">${skelItems(3,'hot')}</div>
          <div class="section-divider"></div>
          <div class="cell-title">ממתינים לאישור</div>
          <div id="miniApprovals">${skelItems(2,'ap')}</div>
        </div>
      </div>

      <!-- UNIFIED TIMELINE -->
      <div class="dash-cell" style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:14px">
        <div class="cell-title">ציר זמן מאוחד<span class="live-dot"></span></div>
        <div class="tl-feed" id="unifiedTl">${skelItems(5,'tl')}</div>
      </div>
    `;
  }

  function skelItems(n, type='p') {
    if (type === 'p')   return Array(n).fill('<div style="display:flex;gap:8px;padding:8px 0;border-bottom:1px solid rgba(34,39,49,.4)"><span class="skel skel-h12" style="width:14px;flex-shrink:0"></span><div style="flex:1"><span class="skel skel-h12 skel-w80"></span><span class="skel skel-h12 skel-w60"></span></div></div>').join('');
    if (type === 'hot') return Array(n).fill('<div style="display:flex;gap:9px;align-items:center;padding:7px 0;border-bottom:1px solid rgba(34,39,49,.4)"><span class="skel" style="width:28px;height:28px;border-radius:50%;flex-shrink:0"></span><div style="flex:1"><span class="skel skel-h12 skel-w80"></span><span class="skel skel-h12 skel-w40"></span></div></div>').join('');
    if (type === 'ap')  return Array(n).fill('<div style="display:flex;gap:7px;padding:7px 0;border-bottom:1px solid rgba(34,39,49,.4)"><span class="skel" style="width:5px;height:5px;border-radius:50%;margin-top:4px;flex-shrink:0"></span><div style="flex:1"><span class="skel skel-h12 skel-w80"></span></div></div>').join('');
    if (type === 'tl')  return Array(n).fill('<div style="display:flex;gap:9px;padding:7px 0;border-bottom:1px solid rgba(34,39,49,.4)"><span class="skel" style="width:26px;height:26px;border-radius:50%;flex-shrink:0"></span><div style="flex:1"><span class="skel skel-h12 skel-w80"></span><span class="skel skel-h12 skel-w60"></span></div></div>').join('');
    if (type === 'pipe')return Array(n).fill('<div style="display:flex;gap:7px;align-items:center;margin-bottom:5px"><span class="skel skel-h12" style="width:80px;flex-shrink:0"></span><span class="skel skel-h12" style="flex:1"></span><span class="skel skel-h12" style="width:48px;flex-shrink:0"></span></div>').join('');
    return '';
  }

  async function init() {
    await load();
    document.getElementById('dashRefresh')?.addEventListener('click', load);
  }

  async function load() {
    const [planRes, dealsRes, leadsRes, approvalsRes] = await Promise.all([
      API.dailyPlan(),
      API.deals(),
      API.leads({ limit: 50 }),
      API.approvals(),
    ]);

    const now = new Date();
    document.getElementById('dashDate').textContent =
      now.toLocaleDateString('he-IL', { weekday:'long', day:'numeric', month:'long' });

    const plan       = planRes.success   ? (planRes.data   || {}) : {};
    const deals      = dealsRes.success  ? (dealsRes.data?.deals  || []) : [];
    const leads      = leadsRes.success  ? (leadsRes.data?.leads  || []) : [];
    const approvals  = approvalsRes.success ? (approvalsRes.data?.approvals || []) : [];

    renderKPIs(plan, deals, leads, approvals);
    renderTodayQueue(plan.priority_items || []);
    renderRevPulse(plan, deals);
    renderPipeSnap(deals);
    renderHotLeads(leads);
    renderApprovals(approvals);
    renderTimeline(leads, deals);
  }

  function renderKPIs(plan, deals, leads, approvals) {
    const activeDeals  = deals.filter(d => !['won','lost'].includes(d.stage));
    const pipeline     = plan.pipeline_value || activeDeals.reduce((s,d)=>s+Math.round((d.value_ils||0)*(d.probability||0.2)),0);
    const hotLeads     = leads.filter(l => l.status === 'חם').length;
    const todayEvents  = (plan.todays_events || []).length;
    const topPriority  = (plan.priority_items||[])[0];

    document.getElementById('kpiBar').innerHTML = `
      <div class="kpi-card">
        <span class="kpi-icon">💰</span>
        <div class="kpi-val kv-ils">${ils(pipeline)}</div>
        <div class="kpi-label">שווי Pipeline</div>
        <span class="kpi-trend flat">— משוקלל</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-icon">📋</span>
        <div class="kpi-val kv-copper">${activeDeals.length}</div>
        <div class="kpi-label">עסקאות פעילות</div>
        <span class="kpi-trend flat">— מתוך ${deals.length} סה"כ</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-icon">🔥</span>
        <div class="kpi-val kv-green">${hotLeads}</div>
        <div class="kpi-label">לידים חמים</div>
        <span class="kpi-trend flat">— מתוך ${leads.length} לידים</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-icon">📅</span>
        <div class="kpi-val">${todayEvents}</div>
        <div class="kpi-label">אירועים היום</div>
        ${approvals.length ? `<span class="kpi-trend down">▲ ${approvals.length} ממתינים</span>` : `<span class="kpi-trend flat">— ללא המתנה</span>`}
      </div>
    `;
  }

  function renderTodayQueue(items) {
    const el = document.getElementById('todayQueue');
    if (!items.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">✅</div><div class="empty-state-msg">אין פריטים ממתינים</div></div>';
      return;
    }
    el.innerHTML = items.slice(0,6).map((it, i) => {
      const pct = Math.round(it.score || 0);
      return `
        <li class="priority-item" onclick="App.switchTo('${it.item_type==='deal'?'crm':'workspace'}')">
          <span class="p-rank">${i+1}</span>
          <div class="p-info">
            <div class="p-title">${it.title}</div>
            <div class="p-sub">${it.reason||''}</div>
          </div>
          <span class="p-score">${Math.round(pct)}</span>
          <div class="p-bar"><div class="p-bar-fill" style="width:${pct}%"></div></div>
        </li>`;
    }).join('');
  }

  function renderRevPulse(plan, deals) {
    const el = document.getElementById('revPulse');
    const pv = plan.pipeline_value || 0;
    const won = deals.filter(d=>d.stage==='won').reduce((s,d)=>s+(d.value_ils||0),0);
    const total = pv + won || 1;
    el.innerHTML = `
      <div style="text-align:center;padding:4px 0 10px">
        <div class="revenue-big">${ils(pv)}</div>
        <div class="rev-label">Pipeline פעיל היום</div>
      </div>
      <div class="pipe-row">
        <span class="pipe-label">Pipeline</span>
        <div class="pipe-track"><div class="pipe-fill" style="width:${Math.min(100,pv/total*100).toFixed(1)}%"></div></div>
        <span class="pipe-val">${ils(pv)}</span>
      </div>
      <div class="pipe-row">
        <span class="pipe-label">נסגר (Won)</span>
        <div class="pipe-track"><div class="pipe-fill pf-w" style="width:${Math.min(100,won/total*100).toFixed(1)}%"></div></div>
        <span class="pipe-val">${ils(won)}</span>
      </div>
    `;
  }

  function renderPipeSnap(deals) {
    const stages = ['new','qualified','proposal','negotiation'];
    const cls    = ['','pf-q','pf-p','pf-n'];
    const totals = stages.map(s => deals.filter(d=>d.stage===s).reduce((sum,d)=>sum+(d.value_ils||0),0));
    const max    = Math.max(...totals, 1);
    document.getElementById('pipeSnap').innerHTML = stages.map((s,i) => `
      <div class="pipe-row">
        <span class="pipe-label">${STAGE_HE[s]}</span>
        <div class="pipe-track"><div class="pipe-fill ${cls[i]}" style="width:${(totals[i]/max*100).toFixed(1)}%"></div></div>
        <span class="pipe-val">${ils(totals[i])}</span>
      </div>`).join('');
  }

  function renderHotLeads(leads) {
    const hot = leads.filter(l=>l.status==='חם').slice(0,4);
    document.getElementById('hotLeads').innerHTML = hot.length
      ? hot.map(l=>`
          <div class="hot-item" onclick="App.switchTo('workspace')">
            <div class="hot-av">${initials(l.name)}</div>
            <div class="hot-info">
              <div class="hot-name">${l.name}</div>
              <div class="hot-status">${l.company||l.sector||''}</div>
            </div>
            <span class="hot-score">${l.score||0}</span>
          </div>`).join('')
      : '<div class="empty-state"><div class="empty-state-msg">אין לידים חמים</div></div>';
  }

  function renderApprovals(approvals) {
    document.getElementById('miniApprovals').innerHTML = approvals.length
      ? approvals.slice(0,3).map(a=>`
          <div class="mini-approval-item">
            <div class="mini-ap-dot"></div>
            <div>
              <div class="mini-ap-text">${a.action||a.type||'אישור נדרש'}</div>
              <div class="mini-ap-sub">${(a.detail||'').slice(0,60)}</div>
            </div>
          </div>`).join('')
      : '<div style="font-size:11px;color:var(--muted);padding:6px 0">✅ אין ממתינים לאישור</div>';
  }

  function renderTimeline(leads, deals) {
    // Build quick synthetic events from deal data as fallback
    const events = [];
    deals.slice(0,3).forEach(d => {
      events.push({ icon: EV_ICON['stage_change'], title: `עסקה: ${d.title}`, meta: `שלב: ${STAGE_HE[d.stage]||d.stage}`, when: d.created_at });
    });
    leads.filter(l=>l.last_contact).slice(0,2).forEach(l => {
      events.push({ icon: EV_ICON['call'], title: `קשר עם ${l.name}`, meta: l.status||'', when: l.last_contact });
    });

    document.getElementById('unifiedTl').innerHTML = events.length
      ? events.slice(0,5).map(e=>`
          <div class="tl-item">
            <div class="tl-icon">${e.icon||'●'}</div>
            <div class="tl-body">
              <div class="tl-title">${e.title}</div>
              <div class="tl-meta">${e.meta}</div>
            </div>
            <span class="tl-when">${relTime(e.when)}</span>
          </div>`).join('')
      : '<div class="empty-state"><div class="empty-state-msg">אין פעילות עדכנית</div></div>';
  }

  return { render, init };
})();
