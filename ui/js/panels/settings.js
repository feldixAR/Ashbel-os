/**
 * settings.js — Settings and System Health Panel
 * Read-only display: DB status, API key, scheduler, env, version, commit hash.
 * Sources: GET /api/health, GET /api/version (optional), GET /api/status (optional).
 */
const SettingsPanel = (() => {

  function render() {
    return `
      <!-- Widget bar -->
      <div class="panel-widgets">
        <div class="pw-chip">
          <div class="pw-val" id="stwDB">—</div>
          <div class="pw-label">מסד נתונים</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val" id="stwAPI">—</div>
          <div class="pw-label">API Key</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val" id="stwEnv">—</div>
          <div class="pw-label">סביבה</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val" id="stwStatus">—</div>
          <div class="pw-label">סטטוס מערכת</div>
        </div>
      </div>

      <div class="section-head">
        <div>
          <div class="section-title">הגדרות ובריאות מערכת</div>
          <div class="section-sub">קריאה בלבד — ערכים נטענים מהשרת</div>
        </div>
        <button class="btn btn-ghost" onclick="SettingsPanel.reload()">↻ בדוק שוב</button>
      </div>

      <!-- Health grid -->
      <div class="health-grid" id="settingsHealthGrid">
        ${Array(6).fill(`
          <div class="health-card">
            <div class="skel" style="width:30px;height:30px;border-radius:6px;margin-bottom:8px"></div>
            <div class="skel skel-h12 skel-w60"></div>
            <div class="skel skel-h12 skel-w80" style="margin-top:4px"></div>
          </div>`).join('')}
      </div>

      <!-- Version info block -->
      <div class="cmd-box" id="settingsVersionBlock" style="display:none">
        <div class="cmd-label">פרטי גרסה ופריסה</div>
        <div id="settingsVersionContent"></div>
      </div>

      <!-- Business profile block -->
      <div class="cmd-box" style="margin-top:16px">
        <div class="cmd-label">פרופיל עסקי פעיל</div>
        <div id="settingsBizProfile">
          ${UI.loading('טוען פרופיל...')}
        </div>
      </div>

      <!-- Env variables guide -->
      <div class="cmd-box" style="margin-top:16px">
        <div class="cmd-label">משתני סביבה נדרשים</div>
        <div style="display:grid;gap:8px;margin-top:4px">
          ${[
            ['DATABASE_URL',      'חיבור PostgreSQL — מוגדר אוטומטית ע"י Railway'],
            ['OS_API_KEY',        'מפתח API לכל נתיבי ה-API'],
            ['SECRET_KEY',        'מפתח הצפנת session של Flask'],
            ['ANTHROPIC_API_KEY', 'מפתח Claude AI לניתוח ו-AI engines'],
            ['BUSINESS_ID',       'מזהה עסק פעיל — ברירת מחדל: ashbel'],
          ].map(([k, desc]) => `
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:6px 0;border-bottom:1px solid var(--border)">
              <code style="font-family:var(--mono);font-size:11px;color:var(--accent);flex-shrink:0">${k}</code>
              <span style="font-size:11px;color:var(--muted);text-align:left">${desc}</span>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  async function init() {
    await load();
  }

  async function load() {
    // ── Health check ──────────────────────────────────────────────────────
    const healthRes = await API.get('/health');
    const health    = healthRes.success ? (healthRes.data || {}) : {};
    const dbOk      = health.db === true;
    const sysOk     = health.status === 'ok';

    // ── Version / status (optional endpoints — may 404) ───────────────────
    const [versionRes, statusRes, bizRes] = await Promise.all([
      API.get('/version').catch(() => ({ success: false })),
      API.get('/status').catch(() => ({ success: false })),
      API.get('/businesses').catch(() => ({ success: false })),
    ]);

    const version  = versionRes.success  ? versionRes.data  : null;
    const status   = statusRes.success   ? statusRes.data   : null;
    const bizData  = bizRes.success      ? bizRes.data      : null;

    // ── Update widgets ────────────────────────────────────────────────────
    _setWidget('stwDB',     dbOk  ? 'Online' : 'Offline', dbOk  ? 'pv-green' : 'pv-red');
    _setWidget('stwAPI',    API.hasKey() ? 'מוגדר' : 'חסר', API.hasKey() ? 'pv-green' : 'pv-red');
    _setWidget('stwEnv',    version?.environment || status?.environment || 'railway', '');
    _setWidget('stwStatus', sysOk ? 'תקין' : 'שגיאה', sysOk ? 'pv-green' : 'pv-red');

    // ── Health grid ───────────────────────────────────────────────────────
    const gridItems = [
      {
        icon: dbOk ? '🗄️' : '🔴',
        label: 'מסד נתונים (PostgreSQL)',
        val: dbOk ? 'מחובר' : 'לא מחובר',
        cls: dbOk ? 'hv-ok' : 'hv-err',
      },
      {
        icon: '🔑',
        label: 'OS_API_KEY',
        val: API.hasKey() ? '••••••••' + (localStorage.getItem('ashbal_api_key') || '').slice(-4) : 'לא מוגדר',
        cls: API.hasKey() ? 'hv-ok' : 'hv-warn',
      },
      {
        icon: sysOk ? '✅' : '⚠️',
        label: 'סטטוס מערכת',
        val: health.status || 'לא ידוע',
        cls: sysOk ? 'hv-ok' : 'hv-err',
      },
      {
        icon: '🌐',
        label: 'סביבת הרצה',
        val: version?.environment || status?.environment || 'production',
        cls: '',
      },
      {
        icon: '📦',
        label: 'גרסת שרת',
        val: version?.version || status?.version || '—',
        cls: '',
      },
      {
        icon: '🔀',
        label: 'Commit Hash',
        val: (version?.commit || status?.commit || '—').slice(0, 10),
        cls: '',
      },
    ];

    document.getElementById('settingsHealthGrid').innerHTML = gridItems.map(item => `
      <div class="health-card">
        <div class="health-icon">${item.icon}</div>
        <div class="health-label">${item.label}</div>
        <div class="health-val ${item.cls}">${item.val}</div>
      </div>
    `).join('');

    // ── Version block ─────────────────────────────────────────────────────
    if (version || status) {
      const d = version || status;
      const content = [
        ['גרסה',      d.version      || '—'],
        ['Commit',    (d.commit      || '—').slice(0, 12)],
        ['סביבה',     d.environment  || '—'],
        ['שירות',     d.service_name || d.service || 'AshbelOS'],
        ['תאריך',     d.build_date   || d.deployed_at || '—'],
      ].map(([k, v]) => `
        <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--border)">
          <span style="font-size:11px;color:var(--muted)">${k}</span>
          <code style="font-family:var(--mono);font-size:11px;color:var(--text)">${v}</code>
        </div>
      `).join('');
      document.getElementById('settingsVersionContent').innerHTML = content;
      document.getElementById('settingsVersionBlock').style.display = '';
    }

    // ── Business profile ──────────────────────────────────────────────────
    if (bizData) {
      const active = bizData.active || 'ashbel';
      const biz    = (bizData.businesses || []).find(b => b.id === active) || { id: active, name: 'Ashbal Aluminum' };
      document.getElementById('settingsBizProfile').innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
          ${[
            ['מזהה', biz.id || '—'],
            ['שם',   biz.name || '—'],
            ['סקטור', biz.sector || 'aluminum'],
            ['מטבע',  biz.currency || 'ILS'],
          ].map(([k, v]) => `
            <div class="ap-row">
              <span class="ap-key">${k}</span>
              <span class="ap-val" style="font-family:var(--mono)">${v}</span>
            </div>
          `).join('')}
        </div>
      `;
    } else {
      document.getElementById('settingsBizProfile').innerHTML = `
        <div class="ap-row">
          <span class="ap-key">מזהה</span>
          <span class="ap-val" style="font-family:var(--mono)">ashbel</span>
        </div>
        <div class="ap-row">
          <span class="ap-key">שם</span>
          <span class="ap-val">אשבל אלומיניום</span>
        </div>
        <div class="ap-row">
          <span class="ap-key">סקטור</span>
          <span class="ap-val">aluminum</span>
        </div>
      `;
    }
  }

  function _setWidget(id, val, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = val;
    // Remove existing color classes then add new one
    el.classList.remove('pv-green', 'pv-amber', 'pv-red', 'pv-accent');
    if (cls) el.classList.add(cls);
  }

  return { render, init, reload: load };
})();
