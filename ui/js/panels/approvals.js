/**
 * approvals.js — approvals panel
 */
const ApprovalsPanel = (() => {
  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">אישורים</div>
          <div class="section-sub" id="approvalCount">טוען...</div>
        </div>
        <button class="btn btn-ghost" onclick="ApprovalsPanel.reload()">רענן</button>
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
    const items = res.data.approvals || [];
    cnt.textContent = `${items.length} ממתינים לאישור`;
    if (!items.length) {
      list.innerHTML = `<div style="color:var(--muted);padding:32px;text-align:center;">אין אישורים ממתינים ✓</div>`;
      App.refreshBadge();
      return;
    }
    list.innerHTML = items.map(a => `
      <div class="approval-card" id="appr-${a.id}">
        <div class="approval-info">
          <div class="approval-action">${a.action}</div>
          <div class="approval-detail">סיכון: ${a.risk_level} | task: ${a.task_id?.slice(0,8) || '—'}</div>
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
    } else {
      Toast.error(res.error || 'שגיאה');
    }
  }

  return { render, init: load, reload: load, resolve };
})();