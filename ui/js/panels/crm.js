/**
 * crm.js — Record View: Revenue CRM (Batch 11)
 * Deal list + selected deal detail: stage bar, timeline, update form, stage transition
 */
const CrmPanel = (() => {

  const STAGE_HE = { new:'חדש', qualified:'כשיר', proposal:'הצעה', negotiation:'משא ומתן', won:'זכה', lost:'הפסיד' };
  const STAGES   = ['new','qualified','proposal','negotiation','won','lost'];
  const EV_ICON  = { message:'💬', whatsapp:'📱', email:'📧', call:'📞', meeting:'🤝', note:'📝', stage_change:'🔄', calendar:'📅' };

  let _deals    = [];
  let _selected = null;
  let _detail   = null;

  function ils(n)    { return '₪' + (Number(n)||0).toLocaleString('he-IL'); }
  function pct(p)    { return Math.round((Number(p)||0)*100)+'%'; }
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

        <!-- LEFT: Deals list + timeline -->
        <div class="ws-main" style="padding:20px">

          <div class="section-head">
            <div>
              <div class="section-title">עסקאות CRM</div>
              <div class="section-sub" id="crmSub">טוען...</div>
            </div>
            <div style="display:flex;gap:8px">
              <select class="form-select" id="crmStageFilter" style="font-size:11px;padding:5px 10px">
                <option value="">כל השלבים</option>
                ${STAGES.map(s=>`<option value="${s}">${STAGE_HE[s]}</option>`).join('')}
              </select>
              <button class="btn btn-ghost" id="crmRefresh" style="font-size:12px">↻</button>
              <button class="btn btn-primary" id="crmNewDeal" style="font-size:11px">+ עסקה</button>
            </div>
          </div>

          <!-- Create deal form (hidden) -->
          <div id="crmNewForm" style="display:none;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:14px;margin-bottom:14px">
            <div class="cell-title" style="margin-bottom:12px">עסקה חדשה</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
              <div><div class="form-label">Lead ID</div><input class="form-input" id="nd-leadId" placeholder="uuid..." /></div>
              <div><div class="form-label">כותרת עסקה</div><input class="form-input" id="nd-title" placeholder="חלונות אלומיניום..." /></div>
              <div><div class="form-label">שווי (₪)</div><input class="form-input" id="nd-value" type="number" placeholder="15000" /></div>
              <div><div class="form-label">הסתברות (0-1)</div><input class="form-input" id="nd-prob" type="number" step=".05" placeholder="0.3" /></div>
              <div><div class="form-label">צפי סגירה</div><input class="form-input" id="nd-close" type="date" /></div>
              <div><div class="form-label">מקור</div><input class="form-input" id="nd-source" placeholder="referral, ads..." /></div>
            </div>
            <div style="display:flex;gap:8px">
              <button class="btn btn-primary" id="ndSubmit">שמור עסקה</button>
              <button class="btn btn-ghost" id="ndCancel">ביטול</button>
              <span id="ndResult" style="font-size:11px;color:var(--muted);align-self:center"></span>
            </div>
          </div>

          <!-- Deal list -->
          <div id="crmDealList">
            ${Array(4).fill(`<div class="deal-card"><span class="skel skel-h20 skel-w80" style="display:block;margin-bottom:8px"></span><span class="skel skel-h12 skel-w60" style="display:block"></span></div>`).join('')}
          </div>

          <!-- Deal timeline (below selected deal) -->
          <div id="crmTimeline" style="display:none;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:14px;margin-top:16px">
            <div class="cell-title">ציר זמן מאוחד <span class="live-dot"></span></div>
            <div class="tl-feed" id="crmTlFeed">
              <div style="color:var(--muted);font-size:12px;padding:8px">טוען ציר זמן...</div>
            </div>
          </div>

        </div>

        <!-- RIGHT: Deal detail + actions -->
        <div class="ws-right">
          <div class="ws-right-label">פרטי עסקה</div>
          <div id="crmDealDetail">
            <div class="no-select">
              <div style="font-size:28px;margin-bottom:10px">📋</div>
              <div>בחר עסקה מהרשימה</div>
            </div>
          </div>
        </div>

      </div>
    `;
  }

  async function init() {
    _deals = []; _selected = null; _detail = null;
    await loadDeals();

    document.getElementById('crmRefresh')?.addEventListener('click', loadDeals);
    document.getElementById('crmStageFilter')?.addEventListener('change', () => {
      renderDealList(document.getElementById('crmStageFilter').value);
    });
    document.getElementById('crmNewDeal')?.addEventListener('click', () => {
      const f = document.getElementById('crmNewForm');
      f.style.display = f.style.display==='none' ? 'block' : 'none';
    });
    document.getElementById('ndCancel')?.addEventListener('click', () => {
      document.getElementById('crmNewForm').style.display='none';
    });
    document.getElementById('ndSubmit')?.addEventListener('click', createDeal);
  }

  async function loadDeals() {
    const res = await API.deals();
    _deals = res.success ? (res.data?.deals || []) : [];
    document.getElementById('crmSub').textContent = `${_deals.length} עסקאות`;
    renderDealList('');
  }

  function renderDealList(stageFilter) {
    const list = stageFilter ? _deals.filter(d=>d.stage===stageFilter) : _deals;
    const el   = document.getElementById('crmDealList');

    if (!list.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div><div class="empty-state-msg">אין עסקאות</div></div>';
      return;
    }

    const sortedList = [...list].sort((a,b) => (b.value_ils||0)-(a.value_ils||0));
    el.innerHTML = sortedList.map(d => {
      const isActive = _selected?.id === d.id;
      const stageIdx = STAGES.indexOf(d.stage);
      const stageCls = d.stage==='won'?'pill-green': d.stage==='lost'?'pill-red':'pill-steel';
      return `
        <div class="deal-card ${isActive?'dc-active':''}" onclick="CrmPanel.selectDeal('${d.id}')">
          <div class="deal-title">${d.title}</div>
          <div class="deal-meta">
            <span class="deal-value">${ils(d.value_ils||0)}</span>
            <span class="deal-prob">× ${pct(d.probability)}</span>
            <span class="pill ${stageCls}" style="font-size:9px">${STAGE_HE[d.stage]||d.stage}</span>
            ${d.expected_close_date?`<span style="font-family:var(--mono);font-size:9px;color:var(--muted)">${d.expected_close_date?.slice(0,10)}</span>`:''}
          </div>
        </div>`;
    }).join('');
  }

  async function selectDeal(dealId) {
    const deal = _deals.find(d=>d.id===dealId);
    if (!deal) return;
    _selected = deal;
    renderDealList(document.getElementById('crmStageFilter').value);

    // Load full detail
    const res = await API.deal(dealId);
    _detail = res.success ? res.data : null;
    renderDetail(deal, _detail);

    // Load unified timeline via leadFull (Batch 7)
    document.getElementById('crmTimeline').style.display = 'block';
    if (deal.lead_id) {
      const tlRes = await API.leadFull(deal.lead_id);
      const events = tlRes.success ? (tlRes.data?.timeline || []) : [];
      renderTimeline(events);
    }
  }

  function renderDetail(deal, detail) {
    const history = detail?.stage_history || [];
    const stageIdx = STAGES.indexOf(deal.stage);

    document.getElementById('crmDealDetail').innerHTML = `
      <!-- Stage pipeline bar -->
      <div class="ap-block">
        <div class="ap-lbl">מסלול עסקה</div>
        <div class="stage-pipe">
          ${STAGES.slice(0,4).map((s,i)=>{
            let cls = '';
            if (i < stageIdx) cls = 'sn-done';
            if (s === deal.stage) cls = 'sn-active';
            if (deal.stage==='won') cls = i<4?'sn-done':'sn-won';
            if (deal.stage==='lost') cls = 'sn-lost';
            return `<div class="stage-node ${cls}" title="${STAGE_HE[s]}">${STAGE_HE[s]}</div>${i<3?'<span class="stage-arrow">›</span>':''}`;
          }).join('')}
        </div>
        ${deal.stage==='won'?`<div style="font-family:var(--mono);font-size:11px;color:var(--green);margin-top:4px">✅ זכינו</div>`:''}
        ${deal.stage==='lost'?`<div style="font-family:var(--mono);font-size:11px;color:var(--red);margin-top:4px">❌ הפסדנו</div>`:''}
      </div>

      <!-- Values -->
      <div class="ap-block">
        <div class="ap-lbl">פרטי עסקה</div>
        <div class="ap-row"><span class="ap-key">שווי</span><span class="ap-val" style="color:var(--ils);font-family:var(--mono)">${ils(deal.value_ils)}</span></div>
        <div class="ap-row"><span class="ap-key">הסתברות</span><span class="ap-val">${pct(deal.probability)}</span></div>
        <div class="ap-row"><span class="ap-key">משוקלל</span><span class="ap-val" style="font-family:var(--mono)">${ils((deal.value_ils||0)*(deal.probability||0))}</span></div>
        <div class="ap-row"><span class="ap-key">צפי סגירה</span><span class="ap-val">${deal.expected_close_date?.slice(0,10)||'—'}</span></div>
        <div class="ap-row"><span class="ap-key">פעולה הבאה</span><span class="ap-val">${deal.next_action||'—'}</span></div>
        <div class="ap-row"><span class="ap-key">מקור</span><span class="ap-val">${deal.source||'—'}</span></div>
      </div>

      <!-- Stage transition -->
      ${!['won','lost'].includes(deal.stage)?`
        <div class="ap-block">
          <div class="ap-lbl">מעבר שלב</div>
          <select class="form-select" id="crmToStage" style="width:100%;margin-bottom:6px">
            ${STAGES.filter(s=>s!==deal.stage).map(s=>`<option value="${s}">${STAGE_HE[s]}</option>`).join('')}
          </select>
          <input class="form-input" id="crmReason" placeholder="סיבה / הערה..." style="width:100%;margin-bottom:6px;font-size:12px" />
          <button class="ap-btn ap-primary" onclick="CrmPanel.transition('${deal.id}')">עדכן שלב →</button>
          <span id="crmTransResult" style="font-size:10px;color:var(--muted);display:block;margin-top:4px"></span>
        </div>`:''}

      <!-- Update fields -->
      <div class="ap-block">
        <div class="ap-lbl">עדכון שדות</div>
        <input class="form-input" id="upValue"     value="${deal.value_ils||''}"     placeholder="שווי ₪" style="width:100%;margin-bottom:5px;font-size:12px" type="number" />
        <input class="form-input" id="upProb"      value="${deal.probability||''}"   placeholder="הסתברות 0-1" style="width:100%;margin-bottom:5px;font-size:12px" type="number" step=".05" />
        <input class="form-input" id="upNextAction" value="${deal.next_action||''}" placeholder="פעולה הבאה..." style="width:100%;margin-bottom:5px;font-size:12px" />
        <button class="ap-btn" onclick="CrmPanel.updateFields('${deal.id}')">💾 עדכן</button>
        <span id="crmUpdateResult" style="font-size:10px;color:var(--muted);display:block;margin-top:4px"></span>
      </div>

      <!-- Stage history -->
      ${history.length?`
        <div class="ap-block">
          <div class="ap-lbl">היסטוריית שלבים</div>
          ${history.slice(0,4).map(h=>`
            <div style="font-size:10px;color:var(--muted);padding:4px 0;border-bottom:1px solid rgba(34,39,49,.3)">
              ${STAGE_HE[h.from_stage]||h.from_stage} → ${STAGE_HE[h.to_stage]||h.to_stage}
              <span style="float:left;font-family:var(--mono)">${(h.changed_at_il||'').slice(0,10)}</span>
            </div>`).join('')}
        </div>`:''}
    `;
  }

  function renderTimeline(events) {
    const el = document.getElementById('crmTlFeed');
    if (!el) return;
    el.innerHTML = events.length
      ? events.map(ev=>`
          <div class="tl-item">
            <div class="tl-icon">${ev.icon||EV_ICON[ev.type]||'●'}</div>
            <div class="tl-body">
              <div class="tl-title">${ev.title||ev.type||'פעילות'}</div>
              <div class="tl-meta">${ev.body||''}</div>
            </div>
            <span class="tl-when">${relTime(ev.ts)}</span>
          </div>`).join('')
      : '<div class="empty-state"><div class="empty-state-msg">אין פעילות רשומה</div></div>';
  }

  async function transition(dealId) {
    const stage  = document.getElementById('crmToStage')?.value;
    const reason = document.getElementById('crmReason')?.value || '';
    const res = await API.transitionStage(dealId, stage, reason);
    const el  = document.getElementById('crmTransResult');
    if (res.success) {
      el.textContent = `✅ עבר ל${STAGE_HE[stage]||stage}`;
      el.style.color  = 'var(--green)';
      await loadDeals();
      selectDeal(dealId);
    } else {
      el.textContent = res.error || 'שגיאה';
      el.style.color  = 'var(--red)';
    }
  }

  async function updateFields(dealId) {
    const data = {};
    const v = document.getElementById('upValue')?.value;
    const p = document.getElementById('upProb')?.value;
    const n = document.getElementById('upNextAction')?.value;
    if (v) data.value_ils    = Number(v);
    if (p) data.probability  = Number(p);
    if (n) data.next_action  = n;
    const res = await API.updateDeal(dealId, data);
    const el  = document.getElementById('crmUpdateResult');
    if (res.success) {
      el.textContent = '✅ עודכן';
      el.style.color  = 'var(--green)';
      await loadDeals();
    } else {
      el.textContent = res.error || 'שגיאה';
      el.style.color  = 'var(--red)';
    }
  }

  async function createDeal() {
    const leadId = document.getElementById('nd-leadId')?.value.trim();
    const title  = document.getElementById('nd-title')?.value.trim();
    if (!leadId || !title) {
      document.getElementById('ndResult').textContent = 'חסרים שדות חובה';
      return;
    }
    const res = await API.createDeal({
      lead_id: leadId, title,
      value_ils:           Number(document.getElementById('nd-value')?.value||0),
      probability:         Number(document.getElementById('nd-prob')?.value||0.2),
      expected_close_date: document.getElementById('nd-close')?.value||undefined,
      source:              document.getElementById('nd-source')?.value.trim()||undefined,
    });
    const el = document.getElementById('ndResult');
    if (res.success) {
      el.textContent = '✅ עסקה נוצרה';
      el.style.color  = 'var(--green)';
      document.getElementById('crmNewForm').style.display='none';
      await loadDeals();
    } else {
      el.textContent = res.error || 'שגיאה';
      el.style.color  = 'var(--red)';
    }
  }

  return { render, init, selectDeal, transition, updateFields };
})();
