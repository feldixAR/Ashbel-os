/**
 * ui.js — AshbelOS shared UI primitives
 * All panels should use these helpers instead of inline HTML duplication.
 * RTL Hebrew, glass design system.
 */
const UI = (() => {

  // ── Formatters ────────────────────────────────────────────────────────────

  function ils(n, opts = {}) {
    n = Number(n) || 0;
    if (opts.full) return '₪' + n.toLocaleString('he-IL');
    if (n >= 1_000_000) return `₪${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000)     return `₪${Math.round(n / 1_000)}K`;
    return '₪' + n.toLocaleString('he-IL');
  }

  function num(n) { return (Number(n) || 0).toLocaleString('he-IL'); }

  function relTime(iso) {
    if (!iso) return '—';
    const diff = (Date.now() - new Date(iso)) / 1000;
    if (diff < 60)   return 'עכשיו';
    if (diff < 3600) return `לפני ${Math.floor(diff / 60)}ד׳`;
    if (diff < 86400) return `לפני ${Math.floor(diff / 3600)}ש׳`;
    return `לפני ${Math.floor(diff / 86400)}י׳`;
  }

  // ── Status pills ──────────────────────────────────────────────────────────

  const LEAD_STATUS_MAP = {
    'חדש': 'pill-steel', 'מתעניין': 'pill-green', 'ניסיון קשר': 'pill-amber',
    'חם': 'pill-red', 'בטיפול': 'pill-amber', 'קר': 'pill-steel',
    'סגור_זכה': 'pill-green', 'סגור_הפסיד': 'pill-red',
  };

  const DEAL_STAGE_MAP = {
    new: 'pill-steel', qualified: 'pill-accent', proposal: 'pill-amber',
    negotiation: 'pill-red', won: 'pill-green', lost: 'pill-steel',
  };

  function pill(text, cls = '') {
    return `<span class="pill ${cls}">${text || '—'}</span>`;
  }

  function leadPill(status) {
    return pill(status, LEAD_STATUS_MAP[status] || '');
  }

  function dealPill(stage) {
    const labels = { new: 'חדש', qualified: 'כשיר', proposal: 'הצעה',
                     negotiation: 'משא ומתן', won: 'זכה', lost: 'הפסיד' };
    return pill(labels[stage] || stage, DEAL_STAGE_MAP[stage] || '');
  }

  function taskPill(status) {
    const map = { open: 'pill-amber', completed: 'pill-green', cancelled: 'pill-steel',
                  overdue: 'pill-red', pending: 'pill-steel' };
    const labels = { open: 'פתוח', completed: 'הושלם', cancelled: 'בוטל',
                     overdue: 'באיחור', pending: 'ממתין' };
    return pill(labels[status] || status, map[status] || '');
  }

  // ── Score badge ───────────────────────────────────────────────────────────

  function scoreBadge(s) {
    s = Number(s) || 0;
    const cls = s >= 70 ? 'score-hot' : s >= 40 ? 'score-warm' : 'score-cold';
    return `<span class="${cls}" style="font-family:var(--mono);font-size:11px;font-weight:600">${s}</span>`;
  }

  // ── Widget bar ────────────────────────────────────────────────────────────
  // chips: [{id, val, label, cls}]  cls one of: pv-green pv-amber pv-red pv-accent

  function widgetBar(chips, id = '') {
    const html = chips.map(c => `
      <div class="pw-chip">
        <div class="pw-val ${c.cls || ''}" ${c.id ? `id="${c.id}"` : ''}>
          ${c.val !== undefined ? c.val : '—'}
        </div>
        <div class="pw-label">${c.label}</div>
      </div>`).join('');
    return `<div class="panel-widgets"${id ? ` id="${id}"` : ''}>${html}</div>`;
  }

  // ── Section header ────────────────────────────────────────────────────────

  function sectionHead(title, sub = '', actionsHtml = '') {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">${title}</div>
          ${sub ? `<div class="section-sub">${sub}</div>` : ''}
        </div>
        ${actionsHtml ? `<div style="display:flex;gap:8px;align-items:center">${actionsHtml}</div>` : ''}
      </div>`;
  }

  // ── Insight strip ─────────────────────────────────────────────────────────
  // items: [{icon, text, cls}]  cls: insight-good insight-warn insight-alert

  function insightStrip(items) {
    if (!items || !items.length) return '';
    const chips = items.map(i =>
      `<div class="insight-chip ${i.cls || ''}">
         ${i.icon ? `<span class="insight-icon">${i.icon}</span>` : ''}
         <span>${i.text}</span>
       </div>`).join('');
    return `<div class="insight-strip">${chips}</div>`;
  }

  // ── Next-action box ───────────────────────────────────────────────────────

  function nextAction(text, btnLabel = '', onclickJs = '') {
    const btn = btnLabel
      ? `<button class="btn btn-primary" onclick="${onclickJs}">${btnLabel}</button>`
      : '';
    return `<div class="next-action-box">▶ ${text}${btn ? `<br>${btn}` : ''}</div>`;
  }

  // ── Loading / empty / error states ───────────────────────────────────────

  function loading(msg = 'טוען...') {
    return `<div class="empty-state">
      <div class="empty-state-icon">
        <span style="display:inline-block;animation:spin 1s linear infinite">◌</span>
      </div>
      <div class="empty-state-msg">${msg}</div>
    </div>`;
  }

  function empty(msg = 'אין נתונים', icon = '○') {
    return `<div class="empty-state">
      <div class="empty-state-icon">${icon}</div>
      <div class="empty-state-msg">${msg}</div>
    </div>`;
  }

  function error(msg = 'שגיאה בטעינת הנתונים') {
    return `<div class="empty-state">
      <div class="empty-state-icon" style="color:var(--red)">⚠</div>
      <div class="empty-state-msg" style="color:var(--red)">${msg}</div>
    </div>`;
  }

  /**
   * guidedEmpty — empty state with mandatory CTA
   * ctaBtns: [{label, onclick, primary?}]  OR single label+onclick
   */
  function guidedEmpty(msg, icon = '○', ctaBtns = [], subMsg = '') {
    // Accept old 4-arg signature: (msg, icon, ctaLabel, ctaJs)
    if (typeof ctaBtns === 'string') {
      const js = subMsg;
      ctaBtns = ctaBtns ? [{ label: ctaBtns, onclick: js, primary: true }] : [];
      subMsg  = '';
    }
    const btns = ctaBtns.map(b =>
      `<button class="btn ${b.primary !== false ? 'btn-primary' : 'btn-ghost'}"
               onclick="${b.onclick}">${b.label}</button>`
    ).join('');
    return `<div class="empty-state">
      <div class="empty-state-icon">${icon}</div>
      <div class="empty-state-msg">${msg}</div>
      ${subMsg ? `<div class="empty-state-sub">${subMsg}</div>` : ''}
      ${btns ? `<div class="empty-state-actions">${btns}</div>` : ''}
    </div>`;
  }

  // ── Skeleton lines ────────────────────────────────────────────────────────

  function skel(widthClass = 'skel-w80', heightClass = 'skel-h12') {
    return `<div class="skel ${heightClass} ${widthClass}"></div>`;
  }

  function skelBlock(lines = 3) {
    const widths = ['skel-w80', 'skel-w60', 'skel-w40'];
    return Array.from({ length: lines }, (_, i) =>
      skel(widths[i % widths.length], i === 0 ? 'skel-h20' : 'skel-h12')
    ).join('');
  }

  // ── Table helpers ─────────────────────────────────────────────────────────

  function tableRow(cells, tag = 'td') {
    return `<tr>${cells.map(c => `<${tag}>${c}</${tag}>`).join('')}</tr>`;
  }

  function tableHead(cols) { return tableRow(cols, 'th'); }

  // ── Expose ────────────────────────────────────────────────────────────────

  return {
    ils, num, relTime,
    pill, leadPill, dealPill, taskPill, scoreBadge,
    widgetBar, sectionHead, insightStrip, nextAction,
    loading, empty, error, guidedEmpty,
    skel, skelBlock,
    tableRow, tableHead,
    LEAD_STATUS_MAP, DEAL_STAGE_MAP,
  };
})();
