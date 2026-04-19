/**
 * shell.js — AshbelOS Operating Console Shell
 * Manages: profile badge, command bar, today strip, tab routing, intel rail.
 */
const Shell = (() => {
  'use strict';

  let _tab     = 'leads';
  let _intelOpen = false;

  // ── Boot ──────────────────────────────────────────────────────────────────
  function init() {
    if (!API.hasKey()) {
      document.getElementById('apiModal').classList.remove('hidden');
      _setupApiModal();
      return;
    }
    _boot();
  }

  function _boot() {
    _loadProfile();
    _initCmdBar();
    _refreshTodayStrip();
    _loadIntelRail();
    switchTab('leads');
    setInterval(_refreshTodayStrip, 30_000);
    setInterval(_refreshBell, 30_000);
    if (typeof UploadModal !== 'undefined') UploadModal.init();
  }

  function _setupApiModal() {
    document.getElementById('apiKeySubmit').onclick = () => {
      const key      = document.getElementById('apiKeyInput').value.trim();
      const remember = document.getElementById('apiRemember').checked;
      if (!key) return;
      API.setKey(key, remember);
      document.getElementById('apiModal').classList.add('hidden');
      _boot();
    };
    document.getElementById('apiKeyInput').addEventListener('keydown', e => {
      if (e.key === 'Enter') document.getElementById('apiKeySubmit').click();
    });
    if (API.isRemembered()) document.getElementById('apiRemember').checked = true;
  }

  // ── Profile badge ─────────────────────────────────────────────────────────
  async function _loadProfile() {
    const el = document.getElementById('shProfileName');
    try {
      const res = await API.get('/businesses');
      if (res.success) {
        const active = res.data?.active || 'ashbel';
        const biz    = (res.data?.businesses || []).find(b => b.id === active);
        el.textContent = biz?.name || active;
      }
    } catch (_) {
      // Fallback: try to read from health or just show AshbelOS
      el.textContent = 'AshbelOS';
    }
  }

  // ── Command bar ───────────────────────────────────────────────────────────
  function _initCmdBar() {
    const input  = document.getElementById('shCmdInput');
    const btn    = document.getElementById('shCmdRun');
    const bell   = document.getElementById('shBell');
    if (!input) return;

    async function _run() {
      const cmd = input.value.trim();
      if (!cmd) return;
      btn.disabled    = true;
      btn.textContent = '⏳';
      _showCmdResult('loading', 'מעבד פקודה...');

      try {
        const res = await API.command(cmd);
        const d   = res.data || {};
        const msg = d.message || (res.success ? 'בוצע' : (res.error || 'שגיאה'));
        _showCmdResult(res.success ? 'ok' : 'err', msg);
        if (res.success) {
          input.value = '';
          // Refresh the current tab surface and today strip
          _refreshTodayStrip();
          if (typeof Console !== 'undefined') Console.reload(_tab);
        }
      } catch (e) {
        _showCmdResult('err', `שגיאה: ${e.message || e}`);
      } finally {
        btn.disabled    = false;
        btn.textContent = '↵';
      }
    }

    btn.addEventListener('click', _run);
    input.addEventListener('keydown', e => { if (e.key === 'Enter') _run(); });
    bell.addEventListener('click', () => switchTab('approvals'));
  }

  function _showCmdResult(type, msg) {
    const bar   = document.getElementById('cmdResultBar');
    const icon  = document.getElementById('cmdResultIcon');
    const text  = document.getElementById('cmdResultText');
    icon.textContent = type === 'loading' ? '⏳' : type === 'ok' ? '✅' : '❌';
    text.textContent = msg.slice(0, 180);
    bar.className    = `cmd-result-bar cmd-result-${type}`;
  }

  function closeCmdResult() {
    const bar = document.getElementById('cmdResultBar');
    if (bar) bar.className = 'cmd-result-bar hidden';
  }

  // ── Today strip ───────────────────────────────────────────────────────────
  async function _refreshTodayStrip() {
    if (!API.hasKey()) return;
    try {
      const [leadsRes, appRes, planRes] = await Promise.all([
        API.leads({ limit: 200 }),
        API.approvals(),
        API.dailyPlan().catch(() => ({ success: false })),
      ]);

      const leads      = leadsRes.success ? (leadsRes.data?.leads || []) : [];
      const approvals  = appRes.success   ? (appRes.data?.approvals || []).filter(a => a.status === 'pending') : [];
      const pipeline   = planRes.success  ? (planRes.data?.pipeline_value || 0) : 0;

      const newLeads     = leads.filter(l => l.status === 'new').length;
      const manualQueue  = leads.filter(l =>
        ['hot','contacted','new'].includes(l.status) &&
        (l.score || l.priority_score || 0) >= 40
      ).length;
      const followupDue = leads.filter(l =>
        l.status === 'contacted' || l.status === 'hot'
      ).length;

      _tsSet('tsNewLeadsVal',  newLeads  || '0');
      _tsSet('tsApprovalsVal', approvals.length || '0');
      _tsSet('tsManualVal',    manualQueue || '0');
      _tsSet('tsFollowupVal',  followupDue || '0');
      _tsSet('tsPipelineVal',  pipeline ? '₪' + Math.round(pipeline / 1000) + 'K' : '—');

      _refreshBell(approvals.length);
    } catch (_) {}
  }

  function _tsSet(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  async function _refreshBell(count) {
    if (count === undefined) {
      try {
        const res = await API.approvals();
        count = res.success ? (res.data?.approvals || []).filter(a => a.status === 'pending').length : 0;
      } catch (_) { count = 0; }
    }
    const badge = document.getElementById('shBellBadge');
    const bnBadge = document.getElementById('bnBadge');
    if (badge) {
      badge.textContent = count;
      badge.classList.toggle('hidden', count === 0);
    }
    if (bnBadge) {
      bnBadge.textContent = count;
      bnBadge.classList.toggle('hidden', count === 0);
    }
  }

  // ── Tab routing ───────────────────────────────────────────────────────────
  function switchTab(tabId) {
    _tab = tabId;
    // Update tab buttons
    document.querySelectorAll('.wt').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    // Update bottom nav
    document.querySelectorAll('.bn-item[data-tab]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    // Render work pane
    if (typeof Console !== 'undefined') {
      Console.render(tabId);
    }
  }

  function currentTab() { return _tab; }

  // ── Intel rail ────────────────────────────────────────────────────────────
  async function _loadIntelRail() {
    if (!API.hasKey()) return;
    await Promise.all([
      _loadIntelAgents(),
      _loadIntelLearning(),
      _loadIntelChannels(),
    ]);
  }

  async function _loadIntelAgents() {
    const elDesktop = document.getElementById('irAgents');
    const elMobile  = document.getElementById('isAgents');
    try {
      const res   = await API.tasks({ limit: 6 });
      const tasks = res.success ? (res.data?.tasks || []) : [];
      const html  = tasks.length
        ? tasks.slice(0, 5).map(t => `
          <div class="ir-item">
            <span class="ir-item-icon">${_taskIcon(t.status)}</span>
            <div class="ir-item-text">
              <div class="ir-item-title">${t.action || t.task_type || '—'}</div>
              <div class="ir-item-sub">${t.status || '—'}</div>
            </div>
          </div>`).join('')
        : '<div class="ir-empty">אין פעילות אחרונה</div>';
      if (elDesktop) elDesktop.innerHTML = html;
      if (elMobile)  elMobile.innerHTML  = html;
    } catch (_) {}
  }

  async function _loadIntelLearning() {
    const elDesktop = document.getElementById('irLearning');
    const elMobile  = document.getElementById('isLearning');
    try {
      const res  = await API.get('/learning/snapshot');
      const snap = res.snapshot || res.data?.snapshot || {};
      const rows = [];
      const ov   = snap.model_overrides || {};
      if (Object.keys(ov).length)
        rows.push(`<div class="ir-item"><span class="ir-item-icon">🔀</span><div class="ir-item-text"><div class="ir-item-title">מודל מותאם</div><div class="ir-item-sub">${Object.keys(ov).join(', ')}</div></div></div>`);
      const conv = snap.conversion?.hot;
      if (conv?.rate != null)
        rows.push(`<div class="ir-item"><span class="ir-item-icon">🔥</span><div class="ir-item-text"><div class="ir-item-title">המרה חמה</div><div class="ir-item-sub">${Math.round(conv.rate * 100)}% (${conv.total || 0})</div></div></div>`);
      const html = rows.length ? rows.join('') : '<div class="ir-empty">אין נתוני למידה עדיין</div>';
      if (elDesktop) elDesktop.innerHTML = html;
      if (elMobile)  elMobile.innerHTML  = html;
    } catch (_) {}
  }

  async function _loadIntelChannels() {
    const elDesktop = document.getElementById('irChannels');
    const elMobile  = document.getElementById('isChannels');
    try {
      const res      = await API.get('/channels/status');
      const channels = res.data?.channels || res.channels || [];
      const html = channels.slice(0, 5).map(ch => {
        const st = ch.status || 'unknown';
        const cls = st === 'active' ? 'ir-ch-active' : st === 'readiness' ? 'ir-ch-ready' : 'ir-ch-blocked';
        return `<div class="ir-item ir-channel">
          <span class="${cls} ir-ch-dot"></span>
          <div class="ir-item-text">
            <div class="ir-item-title">${ch.channel || '—'}</div>
            <div class="ir-item-sub">${st === 'active' ? 'פעיל' : st === 'readiness' ? 'מוכן ידני' : 'ממתין credentials'}</div>
          </div>
        </div>`;
      }).join('') || '<div class="ir-empty">—</div>';
      if (elDesktop) elDesktop.innerHTML = html;
      if (elMobile)  elMobile.innerHTML  = html;
    } catch (_) {}
  }

  function _taskIcon(status) {
    return { running:'⚙', completed:'✓', failed:'✗', created:'○' }[status] || '·';
  }

  // ── Mobile intel sheet ────────────────────────────────────────────────────
  function toggleIntelSheet() {
    _intelOpen = !_intelOpen;
    const sheet = document.getElementById('intelSheet');
    const btn   = document.getElementById('bnIntel');
    if (sheet) sheet.classList.toggle('hidden', !_intelOpen);
    if (btn)   btn.classList.toggle('active', _intelOpen);
    if (_intelOpen) _loadIntelRail();
  }

  function closeIntelSheet() {
    _intelOpen = false;
    document.getElementById('intelSheet')?.classList.add('hidden');
    document.getElementById('bnIntel')?.classList.remove('active');
  }

  return { init, switchTab, currentTab, closeCmdResult, toggleIntelSheet, closeIntelSheet };
})();

document.addEventListener('DOMContentLoaded', Shell.init);
