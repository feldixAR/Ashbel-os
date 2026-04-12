/**
 * clients.js — Clients and Accounts Panel
 * Sources won leads from GET /api/leads?status=סגור_זכה
 * Shows client card grid with last interaction and open deal count.
 */
const ClientsPanel = (() => {

  const ils     = n => UI.ils(n);
  const relTime = s => UI.relTime(s);
  function initials(name) {
    return (name || '?').trim().split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
  }

  function render() {
    return `
      <!-- Widget bar -->
      <div class="panel-widgets">
        <div class="pw-chip">
          <div class="pw-val pv-green" id="clwTotal">—</div>
          <div class="pw-label">לקוחות פעילים</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-amber" id="clwPipeline">—</div>
          <div class="pw-label">Pipeline ללקוחות</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-accent" id="clwDeals">—</div>
          <div class="pw-label">עסקאות פתוחות</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val" id="clwRecent">—</div>
          <div class="pw-label">קשר אחרון (ימים)</div>
        </div>
      </div>

      <div id="clInsight" style="margin-bottom:12px"></div>
      <div id="clNextAction" style="margin-bottom:16px"></div>

      <div class="section-head">
        <div>
          <div class="section-title">לקוחות וחשבונות</div>
          <div class="section-sub" id="clientCount">טוען...</div>
        </div>
        <input class="cmd-input" id="clientSearch" placeholder="חיפוש לקוח..."
               style="width:200px;font-size:12px;padding:7px 10px" />
      </div>

      <div class="clients-grid" id="clientsGrid">
        ${Array(6).fill(`
          <div class="client-card">
            <div class="skel" style="width:40px;height:40px;border-radius:50%;margin-bottom:10px"></div>
            <div class="skel skel-h12 skel-w80"></div>
            <div class="skel skel-h12 skel-w60"></div>
          </div>`).join('')}
      </div>
    `;
  }

  let _clients = [];

  async function init() {
    _clients = [];
    await load();
    document.getElementById('clientSearch')?.addEventListener('input', renderGrid);
  }

  async function load() {
    // Fetch won leads
    const leadsRes = await API.leads({ limit: 300 });
    if (!leadsRes.success) {
      document.getElementById('clientsGrid').innerHTML = UI.error('שגיאה בטעינת לקוחות');
      return;
    }

    const allLeads = leadsRes.data?.leads || [];
    const wonLeads = allLeads.filter(l => l.status === 'סגור_זכה');
    document.getElementById('clientCount').textContent = `${wonLeads.length} לקוחות`;

    // Fetch deals for pipeline calculation
    const dealsRes = await API.deals();
    const allDeals = dealsRes.success ? (dealsRes.data?.deals || []) : [];

    // Build enriched client list
    _clients = wonLeads.map(lead => {
      const openDeals = allDeals.filter(d => d.lead_id === lead.id && !['won','lost'].includes(d.stage));
      const wonDeals  = allDeals.filter(d => d.lead_id === lead.id && d.stage === 'won');
      const pipeVal   = openDeals.reduce((s, d) => s + (d.value_ils || 0), 0);
      const wonValue  = wonDeals.reduce((s, d) => s + (d.value_ils || 0), 0);
      return { ...lead, openDeals, pipeVal, wonValue };
    });

    // Compute widgets
    const totalPipe  = _clients.reduce((s, c) => s + c.pipeVal, 0);
    const totalDeals = _clients.reduce((s, c) => s + c.openDeals.length, 0);

    // Most recent interaction in days
    const recDates = _clients
      .map(c => c.last_activity_at || c.updated_at)
      .filter(Boolean)
      .map(d => Math.floor((Date.now() - new Date(d)) / 86400000));
    const minDays = recDates.length ? Math.min(...recDates) : 0;

    _setText('clwTotal',    _clients.length);
    _setText('clwPipeline', ils(totalPipe));
    _setText('clwDeals',    totalDeals);
    _setText('clwRecent',   minDays);

    // Insight strip
    const dormant  = _clients.filter(c => {
      const d = c.last_activity_at || c.updated_at;
      return d && Math.floor((Date.now() - new Date(d)) / 86400000) > 30;
    });
    const noDeals  = _clients.filter(c => c.openDeals.length === 0);
    const iChips   = [];
    if (dormant.length)  iChips.push({ icon: '⏰', text: `${dormant.length} לקוחות ללא קשר מעל 30 יום`, cls: 'insight-warn' });
    if (noDeals.length)  iChips.push({ icon: '○',  text: `${noDeals.length} לקוחות ללא עסקאות פתוחות`, cls: 'insight-warn' });
    if (!iChips.length)  iChips.push({ icon: '✓',  text: 'כל הלקוחות מטופלים', cls: 'insight-good' });
    const iEl = document.getElementById('clInsight');
    if (iEl) iEl.innerHTML = UI.insightStrip(iChips);

    // Next-action: dormant client with highest pipeline
    const nextClient = (dormant.length ? dormant : _clients)
      .sort((a, b) => b.pipeVal - a.pipeVal)[0];
    const naEl = document.getElementById('clNextAction');
    if (naEl && nextClient) {
      const daysSince = nextClient.last_activity_at
        ? Math.floor((Date.now() - new Date(nextClient.last_activity_at)) / 86400000)
        : null;
      const label = daysSince !== null ? `ללא קשר ${daysSince} ימים` : 'לא נוצר קשר';
      naEl.innerHTML = UI.nextAction(
        `יצור קשר עם ${nextClient.name} — ${label}`,
        'פתח Briefing', `ClientsPanel.openBriefing('${nextClient.id}')`
      );
    }

    renderGrid();
  }

  function renderGrid() {
    const q    = (document.getElementById('clientSearch')?.value || '').toLowerCase();
    const grid = document.getElementById('clientsGrid');

    let list = _clients;
    if (q) {
      list = list.filter(c =>
        (c.name    || '').toLowerCase().includes(q) ||
        (c.company || '').toLowerCase().includes(q) ||
        (c.city    || '').toLowerCase().includes(q) ||
        (c.phone   || '').includes(q)
      );
    }

    if (!list.length) {
      grid.innerHTML = `<div style="grid-column:1/-1">${UI.guidedEmpty(
        'אין לקוחות עדיין',
        '◉',
        [
          { label: '◎ ראה לידים', onclick: "App.switchTo('leads')", primary: true },
          { label: '◇ עסקאות', onclick: "App.switchTo('crm')", primary: false },
        ],
        'לידים עם סטטוס "סגור זכה" יופיעו כאן'
      )}</div>`;
      return;
    }

    grid.innerHTML = list.map(c => {
      const daysSince = c.last_activity_at
        ? Math.floor((Date.now() - new Date(c.last_activity_at)) / 86400000)
        : null;
      const recLabel = daysSince !== null
        ? (daysSince === 0 ? 'היום' : `${daysSince} ימים`)
        : '—';
      const recColor = daysSince !== null && daysSince > 30 ? 'var(--amber)' : 'var(--muted)';

      return `
        <div class="client-card" onclick="ClientsPanel.openBriefing('${c.id}')">
          <div class="cc-av">${initials(c.name)}</div>
          <div class="cc-name">${c.name}</div>
          <div class="cc-company">${c.company || c.city || '—'}</div>
          <div class="cc-meta">
            ${c.phone ? `<span style="font-family:var(--mono);font-size:10px;color:var(--muted);direction:ltr">${c.phone}</span>` : ''}
            ${c.openDeals.length > 0
              ? `<span class="cc-badge">📋 ${c.openDeals.length} עסקאות</span>`
              : '<span style="font-size:10px;color:var(--muted)">אין עסקאות פתוחות</span>'}
          </div>
          ${c.wonValue > 0 ? `<div style="font-family:var(--mono);font-size:11px;color:var(--green);margin-top:6px">✓ ${ils(c.wonValue)} נסגר</div>` : ''}
          ${c.pipeVal  > 0 ? `<div style="font-family:var(--mono);font-size:11px;color:var(--amber);margin-top:4px">${ils(c.pipeVal)} pipeline</div>` : ''}
          <div style="font-size:10px;color:${recColor};margin-top:6px">קשר אחרון: ${recLabel}</div>
        </div>
      `;
    }).join('');
  }

  function openBriefing(leadId) {
    App.switchTo('briefing');
    setTimeout(() => {
      if (typeof BriefingPanel !== 'undefined') {
        BriefingPanel.prefillLead(leadId);
      }
    }, 200);
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  return { render, init, openBriefing };
})();
