/**
 * lead_ops.js — Lead Operations Panel
 * Phase 12: Lead Acquisition OS
 *
 * Surfaces: discovered leads | inbound leads | recommended actions |
 *           drafted messages | approval state | meeting suggestions | follow-up status
 */
const LeadOpsPanel = (() => {

  let _state = {
    discovered: [],
    inbound: [],
    pending_action: [],
    meeting_suggestions: [],
    counts: { discovered: 0, inbound: 0, pending_action: 0, meeting_suggestions: 0 },
    discoveryPlan: null,
    activeTab: 'inbound',
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">מרכז לידים — Lead Acquisition OS</div>
          <div class="section-sub" id="loSubTitle">טוען נתונים...</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <button class="btn btn-sm btn-ghost" onclick="LeadOpsPanel.openDiscoverModal()">+ גלה לידים</button>
          <button class="btn btn-sm btn-ghost" onclick="LeadOpsPanel.openWebsiteModal()">ניתוח אתר</button>
          <button class="btn btn-sm" onclick="LeadOpsPanel.load()">רענן</button>
        </div>
      </div>

      <!-- Summary widgets -->
      <div class="panel-widgets" id="loWidgets">
        <div class="pw-chip lo-tab-btn ${_state.activeTab==='inbound'?'active':''}" data-tab="inbound" onclick="LeadOpsPanel.setTab('inbound')">
          <div class="pw-val pv-green" id="loCntInbound">${_state.counts.inbound}</div>
          <div class="pw-label">לידים נכנסים</div>
        </div>
        <div class="pw-chip lo-tab-btn ${_state.activeTab==='discovered'?'active':''}" data-tab="discovered" onclick="LeadOpsPanel.setTab('discovered')">
          <div class="pw-val" id="loCntDiscovered">${_state.counts.discovered}</div>
          <div class="pw-label">גולשים שנגלו</div>
        </div>
        <div class="pw-chip lo-tab-btn ${_state.activeTab==='pending'?'active':''}" data-tab="pending" onclick="LeadOpsPanel.setTab('pending')">
          <div class="pw-val pv-amber" id="loCntPending">${_state.counts.pending_action}</div>
          <div class="pw-label">ממתינים לפעולה</div>
        </div>
        <div class="pw-chip lo-tab-btn ${_state.activeTab==='meetings'?'active':''}" data-tab="meetings" onclick="LeadOpsPanel.setTab('meetings')">
          <div class="pw-val pv-red" id="loCntMeetings">${_state.counts.meeting_suggestions}</div>
          <div class="pw-label">הצעות פגישה</div>
        </div>
      </div>

      <!-- Tab content -->
      <div id="loTabContent"></div>

      <!-- Discover modal -->
      <div class="modal-overlay hidden" id="loDiscoverModal">
        <div class="modal" style="max-width:520px">
          <h3 style="margin-bottom:12px">גלה לידים חדשים</h3>
          <p style="font-size:12px;color:var(--muted);margin-bottom:12px">
            הזן מטרה עסקית — המערכת תגזור אסטרטגיית מיקור לידים, פלחים, קהילות ואינטנציות חיפוש.
          </p>
          <input class="modal-input" id="loGoalInput" type="text"
                 placeholder="דוגמה: לידים מאדריכלים בתל אביב" dir="rtl" />
          <div style="margin-top:8px;font-size:11px;color:var(--muted)" id="loDiscoverPlanPreview"></div>
          <div style="display:flex;gap:8px;margin-top:14px">
            <button class="btn btn-primary" style="flex:1" onclick="LeadOpsPanel.runDiscover()">הפעל גילוי</button>
            <button class="btn btn-ghost" onclick="LeadOpsPanel.closeDiscoverModal()">ביטול</button>
          </div>
        </div>
      </div>

      <!-- Website analysis modal -->
      <div class="modal-overlay hidden" id="loWebsiteModal">
        <div class="modal" style="max-width:520px">
          <h3 style="margin-bottom:12px">ניתוח אתר — Website Growth</h3>
          <input class="modal-input" id="loUrlInput" type="url"
                 placeholder="כתובת האתר (https://...)" dir="ltr" />
          <div style="display:flex;gap:8px;margin-top:14px">
            <button class="btn btn-primary" style="flex:1" onclick="LeadOpsPanel.runWebsiteAnalysis()">נתח</button>
            <button class="btn btn-ghost" onclick="LeadOpsPanel.closeWebsiteModal()">ביטול</button>
          </div>
          <div id="loWebsiteResult" style="margin-top:14px;display:none"></div>
        </div>
      </div>
    `;
  }

  // ── Init / Load ────────────────────────────────────────────────────────────

  async function init(container) {
    container.innerHTML = render();
    await load();
  }

  async function load() {
    try {
      const data = await API.get('/api/lead_ops/queue');
      if (data.success) {
        _state.discovered = data.discovered || [];
        _state.inbound    = data.inbound    || [];
        _state.pending_action = data.pending_action || [];
        _state.meeting_suggestions = data.meeting_suggestions || [];
        _state.counts     = data.counts    || _state.counts;
      }
    } catch(e) { console.warn('[LeadOps] load failed', e); }
    _refresh();
    _updateHeaderWidget();
  }

  function _refresh() {
    const sub = document.getElementById('loSubTitle');
    if (sub) sub.textContent =
      `נכנסים: ${_state.counts.inbound} | גולשים: ${_state.counts.discovered} | ממתינים: ${_state.counts.pending_action}`;

    _updateCountBadges();
    _renderTab(_state.activeTab);
  }

  function _updateCountBadges() {
    const ids = {
      loCntInbound:    _state.counts.inbound,
      loCntDiscovered: _state.counts.discovered,
      loCntPending:    _state.counts.pending_action,
      loCntMeetings:   _state.counts.meeting_suggestions,
    };
    Object.entries(ids).forEach(([id, val]) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    });
  }

  function _updateHeaderWidget() {
    const w = document.getElementById('leadOpsWidget');
    if (!w) return;
    const total = _state.counts.inbound + _state.counts.discovered + _state.counts.pending_action;
    w.style.display = total > 0 ? 'flex' : 'none';
    _setText('lowDiscovered', _state.counts.discovered);
    _setText('lowInbound',    _state.counts.inbound);
    _setText('lowPending',    _state.counts.pending_action);
  }

  // ── Tab rendering ──────────────────────────────────────────────────────────

  function setTab(tab) {
    _state.activeTab = tab;
    document.querySelectorAll('.lo-tab-btn').forEach(el => {
      el.classList.toggle('active', el.dataset.tab === tab);
    });
    _renderTab(tab);
  }

  function _renderTab(tab) {
    const el = document.getElementById('loTabContent');
    if (!el) return;
    const maps = {
      inbound:    { leads: _state.inbound,    title: 'לידים נכנסים — ממתינים למענה', emptyMsg: 'אין לידים נכנסים כרגע' },
      discovered: { leads: _state.discovered, title: 'לידים שנגלו ממקורות ציבוריים', emptyMsg: 'הפעל גילוי לידים כדי להתחיל' },
      pending:    { leads: _state.pending_action, title: 'פעולות ממתינות לאישור / ביצוע', emptyMsg: 'אין פעולות ממתינות' },
      meetings:   { leads: _state.meeting_suggestions, title: 'הצעות לפגישות', emptyMsg: 'אין הצעות פגישה כרגע' },
    };
    const cfg = maps[tab] || maps.inbound;
    el.innerHTML = `
      <div class="section-head" style="margin-top:16px;margin-bottom:8px">
        <div class="section-title" style="font-size:13px">${cfg.title}</div>
      </div>
      ${cfg.leads.length === 0
        ? `<div class="empty-state">${cfg.emptyMsg}</div>`
        : cfg.leads.map(l => _leadCard(l)).join('')}
    `;
  }

  function _leadCard(l) {
    const score = l.score || 0;
    const scoreCls = score >= 70 ? 'score-hot' : score >= 40 ? 'score-warm' : 'score-cold';
    const inboundBadge = l.is_inbound
      ? `<span class="pill pill-green" style="font-size:9px">נכנס</span>` : '';
    const actionBadge = l.outreach_action && l.outreach_action !== 'wait'
      ? `<span class="pill pill-blue" style="font-size:9px">${_actionLabel(l.outreach_action)}</span>` : '';
    const meetingBadge = l.meeting_suggested
      ? `<span class="pill pill-amber" style="font-size:9px">פגישה הוצעה</span>` : '';
    const draftPreview = l.outreach_draft
      ? `<div class="lo-draft-preview">${_truncate(l.outreach_draft, 100)}</div>` : '';
    const due = l.next_action_due
      ? `<span style="font-size:10px;color:var(--muted)">תאריך יעד: ${l.next_action_due}</span>` : '';

    return `
      <div class="crm-row lo-lead-card">
        <div style="display:flex;align-items:flex-start;gap:12px">
          <div class="score-badge ${scoreCls}">${score}</div>
          <div style="flex:1;min-width:0">
            <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:4px">
              <span class="fw6">${_esc(l.name)}</span>
              ${inboundBadge}${actionBadge}${meetingBadge}
              ${UI.leadPill ? UI.leadPill(l.status) : ''}
            </div>
            <div style="font-size:11px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap">
              ${l.city ? `<span>${_esc(l.city)}</span>` : ''}
              ${l.segment ? `<span>${_esc(l.segment)}</span>` : ''}
              ${l.source_type ? `<span>מקור: ${_esc(l.source_type)}</span>` : ''}
              ${due}
            </div>
            ${draftPreview}
          </div>
          <div style="display:flex;flex-direction:column;gap:4px;align-items:flex-end">
            ${l.outreach_draft
              ? `<button class="btn btn-xs btn-ghost" onclick="LeadOpsPanel.viewDraft('${l.id}')">צפה בטיוטה</button>`
              : `<button class="btn btn-xs btn-ghost" onclick="LeadOpsPanel.generateDraft('${l.id}')">הכן טיוטה</button>`
            }
          </div>
        </div>
      </div>
    `;
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  function openDiscoverModal() {
    document.getElementById('loDiscoverModal').classList.remove('hidden');
  }
  function closeDiscoverModal() {
    document.getElementById('loDiscoverModal').classList.add('hidden');
  }

  async function runDiscover() {
    const goal = (document.getElementById('loGoalInput') || {}).value || '';
    if (!goal.trim()) { Toast.show('הזן מטרה עסקית', 'warning'); return; }
    const preview = document.getElementById('loDiscoverPlanPreview');
    if (preview) preview.textContent = 'מריץ גילוי...';
    try {
      const res = await API.post('/api/lead_ops/discover', { goal, signals: [] });
      if (res.success) {
        Toast.show(`גילוי הושלם — ${res.new_leads} לידים חדשים`, 'success');
        closeDiscoverModal();
        await load();
      } else {
        Toast.show('שגיאה: ' + (res.error || 'unknown'), 'error');
      }
    } catch(e) {
      Toast.show('שגיאת רשת: ' + e.message, 'error');
    }
  }

  function openWebsiteModal() {
    document.getElementById('loWebsiteModal').classList.remove('hidden');
  }
  function closeWebsiteModal() {
    document.getElementById('loWebsiteModal').classList.add('hidden');
  }

  async function runWebsiteAnalysis() {
    const url = (document.getElementById('loUrlInput') || {}).value || '';
    if (!url.trim()) { Toast.show('הזן כתובת אתר', 'warning'); return; }
    try {
      const res = await API.post('/api/lead_ops/website', { url });
      const el  = document.getElementById('loWebsiteResult');
      if (el) {
        el.style.display = 'block';
        if (res.success) {
          el.innerHTML = `
            <div style="font-size:12px;line-height:1.7">
              <b>ציון בריאות: ${res.audit_score}/100</b> | ציון לכידת לידים: ${res.lead_capture_score}/100<br>
              <b>המלצות עדיפות:</b><br>
              <ul style="margin:4px 0 8px 16px">
                ${(res.top_recommendations||[]).slice(0,4).map(r=>`<li>${_esc(r)}</li>`).join('')}
              </ul>
              <b>פערי תוכן:</b> ${(res.content_gaps||[]).slice(0,3).map(g=>g.topic).join(', ')}
            </div>
          `;
        } else {
          el.innerHTML = `<span style="color:var(--red)">שגיאה: ${_esc(res.error||'')}</span>`;
        }
      }
    } catch(e) {
      Toast.show('שגיאת רשת: ' + e.message, 'error');
    }
  }

  async function generateDraft(leadId) {
    try {
      const res = await API.post('/api/lead_ops/draft', { lead: { id: leadId }, action_type: 'first_contact' });
      if (res.success) {
        Toast.show('טיוטה נוצרה — ממתינה לאישור', 'success');
        await load();
      }
    } catch(e) { Toast.show('שגיאה ביצירת טיוטה', 'error'); }
  }

  function viewDraft(leadId) {
    const all = [..._state.inbound, ..._state.discovered, ..._state.pending_action];
    const lead = all.find(l => l.id === leadId);
    if (!lead || !lead.outreach_draft) { Toast.show('לא נמצאה טיוטה', 'warning'); return; }
    alert(`טיוטת הודעה לליד ${lead.name}:\n\n${lead.outreach_draft}\n\n—\nפעולה: ${lead.outreach_action || 'ידני'}`);
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  function _esc(s) {
    return String(s||'').replace(/[<>&"]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'})[c]);
  }
  function _truncate(s, n) { return s.length > n ? s.slice(0, n) + '…' : s; }
  function _setText(id, val) { const el=document.getElementById(id); if(el) el.textContent=val; }
  function _actionLabel(a) {
    return {dm:'DM',follow_up:'מעקב',meeting_request:'פגישה',
            comment_reply:'תגובה',inbound_response:'מענה נכנס',wait:'המתן'}[a] || a;
  }

  // ── Public API ─────────────────────────────────────────────────────────────
  return {
    init,
    load,
    setTab,
    openDiscoverModal,
    closeDiscoverModal,
    runDiscover,
    openWebsiteModal,
    closeWebsiteModal,
    runWebsiteAnalysis,
    generateDraft,
    viewDraft,
  };

})();

// ── App integration ────────────────────────────────────────────────────────────
// Register with the global app shell navigation
if (typeof window !== 'undefined') {
  window.addEventListener('ashbelos:nav', e => {
    if (e.detail && e.detail.panel === 'lead-ops') {
      const el = document.getElementById('panel-lead-ops');
      if (el && !el._loInited) {
        el._loInited = true;
        LeadOpsPanel.init(el);
      } else if (el) {
        LeadOpsPanel.load();
      }
    }
  });

  // Make the header widget clickable — navigate to lead-ops panel
  document.addEventListener('DOMContentLoaded', () => {
    const widget = document.getElementById('leadOpsWidget');
    if (widget) {
      widget.addEventListener('click', () => {
        if (typeof App !== 'undefined' && App.navigate) App.navigate('lead-ops');
      });
    }
  });
}
