/**
 * dashboard.js — Executive Revenue Command Center
 * Living monitor: radial gauge · pressure dials · action queue · intelligence engine
 */
const DashboardPanel = (() => {

  // ── SVG gradient defs (injected once) ─────────────────────────────────
  const DEFS = `
  <svg class="cc-svg-defs" aria-hidden="true">
    <defs>
      <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stop-color="#4e6070"/>
        <stop offset="50%"  stop-color="#c8d2de"/>
        <stop offset="100%" stop-color="#dde5ef"/>
      </linearGradient>
      <linearGradient id="dialGrad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stop-color="#4e6070"/>
        <stop offset="100%" stop-color="#c8d2de"/>
      </linearGradient>
    </defs>
  </svg>`;

  // ── Helpers ────────────────────────────────────────────────────────────
  function ils(n) {
    n = Number(n) || 0;
    if (n >= 1_000_000) return `₪${(n/1_000_000).toFixed(1)}M`;
    if (n >= 1_000)     return `₪${Math.round(n/1_000)}K`;
    return `₪${n.toLocaleString('he-IL')}`;
  }

  function initials(name) {
    return (name || '?').trim().split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
  }

  // ── Dial SVG ──────────────────────────────────────────────────────────
  function dialSVG(id, label) {
    const circ = 226.19;
    return `
    <div class="cc-dial">
      <svg class="cc-dial-svg" viewBox="0 0 90 90">
        <circle class="dial-track" cx="45" cy="45" r="36"/>
        <circle class="dial-fill"  cx="45" cy="45" r="36"
          stroke-dasharray="${circ}" stroke-dashoffset="${circ}" id="dial-${id}"/>
        <text class="dial-pct" x="45" y="50" id="dial-pct-${id}">—</text>
      </svg>
      <div class="cc-dial-label">${label}</div>
      <div class="cc-dial-val" id="dial-val-${id}">—</div>
    </div>`;
  }

  // ── Render shell ──────────────────────────────────────────────────────
  function render() {
    const now = new Date();
    const dateStr = now.toLocaleDateString('he-IL', { weekday: 'long', day: 'numeric', month: 'long' });

    return `
    ${DEFS}
    <div class="cc-shell">

      <!-- Status bar -->
      <div class="cc-status-bar">
        <div class="cc-status-item">
          <div class="cc-pulse-dot"></div>
          REVENUE COMMAND CENTER
        </div>
        <span style="font-family:var(--mono);font-size:9px;color:var(--muted)">${dateStr}</span>
        <div class="cc-live-monitors" id="ccMonitors">
          <div class="cc-monitor"><span class="cc-mon-val">—</span><span class="cc-mon-label">PIPELINE</span></div>
          <div class="cc-mon-sep"></div>
          <div class="cc-monitor"><span class="cc-mon-val">—</span><span class="cc-mon-label">DEALS</span></div>
          <div class="cc-mon-sep"></div>
          <div class="cc-monitor"><span class="cc-mon-val">—</span><span class="cc-mon-label">HOT</span></div>
          <div class="cc-mon-sep"></div>
          <div class="cc-monitor"><span class="cc-mon-val">—</span><span class="cc-mon-label">ACTIONS</span></div>
        </div>
        <button class="btn-xs" id="dashRefresh" style="margin-right:auto">↻</button>
      </div>

      <!-- Main hub -->
      <div class="cc-hub">

        <!-- Left: Central radial gauge -->
        <div class="cc-gauge-hub">
          <div class="cc-gauge-title">PIPELINE REVENUE</div>
          <div class="cc-radial-wrap">
            <svg class="cc-radial" viewBox="0 0 200 200">
              <!-- Deco rings -->
              <circle class="gauge-deco" cx="100" cy="100" r="95"/>
              <circle class="gauge-deco" cx="100" cy="100" r="46"/>
              <!-- Background tracks -->
              <circle class="gauge-track"    cx="100" cy="100" r="80"/>
              <circle class="gauge-track-sm" cx="100" cy="100" r="62"/>
              <!-- Live fill rings -->
              <circle class="gauge-fill gauge-revenue" cx="100" cy="100" r="80" id="gaugeRevenue"/>
              <circle class="gauge-fill gauge-deals"   cx="100" cy="100" r="62" id="gaugeDeals"/>
            </svg>
            <div class="cc-gauge-center">
              <div class="cc-gauge-val" id="gaugeVal">—</div>
              <div class="cc-gauge-sub" id="gaugeSub">טוען...</div>
            </div>
          </div>
          <div class="cc-gauge-meta">
            <div class="cc-meta-item">
              <span class="cc-meta-dot dot-silver"></span>
              <span id="metaDeals">—</span>&nbsp;עסקאות פעילות
            </div>
            <div class="cc-meta-item">
              <span class="cc-meta-dot dot-green"></span>
              <span id="metaHot">—</span>&nbsp;לידים חמים
            </div>
          </div>
        </div>

        <!-- Center: Pressure dials + action queue -->
        <div class="cc-dials-col">
          <div class="cc-dials-title">STAGE PRESSURE</div>
          <div class="cc-dials">
            ${dialSVG('qualif',      'QUALIF.')}
            ${dialSVG('proposal',    'PROPOSAL')}
            ${dialSVG('negotiation', 'CLOSING')}
          </div>
          <div class="cc-queue-wrap">
            <div class="cc-queue-title">
              TODAY'S ACTION QUEUE
              <span class="cc-queue-count" id="queueCount">—</span>
            </div>
            <div class="cc-queue" id="ccQueue">
              ${[1,2,3,4].map(() => `
              <div class="cc-q-item">
                <span class="cc-q-rank">·</span>
                <div class="cc-q-info">
                  <span class="skel skel-h12 skel-w80"></span>
                  <span class="skel skel-h12 skel-w40" style="margin-top:3px"></span>
                </div>
              </div>`).join('')}
            </div>
          </div>
        </div>

        <!-- Right: Revenue intelligence engine -->
        <div class="cc-assistant">
          <div class="cc-asst-header">
            <div class="cc-asst-title">
              <div class="cc-asst-pulse"></div>
              REVENUE INTELLIGENCE
            </div>
            <div class="cc-asst-sub">LIVE RECOMMENDATIONS</div>
          </div>
          <div class="cc-asst-body" id="asstBody">
            ${[1,2,3].map(() => `
            <div class="cc-signal">
              <span class="skel" style="width:18px;height:18px;border-radius:3px;flex-shrink:0"></span>
              <div style="flex:1">
                <span class="skel skel-h12 skel-w80"></span>
                <span class="skel skel-h12 skel-w60" style="margin-top:5px"></span>
              </div>
            </div>`).join('')}
          </div>
        </div>

      </div>
    </div>`;
  }

  // ── Update radial gauge ring ───────────────────────────────────────────
  function setGauge(id, pct, totalCirc) {
    const el = document.getElementById(id);
    if (!el) return;
    const offset = totalCirc * (1 - Math.min(Math.max(pct, 0), 1));
    el.style.strokeDasharray  = `${totalCirc}`;
    el.style.strokeDashoffset = `${offset}`;
  }

  // ── Update pressure dial ───────────────────────────────────────────────
  function setDial(id, pct, valText) {
    const circ  = 226.19;
    const fill  = document.getElementById(`dial-${id}`);
    const pctEl = document.getElementById(`dial-pct-${id}`);
    const valEl = document.getElementById(`dial-val-${id}`);
    if (!fill) return;
    fill.style.strokeDasharray  = `${circ}`;
    fill.style.strokeDashoffset = `${circ * (1 - Math.min(Math.max(pct, 0), 1))}`;
    if (pctEl) pctEl.textContent = Math.round(pct * 100) + '%';
    if (valEl) valEl.textContent = valText;
  }

  // ── Build intelligence signals ─────────────────────────────────────────
  function buildSignals(deals, leads, plan) {
    const signals = [];
    const active  = deals.filter(d => !['won','lost'].includes(d.stage));
    const pipeline = plan?.pipeline_value || active.reduce((s,d) => s+(d.value||d.value_ils||0), 0);

    // Top opportunity: highest-value active deal
    const top = [...active].sort((a,b) => (b.value||b.value_ils||0) - (a.value||a.value_ils||0))[0];
    if (top) signals.push({
      type: 'opportunity',
      icon: '▲',
      title: `הזדמנות מובילה: ${top.title || top.name || '—'}`,
      text:  `${ils(top.value||top.value_ils)} · שלב ${top.stage}`,
    });

    // Hot leads not yet contacted
    const hotNew = leads.filter(l => l.status === 'חם' && !l.last_contact).slice(0, 2);
    hotNew.forEach(l => signals.push({
      type: 'signal',
      icon: '◉',
      title: `ליד חם ללא מגע: ${l.name || l.company || '—'}`,
      text:  'קבע פגישה או שלח הצעה מחיר',
    }));

    // Pipeline pressure signal
    if (pipeline < 30000) signals.push({
      type: 'risk',
      icon: '⚠',
      title: 'לחץ פייפליין נמוך',
      text:  `${ils(pipeline)} פעיל — הזן עסקאות חדשות`,
    });

    // Closing stage deals
    const closing = active.filter(d => ['negotiation','closing'].includes((d.stage||'').toLowerCase()));
    if (closing.length) signals.push({
      type: 'opportunity',
      icon: '◈',
      title: `${closing.length} עסקאות בשלב סגירה`,
      text:  `${ils(closing.reduce((s,d)=>s+(d.value||d.value_ils||0),0))} — פעל היום`,
    });

    // Today's top action
    const actions = plan?.priority_items || plan?.priorities || [];
    if (actions.length) signals.push({
      type: 'action',
      icon: '→',
      title: `פעולה ראשונה להיום`,
      text:  actions[0]?.title || actions[0]?.lead_name || `${actions.length} פריטים בתור`,
    });

    if (!signals.length) signals.push({
      type: 'ok', icon: '✓',
      title: 'כל המערכות תקינות',
      text:  'אין אזהרות פעילות',
    });

    return signals;
  }

  // ── Main async init ────────────────────────────────────────────────────
  async function init() {
    await load();
    document.getElementById('dashRefresh')?.addEventListener('click', load);
  }

  async function load() {
    const [planRes, dealsRes, leadsRes] = await Promise.all([
      API.dailyPlan(300),
      API.deals(),
      API.leads({ limit: 60 }),
    ]);

    const plan   = planRes.success  ? (planRes.data  || {}) : {};
    const deals  = dealsRes.success ? (dealsRes.data?.deals || []) : [];
    const leads  = leadsRes.success ? (leadsRes.data?.leads || []) : [];
    const active = deals.filter(d => !['won','lost'].includes(d.stage));

    const pipeline = plan.pipeline_value ||
      active.reduce((s,d) => s + (d.value||d.value_ils||0), 0);
    const TARGET   = 200_000;
    const hotCount = leads.filter(l => l.status === 'חם').length;

    // ── Central gauge ─────────────────────────────────────────────────────
    setGauge('gaugeRevenue', pipeline / TARGET, 502.65);
    setGauge('gaugeDeals',   Math.min(active.length / 20, 1), 389.56);

    document.getElementById('gaugeVal').textContent = ils(pipeline);
    document.getElementById('gaugeSub').textContent = 'PIPELINE ACTIVE';
    document.getElementById('metaDeals').textContent = active.length;
    document.getElementById('metaHot').textContent   = hotCount;

    // ── Status bar monitors ───────────────────────────────────────────────
    const actions = plan.priority_items || plan.priorities || [];
    document.getElementById('ccMonitors').innerHTML = `
      <div class="cc-monitor">
        <span class="cc-mon-val cc-mon-ils">${ils(pipeline)}</span>
        <span class="cc-mon-label">PIPELINE</span>
      </div>
      <div class="cc-mon-sep"></div>
      <div class="cc-monitor">
        <span class="cc-mon-val">${active.length}</span>
        <span class="cc-mon-label">DEALS</span>
      </div>
      <div class="cc-mon-sep"></div>
      <div class="cc-monitor">
        <span class="cc-mon-val cc-mon-ok">${hotCount}</span>
        <span class="cc-mon-label">HOT LEADS</span>
      </div>
      <div class="cc-mon-sep"></div>
      <div class="cc-monitor">
        <span class="cc-mon-val">${actions.length}</span>
        <span class="cc-mon-label">ACTIONS</span>
      </div>`;

    // ── Pressure dials (deals by stage) ───────────────────────────────────
    const stageBuckets = { qualif: 0, proposal: 0, negotiation: 0 };
    const stageVals    = { qualif: 0, proposal: 0, negotiation: 0 };
    active.forEach(d => {
      const s = (d.stage || '').toLowerCase();
      const v = d.value || d.value_ils || 0;
      if (['new','qualified','contact'].some(x => s.includes(x))) {
        stageBuckets.qualif++;   stageVals.qualif   += v;
      } else if (['proposal','quote','offer'].some(x => s.includes(x))) {
        stageBuckets.proposal++; stageVals.proposal += v;
      } else if (['negotiation','closing','neg'].some(x => s.includes(x))) {
        stageBuckets.negotiation++; stageVals.negotiation += v;
      }
    });
    const maxB = Math.max(...Object.values(stageBuckets), 1);
    setDial('qualif',      stageBuckets.qualif      / maxB, ils(stageVals.qualif));
    setDial('proposal',    stageBuckets.proposal    / maxB, ils(stageVals.proposal));
    setDial('negotiation', stageBuckets.negotiation / maxB, ils(stageVals.negotiation));

    // ── Action queue ──────────────────────────────────────────────────────
    const queue = actions.length
      ? actions
      : active.slice(0, 6).map(d => ({ title: d.title, stage: d.stage, value: d.value||d.value_ils }));

    document.getElementById('queueCount').textContent = queue.length;
    document.getElementById('ccQueue').innerHTML = queue.slice(0, 7).map((it, i) => {
      const urgency = Math.round((1 - i * 0.13) * 100);
      return `
      <div class="cc-q-item" onclick="App.switchTo('workspace')">
        <span class="cc-q-rank">${i+1}</span>
        <div class="cc-q-info">
          <div class="cc-q-title">${it.title || it.lead_name || '—'}</div>
          <div class="cc-q-sub">${it.stage||''} ${(it.value||it.value_ils) ? '· '+ils(it.value||it.value_ils) : ''}</div>
        </div>
        <div class="cc-q-urgency" style="width:${urgency}%"></div>
      </div>`;
    }).join('');

    // ── Intelligence signals ──────────────────────────────────────────────
    const signals = buildSignals(deals, leads, plan);
    document.getElementById('asstBody').innerHTML = signals.map(s => `
    <div class="cc-signal cc-signal-${s.type}">
      <div class="cc-signal-icon">${s.icon}</div>
      <div class="cc-signal-body">
        <div class="cc-signal-title">${s.title}</div>
        <div class="cc-signal-text">${s.text}</div>
      </div>
    </div>`).join('');
  }

  return { render, init };
})();
