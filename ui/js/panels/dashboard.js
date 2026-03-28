/**
 * dashboard.js — Executive Revenue Control Center
 * Implements the approved preview design: light silver metallic, glass morphism,
 * animated ring gauge, AI recommendation engine, risk/opportunity queue.
 */
const DashboardPanel = (() => {

  // ── Helpers ────────────────────────────────────────────────────────────
  function ils(n) {
    n = Number(n) || 0;
    if (n >= 1_000_000) return `₪${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000)     return `₪${Math.round(n / 1_000)}K`;
    return `₪${n.toLocaleString('he-IL')}`;
  }
  function stageLabel(s) {
    return ({ new: 'חדש', qualified: 'כשיר', proposal: 'בשלב הצעה',
              negotiation: 'לקראת סגירה', won: 'זכה', lost: 'הפסיד' })[s] || s || '—';
  }
  function riskLabel(deal) {
    const s = (deal.stage || '').toLowerCase();
    if (['negotiation','closing'].some(x => s.includes(x))) return 'גבוה';
    if (['proposal','quote'].some(x => s.includes(x)))     return 'בינוני';
    return 'נמוך';
  }

  // ── Skeleton helpers ───────────────────────────────────────────────────
  function skelCard() {
    return `<div class="cc2-decision-card">
      <div class="skel skel-h12" style="width:70%;background:rgba(0,0,0,.08)"></div>
      <div class="skel skel-h20" style="width:50%;margin-top:8px;background:rgba(0,0,0,.08)"></div>
      <div class="skel skel-h12" style="width:80%;margin-top:6px;background:rgba(0,0,0,.08)"></div>
    </div>`;
  }
  function skelSignal() {
    return `<div class="cc2-signal-card">
      <div class="skel skel-h12" style="width:80%;background:rgba(0,0,0,.08)"></div>
      <div class="skel skel-h20" style="width:50%;margin-top:8px;background:rgba(0,0,0,.08)"></div>
      <div class="skel skel-h12" style="width:70%;margin-top:6px;background:rgba(0,0,0,.08)"></div>
    </div>`;
  }
  function skelQueueItem() {
    return `<div class="cc2-queue-item">
      <div class="cc2-qi-head">
        <div class="skel skel-h12" style="width:55%;background:rgba(255,255,255,.1)"></div>
        <span class="cc2-qi-dot"></span>
      </div>
      <div class="cc2-deal-fields" style="margin-top:10px">
        ${[0,1,2].map(() => `<div class="cc2-deal-field"><div class="skel skel-h12" style="width:90%;background:rgba(255,255,255,.07)"></div></div>`).join('')}
      </div>
    </div>`;
  }

  // ── Render ─────────────────────────────────────────────────────────────
  function render() {
    const topKeys = ['סטטוס מערכת', 'לחץ הכנסה', 'הזדמנויות חיות', 'פעולות חמות'];
    const chips   = ['זהה את מוקד ההכנסה הבא', 'הצג מעקבים הדורשים תשומת לב', 'הכן מהלך מומלץ לסגירה', 'הצג עסקאות עם סיכון עולה'];

    return `
    <div class="cc2-shell" dir="rtl">
      <div class="cc2-bg"></div>
      <div class="cc2-grid-overlay"></div>
      <div class="cc2-glow cc2-glow-r"></div>
      <div class="cc2-glow cc2-glow-l"></div>

      <!-- ── Header ── -->
      <header class="cc2-header">
        <div class="cc2-brand">
          <div class="cc2-logo-ring">
            <div class="cc2-logo-ping"></div>
            <div class="cc2-logo-ring2"></div>
            <span class="cc2-logo-text">AO</span>
          </div>
          <div>
            <div class="cc2-brand-label">ASHBALOS</div>
            <h1 class="cc2-brand-title">Executive Revenue Control Center</h1>
            <p class="cc2-brand-sub">מרכז שליטה עסקי חכם עם סדר עדיפויות, לחץ הכנסה ופעולה מומלצת בזמן אמת</p>
          </div>
        </div>
        <div class="cc2-top-strip">
          ${topKeys.map((k, i) => `
          <div class="cc2-stat-chip">
            <div class="cc2-chip-label">${k}</div>
            <div class="cc2-chip-val" dir="ltr">
              <span class="cc2-live-dot"></span>
              <span id="cc2s${i}">—</span>
            </div>
          </div>`).join('')}
        </div>
      </header>

      <!-- ── Main ── -->
      <main class="cc2-main">

        <!-- Left large section -->
        <section class="cc2-left">
          <div class="cc2-left-inner">

            <!-- Intelligence priority panel -->
            <div class="cc2-intel">
              <div class="cc2-intel-head">
                <div>
                  <div class="cc2-section-label">INTELLIGENCE PRIORITY</div>
                  <h2 class="cc2-intel-title">מה צפוי לייצר את ההשפעה העסקית הקרובה ביותר</h2>
                  <p class="cc2-intel-desc">בתוך מוקד אחד מוצגים פוטנציאל ההכנסה, רמת הדחיפות, חלון הסיכון וההמלצה הבאה לביצוע. המטרה היא להבין מהר מה מקדם כסף ומה דורש החלטה עכשיו.</p>
                </div>
                <span class="cc2-intel-badge">מצב בינה פעיל</span>
              </div>

              <div class="cc2-intel-body">
                <!-- Dark ring card -->
                <div class="cc2-gauge-card">
                  <div class="cc2-gauge-top">
                    <span>מוקד הכנסה מרכזי</span>
                    <span class="cc2-live-badge">Live</span>
                  </div>
                  <div class="cc2-ring-wrap">
                    <div class="cc2-ring-halo"></div>
                    <div class="cc2-ring-orbit"></div>
                    <div class="cc2-ring-spinner"></div>
                    <div class="cc2-ring-inner"></div>
                    <div class="cc2-ring-core"></div>
                    <div class="cc2-ring-center">
                      <div class="cc2-rc-label">FOCUS SCORE</div>
                      <div class="cc2-rc-val" id="cc2FocusScore">—</div>
                      <div class="cc2-rc-sub">סבירות מימוש ברבעון הנוכחי</div>
                      <div class="cc2-rc-live">
                        <span class="cc2-rc-dot"></span>
                        הזדמנות חיה ברמת עדיפות גבוהה
                      </div>
                    </div>
                    <!-- Floating stat chips -->
                    <div class="cc2-rf cc2-rf-r">
                      <div class="cc2-rf-label">לחץ הכנסה</div>
                      <div class="cc2-rf-val cc2-rf-sky" id="cc2Pressure">—</div>
                    </div>
                    <div class="cc2-rf cc2-rf-l">
                      <div class="cc2-rf-label">סיכון</div>
                      <div class="cc2-rf-val cc2-rf-amber" id="cc2Risk">—</div>
                    </div>
                    <div class="cc2-rf cc2-rf-b">
                      <div class="cc2-rf-label">הצעד הבא</div>
                      <div class="cc2-rf-val cc2-rf-white" id="cc2Next">—</div>
                    </div>
                  </div>
                </div>

                <!-- Side signal cards -->
                <div class="cc2-side-signals" id="cc2SideSignals">
                  ${[0,1,2,3].map(() => skelSignal()).join('')}
                </div>
              </div>
            </div>

            <!-- Right aside: AI rec + command -->
            <aside class="cc2-aside">
              <div class="cc2-ai-rec">
                <div class="cc2-ai-head">
                  <div>
                    <div class="cc2-section-label">AI RECOMMENDATION</div>
                    <div class="cc2-ai-title">מה הפעולה הבאה שהמערכת ממליצה לבצע</div>
                  </div>
                  <span class="cc2-live-dot cc2-ld-pulse"></span>
                </div>
                <div class="cc2-rec-box">
                  <div class="cc2-rec-lbl">המלצה מיידית</div>
                  <div class="cc2-rec-title" id="cc2RecTitle">מנתח...</div>
                  <p class="cc2-rec-text" id="cc2RecText">טוען נתונים...</p>
                </div>
                <div class="cc2-asst-stats" id="cc2AsstStats">
                  ${[['רמת ביטחון','—'],['חלון סיכון','—'],['פוטנציאל','—']].map(([k,v]) => `
                  <div class="cc2-asst-stat"><span>${k}</span><span class="cc2-asst-stat-val">${v}</span></div>`).join('')}
                </div>
              </div>

              <div class="cc2-command">
                <div class="cc2-section-label">COMMAND INPUT</div>
                <div class="cc2-cmd-title">תן הוראה טבעית למערכת</div>
                <div class="cc2-cmd-text">"נתח את ההזדמנויות הקרובות והצע מהלך שמגדיל את סיכויי הסגירה היום"</div>
                <div class="cc2-primary-acts">
                  <button class="cc2-btn cc2-btn-primary" onclick="App.switchTo('workspace')">
                    <span>הפעל ניתוח חכם</span><span class="cc2-btn-tag">AI</span>
                  </button>
                  <button class="cc2-btn cc2-btn-sec" onclick="App.switchTo('workspace')">
                    <span>פתח פעולות חמות</span><span class="cc2-btn-tag">Live</span>
                  </button>
                  <button class="cc2-btn cc2-btn-sec" onclick="App.switchTo('briefing')">
                    <span>הצג המלצות מיידיות</span><span class="cc2-btn-tag">Next</span>
                  </button>
                  <button class="cc2-btn cc2-btn-sec" onclick="App.switchTo('briefing')">
                    <span>הפעל קלט קולי</span><span>🎙</span>
                  </button>
                </div>
                <div class="cc2-chips">
                  ${chips.map(c => `<button class="cc2-chip-btn" onclick="App.switchTo('workspace')">${c}</button>`).join('')}
                </div>
              </div>
            </aside>
          </div>
        </section>

        <!-- Right column -->
        <section class="cc2-right">
          <div class="cc2-decisions">
            <div class="cc2-section-label">DECISION PRIORITIES</div>
            <div class="cc2-dec-cards" id="cc2DecCards">
              ${[0,1,2].map(() => skelCard()).join('')}
            </div>
          </div>

          <div class="cc2-risk-section">
            <div class="cc2-risk-head">
              <div>
                <div class="cc2-section-label">RISK &amp; OPPORTUNITY</div>
                <div class="cc2-risk-title">איפה קיים סיכון לאובדן עסקה</div>
              </div>
              <button class="cc2-btn cc2-btn-sm" onclick="App.switchTo('crm')">הצג מעקבים חמים</button>
            </div>
            <div class="cc2-queue" id="cc2Queue">
              ${[0,1,2].map(() => skelQueueItem()).join('')}
            </div>
          </div>
        </section>

      </main>
    </div>`;
  }

  // ── Init & data load ───────────────────────────────────────────────────
  async function init() { await load(); }

  async function load() {
    // ── Guard: never fire without a key (defense-in-depth) ────────────────
    if (!API.hasKey()) {
      console.warn('[Dashboard] load() aborted — no API key in sessionStorage');
      return;
    }
    // ── Single source of truth: /api/dashboard/summary (Batch 7) ──────────
    const res = await API.dashboardSummary();
    if (!res.success) {
      _setText('cc2FocusScore', 'ERR');
      _setText('cc2RecTitle', 'שגיאה בטעינת נתונים — נסה שוב');
      _setText('cc2RecText', res.error || 'לא ניתן לטעון את מרכז השליטה');
      return;
    }

    const snap  = res.data.revenue_snapshot    || {};
    const queue = res.data.today_queue         || [];   // top-7 priority leads
    const hot   = res.data.hot_leads           || [];   // status === 'חם'
    const stuck = res.data.stuck_deals         || [];   // no activity 5d
    const bott  = res.data.bottlenecks         || [];   // missing next_action
    const recs  = res.data.recommended_actions || [];   // AI rec list

    const pipeline = snap.pipeline    || 0;
    const weighted = snap.weighted    || 0;
    const topRec   = recs[0]          || {};
    const topStuck = stuck[0]         || null;

    // ── Top strip ──────────────────────────────────────────────────────────
    [
      'Online',
      ils(weighted),
      String(snap.active_deals || 0),
      String(snap.hot_leads_count || 0),
    ].forEach((v, i) => _setText(`cc2s${i}`, v));

    // ── Focus score: weighted / pipeline ratio ─────────────────────────────
    const focusPct = pipeline > 0
      ? Math.min(Math.round((weighted / pipeline) * 100), 99)
      : 1;
    _setText('cc2FocusScore', focusPct + '%');

    // ── Floating ring chips ────────────────────────────────────────────────
    _setText('cc2Pressure', String(bott.length));     // missing next_action = revenue pressure
    _setText('cc2Risk',     String(stuck.length));    // stuck deals = risk exposure
    _setText('cc2Next',     topRec.action ? topRec.action.slice(0, 8) : 'מעקב');

    // ── Side signal cards ──────────────────────────────────────────────────
    _html('cc2SideSignals', [
      { label: 'צינור עסקאות פעיל',  value: ils(pipeline),              sub: `${snap.active_deals||0} עסקאות פתוחות` },
      { label: 'לידים חמים',          value: String(snap.hot_leads_count||0), sub: `${hot.length} לידים בעדיפות גבוהה` },
      { label: 'עסקאות תקועות',       value: String(stuck.length),       sub: 'ללא פעילות 5 ימים' },
      { label: 'חסרה פעולה הבאה',     value: String(bott.length),        sub: 'לידים דורשים הגדרת מהלך' },
    ].map(s => `
    <div class="cc2-signal-card">
      <div class="cc2-sc-label">${s.label}</div>
      <div class="cc2-sc-val">${s.value}</div>
      <div class="cc2-sc-sub">${s.sub}</div>
    </div>`).join(''));

    // ── AI recommendation: recommended_actions[0] ──────────────────────────
    if (topRec.lead_name) {
      _setText('cc2RecTitle', `${topRec.action || 'פעל עכשיו'} — ${topRec.lead_name}`);
      _setText('cc2RecText',  topRec.reason || 'ליד בעדיפות גבוהה דורש טיפול מיידי.');
    } else {
      _setText('cc2RecTitle', 'הגדר עסקאות ופעולות לקבלת המלצות');
      _setText('cc2RecText',  'אין המלצות פעילות. הוסף פעולות הבאות ללידים להמשך.');
    }
    _html('cc2AsstStats', [
      ['ציון עדיפות',      topRec.score ? Math.round(topRec.score) + '/100' : '—'],
      ['עסקאות תקועות',    String(stuck.length)],
      ['פוטנציאל משוקלל',  ils(weighted)],
    ].map(([k, v]) => `
    <div class="cc2-asst-stat"><span>${k}</span><span class="cc2-asst-stat-val">${v}</span></div>`).join(''));

    // ── Decision priorities: today_queue / hot_leads / bottlenecks ─────────
    _html('cc2DecCards', [
      {
        title: 'פעולות היום לפי עדיפות',
        value: `${queue.length} לידים בתור`,
        note:  queue[0] ? `${queue[0].lead_name} — ציון ${Math.round(queue[0].score||0)}` : 'אין לידים פעילים',
      },
      {
        title: 'לידים חמים לפעולה מיידית',
        value: `${hot.length} לידים חמים`,
        note:  hot[0] ? `${hot[0].name} — ${ils(hot[0].potential_value||0)}` : 'אין לידים חמים',
      },
      {
        title: 'צווארי בקבוק לטיפול',
        value: `${bott.length} חסרי מהלך`,
        note:  bott[0] ? `${bott[0].name} — הגדר פעולה הבאה` : 'אין צווארי בקבוק',
      },
    ].map(c => `
    <div class="cc2-decision-card">
      <div class="cc2-dc-title">${c.title}</div>
      <div class="cc2-dc-val">${c.value}</div>
      <div class="cc2-dc-note">${c.note}</div>
    </div>`).join(''));

    // ── Risk queue: stuck_deals ────────────────────────────────────────────
    _html('cc2Queue', stuck.length
      ? stuck.slice(0, 3).map(d => `
      <div class="cc2-queue-item">
        <div class="cc2-qi-head">
          <span class="cc2-qi-name">${d.title || d.name || '—'}</span>
          <span class="cc2-qi-dot"></span>
        </div>
        <div class="cc2-deal-fields">
          <div class="cc2-deal-field"><div class="cc2-df-lbl">שלב</div><div class="cc2-df-val">${stageLabel(d.stage)}</div></div>
          <div class="cc2-deal-field"><div class="cc2-df-lbl">פוטנציאל</div><div class="cc2-df-val" dir="ltr">${ils(d.value_ils||0)}</div></div>
          <div class="cc2-deal-field"><div class="cc2-df-lbl">סיכון</div><div class="cc2-df-val" style="color:#f87171">גבוה</div></div>
        </div>
      </div>`).join('')
      : '<div style="text-align:center;color:rgba(255,255,255,.35);padding:24px 0;font-size:13px">אין עסקאות תקועות</div>');
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }
  function _html(id, html)   { const el = document.getElementById(id); if (el) el.innerHTML  = html; }

  return { render, init };
})();
