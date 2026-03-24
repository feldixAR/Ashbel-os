/**
 * app.js — application shell: init, navigation, badge refresh.
 */
const App = (() => {

  const PANELS = [
    { id: 'cmd',       label: 'פקודות',       icon: '⌨',  panel: () => CommandPanel   },
    { id: 'dashboard', label: 'בית',          icon: '🏠',  panel: () => DashboardPanel },
    { id: 'leads',     label: 'לידים',        icon: '👥',  panel: () => LeadsPanel     },
    { id: 'pipeline',  label: 'צנרת',         icon: '📤',  panel: () => PipelinePanel  },
    { id: 'goals',     label: 'יעדים',        icon: '🎯',  panel: () => GoalsPanel     },
    { id: 'tasks',     label: 'משימות',       icon: '📋',  panel: () => TasksPanel     },
    { id: 'revenue',   label: 'הכנסות',       icon: '💰',  panel: () => RevenuePanel   },
    { id: 'calendar',  label: 'יומן',         icon: '📅',  panel: () => CalendarPanel  },
    { id: 'agents',    label: 'סוכנים',       icon: '🤖',  panel: () => AgentsPanel    },
    { id: 'approvals', label: 'אישורים',      icon: '⏸',  panel: () => ApprovalsPanel },
    { id: 'reports',   label: 'דוחות',        icon: '📊',  panel: () => ReportsPanel   },
  ];

  let currentPanel = 'cmd';

  function init() {
    // Check API key
    if (!API.hasKey()) {
      document.getElementById('apiModal').classList.remove('hidden');
    }

    // Nav items
    const nav = document.getElementById('sideNav');
    PANELS.forEach(p => {
      const el = document.createElement('div');
      el.className = 'nav-item' + (p.id === currentPanel ? ' active' : '');
      el.id = 'nav-' + p.id;
      el.innerHTML = `<span class="nav-icon">${p.icon}</span>${p.label}`;
      el.onclick = () => switchTo(p.id);
      nav.appendChild(el);
    });

    // Render initial panel
    switchTo('cmd');

    // API key form
    document.getElementById('apiKeySubmit').onclick = () => {
      const key = document.getElementById('apiKeyInput').value.trim();
      if (!key) return;
      API.setKey(key);
      document.getElementById('apiModal').classList.add('hidden');
      refreshBadge();
    };

    // Bell → switch to approvals
    document.getElementById('bellBtn').onclick = () => switchTo('approvals');

    // Periodic badge refresh
    setInterval(refreshBadge, 30_000);
    refreshBadge();
  }

  function switchTo(id) {
    // Deactivate old
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(el => el.classList.remove('active'));
    document.getElementById('nav-' + id)?.classList.add('active');

    const panelEl = document.getElementById('panel-' + id);
    panelEl.classList.add('active');

    if (id !== currentPanel || !panelEl.dataset.rendered) {
      // Render fresh HTML
      const def = PANELS.find(p => p.id === id);
      if (def) {
        panelEl.innerHTML = def.panel().render();
        panelEl.dataset.rendered = '1';
        def.panel().init();
      }
    }
    currentPanel = id;
  }

  async function refreshBadge() {
    if (!API.hasKey()) return;
    const res    = await API.approvals();
    const count  = res.success ? (res.data.approvals || []).length : 0;
    const badge  = document.getElementById('bellBadge');
    const bellTx = document.getElementById('bellTxt');
    if (count > 0) {
      badge.textContent = count;
      badge.classList.remove('hidden');
      bellTx.textContent = `${count} אישורים`;
    } else {
      badge.classList.add('hidden');
      bellTx.textContent = 'אישורים';
    }
  }

  return { init, switchTo, refreshBadge };
})();

document.addEventListener('DOMContentLoaded', App.init);
