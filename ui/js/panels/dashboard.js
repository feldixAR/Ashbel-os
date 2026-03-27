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
    const [planRes, dealsRes, leadsRes, approvalsRes] = await Promise.all([
      API.dailyPlan(300), API.deals(), API.leads({ limit: 60 }), API.approvals(),
    ]);

    const plan      = planRes.success      ? (planRes.data || {})                 : {};
    const deals     = dealsRes.success     ? (dealsRes.data?.deals || [])         : [];
    const leads     = leadsRes.success     ? (leadsRes.data?.leads || [])         : [];
    const approvals = approvalsRes.success ? (approvalsRes.data?.approvals || []) : [];

    const active   = deals.filter(d => !['won','lost'].includes(d.stage));
    const closing  = active.filter(d => ['negotiation','closing'].some(x => (d.stage||'').toLowerCase().includes(x)));
    const pipeline = plan.pipeline_value || active.reduce((s,d) => s+(d.value||d.value_ils||0), 0);
    const actions  = plan.priority_items || plan.priorities || [];
    const hotCount = leads.filter(l => l.status === 'חם').length;

    // Top strip
    const stripVals = ['Online', 'High', String(active.length), String(actions.length)];
    stripVals.forEach((v, i) => { const el = document.getElementById(`cc2s${i}`); if (el) el.textContent = v; });

    // Focus score
    const focusPct = Math.min(Math.round((pipeline / 200_000) * 100), 99) || 1;
    const fEl = document.getElementById('cc2FocusScore');
    if (fEl) fEl.textContent = focusPct + '%';

    // Floating ring chips
    const pressureScore = Math.min(Math.round((closing.length / Math.max(active.length, 1)) * 100), 99);
    const riskCount     = active.filter(d => {
      const s = (d.stage||'').toLowerCase();
      return ['negotiation','closing'].some(x => s.includes(x));
    }).length;
    const topClosing = [...closing].sort((a,b) => (b.value||b.value_ils||0)-(a.value||a.value_ils||0))[0];
    _setText('cc2Pressure', pressureScore);
    _setText('cc2Risk',     riskCount);
    _setText('cc2Next',     topClosing ? 'שיחת סגירה' : 'מעקב');

    // Side signals
    const nearClose = active.filter(d => ['negotiation','proposal'].some(x => (d.stage||'').toLowerCase().includes(x)));
    const nearVal   = nearClose.reduce((s,d) => s+(d.value||d.value_ils||0), 0);
    const urgency   = approvals.length > 2 ? 'גבוהה' : approvals.length > 0 ? 'בינונית' : 'נמוכה';
    const topAction = actions[0]?.title || (topClosing ? 'סגירה' : 'מעקב');
    _html('cc2SideSignals', [
      { label: 'פוטנציאל מימוש קרוב', value: ils(nearVal),  sub: `${nearClose.length} הזדמנויות פעילות` },
      { label: 'רמת דחיפות ניהולית', value: urgency,       sub: `${approvals.length} החלטות מחכות להכרעה` },
      { label: 'חשיפת סיכון',         value: String(riskCount), sub: 'עסקאות דורשות התערבות' },
      { label: 'הפעולה המומלצת כעת',  value: topAction.slice(0,12), sub: 'פעל היום לסגירה' },
    ].map(s => `
    <div class="cc2-signal-card">
      <div class="cc2-sc-label">${s.label}</div>
      <div class="cc2-sc-val">${s.value}</div>
      <div class="cc2-sc-sub">${s.sub}</div>
    </div>`).join(''));

    // AI recommendation
    if (topClosing) {
      const name = topClosing.title || topClosing.name || 'עסקה מובילה';
      _setText('cc2RecTitle', `לסגור היום את ${name} לפני ירידת מומנטום`);
      _setText('cc2RecText', 'הלקוח חם, ההצעה פתוחה וחלון ההחלטה מצטמצם. מומלץ לבצע שיחת הנהלה ולהפעיל מהלך סגירה מונחה.');
    } else {
      _setText('cc2RecTitle', 'הגדר עסקאות פעילות לקבלת המלצות מדויקות');
      _setText('cc2RecText',  'אין עסקאות בשלב סגירה כרגע. הוסף עסקאות לקבלת ניתוח AI מותאם.');
    }
    _html('cc2AsstStats', [
      ['רמת ביטחון', focusPct + '%'],
      ['חלון סיכון',  '6 שעות'],
      ['פוטנציאל',    topClosing ? ils(topClosing.value||topClosing.value_ils||0) : '—'],
    ].map(([k,v]) => `
    <div class="cc2-asst-stat"><span>${k}</span><span class="cc2-asst-stat-val">${v}</span></div>`).join(''));

    // Decision priorities
    const won = deals.filter(d => d.stage === 'won');
    _html('cc2DecCards', [
      { title: 'מה צפוי לייצר הכנסה עכשיו', value: `${closing.length} עסקאות קרובות`,        note: `${Math.min(closing.length,2)} מהן עם הסתברות גבוהה` },
      { title: 'איפה נדרשת הכרעה שלך',       value: `${approvals.length||Math.min(active.length,2)} החלטות`, note: approvals.length ? 'אחת מהן קריטית לשעתיים הקרובות' : 'בדוק עסקאות פתוחות' },
      { title: 'מה המערכת קידמה עבורך',       value: `${actions.length} פעולות`,              note: 'פולואפים, תזכורות והנעה אוטומטית' },
    ].map(c => `
    <div class="cc2-decision-card">
      <div class="cc2-dc-title">${c.title}</div>
      <div class="cc2-dc-val">${c.value}</div>
      <div class="cc2-dc-note">${c.note}</div>
    </div>`).join(''));

    // Risk queue
    const queue = [...active].sort((a,b) => (b.value||b.value_ils||0)-(a.value||a.value_ils||0)).slice(0,3);
    _html('cc2Queue', queue.length
      ? queue.map(d => `
      <div class="cc2-queue-item">
        <div class="cc2-qi-head">
          <span class="cc2-qi-name">${d.title||d.name||'—'}</span>
          <span class="cc2-qi-dot"></span>
        </div>
        <div class="cc2-deal-fields">
          <div class="cc2-deal-field"><div class="cc2-df-lbl">שלב</div><div class="cc2-df-val">${stageLabel(d.stage)}</div></div>
          <div class="cc2-deal-field"><div class="cc2-df-lbl">פוטנציאל</div><div class="cc2-df-val" dir="ltr">${ils(d.value||d.value_ils||0)}</div></div>
          <div class="cc2-deal-field"><div class="cc2-df-lbl">סיכון</div><div class="cc2-df-val">${riskLabel(d)}</div></div>
        </div>
      </div>`).join('')
      : '<div style="text-align:center;color:rgba(255,255,255,.35);padding:24px 0;font-size:13px">אין עסקאות פעילות</div>');
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }
  function _html(id, html)   { const el = document.getElementById(id); if (el) el.innerHTML  = html; }

  return { render, init };
})();
