/**
 * approvals.js — Approvals and Audit Panel
 * Tabs: pending approvals | audit history
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
        <div class="pw-chip">
          <div class="pw-val" id="apwResolved">—</div>
          <div class="pw-label">הוחלט</div>
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

      <!-- Tab bar -->
      <div class="leads-filter" id="apTabs">
        <button class="filter-pill active" data-tab="pending">ממתינים</button>
        <button class="filter-pill" data-tab="history">היסטוריה</button>
      </div>

      <div id="approvalsList" style="margin-top:12px">${UI.loading('טוען אישורים...')}</div>
      <div id="approvalsHistory" style="display:none;margin-top:12px">${UI.loading('טוען היסטוריה...')}</div>
    `;
  }

  let _activeTab = 'pending';

  async function load() {
    _activeTab = _activeTab || 'pending';
    const [pendRes, histRes] = await Promise.all([
      API.approvals(),
      API.approvalHistory(50),
    ]);

    const list = document.getElementById('approvalsList');
    const hist = document.getElementById('approvalsHistory');
    const cnt  = document.getElementById('approvalCount');

    // ── Pending ───────────────────────────────────────────────────────────────
    if (!pendRes.success) {
      list.innerHTML = UI.error('שגיאה בטעינת אישורים');
    } else {
      const items    = pendRes.data.approvals || [];
      const highRisk = items.filter(a => (a.risk_level || 0) >= 3).length;
      const lowRisk  = items.filter(a => (a.risk_level || 0) < 3).length;

      _setText('apwPending',  items.length);
      _setText('apwHighRisk', highRisk);
      _setText('apwLowRisk',  lowRisk);
      cnt.textContent = `${items.length} ממתינים לאישור`;

      // Insight strip
      const iChips = [];
      if (highRisk)      iChips.push({ icon: '⚠', text: `${highRisk} פעולות סיכון גבוה`, cls: 'insight-alert' });
      if (lowRisk)       iChips.push({ icon: '○', text: `${lowRisk} פעולות סיכון נמוך`,   cls: 'insight-warn'  });
      if (!items.length) iChips.push({ icon: '✓', text: 'אין אישורים ממתינים',            cls: 'insight-good'  });
      const iEl = document.getElementById('apInsight');
      if (iEl) iEl.innerHTML = UI.insightStrip(iChips);

      // Next-action
      const top = items.sort((a,b) => (b.risk_level||0) - (a.risk_level||0))[0];
      const naEl = document.getElementById('apNextAction');
      if (naEl && top) {
        naEl.innerHTML = UI.nextAction(`בדוק ואשר: "${top.action}" — סיכון רמה ${top.risk_level}`);
      } else if (naEl) { naEl.innerHTML = ''; }

      if (!items.length) {
        list.innerHTML = UI.empty('אין אישורים ממתינים — כל הפעולות עובדו', '✓');
      } else {
        list.innerHTML = items.map(a => _pendingCard(a)).join('');
      }
      App.refreshBadge();
    }

    // ── History ───────────────────────────────────────────────────────────────
    if (!histRes.success) {
      hist.innerHTML = UI.error('שגיאה בטעינת היסטוריה');
    } else {
      const resolved = histRes.data.history || [];
      _setText('apwResolved', resolved.length);
      hist.innerHTML = resolved.length
        ? resolved.map(a => _historyCard(a)).join('')
        : UI.empty('אין אישורים שהוחלטו עדיין', '○');
    }
  }

  function _pendingCard(a) {
    const ot       = a.details?.outreach_task || {};
    const leadName = ot.lead_name || a.details?.lead_name || '—';
    const audience = ot.audience  || '—';
    const channel  = ot.channel   || 'whatsapp';
    const preview  = ot.message   || '';
    return `
      <div class="approval-card" id="appr-${a.id}">
        <div class="approval-info" style="flex:1">
          <div class="approval-action">${a.action}</div>
          <div class="approval-detail">
            👤 ${leadName} | 🎯 ${audience} | 📡 ${channel} | סיכון: ${a.risk_level}
            ${a.created_at ? `| ${a.created_at.slice(0,16).replace('T',' ')}` : ''}
          </div>
          ${preview ? `<div style="margin-top:6px;padding:8px;background:var(--surface-2,rgba(0,0,0,.06));border-radius:6px;font-size:11px;color:var(--muted);max-height:60px;overflow:hidden;direction:rtl">${preview.slice(0,200)}</div>` : ''}
        </div>
        <div style="display:flex;flex-direction:column;gap:5px;min-width:80px">
          <span class="approval-risk">רמה ${a.risk_level}</span>
          <button class="btn btn-primary" style="padding:5px 10px;font-size:11px;"
                  onclick="ApprovalsPanel.resolve('${a.id}', 'approve')">✅ אשר</button>
          <button class="btn btn-danger" style="padding:5px 10px;font-size:11px;"
                  onclick="ApprovalsPanel.resolve('${a.id}', 'deny')">❌ דחה</button>
        </div>
      </div>
    `;
  }

  function _historyCard(a) {
    const approved = a.status === 'approved';
    const statusCls = approved ? 'pv-green' : 'pv-red';
    const statusLabel = approved ? 'אושר ✓' : 'נדחה ✗';
    const hasOutreach = a.details?.outreach_task;

    return `
      <div class="approval-card" style="opacity:0.85">
        <div class="approval-info">
          <div class="approval-action">${a.action}</div>
          <div class="approval-detail">
            סיכון: ${a.risk_level} | task: ${(a.task_id||'—').slice(0,8)}
            ${a.resolved_at ? `| ${a.resolved_at.slice(0,16).replace('T',' ')}` : ''}
            ${a.resolved_by ? `| ע"י: ${a.resolved_by}` : ''}
            ${hasOutreach ? `| 📱 outreach: ${a.details.outreach_task.lead_name || '—'}` : ''}
          </div>
        </div>
        <span class="approval-risk ${statusCls}" style="font-size:11px;padding:4px 8px">${statusLabel}</span>
      </div>
    `;
  }

  async function init() {
    await load();
    document.querySelectorAll('#apTabs .filter-pill').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#apTabs .filter-pill').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _activeTab = btn.dataset.tab;
        document.getElementById('approvalsList').style.display    = _activeTab === 'pending' ? '' : 'none';
        document.getElementById('approvalsHistory').style.display = _activeTab === 'history' ? '' : 'none';
      });
    });
  }

  async function resolve(id, action) {
    const res = action === 'approve' ? await API.approve(id) : await API.deny(id);
    if (res.success) {
      document.getElementById('appr-' + id)?.remove();
      Toast.success(action === 'approve' ? 'פעולה אושרה' : 'פעולה נדחתה');
      // Refresh history to show newly resolved item
      const histRes = await API.approvalHistory(50);
      if (histRes.success) {
        const resolved = histRes.data.history || [];
        _setText('apwResolved', resolved.length);
        document.getElementById('approvalsHistory').innerHTML = resolved.length
          ? resolved.map(a => _historyCard(a)).join('')
          : UI.empty('אין אישורים שהוחלטו עדיין', '○');
      }
      const remaining = document.querySelectorAll('[id^="appr-"]').length;
      _setText('apwPending', remaining);
      App.refreshBadge();
    } else {
      Toast.error(res.error || 'שגיאה');
    }
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  return { render, init, reload: load, resolve };
})();
