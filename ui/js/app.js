/**
 * app.js — AshbelOS application shell
 * Grouped navigation, header KPI strip, panel routing, badge refresh.
 */
const App = (() => {

  // ── Navigation definition ────────────────────────────────────────────────
  const NAV = [
    // CRM & Revenue
    { group: 'CRM & REVENUE' },
    { id: 'dashboard',      label: 'מרכז פיקוד',      icon: '◈',  panel: () => DashboardPanel      },
    { id: 'leads',          label: 'לידים',            icon: '◎',  panel: () => LeadsPanel          },
    { id: 'crm',            label: 'עסקאות',           icon: '◇',  panel: () => CrmPanel            },
    { id: 'clients',        label: 'לקוחות',           icon: '◉',  panel: () => ClientsPanel        },
    { id: 'revenue',        label: 'תוכנית יומית',     icon: '▲',  panel: () => RevenuePanel        },
    { id: 'calendar',       label: 'יומן שבועי',       icon: '▦',  panel: () => CalendarPanel       },
    { id: 'briefing',       label: 'Briefing חי',      icon: '⊛',  panel: () => BriefingPanel       },
    // Operations
    { group: 'OPERATIONS' },
    { id: 'tasks',          label: 'משימות',           icon: '◫',  panel: () => TasksPanel          },
    { id: 'communications', label: 'תקשורת',           icon: '◁',  panel: () => CommunicationsPanel },
    { id: 'approvals',      label: 'אישורים',          icon: '⚑',  panel: () => ApprovalsPanel      },
    { id: 'pipeline',       label: 'צנרת Outreach',    icon: '⊳',  panel: () => PipelinePanel       },
    // System
    { group: 'SYSTEM' },
    { id: 'agents',         label: 'סוכנים',           icon: '⊙',  panel: () => AgentsPanel         },
    { id: 'goals',          label: 'יעדים',            icon: '⊕',  panel: () => GoalsPanel          },
    { id: 'reports',        label: 'דוחות',            icon: '▣',  panel: () => ReportsPanel        },
    { id: 'settings',       label: 'הגדרות',           icon: '⚙',  panel: () => SettingsPanel       },
  ];

  const PANELS     = NAV.filter(p => p.id);
  let currentPanel = 'dashboard';

  // ── Init ─────────────────────────────────────────────────────────────────
  function init() {
    if (!API.hasKey()) {
      document.getElementById('apiModal').classList.remove('hidden');
    }

    // Build sidebar nav
    const nav = document.getElementById('sideNav');
    NAV.forEach(item => {
      if (item.group) {
        const g = document.createElement('div');
        g.className = 'nav-group';
        g.textContent = item.group;
        nav.appendChild(g);
        return;
      }
      const el = document.createElement('div');
      el.className = 'nav-item' + (item.id === currentPanel ? ' active' : '');
      el.id = 'nav-' + item.id;
      el.innerHTML = `<span class="nav-icon">${item.icon}</span>${item.label}`;
      el.onclick = () => switchTo(item.id);
      nav.appendChild(el);
    });

    // Render initial panel only when key is already present
    if (API.hasKey()) {
      switchTo('dashboard');
    }

    // Pre-check "remember" if key is already in localStorage
    if (API.isRemembered()) {
      document.getElementById('apiRemember').checked = true;
    }

    document.getElementById('apiKeySubmit').onclick = () => {
      const key      = document.getElementById('apiKeyInput').value.trim();
      const remember = document.getElementById('apiRemember').checked;
      if (!key) return;
      API.setKey(key, remember);
      document.getElementById('apiModal').classList.add('hidden');
      switchTo('dashboard');
      refreshBadge();
      refreshHeaderKpis();
      _loadProfileBadge();
    };

    // Bell → approvals
    document.getElementById('bellBtn').onclick = () => switchTo('approvals');

    // Load active business profile badge into sidebar footer
    if (API.hasKey()) _loadProfileBadge();

    // ── Mobile FAB ─────────────────────────────────────────────────────────
    _initFab();

    // Periodic refresh
    setInterval(refreshBadge, 30_000);
    setInterval(refreshHeaderKpis, 60_000);
    refreshBadge();
    if (API.hasKey()) refreshHeaderKpis();
  }

  // ── Panel switching ───────────────────────────────────────────────────────
  function switchTo(id) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(el => el.classList.remove('active'));
    document.getElementById('nav-' + id)?.classList.add('active');

    const panelEl = document.getElementById('panel-' + id);
    if (!panelEl) return;
    panelEl.classList.add('active');

    const def = PANELS.find(p => p.id === id);
    if (def && (id !== currentPanel || !panelEl.dataset.rendered)) {
      panelEl.innerHTML = def.panel().render();
      panelEl.dataset.rendered = '1';
      def.panel().init();
    }
    currentPanel = id;
  }

  // Force re-render (used after mutations)
  function rerender(id) {
    const panelEl = document.getElementById('panel-' + id);
    if (panelEl) panelEl.dataset.rendered = '';
    if (currentPanel === id) switchTo(id);
  }

  // ── Approvals badge ───────────────────────────────────────────────────────
  async function refreshBadge() {
    if (!API.hasKey()) return;
    const res   = await API.approvals();
    const count = res.success ? (res.data.approvals || []).length : 0;
    const badge = document.getElementById('bellBadge');
    const txt   = document.getElementById('bellTxt');
    if (count > 0) {
      badge.textContent = count;
      badge.classList.remove('hidden');
      txt.textContent = `${count} אישורים`;
    } else {
      badge.classList.add('hidden');
      txt.textContent = 'אישורים';
    }
  }

  // ── Header KPI strip ─────────────────────────────────────────────────────
  async function refreshHeaderKpis() {
    if (!API.hasKey()) return;
    const [planRes, dealsRes, leadsRes] = await Promise.all([
      API.dailyPlan(),
      API.deals(),
      API.leads({ limit: 100 }),
    ]);

    const pipeline = planRes.success  ? (planRes.data?.pipeline_value || 0) : 0;
    const deals    = dealsRes.success ? (dealsRes.data?.deals || []).filter(d=>!['won','lost'].includes(d.stage)).length : 0;
    const hot      = leadsRes.success ? (leadsRes.data?.leads || []).filter(l=>l.status==='חם').length : 0;

    document.getElementById('hkPipeline').textContent = '₪' + (pipeline||0).toLocaleString('he-IL');
    document.getElementById('hkDeals').textContent    = deals;
    document.getElementById('hkHot').textContent      = hot;
    document.getElementById('headerKpis').style.display = '';
  }

  // ── Business profile badge in sidebar footer ─────────────────────────────
  async function _loadProfileBadge() {
    try {
      const res = await API.get('/businesses');
      if (!res.success) return;
      const active = res.data?.active || 'ashbel';
      const biz    = (res.data?.businesses || []).find(b => b.id === active);
      const name   = biz?.name || active;
      let badge = document.getElementById('bizBadge');
      if (!badge) {
        badge = document.createElement('div');
        badge.id = 'bizBadge';
        badge.style.cssText = 'padding:10px 16px;font-size:10px;color:var(--muted);border-top:1px solid var(--border);margin-top:auto;font-family:var(--mono)';
        document.getElementById('sideNav').after(badge);
      }
      badge.textContent = `⬡ ${name}`;
    } catch (_) {}
  }

  // ── Mobile Floating Action Button ────────────────────────────────────────
  function _initFab() {
    const fab = document.createElement('div');
    fab.id = 'mobileFab';
    fab.innerHTML = `
      <button class="fab-main" id="fabMain" title="פעולות מהירות">＋</button>
      <div class="fab-sheet hidden" id="fabSheet">
        <button class="fab-action" onclick="App.switchTo('leads');document.getElementById('fabSheet').classList.add('hidden')">לידים חדשים</button>
        <button class="fab-action" onclick="App.switchTo('briefing');document.getElementById('fabSheet').classList.add('hidden')">Briefing חי</button>
        <button class="fab-action" onclick="App.switchTo('revenue');document.getElementById('fabSheet').classList.add('hidden')">תוכנית היום</button>
        <button class="fab-action" onclick="App.switchTo('calendar');document.getElementById('fabSheet').classList.add('hidden')">יומן</button>
      </div>`;
    document.body.appendChild(fab);

    document.getElementById('fabMain').addEventListener('click', () => {
      const sheet = document.getElementById('fabSheet');
      sheet.classList.toggle('hidden');
    });

    document.addEventListener('click', e => {
      if (!fab.contains(e.target)) {
        document.getElementById('fabSheet')?.classList.add('hidden');
      }
    });
  }

  return { init, switchTo, rerender, refreshBadge };
})();

document.addEventListener('DOMContentLoaded', App.init);
