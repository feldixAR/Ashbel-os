/**
 * qa_console.js — read-only browser QA panel for AshbelOS.
 * Injects a QA button into the existing UI without replacing the console.
 */
const QAConsole = (() => {
  function init() {
    _injectStyle();
    const chips = document.getElementById('cmdChips');
    if (chips && !document.getElementById('qaConsoleBtn')) {
      const btn = document.createElement('button');
      btn.className = 'cmd-chip';
      btn.id = 'qaConsoleBtn';
      btn.textContent = '🧪 בדיקת מערכת';
      btn.onclick = open;
      chips.appendChild(btn);
    }

    if (!document.getElementById('qaConsoleOverlay')) {
      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay hidden';
      overlay.id = 'qaConsoleOverlay';
      overlay.innerHTML = `
        <div class="um-modal qa-modal" style="max-width:920px">
          <div class="um-header">
            <div style="font-size:15px;font-weight:700">🧪 בדיקת מערכת AshbelOS</div>
            <button class="btn btn-ghost" style="font-size:12px" onclick="QAConsole.close()">✕</button>
          </div>
          <div id="qaConsoleBody">
            <div class="work-loading">טוען בדיקות...</div>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      overlay.addEventListener('click', e => {
        if (e.target === overlay) close();
      });
    }
  }

  async function open() {
    init();
    document.getElementById('qaConsoleOverlay').classList.remove('hidden');
    const body = document.getElementById('qaConsoleBody');
    body.innerHTML = '<div class="work-loading">טוען בדיקות מערכת...</div>';

    try {
      const res = API.systemQa ? await API.systemQa() : await API.get('/system/qa');
      if (!res.success) {
        body.innerHTML = `<div class="um-error">שגיאה בטעינת בדיקת מערכת: ${_err(res)}</div>`;
        return;
      }
      render(res.data || {});
    } catch (e) {
      body.innerHTML = `<div class="um-error">שגיאה: ${e.message || e}</div>`;
    }
  }

  function close() {
    document.getElementById('qaConsoleOverlay')?.classList.add('hidden');
  }

  function render(data) {
    const body = document.getElementById('qaConsoleBody');
    const checks = data.checks || [];
    const pass = checks.filter(c => c.status === 'pass').length;
    const fail = checks.filter(c => c.status === 'fail').length;
    const warn = checks.filter(c => c.status === 'warn').length;
    const manual = checks.filter(c => c.status === 'manual').length;

    const checkHtml = checks.map(c => {
      const cls = c.status === 'pass' ? 'pill-green'
        : c.status === 'fail' ? 'pill-red'
        : c.status === 'warn' ? 'pill-amber'
        : 'pill-steel';
      const label = c.status === 'pass' ? 'תקין'
        : c.status === 'fail' ? 'תקלה'
        : c.status === 'warn' ? 'אזהרה'
        : 'בדיקה ידנית';
      return `
        <div class="qa-check-row">
          <div>
            <div class="qa-check-name">${_esc(c.name)}</div>
            ${c.next_action ? `<div class="qa-next">${_esc(c.next_action)}</div>` : ''}
            <pre class="qa-details">${_esc(JSON.stringify(c.details || {}, null, 2))}</pre>
          </div>
          <span class="pill ${cls}">${label}</span>
        </div>`;
    }).join('');

    const steps = (data.browser_walkthrough || []).map((s, i) =>
      `<li>${i + 1}. ${_esc(s)}</li>`
    ).join('');

    body.innerHTML = `
      <div class="qa-summary-grid">
        <div class="qa-summary-card"><div class="qa-num">${pass}</div><div>תקין</div></div>
        <div class="qa-summary-card"><div class="qa-num">${warn}</div><div>אזהרות</div></div>
        <div class="qa-summary-card"><div class="qa-num">${fail}</div><div>תקלות</div></div>
        <div class="qa-summary-card"><div class="qa-num">${manual}</div><div>ידני</div></div>
      </div>
      <div class="qa-meta">
        סביבה: ${_esc(data.environment || 'local')} · שירות: ${_esc(data.service || '')} · commit: ${_esc(data.commit || 'unknown')}
      </div>
      <div class="qa-section-title">בדיקות מערכת</div>
      <div class="qa-checks">${checkHtml}</div>
      <div class="qa-section-title">מעבר דפדפן מומלץ</div>
      <ol class="qa-steps">${steps}</ol>
      <div class="qa-safe-note">המסך הזה לקריאה בלבד. הוא לא מייבא לידים, לא שולח הודעות ולא משנה נתוני לקוחות.</div>
    `;
  }

  function _injectStyle() {
    if (document.getElementById('qaConsoleStyle')) return;
    const style = document.createElement('style');
    style.id = 'qaConsoleStyle';
    style.textContent = `
      .qa-summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0 14px}
      .qa-summary-card{border:1px solid rgba(148,163,184,.25);border-radius:14px;padding:12px;background:rgba(15,23,42,.42);text-align:center}
      .qa-num{font-size:24px;font-weight:800;margin-bottom:4px}
      .qa-meta{font-size:12px;color:var(--muted);margin-bottom:14px}
      .qa-section-title{font-size:14px;font-weight:800;margin:14px 0 8px}
      .qa-check-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:start;border:1px solid rgba(148,163,184,.22);border-radius:14px;padding:10px;margin-bottom:8px;background:rgba(15,23,42,.28)}
      .qa-check-name{font-weight:700;margin-bottom:3px}
      .qa-next{font-size:12px;color:var(--muted);margin-bottom:6px}
      .qa-details{direction:ltr;text-align:left;white-space:pre-wrap;font-size:11px;max-height:120px;overflow:auto;background:rgba(2,6,23,.35);border-radius:10px;padding:8px}
      .qa-steps{padding-right:22px;line-height:1.8;font-size:13px}
      .qa-safe-note{margin-top:12px;padding:10px;border-radius:12px;background:rgba(16,185,129,.10);font-size:12px}
      @media(max-width:640px){.qa-summary-grid{grid-template-columns:repeat(2,1fr)}.qa-check-row{grid-template-columns:1fr}.qa-modal{width:94vw;max-height:88vh;overflow:auto}}
    `;
    document.head.appendChild(style);
  }

  function _err(res) {
    return res?.error || res?.data?.message || res?.message || 'שגיאה לא ידועה';
  }

  function _esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, ch => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
  }

  return { init, open, close };
})();

document.addEventListener('DOMContentLoaded', () => QAConsole.init());
