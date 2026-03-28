/**
 * app.js — AshbelOS application shell (Batch 11)
 * Grouped navigation, header KPI strip, panel routing, badge refresh.
 */
const App = (() => {

  // ── Navigation definition ────────────────────────────────────────────────
  const NAV = [
    // CRM
    { group: 'CRM REVENUE' },
    { id: 'dashboard',  label: 'מרכז פיקוד',      icon: '◈',  panel: () => DashboardPanel  },
    { id: 'workspace',  label: 'סביבת עבודה',      icon: '⬡',  panel: () => WorkspacePanel  },
    { id: 'crm',        label: 'עסקאות',           icon: '◇',  panel: () => CrmPanel        },
    { id: 'revenue',    label: 'תוכנית יומית',     icon: '▲',  panel: () => RevenuePanel    },
    { id: 'calendar',   label: 'יומן שבועי',       icon: '▦',  panel: () => CalendarPanel   },
    { id: 'briefing',   label: 'Briefing חי',      icon: '◉',  panel: () => BriefingPanel   },
    // Operations
    { group: 'OPERATIONS' },
    { id: 'cmd',        label: 'פקודות',           icon: '⌨',  panel: () => CommandPanel    },
    { id: 'leads',      label: 'לידים',            icon: '◎',  panel: () => LeadsPanel      },
    { id: 'pipeline',   label: 'צנרת Outreach',    icon: '◁',  panel: () => PipelinePanel   },
    { id: 'goals',      label: 'יעדים',            icon: '⊕',  panel: () => GoalsPanel      },
    { id: 'tasks',      label: 'משימות',           icon: '◫',  panel: () => TasksPanel      },
    // System
    { group: 'SYSTEM' },
    { id: 'agents',     label: 'סוכנים',           icon: '⊙',  panel: () => AgentsPanel     },
    { id: 'approvals',  label: 'אישורים',          icon: '⚑',  panel: () => ApprovalsPanel  },
    { id: 'reports',    label: 'דוחות',            icon: '▣',  panel: () => ReportsPanel    },
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

    // Render initial panel only when key is already present.
    // If key is missing, the modal is visible — do NOT init any panel yet
    // (prevents unauthenticated prefetch of /api/dashboard/summary and others).
    if (API.hasKey()) {
      switchTo('dashboard');
    }

    // API key form — init dashboard only AFTER key is stored
    document.getElementById('apiKeySubmit').onclick = () => {
      const key = document.getElementById('apiKeyInput').value.trim();
      if (!key) return;
      API.setKey(key);
      document.getElementById('apiModal').classList.add('hidden');
      switchTo('dashboard');   // first authenticated panel init
      refreshBadge();
      refreshHeaderKpis();
    };

    // Bell → approvals
    document.getElementById('bellBtn').onclick = () => switchTo('approvals');

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

  return { init, switchTo, rerender, refreshBadge };
})();

document.addEventListener('DOMContentLoaded', App.init);
