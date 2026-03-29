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

      <div id="apInsight"></div>
      <div id="apNextAction" style="margin-bottom:16px"></div>

      <div class="section-head">
        <div>
          <div class="section-title">אישורים ומסלול ביקורת</div>
          <div class="section-sub" id="approvalCount">טוען...</div>
        </div>
        <button class="btn btn-ghost" onclick="ApprovalsPanel.reload()">↻ רענן</button>
      </div>
      <div id="approvalsList">${UI.loading('טוען אישורים...')}</div>
    `;
  }

  async function load() {
    const res  = await API.approvals();
    const list = document.getElementById('approvalsList');
    const cnt  = document.getElementById('approvalCount');
    if (!res.success) {
      list.innerHTML = UI.error('שגיאה בטעינת אישורים');
      return;
    }
    const items    = res.data.approvals || [];
    const highRisk = items.filter(a => (a.risk_level || 0) >= 3).length;
    const lowRisk  = items.filter(a => (a.risk_level || 0) < 3).length;

    _setText('apwPending',  items.length);
    _setText('apwHighRisk', highRisk);
    _setText('apwLowRisk',  lowRisk);
    cnt.textContent = `${items.length} ממתינים לאישור`;

    // Insight strip
    const iChips = [];
    if (highRisk)        iChips.push({ icon: '⚠', text: `${highRisk} פעולות סיכון גבוה`, cls: 'insight-alert' });
    if (lowRisk)         iChips.push({ icon: '○', text: `${lowRisk} פעולות סיכון נמוך`,   cls: 'insight-warn'  });
    if (!items.length)   iChips.push({ icon: '✓', text: 'אין אישורים ממתינים',            cls: 'insight-good'  });
    const iEl = document.getElementById('apInsight');
    if (iEl) iEl.innerHTML = UI.insightStrip(iChips);

    // Next-action
    const topApproval = items.sort((a,b) => (b.risk_level||0) - (a.risk_level||0))[0];
    const naEl = document.getElementById('apNextAction');
    if (naEl && topApproval) {
      naEl.innerHTML = UI.nextAction(`בדוק ואשר: "${topApproval.action}" — סיכון רמה ${topApproval.risk_level}`);
    } else if (naEl) { naEl.innerHTML = ''; }

    if (!items.length) {
      list.innerHTML = UI.empty('אין אישורים ממתינים — כל הפעולות עובדו', '✓');
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
