/**
 * settings.js — Settings and System Health Panel
 * Sources: GET /api/health, /api/version, /api/status, /api/admin/status, /api/admin/usage
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
          <div class="pw-val" id="stwUptime">—</div>
          <div class="pw-label">זמן פעילות</div>
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

      <!-- DB record counts -->
      <div class="cmd-box" id="settingsDbCounts" style="display:none;margin-top:16px">
        <div class="cmd-label">רשומות במסד הנתונים</div>
        <div id="settingsDbContent"></div>
      </div>

      <!-- Daily usage -->
      <div class="cmd-box" id="settingsUsageBlock" style="display:none;margin-top:16px">
        <div class="cmd-label">שימוש יומי — היום</div>
        <div id="settingsUsageContent"></div>
      </div>

      <!-- Version info block -->
      <div class="cmd-box" id="settingsVersionBlock" style="display:none;margin-top:16px">
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
    // ── All parallel ──────────────────────────────────────────────────────────
    const [healthRes, versionRes, statusRes, bizRes, adminStatRes, adminUsageRes] = await Promise.all([
      API.get('/health'),
      API.get('/version').catch(() => ({ success: false })),
      API.get('/status').catch(() => ({ success: false })),
      API.get('/businesses').catch(() => ({ success: false })),
      API.adminStatus().catch(() => ({ success: false })),
      API.adminUsage().catch(() => ({ success: false })),
    ]);

    const health = healthRes.success ? (healthRes.data || {}) : {};
    const dbOk   = health.db === true;
    const sysOk  = health.status === 'ok';
    const version = versionRes.success ? versionRes.data : null;
    const status  = statusRes.success  ? statusRes.data  : null;
    const bizData = bizRes.success     ? bizRes.data     : null;
    const adm     = adminStatRes.success ? adminStatRes.data : null;
    const usage   = adminUsageRes.success ? adminUsageRes.data : null;

    // ── Uptime ────────────────────────────────────────────────────────────────
    const uptimeSec = adm?.runtime?.uptime_seconds;
    const uptimeStr = uptimeSec != null ? _fmtUptime(uptimeSec) : '—';

    // ── Widgets ───────────────────────────────────────────────────────────────
    _setWidget('stwDB',     dbOk  ? 'Online' : 'Offline', dbOk  ? 'pv-green' : 'pv-red');
    _setWidget('stwAPI',    API.hasKey() ? 'מוגדר' : 'חסר', API.hasKey() ? 'pv-green' : 'pv-red');
    _setWidget('stwEnv',    version?.environment || status?.environment || 'railway', '');
    _setWidget('stwUptime', uptimeStr, '');

    // ── Health grid ───────────────────────────────────────────────────────────
    const gridItems = [
      { icon: dbOk ? '🗄️' : '🔴', label: 'מסד נתונים (PostgreSQL)', val: dbOk ? 'מחובר' : 'לא מחובר', cls: dbOk ? 'hv-ok' : 'hv-err' },
      { icon: '🔑', label: 'OS_API_KEY',   val: API.hasKey() ? '••••••••' + (localStorage.getItem('ashbal_api_key') || '').slice(-4) : 'לא מוגדר', cls: API.hasKey() ? 'hv-ok' : 'hv-warn' },
      { icon: sysOk ? '✅' : '⚠️', label: 'סטטוס מערכת', val: health.status || 'לא ידוע', cls: sysOk ? 'hv-ok' : 'hv-err' },
      { icon: '🌐', label: 'סביבת הרצה',  val: version?.environment || status?.environment || 'production', cls: '' },
      { icon: '📦', label: 'גרסת שרת',    val: version?.version     || status?.version     || '—', cls: '' },
      { icon: '🔀', label: 'Commit Hash',  val: (version?.commit     || status?.commit      || '—').slice(0, 10), cls: '' },
    ];
    document.getElementById('settingsHealthGrid').innerHTML = gridItems.map(item => `
      <div class="health-card">
        <div class="health-icon">${item.icon}</div>
        <div class="health-label">${item.label}</div>
        <div class="health-val ${item.cls}">${item.val}</div>
      </div>
    `).join('');

    // ── DB record counts (admin/status) ───────────────────────────────────────
    if (adm?.db) {
      const db = adm.db;
      document.getElementById('settingsDbContent').innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">
          ${[
            ['לידים — סה"כ',    db.leads_total,       ''],
            ['לידים — פעילים',  db.leads_active,      'pv-green'],
            ['עסקאות — סה"כ',   db.deals_total,       ''],
            ['עסקאות — פעילות', db.deals_active,      'pv-amber'],
            ['פניות יוצאות',    db.outreach_total,    ''],
            ['אישורים ממתינים', db.approvals_pending, db.approvals_pending > 0 ? 'pv-red' : 'pv-green'],
          ].map(([k, v, cls]) => `
            <div class="ap-row">
              <span class="ap-key">${k}</span>
              <span class="ap-val ${cls}" style="font-family:var(--mono)">${v ?? '—'}</span>
            </div>`).join('')}
        </div>
        <div style="font-size:9px;color:var(--muted);margin-top:8px;border-top:1px solid var(--border);padding-top:6px">
          זמן פעילות: ${uptimeStr} · ${adm.runtime?.timestamp_utc?.slice(0,19).replace('T',' ')} UTC
        </div>
      `;
      document.getElementById('settingsDbCounts').style.display = '';
    }

    // ── Daily usage ───────────────────────────────────────────────────────────
    if (usage) {
      const acts  = usage.activities  || {};
      const outr  = usage.outreach    || {};
      const actEntries  = Object.entries(acts);
      const outrEntries = Object.entries(outr);

      const section = (label, entries) => entries.length ? `
        <div style="margin-top:10px">
          <div style="font-size:10px;color:var(--muted);margin-bottom:6px">${label}</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            ${entries.map(([k,v]) => `
              <div style="background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:6px;padding:5px 10px;text-align:center">
                <div style="font-family:var(--mono);font-size:13px;font-weight:600;color:var(--accent)">${v}</div>
                <div style="font-size:9px;color:var(--muted)">${k}</div>
              </div>`).join('')}
          </div>
        </div>` : '';

      document.getElementById('settingsUsageContent').innerHTML = `
        <div style="font-size:11px;color:var(--muted)">${usage.date} · סה"כ פעולות: <strong style="color:var(--text)">${usage.total_actions || 0}</strong> · אישורים הוחלטו: <strong style="color:var(--text)">${usage.approvals_resolved || 0}</strong></div>
        ${section('פעילויות לפי סוג', actEntries)}
        ${section('פניות לפי ערוץ', outrEntries)}
        ${(!actEntries.length && !outrEntries.length) ? '<div style="font-size:11px;color:var(--muted);margin-top:8px">אין פעילות היום עדיין</div>' : ''}
      `;
      document.getElementById('settingsUsageBlock').style.display = '';
    }

    // ── Version block ─────────────────────────────────────────────────────────
    if (version || status) {
      const d = version || status;
      document.getElementById('settingsVersionContent').innerHTML = [
        ['גרסה',   d.version      || '—'],
        ['Commit', (d.commit      || '—').slice(0, 12)],
        ['סביבה',  d.environment  || '—'],
        ['שירות',  d.service_name || d.service || 'AshbelOS'],
        ['תאריך',  d.build_date   || d.deployed_at || '—'],
      ].map(([k, v]) => `
        <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--border)">
          <span style="font-size:11px;color:var(--muted)">${k}</span>
          <code style="font-family:var(--mono);font-size:11px;color:var(--text)">${v}</code>
        </div>
      `).join('');
      document.getElementById('settingsVersionBlock').style.display = '';
    }

    // ── Business profile ──────────────────────────────────────────────────────
    const bizFromAdmin = adm?.business;
    if (bizFromAdmin) {
      document.getElementById('settingsBizProfile').innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
          ${[
            ['מזהה',      bizFromAdmin.id       || '—'],
            ['שם',        bizFromAdmin.name      || '—'],
            ['סקטור',     bizFromAdmin.domain    || 'aluminum'],
            ['מטבע',      bizFromAdmin.currency  || 'ILS'],
            ['ערוץ ראשי', bizFromAdmin.primary_channel || '—'],
            ['עסקה ממוצעת', UI.ils(bizFromAdmin.avg_deal_size || 0)],
          ].map(([k, v]) => `
            <div class="ap-row">
              <span class="ap-key">${k}</span>
              <span class="ap-val" style="font-family:var(--mono)">${v}</span>
            </div>`).join('')}
        </div>
      `;
    } else if (bizData) {
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
            </div>`).join('')}
        </div>
      `;
    } else {
      document.getElementById('settingsBizProfile').innerHTML = `
        <div class="ap-row"><span class="ap-key">מזהה</span><span class="ap-val" style="font-family:var(--mono)">ashbel</span></div>
        <div class="ap-row"><span class="ap-key">שם</span><span class="ap-val">אשבל אלומיניום</span></div>
        <div class="ap-row"><span class="ap-key">סקטור</span><span class="ap-val">aluminum</span></div>
      `;
    }
  }

  function _fmtUptime(sec) {
    if (sec < 60)   return `${sec}ש`;
    if (sec < 3600) return `${Math.floor(sec/60)}ד`;
    if (sec < 86400)return `${Math.floor(sec/3600)}ש'`;
    return `${Math.floor(sec/86400)}י'`;
  }

  function _setWidget(id, val, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = val;
    el.classList.remove('pv-green', 'pv-amber', 'pv-red', 'pv-accent');
    if (cls) el.classList.add(cls);
  }

  return { render, init, reload: load };
})();
