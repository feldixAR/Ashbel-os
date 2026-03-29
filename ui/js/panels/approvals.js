/**
 * approvals.js — Approvals and Audit Panel
 */
const ApprovalsPanel = (() => {

  function render() {
    return `
      <!-- Widget bar -->
      <div class="panel-widgets">
        <div class="pw-chip">
          <div class="pw-val pv-amber" id="apwPending">—</div>
          <div class="pw-label">ממתינים לאישור</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-red" id="apwHighRisk">—</div>
          <div class="pw-label">סיכון גבוה</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-green" id="apwLowRisk">—</div>
          <div class="pw-label">סיכון נמוך</div>
        </div>
      </div>

      <div class="section-head">
        <div>
          <div class="section-title">אישורים ומסלול ביקורת</div>
          <div class="section-sub" id="approvalCount">טוען...</div>
        </div>
        <button class="btn btn-ghost" onclick="ApprovalsPanel.reload()">↻ רענן</button>
      </div>
      <div id="approvalsList"></div>
    `;
  }

  async function load() {
    const res  = await API.approvals();
    const list = document.getElementById('approvalsList');
    const cnt  = document.getElementById('approvalCount');
    if (!res.success) {
      list.innerHTML = `<div style="color:var(--red);padding:16px;">שגיאה בטעינת אישורים</div>`;
      return;
    }
    const items    = res.data.approvals || [];
    const highRisk = items.filter(a => (a.risk_level || 0) >= 3).length;
    const lowRisk  = items.filter(a => (a.risk_level || 0) < 3).length;

    _setText('apwPending',  items.length);
    _setText('apwHighRisk', highRisk);
    _setText('apwLowRisk',  lowRisk);
    cnt.textContent = `${items.length} ממתינים לאישור`;

    if (!items.length) {
      list.innerHTML = `
        <div style="text-align:center;padding:48px 16px">
          <div style="font-size:32px;margin-bottom:10px">✓</div>
          <div style="color:var(--green);font-weight:600;margin-bottom:4px">אין אישורים ממתינים</div>
          <div style="color:var(--muted);font-size:12px">כל הפעולות עובדו</div>
        </div>`;
      App.refreshBadge();
      return;
    }
    list.innerHTML = items.map(a => `
      <div class="approval-card" id="appr-${a.id}">
        <div class="approval-info">
          <div class="approval-action">${a.action}</div>
          <div class="approval-detail">
            סיכון: ${a.risk_level} | task: ${a.task_id?.slice(0,8) || '—'}
          </div>
        </div>
        <span class="approval-risk">רמה ${a.risk_level}</span>
        <button class="btn btn-primary" style="padding:6px 12px;font-size:11px;"
                onclick="ApprovalsPanel.resolve('${a.id}', 'approve')">אשר</button>
        <button class="btn btn-danger"
                onclick="ApprovalsPanel.resolve('${a.id}', 'deny')">דחה</button>
      </div>
    `).join('');
    App.refreshBadge();
  }

  async function resolve(id, action) {
    const res = action === 'approve' ? await API.approve(id) : await API.deny(id);
    if (res.success) {
      document.getElementById('appr-' + id)?.remove();
      Toast.success(action === 'approve' ? 'פעולה אושרה' : 'פעולה נדחתה');
      App.refreshBadge();
      // Refresh widget counts
      const remaining = document.querySelectorAll('[id^="appr-"]').length;
      _setText('apwPending', remaining);
    } else {
      Toast.error(res.error || 'שגיאה');
    }
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  return { render, init: load, reload: load, resolve };
})();
