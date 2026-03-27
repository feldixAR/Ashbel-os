/**
 * workspace.js — Operational Workspace (Batch 11)
 * Lead list with smart filters + right panel: selected lead detail,
 * open deals, last timeline events, quick actions
 */
const WorkspacePanel = (() => {

  const STATUS_W  = { 'חם':2, 'בטיפול':1, 'חדש':0, 'קר':-1, 'לא רלוונטי':-2 };
  const PILL_CLS  = { 'חם':'pill-red', 'בטיפול':'pill-amber', 'חדש':'pill-steel', 'קר':'pill-green' };
  const EV_ICON   = { message:'💬', whatsapp:'📱', email:'📧', call:'📞', meeting:'🤝', note:'📝', stage_change:'🔄', calendar:'📅' };

  let _leads    = [];
  let _filter   = 'all';
  let _selected = null;

  function ils(n)       { return '₪' + (Number(n)||0).toLocaleString('he-IL'); }
  function initials(nm) { return (nm||'?').trim().split(/\s+/).map(w=>w[0]).join('').slice(0,2).toUpperCase(); }
  function relTime(s) {
    if (!s) return '';
    const diff = Math.floor((Date.now() - new Date(s)) / 60000);
    if (diff < 2)    return 'כעת';
    if (diff < 60)   return `${diff} דק'`;
    if (diff < 1440) return `${Math.floor(diff/60)} שע'`;
    return `${Math.floor(diff/1440)} ימ'`;
  }

  function render() {
    return `
      <div class="ws-split">

        <!-- LEFT: Lead list -->
        <div class="ws-main" style="padding:20px">

          <div class="section-head">
            <div>
              <div class="section-title">סביבת עבודה</div>
              <div class="section-sub" id="wsSub">טוען לידים...</div>
            </div>
            <button class="btn btn-ghost" id="wsRefresh" style="font-size:12px">↻</button>
          </div>

          <!-- Filters -->
          <div class="leads-filter" id="wsFilters">
            <button class="filter-pill active" data-f="all">הכל</button>
            <button class="filter-pill" data-f="חם">🔥 חם</button>
            <button class="filter-pill" data-f="בטיפול">בטיפול</button>
            <button class="filter-pill" data-f="חדש">חדש</button>
            <button class="filter-pill" data-f="קר">קר</button>
          </div>

          <!-- Search -->
          <input class="cmd-input" id="wsSearch" placeholder="חפש שם, חברה, טלפון..."
                 style="width:100%;margin-bottom:14px;font-size:13px" />

          <!-- Lead list -->
          <div id="wsLeadList">
            ${Array(6).fill(`<div style="display:flex;gap:9px;align-items:center;padding:10px 0;border-bottom:1px solid rgba(34,39,49,.4)"><span class="skel" style="width:32px;height:32px;border-radius:50%;flex-shrink:0"></span><div style="flex:1"><span class="skel skel-h12 skel-w80" style="display:block;margin-bottom:5px"></span><span class="skel skel-h12 skel-w60" style="display:block"></span></div></div>`).join('')}
          </div>

        </div>

        <!-- RIGHT: Lead detail -->
        <div class="ws-right">
          <div class="ws-right-label">פרטי ליד</div>
          <div id="wsLeadDetail">
            <div class="no-select">
              <div style="font-size:28px;margin-bottom:10px">👆</div>
              <div>בחר ליד מהרשימה</div>
            </div>
          </div>
        </div>

      </div>
    `;
  }

  async function init() {
    _leads    = [];
    _filter   = 'all';
    _selected = null;

    await loadLeads();

    document.getElementById('wsRefresh')?.addEventListener('click', loadLeads);

    document.querySelectorAll('.filter-pill').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-pill').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        _filter = btn.dataset.f;
        renderList();
      });
    });

    document.getElementById('wsSearch')?.addEventListener('input', renderList);
  }

  async function loadLeads() {
    const res = await API.leads({ limit: 200 });
    _leads = res.success ? (res.data?.leads || []) : [];
    document.getElementById('wsSub').textContent = `${_leads.length} לידים`;
    renderList();
  }

  function renderList() {
    const q  = (document.getElementById('wsSearch')?.value || '').toLowerCase();
    let list = _leads;

    if (_filter !== 'all') list = list.filter(l => l.status === _filter);
    if (q) list = list.filter(l =>
      (l.name||'').toLowerCase().includes(q) ||
      (l.company||'').toLowerCase().includes(q) ||
      (l.phone||'').includes(q)
    );

    list = [...list].sort((a,b) => (STATUS_W[b.status]||0) - (STATUS_W[a.status]||0) || (b.score||0) - (a.score||0));

    const el = document.getElementById('wsLeadList');
    if (!list.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔍</div><div class="empty-state-msg">לא נמצאו לידים</div></div>';
      return;
    }

    el.innerHTML = list.map(l => {
      const pillCls  = PILL_CLS[l.status] || '';
      const isActive = _selected?.id === l.id;
      const score    = l.priority_score || l.score || 0;
      const scoreCls = score >= 70 ? 'score-hot' : score >= 40 ? 'score-warm' : 'score-cold';
      // RED border for missing next_action (Batch 7 enforcement)
      const missingAction = !l.next_action;
      const rowBorder = missingAction
        ? 'border-right:3px solid var(--red);padding-right:6px;'
        : '';
      return `
        <div onclick="WorkspacePanel.selectLead('${l.id}')"
             style="display:flex;align-items:center;gap:10px;padding:10px 8px;border-bottom:1px solid rgba(34,39,49,.4);cursor:pointer;border-radius:5px;transition:.15s;${rowBorder}${isActive?'background:rgba(184,115,51,.06);':''}">
          <div class="hot-av" style="${score>=70?'background:linear-gradient(135deg,var(--red),#c0392b)':''}">${initials(l.name)}</div>
          <div style="flex:1;min-width:0">
            <div style="font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${l.name}</div>
            <div style="font-size:10px;color:var(--muted)">${l.company||l.sector||l.phone||''}</div>
            ${missingAction ? '<div style="font-size:9px;color:var(--red);margin-top:2px">⚠ חסרה פעולה הבאה</div>' : ''}
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:3px;flex-shrink:0">
            <span class="pill ${pillCls}" style="font-size:9px">${l.status||'—'}</span>
            <span class="score ${scoreCls}" style="font-size:10px">${Math.round(score)}</span>
          </div>
        </div>`;
    }).join('');
  }

  async function selectLead(leadId) {
    const lead = _leads.find(l => l.id === leadId);
    if (!lead) return;
    _selected = lead;
    renderList();

    const detail = document.getElementById('wsLeadDetail');
    // Skeleton while loading full record
    detail.innerHTML = `
      <div style="padding:12px 0">
        <div class="skel skel-h20 skel-w80" style="margin-bottom:8px"></div>
        <div class="skel skel-h12 skel-w60"></div>
      </div>
      <div class="skel skel-h12 skel-w80" style="margin:12px 0"></div>
      ${[0,1,2,3].map(()=>'<div class="skel skel-h12 skel-w80" style="margin-bottom:6px"></div>').join('')}`;

    // Fetch full record
    const res = await API.leadFull(leadId);
    const full   = res.success ? res.data : null;
    const record = full?.lead || lead;
    const deals  = full?.open_deals || [];
    const tl     = full?.timeline || [];
    const ai     = full?.ai_summary || {};
    const score  = full?.priority_score ?? (record.score || 0);

    const missingAction = !record.next_action;
    const alertBanner   = missingAction
      ? `<div style="background:rgba(224,82,82,.1);border:1px solid var(--red);border-radius:6px;padding:8px 10px;margin-bottom:12px;font-size:11px;color:var(--red)">⚠ אין פעולה הבאה מוגדרת — הוסף כדי לשמור על קשר</div>`
      : '';

    detail.innerHTML = `
      ${alertBanner}
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
        <div class="hot-av" style="width:38px;height:38px;font-size:15px">${initials(record.name)}</div>
        <div style="flex:1;min-width:0">
          <div style="font-size:15px;font-weight:700">${record.name}</div>
          <div style="font-size:10px;color:var(--muted)">${record.company||record.sector||''}</div>
        </div>
        <span class="pill ${PILL_CLS[record.status]||''}">${record.status||'—'}</span>
      </div>

      <!-- Next action -->
      <div class="ap-block" style="${missingAction?'border:1px solid rgba(224,82,82,.3);':''}">
        <div class="ap-lbl" style="${missingAction?'color:var(--red)':''}">פעולה הבאה</div>
        <div style="font-size:12px;color:var(--text);padding:4px 0">${record.next_action||'<span style="color:var(--red)">לא מוגדרת</span>'}</div>
        ${record.next_action_due ? `<div style="font-size:10px;color:var(--muted)">עד: ${record.next_action_due}</div>` : ''}
      </div>

      <!-- AI Summary -->
      ${ai.what_they_want ? `
      <div class="ap-block">
        <div class="ap-lbl">AI Summary</div>
        <div class="ap-row"><span class="ap-key">רוצה</span><span class="ap-val">${ai.what_they_want||'—'}</span></div>
        <div class="ap-row"><span class="ap-key">סיכון</span><span class="ap-val" style="color:var(--red)">${ai.risk||'—'}</span></div>
        <div class="ap-row"><span class="ap-key">התנגדות</span><span class="ap-val">${ai.objection||'—'}</span></div>
      </div>` : ''}

      <!-- Lead stats -->
      <div class="ap-block">
        <div class="ap-lbl">פרטים</div>
        <div class="ap-row"><span class="ap-key">ציון עדיפות</span><span class="ap-val" style="font-family:var(--mono);color:var(--silver)">${Math.round(score)}</span></div>
        <div class="ap-row"><span class="ap-key">פוטנציאל</span><span class="ap-val" style="color:var(--ils);font-family:var(--mono)">₪${(record.potential_value||0).toLocaleString('he-IL')}</span></div>
        <div class="ap-row"><span class="ap-key">טלפון</span><span class="ap-val" dir="ltr">${record.phone||'—'}</span></div>
        <div class="ap-row"><span class="ap-key">מקור</span><span class="ap-val">${record.source||'—'}</span></div>
      </div>

      <!-- Open deals -->
      ${deals.length ? `
      <div class="ap-block">
        <div class="ap-lbl">עסקאות פתוחות (${deals.length})</div>
        ${deals.map(d=>`
        <div class="ap-row" onclick="App.switchTo('crm')" style="cursor:pointer">
          <span class="ap-key">${d.title||'—'}</span>
          <span class="ap-val" style="font-family:var(--mono);color:var(--ils)">₪${(d.value_ils||0).toLocaleString()}</span>
        </div>`).join('')}
      </div>` : ''}

      <!-- Timeline -->
      <div class="ap-block">
        <div class="ap-lbl">ציר פעילות</div>
        <div id="wsTimeline">
          ${tl.length ? tl.slice(0,6).map(ev=>`
          <div style="display:flex;gap:8px;padding:6px 0;border-bottom:1px solid rgba(34,39,49,.3)">
            <span style="font-size:14px;flex-shrink:0">${ev.icon||'●'}</span>
            <div>
              <div style="font-size:11px;font-weight:500">${ev.title||'—'}</div>
              <div style="font-size:9px;color:var(--muted)">${ev.body||''} ${ev.ts?'· '+ev.ts.slice(0,10):''}</div>
            </div>
          </div>`).join('')
          : '<div style="font-size:11px;color:var(--muted)">אין פעילות רשומה</div>'}
        </div>
      </div>

      <div class="ap-btn-col">
        <button class="ap-btn ap-primary" onclick="WorkspacePanel.openBriefing('${record.id}')">📞 פתח briefing</button>
        <button class="ap-btn" onclick="WorkspacePanel.logCallPrompt('${record.id}')">📝 רשום שיחה</button>
        <button class="ap-btn" onclick="App.switchTo('crm')">📋 עסקאות</button>
      </div>

      <!-- Quick log activity -->
      <div id="wsLogForm" style="display:none;margin-top:12px">
        <select class="form-select" id="wsOutcome" style="width:100%;margin-bottom:7px">
          <option value="interested">מעוניין</option>
          <option value="not_interested">לא מעוניין</option>
          <option value="follow_up">המשך טיפול</option>
          <option value="left_message">השארתי הודעה</option>
        </select>
        <textarea class="form-input" id="wsNotes" placeholder="הערות..." style="height:60px;resize:none;width:100%;margin-bottom:7px"></textarea>
        <button class="ap-btn ap-primary" id="wsLogSubmit">💾 שמור שיחה</button>
      </div>
    `;

    loadTimeline(leadId);
    document.getElementById('wsLogSubmit')?.addEventListener('click', () => logCall(leadId));
  }

  async function loadTimeline(leadId) {
    const res = await API.timeline(leadId, 5);
    const el  = document.getElementById('wsTimeline');
    if (!el) return;
    const events = res.success ? (res.data?.events || []) : [];
    el.innerHTML = events.length
      ? events.map(ev=>`
          <div class="tl-item" style="padding:5px 0">
            <div class="tl-icon" style="width:22px;height:22px;font-size:10px">${EV_ICON[ev.event_type]||'●'}</div>
            <div class="tl-body">
              <div class="tl-title" style="font-size:11px">${ev.title||ev.description||ev.event_type||'פעילות'}</div>
              <div class="tl-meta" style="font-size:9px">${relTime(ev.occurred_at)}</div>
            </div>
          </div>`).join('')
      : '<div style="font-size:10px;color:var(--muted)">אין פעילות רשומה</div>';
  }

  function openBriefing(leadId) {
    App.switchTo('briefing');
    // Pass lead ID to briefing panel after render
    setTimeout(() => {
      if (typeof BriefingPanel !== 'undefined') {
        BriefingPanel.prefillLead(leadId);
      }
    }, 200);
  }

  function logCallPrompt(leadId) {
    const f = document.getElementById('wsLogForm');
    if (f) f.style.display = f.style.display==='none'?'block':'none';
  }

  async function logCall(leadId) {
    const outcome = document.getElementById('wsOutcome')?.value;
    const notes   = document.getElementById('wsNotes')?.value;
    const res = await API.logActivity(leadId, {
      activity_type: 'call',
      direction:     'outbound',
      outcome,
      notes,
    });
    if (res.success) {
      document.getElementById('wsLogForm').style.display = 'none';
      document.getElementById('wsNotes').value = '';
      await loadTimeline(leadId);
    }
  }

  return { render, init, selectLead, openBriefing, logCallPrompt };
})();
