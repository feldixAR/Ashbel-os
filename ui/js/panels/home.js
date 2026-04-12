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

  <!-- Date + system status bar -->
  <div class="home-top-bar">
    <div class="home-date">${today}</div>
    <div class="home-status-strip" id="homeStatus">
      <span class="home-status-dot"></span>
      <span style="font-size:11px;color:var(--muted)">מערכת פעילה</span>
    </div>
  </div>

  <!-- Primary action buttons -->
  <div class="home-primary-actions">
    <button class="home-action-btn home-upload-btn" id="homeUploadBtn" onclick="UploadModal.open()">
      <span class="home-action-icon">📂</span>
      <div>
        <div class="home-action-title">העלה קובץ / יבוא לידים</div>
        <div class="home-action-sub">Excel, Word, CSV, PDF</div>
      </div>
    </button>
    <button class="home-action-btn home-discover-btn" id="homeDiscoverBtn" onclick="HomePanel.openDiscover()">
      <span class="home-action-icon">🔍</span>
      <div>
        <div class="home-action-title">גלה לידים חכם</div>
        <div class="home-action-sub">סריקה פעילה + דירוג + המלצות</div>
      </div>
    </button>
  </div>

  <!-- Discover modal (inline) -->
  <div class="home-discover-modal hidden" id="homeDiscoverModal">
    <div class="home-discover-inner">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <div style="font-size:14px;font-weight:700">גילוי לידים חכם</div>
        <button class="btn btn-ghost" style="font-size:12px" onclick="document.getElementById('homeDiscoverModal').classList.add('hidden')">✕</button>
      </div>
      <div style="margin-bottom:10px">
        <div class="form-label">מטרה / סוג לקוח</div>
        <input class="form-input" id="homeDiscoverGoal" placeholder="לדוגמה: אדריכלים בתל אביב, קבלנים בחיפה..." />
      </div>
      <button class="btn btn-primary" style="width:100%" id="homeDiscoverRun">הפעל גילוי →</button>
      <div id="homeDiscoverResult" style="margin-top:12px"></div>
    </div>
  </div>

  <!-- Main grid: 2 columns -->
  <div class="home-grid">

    <!-- Urgent Next Actions -->
    <div class="home-card">
      <div class="home-card-hd">
        <span class="home-card-icon">⚡</span>
        <span>פעולות דחופות</span>
        <span class="home-card-badge" id="homeUrgentCount">—</span>
      </div>
      <div id="homeUrgentList"><div class="home-loading">טוען...</div></div>
    </div>

    <!-- Pending Approvals -->
    <div class="home-card">
      <div class="home-card-hd">
        <span class="home-card-icon">⚑</span>
        <span>ממתין לאישור</span>
        <span class="home-card-badge home-badge-red" id="homeAppCount">—</span>
      </div>
      <div id="homeAppList"><div class="home-loading">טוען...</div></div>
      <button class="home-card-more" onclick="App.switchTo('approvals')">הצג הכל →</button>
    </div>

    <!-- Hot Leads -->
    <div class="home-card">
      <div class="home-card-hd">
        <span class="home-card-icon">🔥</span>
        <span>לידים חמים</span>
        <span class="home-card-badge home-badge-green" id="homeHotCount">—</span>
      </div>
      <div id="homeHotList"><div class="home-loading">טוען...</div></div>
      <button class="home-card-more" onclick="App.switchTo('leads')">הצג הכל →</button>
    </div>

    <!-- System status / today summary -->
    <div class="home-card">
      <div class="home-card-hd">
        <span class="home-card-icon">◈</span>
        <span>מצב מערכת</span>
      </div>
      <div id="homeSysStatus"><div class="home-loading">טוען...</div></div>
      <button class="home-card-more" onclick="App.switchTo('dashboard')">מרכז שליטה מלא →</button>
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
    ]);

    document.getElementById('homeDiscoverRun')?.addEventListener('click', _runDiscover);
  }

  // ── Urgent next actions ───────────────────────────────────────────────────
  async function _loadUrgent() {
    const el = document.getElementById('homeUrgentList');
    const countEl = document.getElementById('homeUrgentCount');
    try {
      const res = await API.tasks({ status: 'created', limit: 5 });
      const tasks = res.success ? (res.data?.tasks || []) : [];
      const overdue = tasks.filter(t => t.priority <= 2 || t.status === 'running');
      countEl.textContent = overdue.length || tasks.length;
      if (!tasks.length) {
        el.innerHTML = '<div class="home-empty">אין פעולות ממתינות ✓</div>';
        return;
      }
      el.innerHTML = tasks.slice(0,4).map(t => `
        <div class="home-item" onclick="App.switchTo('tasks')">
          <div class="home-item-title">${t.action || t.type || 'משימה'}</div>
          <div class="home-item-sub">${t.status || ''} · עדיפות ${t.priority ?? '—'}</div>
          ${_statusPill(t.status)}
        </div>`).join('');
    } catch(e) {
      el.innerHTML = '<div class="home-empty">לא ניתן לטעון</div>';
    }
  }

  // ── Pending approvals ─────────────────────────────────────────────────────
  async function _loadApprovals() {
    const el = document.getElementById('homeAppList');
    const countEl = document.getElementById('homeAppCount');
    try {
      const res = await API.approvals();
      const items = res.success ? (res.data?.approvals || []).filter(a => a.status === 'pending') : [];
      countEl.textContent = items.length;
      if (!items.length) {
        el.innerHTML = '<div class="home-empty">אין אישורים ממתינים ✓</div>';
        return;
      }
      el.innerHTML = items.slice(0,3).map(a => `
        <div class="home-item" onclick="App.switchTo('approvals')">
          <div class="home-item-title">${a.action || '—'}</div>
          <div class="home-item-sub">סיכון ${a.risk_level || '—'} · ${(a.created_at || '').slice(0,10)}</div>
          <span class="pill pill-amber" style="font-size:9px">ממתין</span>
        </div>`).join('');
    } catch(e) {
      el.innerHTML = '<div class="home-empty">לא ניתן לטעון</div>';
    }
  }

  // ── Hot leads ─────────────────────────────────────────────────────────────
  async function _loadHotLeads() {
    const el = document.getElementById('homeHotList');
    const countEl = document.getElementById('homeHotCount');
    try {
      const res = await API.leads({ limit: 20 });
      const all  = res.success ? (res.data?.leads || []) : [];
      const hot  = all.filter(l => (l.score || l.priority_score || 0) >= 60 || l.status === 'חם');
      hot.sort((a,b) => (b.score||b.priority_score||0) - (a.score||a.priority_score||0));
      countEl.textContent = hot.length;
      if (!hot.length) {
        el.innerHTML = '<div class="home-empty">אין לידים חמים כרגע</div>';
        return;
      }
      el.innerHTML = hot.slice(0,4).map(l => `
        <div class="home-item" onclick="App.switchTo('briefing')">
          <div class="home-item-title">${l.name || '—'}</div>
          <div class="home-item-sub">${l.city || ''} · ציון ${Math.round(l.score||l.priority_score||0)}</div>
          <span class="score ${(l.score||0)>=70?'score-hot':'score-warm'}" style="font-size:9px">${Math.round(l.score||0)}</span>
        </div>`).join('');
    } catch(e) {
      el.innerHTML = '<div class="home-empty">לא ניתן לטעון</div>';
    }
  }

  // ── System status ─────────────────────────────────────────────────────────
  async function _loadSysStatus() {
    const el = document.getElementById('homeSysStatus');
    try {
      const [planRes, healthRes] = await Promise.all([
        API.dailyPlan(),
        API.get('/health'),
      ]);
      const plan  = planRes.success  ? (planRes.data || {}) : {};
      const db_ok = (healthRes.data?.db || healthRes.data?.data?.db || false);
      el.innerHTML = `
        <div class="home-sys-row">
          <span>DB</span>
          <span class="${db_ok ? 'home-ok' : 'home-err'}">${db_ok ? '✓ מחובר' : '✗ ניתוק'}</span>
        </div>
        <div class="home-sys-row">
          <span>Pipeline</span>
          <span class="home-val">${ils(plan.pipeline_value||0)}</span>
        </div>
        <div class="home-sys-row">
          <span>עסקאות פעילות</span>
          <span class="home-val">${plan.total_deals||0}</span>
        </div>
        <div class="home-sys-row">
          <span>לידים סה"כ</span>
          <span class="home-val">${plan.total_leads||0}</span>
        </div>`;
    } catch(e) {
      el.innerHTML = '<div class="home-empty">לא ניתן לטעון מצב</div>';
    }
  }

  // ── Smart discovery ───────────────────────────────────────────────────────
  function openDiscover() {
    document.getElementById('homeDiscoverModal').classList.remove('hidden');
    document.getElementById('homeDiscoverGoal').focus();
  }

  async function _runDiscover() {
    const goal = (document.getElementById('homeDiscoverGoal').value || '').trim();
    const btn  = document.getElementById('homeDiscoverRun');
    const resEl = document.getElementById('homeDiscoverResult');
    if (!goal) return;
    btn.disabled = true;
    btn.textContent = 'מגלה...';
    resEl.innerHTML = '<div class="home-loading">סורק מקורות...</div>';

    try {
      const res = await API.post('/command', {
        command: `גלה לידים: ${goal}`,
        params: { goal, signals: [] },
      });
      const data = res.success ? (res.data?.output || res.data || {}) : {};
      const queue = data.work_queue || [];
      const plan  = data.discovery_plan || {};

      if (!res.success) {
        resEl.innerHTML = `<div class="home-err-msg">${res.data?.message || 'שגיאה'}</div>`;
        return;
      }

      // Show discovery results
      resEl.innerHTML = `
        <div class="home-disc-summary">
          <span class="home-disc-count">${queue.length}</span> לידים נמצאו
          <span style="font-size:11px;color:var(--muted);margin-right:8px">·
            ${plan.suggested_sources?.length || 0} מקורות הומלצו</span>
        </div>
        ${queue.slice(0,5).map(item => `
          <div class="home-disc-item">
            <div class="home-item-title">${item.lead_name||item.name||'—'}</div>
            <div class="home-item-sub">${item.next_action||'בדוק ידנית'}</div>
            <span class="score ${(item.score||0)>=70?'score-hot':'score-warm'}">${Math.round(item.score||0)}</span>
          </div>`).join('')}
        ${queue.length > 0 ? `<button class="btn btn-primary" style="width:100%;margin-top:8px" onclick="App.switchTo('leads');document.getElementById('homeDiscoverModal').classList.add('hidden')">הצג לידים →</button>` : ''}
      `;
    } catch(e) {
      resEl.innerHTML = `<div class="home-err-msg">שגיאה: ${e.message || e}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = 'הפעל גילוי →';
    }
  }

  function _statusPill(status) {
    const map = { running: 'pill-amber', completed: 'pill-green', failed: 'pill-red', created: 'pill-steel' };
    const lbl = { running: 'פועל', completed: 'הושלם', failed: 'נכשל', created: 'ממתין' };
    return `<span class="pill ${map[status]||''}" style="font-size:9px">${lbl[status]||status||''}</span>`;
  }

  return { render, init, openDiscover };
})();
