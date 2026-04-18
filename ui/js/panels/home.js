/**
 * home.js — Daily Work Surface (AshbelOS Home)
 * Primary panel: Upload/Import, Smart Discovery, Urgent Actions,
 * Hot Leads, Pending Approvals, System Status.
 */
const HomePanel = (() => {

  const ils = n => UI.ils(n);

  // ── Render ────────────────────────────────────────────────────────────────
  function render() {
    const today = new Date().toLocaleDateString('he-IL', {weekday:'long',day:'numeric',month:'long'});
    return `
<div class="home-shell" dir="rtl">

  <div class="home-top-bar">
    <div class="home-date">${today}</div>
    <div class="home-status-strip">
      <span class="home-status-dot"></span>
      <span style="font-size:11px;color:var(--muted)">מערכת פעילה</span>
    </div>
  </div>

  <div class="home-primary-actions">
    <button class="home-action-btn home-upload-btn" onclick="UploadModal.open()">
      <span class="home-action-icon">📂</span>
      <div>
        <div class="home-action-title">יבוא לידים</div>
        <div class="home-action-sub">Excel, Word, CSV, PDF</div>
      </div>
    </button>
    <button class="home-action-btn home-discover-btn" onclick="HomePanel.openDiscover()">
      <span class="home-action-icon">🔍</span>
      <div>
        <div class="home-action-title">גלה לידים חכם</div>
        <div class="home-action-sub">סריקה + דירוג + המלצות</div>
      </div>
    </button>
  </div>

  <div class="home-grid">
    <div class="home-card">
      <div class="home-card-hd">
        <span class="home-card-icon">⚡</span>
        <span>פעולות דחופות</span>
        <span class="home-card-badge" id="homeUrgentCount">—</span>
      </div>
      <div id="homeUrgentList"><div class="home-loading">טוען...</div></div>
      <button class="home-card-more" onclick="App.switchTo('tasks')">הצג הכל →</button>
    </div>

    <div class="home-card">
      <div class="home-card-hd">
        <span class="home-card-icon">⚑</span>
        <span>ממתין לאישור</span>
        <span class="home-card-badge home-badge-red" id="homeAppCount">—</span>
      </div>
      <div id="homeAppList"><div class="home-loading">טוען...</div></div>
      <button class="home-card-more" onclick="App.switchTo('approvals')">הצג הכל →</button>
    </div>

    <div class="home-card">
      <div class="home-card-hd">
        <span class="home-card-icon">🔥</span>
        <span>לידים חמים</span>
        <span class="home-card-badge home-badge-green" id="homeHotCount">—</span>
      </div>
      <div id="homeHotList"><div class="home-loading">טוען...</div></div>
      <button class="home-card-more" onclick="App.switchTo('leads')">הצג הכל →</button>
    </div>

    <div class="home-card">
      <div class="home-card-hd">
        <span class="home-card-icon">◈</span>
        <span>מצב מערכת</span>
      </div>
      <div id="homeSysStatus"><div class="home-loading">טוען...</div></div>
      <button class="home-card-more" onclick="App.switchTo('dashboard')">מרכז שליטה →</button>
    </div>

    <div class="home-card">
      <div class="home-card-hd">
        <span class="home-card-icon">💰</span>
        <span>תור הכנסות היום</span>
        <span class="home-card-badge home-badge-green" id="homeQueueCount">—</span>
      </div>
      <div id="homeQueueList"><div class="home-loading">טוען...</div></div>
      <button class="home-card-more" onclick="App.switchTo('revenue')">תור מלא →</button>
    </div>

    <div class="home-card">
      <div class="home-card-hd">
        <span class="home-card-icon">🧠</span>
        <span>אותות למידה</span>
      </div>
      <div id="homeLearningSignals"><div class="home-loading">טוען...</div></div>
    </div>
  </div>

</div>

<!-- Discover overlay modal -->
<div class="home-disc-overlay hidden" id="homeDiscoverOverlay">
  <div class="home-disc-modal">
    <div class="home-disc-modal-hd">
      <span>גילוי לידים חכם</span>
      <button class="btn btn-ghost" style="font-size:12px" id="homeDiscCloseBtn">✕</button>
    </div>
    <div style="padding:16px">
      <div class="form-label" style="margin-bottom:6px">מטרה / סוג לקוח</div>
      <input class="form-input" id="homeDiscoverGoal"
             placeholder="לדוגמה: אדריכלים בתל אביב, קבלנים בחיפה..." />
      <button class="btn btn-primary" style="width:100%;margin-top:10px" id="homeDiscoverRun">הפעל גילוי →</button>
      <div id="homeDiscoverResult" style="margin-top:14px"></div>
    </div>
  </div>
</div>
    `;
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  async function init() {
    await Promise.all([
      _loadUrgent(),
      _loadApprovals(),
      _loadHotLeads(),
      _loadSysStatus(),
      _loadRevenueQueue(),
      _loadLearningSignals(),
    ]);

    document.getElementById('homeDiscoverRun')?.addEventListener('click', _runDiscover);
    document.getElementById('homeDiscoverGoal')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') _runDiscover();
    });
    document.getElementById('homeDiscCloseBtn')?.addEventListener('click', closeDiscover);
    document.getElementById('homeDiscoverOverlay')?.addEventListener('click', e => {
      if (e.target === document.getElementById('homeDiscoverOverlay')) closeDiscover();
    });
  }

  // ── Discover overlay ──────────────────────────────────────────────────────
  function openDiscover() {
    document.getElementById('homeDiscoverOverlay')?.classList.remove('hidden');
    document.getElementById('homeDiscoverGoal')?.focus();
  }

  function closeDiscover() {
    document.getElementById('homeDiscoverOverlay')?.classList.add('hidden');
    const r = document.getElementById('homeDiscoverResult');
    if (r) r.innerHTML = '';
    const btn = document.getElementById('homeDiscoverRun');
    if (btn) { btn.disabled = false; btn.textContent = 'הפעל גילוי →'; }
  }

  // ── Smart Discovery — real /api/lead_ops/discover ─────────────────────────
  async function _runDiscover() {
    const goal  = (document.getElementById('homeDiscoverGoal')?.value || '').trim();
    const btn   = document.getElementById('homeDiscoverRun');
    const resEl = document.getElementById('homeDiscoverResult');
    if (!goal) return;

    btn.disabled = true;
    btn.textContent = 'מגלה...';
    resEl.innerHTML = '<div class="home-loading" style="text-align:center;padding:16px 0">ממפה מקורות ולידים...</div>';

    try {
      const res = await API.post('/lead_ops/discover', { goal, signals: [] });

      if (!res.success) {
        resEl.innerHTML = `<div class="home-err-msg">שגיאה: ${res.error || res.message || 'נסה שוב'}</div>`;
        return;
      }

      const queue   = res.work_queue        || [];
      const plan    = res.discovery_plan    || {};
      const segs    = plan.segments         || [];
      const intents = plan.search_intents   || [];
      const comms   = plan.communities      || [];

      let html = '';

      if (queue.length > 0) {
        html += `<div class="home-disc-section-title">לידים שנמצאו (${queue.length})</div>`;
        html += queue.slice(0,5).map(item => `
          <div class="home-disc-item">
            <div>
              <div class="home-item-title">${item.lead_name || item.name || '—'}</div>
              <div class="home-item-sub">${item.next_action || 'בדוק ידנית'}</div>
            </div>
            <span class="score ${(item.score||0)>=70?'score-hot':(item.score||0)>=40?'score-warm':'score-cold'}"
                  style="font-size:10px">${Math.round(item.score||0)}</span>
          </div>`).join('');
        html += `<button class="btn btn-primary" style="width:100%;margin-top:10px"
          onclick="App.switchTo('leads');HomePanel.closeDiscover()">הצג לידים ב-CRM →</button>`;
        if (segs.length || intents.length) {
          html += '<div style="border-top:1px solid var(--border);margin:14px 0"></div>';
        }
      }

      if (segs.length) {
        html += `<div class="home-disc-section-title">קהלי יעד</div>
          <div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:12px">
            ${segs.map(s=>`<span class="insight-chip insight-good">${_segLabel(s)}</span>`).join('')}
          </div>`;
      }

      if (intents.length) {
        html += `<div class="home-disc-section-title">ביטויי חיפוש מומלצים</div>
          ${intents.slice(0,5).map(i=>`
            <div class="home-disc-intent">
              <span class="home-disc-src-icon">${_srcIcon(i.source_type)}</span>
              <span style="font-size:12px">${i.query}</span>
            </div>`).join('')}`;
      }

      if (comms.length) {
        html += `<div class="home-disc-section-title" style="margin-top:10px">קהילות לסרוק</div>
          ${comms.slice(0,4).map(c=>`
            <div class="home-disc-intent">
              <span class="home-disc-src-icon">${_srcIcon(c.source_type)}</span>
              <span style="font-size:12px">${c.name}</span>
            </div>`).join('')}`;
      }

      if (segs.length || intents.length || comms.length || queue.length === 0) {
        html += `<div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
          <button class="btn btn-primary" style="flex:1;min-width:120px"
            onclick="UploadModal.open();HomePanel.closeDiscover()">📂 יבא קובץ לידים</button>
          <button class="btn btn-secondary" style="flex:1;min-width:120px"
            onclick="App.switchTo('leads');HomePanel.closeDiscover()">רשימת לידים</button>
        </div>`;
      }

      if (!html) {
        html = '<div class="home-empty">לא נמצאו תוצאות לשאילתה זו</div>';
      }

      resEl.innerHTML = html;
    } catch(e) {
      resEl.innerHTML = `<div class="home-err-msg">שגיאה: ${e.message || e}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = 'הפעל גילוי →';
    }
  }

  function _segLabel(s) {
    const map = { architects:'אדריכלים', contractors:'קבלנים', interior_design:'מעצבי פנים',
                  developers:'יזמים', homeowners:'בעלי בתים', business:'עסקים' };
    return map[s] || s;
  }
  function _srcIcon(t) {
    const m = { linkedin:'💼', instagram:'📸', facebook_group:'👥', facebook:'👥',
                directory:'📋', google_maps:'📍', forum:'💬', blog:'📝',
                professional_blog:'📝', whatsapp_group:'📱', pinterest:'📌',
                yad2:'🏠', company_site:'🌐' };
    return m[t] || '🔎';
  }

  // ── Data loaders ──────────────────────────────────────────────────────────
  async function _loadUrgent() {
    const el = document.getElementById('homeUrgentList');
    const countEl = document.getElementById('homeUrgentCount');
    try {
      const res = await API.tasks({ status: 'created', limit: 5 });
      const tasks = res.success ? (res.data?.tasks || []) : [];
      countEl.textContent = tasks.length || '0';
      if (!tasks.length) { el.innerHTML = '<div class="home-empty">אין משימות פתוחות ✓</div>'; return; }
      el.innerHTML = tasks.slice(0,4).map(t => `
        <div class="home-item" onclick="App.switchTo('tasks')">
          <div class="home-item-title">${t.action || t.type || 'משימה'}</div>
          <div class="home-item-sub">עדיפות ${t.priority ?? '—'}</div>
          ${_pill(t.status)}
        </div>`).join('');
    } catch(e) { el.innerHTML = '<div class="home-empty">לא ניתן לטעון</div>'; }
  }

  async function _loadApprovals() {
    const el = document.getElementById('homeAppList');
    const countEl = document.getElementById('homeAppCount');
    try {
      const res = await API.approvals();
      const items = res.success ? (res.data?.approvals || []).filter(a => a.status === 'pending') : [];
      countEl.textContent = items.length || '0';
      if (!items.length) { el.innerHTML = '<div class="home-empty">אין אישורים ממתינים ✓</div>'; return; }
      el.innerHTML = items.slice(0,3).map(a => `
        <div class="home-item" onclick="App.switchTo('approvals')">
          <div class="home-item-title">${a.action || '—'}</div>
          <div class="home-item-sub">סיכון ${a.risk_level || '—'}</div>
          <span class="pill pill-amber" style="font-size:9px">ממתין</span>
        </div>`).join('');
    } catch(e) { el.innerHTML = '<div class="home-empty">לא ניתן לטעון</div>'; }
  }

  async function _loadHotLeads() {
    const el = document.getElementById('homeHotList');
    const countEl = document.getElementById('homeHotCount');
    try {
      const res = await API.leads({ limit: 20 });
      const all  = res.success ? (res.data?.leads || []) : [];
      const hot  = all.filter(l => (l.score || l.priority_score || 0) >= 60 || l.status === 'חם');
      hot.sort((a,b) => (b.score||b.priority_score||0) - (a.score||a.priority_score||0));
      countEl.textContent = hot.length || '0';
      if (!hot.length) { el.innerHTML = '<div class="home-empty">אין לידים חמים כרגע</div>'; return; }
      el.innerHTML = hot.slice(0,4).map(l => `
        <div class="home-item" onclick="App.switchTo('briefing')">
          <div class="home-item-title">${l.name || '—'}</div>
          <div class="home-item-sub">${l.city || ''} · ציון ${Math.round(l.score||l.priority_score||0)}</div>
          <span class="score ${(l.score||0)>=70?'score-hot':'score-warm'}" style="font-size:9px">${Math.round(l.score||0)}</span>
        </div>`).join('');
    } catch(e) { el.innerHTML = '<div class="home-empty">לא ניתן לטעון</div>'; }
  }

  async function _loadSysStatus() {
    const el = document.getElementById('homeSysStatus');
    try {
      const [planRes, healthRes] = await Promise.all([API.dailyPlan(), API.get('/health')]);
      const plan  = planRes.success  ? (planRes.data || {}) : {};
      const db_ok = (healthRes.data?.db || healthRes.data?.data?.db || false);
      el.innerHTML = `
        <div class="home-sys-row"><span>DB</span>
          <span class="${db_ok?'home-ok':'home-err'}">${db_ok?'✓ מחובר':'✗ ניתוק'}</span></div>
        <div class="home-sys-row"><span>Pipeline</span>
          <span class="home-val">${ils(plan.pipeline_value||0)}</span></div>
        <div class="home-sys-row"><span>עסקאות פעילות</span>
          <span class="home-val">${plan.total_deals||0}</span></div>
        <div class="home-sys-row"><span>לידים סה"כ</span>
          <span class="home-val">${plan.total_leads||0}</span></div>`;
    } catch(e) { el.innerHTML = '<div class="home-empty">לא ניתן לטעון מצב</div>'; }
  }

  async function _loadRevenueQueue() {
    const el      = document.getElementById('homeQueueList');
    const countEl = document.getElementById('homeQueueCount');
    try {
      const res   = await API.get('/daily_revenue_queue');
      const items = res.data?.queue || res.queue || [];
      countEl.textContent = items.length || '0';
      if (!items.length) {
        el.innerHTML = '<div class="home-empty">תור ריק — הוסף לידים להפעלה</div>';
        return;
      }
      el.innerHTML = items.slice(0, 3).map(it => `
        <div class="home-item" onclick="App.switchTo('leads')">
          <div class="home-item-title">${it.lead_name || it.name || '—'}</div>
          <div class="home-item-sub">${it.next_best_action || '—'}</div>
          <span class="score ${(it.priority_score||0)>=70?'score-hot':(it.priority_score||0)>=40?'score-warm':'score-cold'}"
                style="font-size:9px">${Math.round(it.priority_score||0)}</span>
        </div>`).join('');
    } catch(e) {
      el.innerHTML = '<div class="home-empty">לא ניתן לטעון</div>';
    }
  }

  async function _loadLearningSignals() {
    const el = document.getElementById('homeLearningSignals');
    try {
      const res  = await API.get('/learning/snapshot');
      const snap = res.snapshot || res.data?.snapshot || {};
      const overrides = snap.model_overrides || {};
      const sources   = snap.best_sources   || {};
      const conv      = snap.conversion     || {};

      let html = '';

      const ovKeys = Object.keys(overrides);
      if (ovKeys.length) {
        html += `<div class="home-sys-row"><span>🔀 מודל מותאם</span>
          <span class="home-val">${ovKeys.map(k => `${k}:${overrides[k]}`).join(', ')}</span></div>`;
      }
      const srcKeys = Object.keys(sources);
      if (srcKeys.length) {
        html += `<div class="home-sys-row"><span>📍 מקור מוביל</span>
          <span class="home-val">${Object.entries(sources).map(([k,v])=>`${k}→${v}`).slice(0,2).join(', ')}</span></div>`;
      }
      const hot = conv.hot;
      if (hot?.rate != null) {
        html += `<div class="home-sys-row"><span>🔥 המרה חמה</span>
          <span class="home-val">${Math.round((hot.rate||0)*100)}% (${hot.total||0} לידים)</span></div>`;
      }
      const agentSummary = snap.agent_summary || {};
      const agentList    = Object.entries(agentSummary);
      if (agentList.length) {
        const best = agentList.sort((a,b)=>(b[1].success_rate||0)-(a[1].success_rate||0))[0];
        html += `<div class="home-sys-row"><span>🤖 סוכן מוביל</span>
          <span class="home-val">${best[0]} (${Math.round((best[1].success_rate||0)*100)}%)</span></div>`;
      }
      if (!html) html = '<div class="home-empty">אין מספיק נתוני למידה עדיין</div>';
      el.innerHTML = html;
    } catch(e) {
      el.innerHTML = '<div class="home-empty">לא ניתן לטעון</div>';
    }
  }

  function _pill(status) {
    const map = { running:'pill-amber', completed:'pill-green', failed:'pill-red', created:'pill-steel' };
    const lbl = { running:'פועל', completed:'הושלם', failed:'נכשל', created:'ממתין' };
    return `<span class="pill ${map[status]||''}" style="font-size:9px">${lbl[status]||status||''}</span>`;
  }

  return { render, init, openDiscover, closeDiscover };
})();
