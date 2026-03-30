/**
 * briefing.js — Live Client Briefing Panel (Phase 9)
 *
 * Sections:
 *   1. Caller identification + risk signals
 *   2. Customer summary (relationship state, score, key notes)
 *   3. Recent context timeline (load-more)
 *   4. Next best action stack (prioritized)
 *   5. Call session + post-call update
 *   6. Action launch surface (note / WhatsApp deep link / meeting / CRM)
 */
const BriefingPanel = (() => {

  const STAGE_HE = { new:'חדש', qualified:'כשיר', proposal:'הצעה', negotiation:'משא ומתן', won:'זכה', lost:'הפסיד' };
  const EV_ICON  = { message:'💬', whatsapp:'📱', email:'📧', call:'📞', meeting:'🤝', note:'📝', stage_change:'🔄', calendar:'📅' };

  let _identity   = null;
  let _summary    = null;
  let _callId     = null;
  let _callActive = false;
  let _ctxLimit   = 8;

  const ils = n => UI.ils(n);

  function relTime(s) {
    if (!s) return '';
    const diff = Math.floor((Date.now() - new Date(s)) / 60000);
    if (diff < 2)    return 'כעת';
    if (diff < 60)   return `לפני ${diff} דק'`;
    if (diff < 1440) return `לפני ${Math.floor(diff/60)} שע'`;
    return `לפני ${Math.floor(diff/1440)} ימ'`;
  }

  // ── Render ────────────────────────────────────────────────────────────────
  function render() {
    return `
      <div class="briefing-wrap">

        <!-- 1. CALLER IDENTIFICATION -->
        <div class="briefing-hero">
          <div class="cell-title" style="margin-bottom:14px">
            📞 זיהוי מתקשר
            <span class="live-dot"></span>
          </div>
          <div class="bf-phone-row">
            <input class="bf-phone-in" id="bfPhone" type="tel"
                   placeholder="+972501234567" autocomplete="off" />
            <button class="btn btn-primary" id="bfIdentify">זהה</button>
            <button class="btn btn-ghost"   id="bfClear" style="font-size:11px">נקה</button>
          </div>
          <div id="bfCallerCard">
            <div style="text-align:center;color:var(--muted);font-size:12px;padding:8px 0">
              הכנס מספר טלפון ולחץ "זהה"
            </div>
          </div>
          <div id="bfRiskStrip"></div>
        </div>

        <!-- 2. CUSTOMER SUMMARY -->
        <div class="bf-section" id="bfSummarySection" style="display:none">
          <div class="bf-sec-title">פרופיל לקוח <span class="live-indicator"></span></div>
          <div id="bfSummaryContent"></div>
        </div>

        <!-- 3. RECENT CONTEXT TIMELINE -->
        <div class="bf-section" id="bfContextSection" style="display:none">
          <div class="bf-sec-title">📋 היסטוריית קשר אחרונה</div>
          <div class="tl-feed" id="bfContextFeed">
            <div style="color:var(--muted);font-size:12px">טוען...</div>
          </div>
        </div>

        <!-- 4. NEXT BEST ACTION STACK -->
        <div class="bf-section" id="bfNextSection" style="display:none">
          <div class="bf-sec-title">🎯 פעולות הבאות מומלצות</div>
          <div id="bfNextAction"></div>
        </div>

        <!-- 5. CALL SESSION -->
        <div class="bf-section" id="bfCallSection" style="display:none">
          <div class="bf-sec-title">📞 ניהול שיחה</div>
          <div class="call-bar">
            <div class="call-status" id="bfCallStatus">⬤ &nbsp;אין שיחה פעילה</div>
            <button class="btn btn-primary" id="bfStartCall" style="font-size:11px">▶ פתח שיחה</button>
            <button class="btn btn-danger"  id="bfEndCall"   style="font-size:11px;display:none">■ סיים שיחה</button>
          </div>
          <div id="bfPostCall" style="display:none">
            <div class="cell-title" style="margin-bottom:10px">עדכון לאחר שיחה</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
              <div>
                <div class="form-label">תוצאת שיחה</div>
                <select class="form-select" id="bfOutcome">
                  <option value="interested">מעוניין ✅</option>
                  <option value="follow_up">המשך טיפול 🔄</option>
                  <option value="not_interested">לא מעוניין ❌</option>
                  <option value="left_message">השארתי הודעה 📩</option>
                  <option value="no_answer">לא ענה 📵</option>
                </select>
              </div>
              <div>
                <div class="form-label">משך שיחה (שניות)</div>
                <input class="form-input" id="bfDuration" type="number" placeholder="180" />
              </div>
              <div style="grid-column:1/-1">
                <div class="form-label">הערות שיחה</div>
                <textarea class="form-input" id="bfNotes"
                          placeholder="הלקוח מעוניין בחלונות לפרויקט X..."
                          style="height:70px;resize:none;width:100%"></textarea>
              </div>
            </div>
            <div style="display:flex;gap:8px;align-items:center">
              <button class="btn btn-primary" id="bfSaveCall">💾 שמור ועדכן</button>
              <span id="bfSaveResult" style="font-size:11px;color:var(--muted)"></span>
            </div>
          </div>
        </div>

        <!-- 6. ACTION LAUNCH SURFACE -->
        <div class="bf-section" id="bfActionsSection" style="display:none">
          <div class="bf-sec-title">⚡ פעולות מהירות</div>
          <div class="ap-btn-col" id="bfActionButtons"></div>

          <!-- Quick note form -->
          <div id="bfNoteForm" style="display:none;margin-top:10px">
            <textarea class="form-input" id="bfQuickNote"
                      placeholder="הערה מהירה..." style="height:60px;resize:none;width:100%;margin-bottom:6px"></textarea>
            <div style="display:flex;gap:8px">
              <button class="btn btn-primary" style="font-size:11px" onclick="BriefingPanel.submitNote()">שמור הערה</button>
              <button class="btn btn-ghost"   style="font-size:11px" onclick="BriefingPanel.toggleNoteForm(false)">ביטול</button>
              <span id="bfNoteResult" style="font-size:11px;color:var(--muted);align-self:center"></span>
            </div>
          </div>

          <!-- Meeting form -->
          <div id="bfMeetingForm" style="display:none;margin-top:10px">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
              <div>
                <div class="form-label">כותרת פגישה</div>
                <input class="form-input" id="bfMeetTitle" placeholder="פגישה עם לקוח..." />
              </div>
              <div>
                <div class="form-label">תאריך ושעה</div>
                <input class="form-input" id="bfMeetAt" type="datetime-local" />
              </div>
            </div>
            <div style="display:flex;gap:8px">
              <button class="btn btn-primary" style="font-size:11px" onclick="BriefingPanel.submitMeeting()">קבע פגישה</button>
              <button class="btn btn-ghost"   style="font-size:11px" onclick="BriefingPanel.toggleMeetingForm(false)">ביטול</button>
              <span id="bfMeetResult" style="font-size:11px;color:var(--muted);align-self:center"></span>
            </div>
          </div>

          <!-- WhatsApp result -->
          <div id="bfWaResult" style="display:none;margin-top:10px"></div>
        </div>

      </div>
    `;
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  async function init() {
    _identity = null; _summary = null; _callId = null;
    _callActive = false; _ctxLimit = 8;

    document.getElementById('bfIdentify')?.addEventListener('click', identify);
    document.getElementById('bfClear')?.addEventListener('click',    clearAll);
    document.getElementById('bfStartCall')?.addEventListener('click', startCall);
    document.getElementById('bfEndCall')?.addEventListener('click',   endCallFlow);
    document.getElementById('bfSaveCall')?.addEventListener('click',  savePostCall);
    document.getElementById('bfPhone')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') identify();
    });
  }

  // ── Prefill from cross-panel navigation ───────────────────────────────────
  async function prefillLead(leadId) {
    const [summaryRes, contextRes] = await Promise.all([
      API.customerSummary(leadId),
      API.briefingContext(leadId, _ctxLimit),
    ]);
    _identity = { identified: true, lead_id: leadId, name: summaryRes.data?.name || leadId };
    showIdentified(_identity);
    if (summaryRes.success) { _summary = summaryRes.data; showSummary(_summary); }
    if (contextRes.success) showContext(contextRes.data?.events || [], contextRes.data?.total || 0);
    showNextAction(_summary);
    showCallSection();
    showActions(leadId, _summary);
  }

  // ── Identify ──────────────────────────────────────────────────────────────
  async function identify() {
    const phone = document.getElementById('bfPhone')?.value.trim();
    if (!phone) return;
    document.getElementById('bfCallerCard').innerHTML = UI.loading('מזהה...');
    const res = await API.identifyCaller(phone);
    if (!res.success) {
      document.getElementById('bfCallerCard').innerHTML = UI.error(res.error || 'לא ניתן לזהות');
      return;
    }
    _identity = res.data;
    showIdentified(_identity);
    if (_identity.identified) {
      const [summaryRes, contextRes] = await Promise.all([
        API.customerSummary(_identity.lead_id),
        API.briefingContext(_identity.lead_id, _ctxLimit),
      ]);
      if (summaryRes.success) { _summary = summaryRes.data; showSummary(_summary); }
      if (contextRes.success) showContext(contextRes.data?.events || [], contextRes.data?.total || 0);
      showNextAction(_summary);
      showCallSection();
      showActions(_identity.lead_id, _summary);
    }
  }

  // ── Section renderers ─────────────────────────────────────────────────────
  function showIdentified(identity) {
    const el = document.getElementById('bfCallerCard');
    if (!identity.identified) {
      el.innerHTML = `
        <div class="caller-unknown">
          <div style="font-size:28px;margin-bottom:6px">❓</div>
          <div style="font-size:13px;font-weight:600;margin-bottom:3px">לא מזוהה</div>
          <div style="font-size:11px">${identity.phone} — לא נמצא במאגר</div>
          <div style="margin-top:10px">
            <button class="btn btn-ghost" style="font-size:11px" onclick="App.switchTo('leads')">+ צור ליד חדש</button>
          </div>
        </div>`;
      document.getElementById('bfRiskStrip').innerHTML = '';
      return;
    }

    const init2 = (identity.name||'?').trim().split(/\s+/).map(w=>w[0]).join('').slice(0,2).toUpperCase();
    const score = identity.score || identity.priority_score || null;
    const scoreBadge = score !== null
      ? `<span class="score ${score>=70?'score-hot':score>=40?'score-warm':'score-cold'}" style="margin-right:6px">${Math.round(score)}</span>`
      : '';

    el.innerHTML = `
      <div class="caller-card">
        <div class="caller-av">${init2}</div>
        <div class="caller-info">
          <div class="caller-name">${identity.name} ${scoreBadge}</div>
          <div class="caller-sub">
            <span class="pill ${identity.status==='חם'?'pill-red':identity.status==='בטיפול'?'pill-amber':'pill-steel'}">${identity.status||'—'}</span>
            <span style="direction:ltr">${identity.phone||''}</span>
            ${identity.last_contact?`<span>קשר אחרון: ${identity.last_contact}</span>`:''}
          </div>
          <div class="caller-deals">
            ${identity.open_deals>0
              ? `<span class="caller-deal-badge">📋 ${identity.open_deals} עסקאות פתוחות</span>`
              : `<span class="caller-deal-badge" style="color:var(--muted)">אין עסקאות פתוחות</span>`}
          </div>
        </div>
      </div>`;
  }

  function showRiskSignals(identity, summary) {
    const el = document.getElementById('bfRiskStrip');
    if (!el || !identity?.identified) return;
    const chips = [];
    const deals = summary?.open_deals || [];

    // Stale contact
    const lastContact = summary?.last_interaction || identity.last_contact;
    if (lastContact) {
      const days = Math.floor((Date.now() - new Date(lastContact)) / 86400000);
      if (days > 14) chips.push({ icon: '⏰', text: `${days} ימים ללא קשר`, cls: 'insight-warn' });
    }

    // Overdue deal actions
    const overdueDeals = deals.filter(d => d.next_action_due && new Date(d.next_action_due) < new Date());
    if (overdueDeals.length) chips.push({ icon: '⚠', text: `${overdueDeals.length} פעולות עסקה באיחור`, cls: 'insight-alert' });

    // Missing next actions
    const noAction = deals.filter(d => !d.next_action && !['won','lost'].includes(d.stage));
    if (noAction.length) chips.push({ icon: '○', text: `${noAction.length} עסקאות ללא פעולה הבאה`, cls: 'insight-warn' });

    // Hot status
    if (identity.status === 'חם' && !deals.length) chips.push({ icon: '🔥', text: 'ליד חם ללא עסקה פתוחה', cls: 'insight-alert' });

    if (chips.length) el.innerHTML = `<div style="margin-top:8px">${UI.insightStrip(chips)}</div>`;
  }

  function showSummary(s) {
    if (!s) return;
    const sec = document.getElementById('bfSummarySection');
    const con = document.getElementById('bfSummaryContent');
    sec.style.display = 'block';

    const deals = s.open_deals || [];
    const now   = new Date();

    // Show risk signals now that we have full summary
    showRiskSignals(_identity, s);

    con.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
        <div class="ap-row"><span class="ap-key">סטטוס</span>
          <span class="ap-val">${UI.leadPill(s.status || '')}</span></div>
        <div class="ap-row"><span class="ap-key">הודעות אחרונות</span>
          <span class="ap-val">${s.recent_messages||0}</span></div>
        <div class="ap-row"><span class="ap-key">קשר אחרון</span>
          <span class="ap-val">${s.last_interaction||'—'}</span></div>
        <div class="ap-row"><span class="ap-key">עסקאות פתוחות</span>
          <span class="ap-val">${deals.length}</span></div>
        ${s.sector ? `<div class="ap-row"><span class="ap-key">סקטור</span><span class="ap-val">${s.sector}</span></div>` : ''}
      </div>

      ${s.key_notes ? `
        <div style="background:rgba(184,115,51,.06);border:1px solid rgba(184,115,51,.15);
                    border-radius:4px;padding:8px;font-size:11px;line-height:1.6;margin-bottom:10px">
          📝 ${s.key_notes}
        </div>` : ''}

      ${deals.length ? `
        <div class="ap-lbl" style="margin-bottom:6px">עסקאות פעילות</div>
        ${deals.map(d => {
          const closeStr  = d.expected_close_date?.slice(0,10);
          const daysLeft  = closeStr ? Math.ceil((new Date(closeStr) - now) / 86400000) : null;
          const closeCls  = daysLeft !== null && daysLeft < 0 ? 'color:var(--red)' : daysLeft !== null && daysLeft < 7 ? 'color:var(--amber)' : 'color:var(--muted)';
          const closeNote = daysLeft !== null ? (daysLeft < 0 ? ` ⚠ ${Math.abs(daysLeft)}י' עבר` : ` · ${daysLeft}י'`) : '';
          const naOk      = d.next_action ? '✓' : '⚠';
          const naCls     = d.next_action ? 'color:var(--green)' : 'color:var(--red)';
          return `
            <div style="padding:7px 0;border-bottom:1px solid rgba(34,39,49,.4)">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
                <span style="font-size:11px;font-weight:600;flex:1">${d.title||'עסקה'}</span>
                <span style="font-family:var(--mono);font-size:10px;color:var(--ils)">${ils(d.value_ils)}</span>
                <span class="pill pill-steel" style="font-size:9px">${STAGE_HE[d.stage]||d.stage}</span>
              </div>
              <div style="display:flex;gap:12px;font-size:10px">
                ${closeStr ? `<span style="${closeCls};font-family:var(--mono)">${closeStr}${closeNote}</span>` : ''}
                <span style="${naCls}">${naOk} ${d.next_action ? d.next_action.slice(0,35) : 'פעולה הבאה חסרה'}</span>
              </div>
            </div>`;
        }).join('')}` : ''}
    `;
  }

  function showContext(events, total = 0) {
    const sec = document.getElementById('bfContextSection');
    const el  = document.getElementById('bfContextFeed');
    sec.style.display = 'block';
    const hasMore = total > events.length || events.length === _ctxLimit;
    el.innerHTML = events.length
      ? events.map(ev => `
          <div class="tl-item">
            <div class="tl-icon">${EV_ICON[ev.event_type]||'●'}</div>
            <div class="tl-body">
              <div class="tl-title">${ev.title||ev.description||ev.event_type||'פעילות'}</div>
              <div class="tl-meta">${ev.channel||ev.direction||''} ${ev.body?'· '+ev.body.slice(0,60):''}</div>
            </div>
            <span class="tl-when">${relTime(ev.occurred_at)}</span>
          </div>`).join('')
        + (hasMore ? `<div style="text-align:center;padding:8px 0">
            <button class="btn btn-ghost" style="font-size:11px"
                    onclick="BriefingPanel.loadMoreContext()">טען עוד ↓ (${events.length}/${total||'?'})</button>
          </div>` : '')
      : '<div style="color:var(--muted);font-size:11px;padding:8px 0">אין היסטוריית קשר</div>';
  }

  async function loadMoreContext() {
    if (!_identity?.lead_id) return;
    _ctxLimit += 10;
    const res = await API.briefingContext(_identity.lead_id, _ctxLimit);
    if (res.success) showContext(res.data?.events || [], res.data?.total || 0);
  }

  function showNextAction(summary) {
    const sec = document.getElementById('bfNextSection');
    const el  = document.getElementById('bfNextAction');
    sec.style.display = 'block';

    const stack = _buildActionStack(summary);
    el.innerHTML = stack.map((a, i) => {
      const borderCls = a.cls === 'alert' ? 'rgba(239,68,68,.4)'
                      : a.cls === 'warn'  ? 'rgba(245,158,11,.3)'
                      : 'rgba(59,130,246,.4)';
      return `
        <div class="next-action-box" style="margin-bottom:${i<stack.length-1?'8px':'0'};
             border-left-color:${borderCls}">
          <span style="margin-left:6px;font-size:13px">${a.icon}</span>${a.text}
        </div>`;
    }).join('');
  }

  function _buildActionStack(summary) {
    const actions = [];
    const deals   = summary?.open_deals || [];
    const now     = new Date();

    const overdueDeals = deals.filter(d => d.next_action_due && new Date(d.next_action_due) < now);
    overdueDeals.forEach(d => {
      actions.push({ icon: '⚠', text: `פעולה באיחור: "${d.next_action||'עדכן'}" — ${d.title}`, cls: 'alert' });
    });

    const closingDeal = deals.find(d => d.stage === 'negotiation');
    if (closingDeal) actions.push({ icon: '🎯', text: `לחץ לסגירה: "${closingDeal.title}" — ${ils(closingDeal.value_ils)}`, cls: 'primary' });

    if (summary?.status === 'חם' && !deals.length) actions.push({ icon: '🔥', text: 'ליד חם — הצג הצעת מחיר ופתח עסקה', cls: 'primary' });

    const noAction = deals.filter(d => !d.next_action && !['won','lost'].includes(d.stage));
    noAction.forEach(d => {
      actions.push({ icon: '○', text: `הגדר פעולה הבאה לעסקה "${d.title}"`, cls: 'warn' });
    });

    const activeDeal = deals.find(d => d.next_action && !['won','lost'].includes(d.stage));
    if (activeDeal && !closingDeal) actions.push({ icon: '📋', text: `${activeDeal.next_action.slice(0,60)} — "${activeDeal.title}"`, cls: 'normal' });

    if (!actions.length && summary) {
      actions.push({ icon: '📞', text: 'בדוק צרכי לקוח, עדכן סטטוס ותכנן פעולה הבאה', cls: 'normal' });
    } else if (!actions.length) {
      actions.push({ icon: '📋', text: 'זהה לקוח לקבלת המלצות', cls: 'normal' });
    }

    return actions;
  }

  function showCallSection() {
    document.getElementById('bfCallSection').style.display = 'block';
  }

  function showActions(leadId, summary) {
    const sec  = document.getElementById('bfActionsSection');
    const btns = document.getElementById('bfActionButtons');
    sec.style.display = 'block';

    const phone = _identity?.phone || summary?.phone || '';
    btns.innerHTML = `
      <button class="ap-btn" onclick="BriefingPanel.toggleNoteForm(true)">
        📝 רשום הערה מהירה
      </button>
      <button class="ap-btn" onclick="BriefingPanel.toggleMeetingForm(true)">
        📅 קבע פגישה
      </button>
      ${phone ? `<button class="ap-btn" onclick="BriefingPanel.sendWhatsApp()">
        📱 שלח WhatsApp
      </button>` : ''}
      <button class="ap-btn" onclick="CrmPanel ? CrmPanel.openBriefing && (App.switchTo('crm')) : App.switchTo('crm')">
        💰 פתח עסקאות ב-CRM
      </button>
    `;
  }

  // ── Action handlers ───────────────────────────────────────────────────────
  function toggleNoteForm(show) {
    document.getElementById('bfNoteForm').style.display    = show ? 'block' : 'none';
    document.getElementById('bfMeetingForm').style.display = 'none';
    if (show) document.getElementById('bfQuickNote')?.focus();
  }

  function toggleMeetingForm(show) {
    document.getElementById('bfMeetingForm').style.display = show ? 'block' : 'none';
    document.getElementById('bfNoteForm').style.display    = 'none';
  }

  async function submitNote() {
    if (!_identity?.lead_id) return;
    const text   = document.getElementById('bfQuickNote')?.value.trim();
    const result = document.getElementById('bfNoteResult');
    if (!text) { result.textContent = 'הערה ריקה'; return; }
    const res = await API.logActivity(_identity.lead_id, {
      activity_type: 'note', direction: 'outbound', notes: text,
    });
    if (res.success) {
      result.textContent    = '✅ הערה נשמרה';
      result.style.color    = 'var(--green)';
      document.getElementById('bfQuickNote').value = '';
      toggleNoteForm(false);
      const ctxRes = await API.briefingContext(_identity.lead_id, _ctxLimit);
      if (ctxRes.success) showContext(ctxRes.data?.events || [], ctxRes.data?.total || 0);
    } else {
      result.textContent = res.error || 'שגיאה';
      result.style.color = 'var(--red)';
    }
  }

  async function submitMeeting() {
    if (!_identity?.lead_id) return;
    const title   = document.getElementById('bfMeetTitle')?.value.trim();
    const startsAt = document.getElementById('bfMeetAt')?.value;
    const result  = document.getElementById('bfMeetResult');
    if (!title || !startsAt) { result.textContent = 'כותרת ותאריך חובה'; return; }
    const res = await API.createCalEvent({
      title, lead_id: _identity.lead_id,
      starts_at_il: startsAt, event_type: 'meeting',
    });
    if (res.success) {
      result.textContent = '✅ פגישה נקבעה';
      result.style.color = 'var(--green)';
      document.getElementById('bfMeetTitle').value = '';
      toggleMeetingForm(false);
    } else {
      result.textContent = res.error || 'שגיאה';
      result.style.color = 'var(--red)';
    }
  }

  async function sendWhatsApp() {
    if (!_identity?.lead_id) return;
    const phone = _identity.phone || '';
    const name  = _identity.name  || '';
    if (!phone) { Toast.error('אין מספר טלפון ללקוח זה'); return; }

    const waEl  = document.getElementById('bfWaResult');
    waEl.style.display = 'block';
    waEl.innerHTML = UI.loading('מכין קישור...');

    const res = await API.sendToLead({ name, phone, message: `שלום ${name},`, lead_id: _identity.lead_id });
    if (res.success && res.data?.deep_link) {
      waEl.innerHTML = `
        <a href="${res.data.deep_link}" target="_blank"
           class="btn btn-primary" style="font-size:11px;text-decoration:none;display:inline-block">
          📱 פתח WhatsApp ושלח הודעה
        </a>
        <div style="font-size:9px;color:var(--muted);margin-top:4px">הקישור נפתח באפליקציית WhatsApp</div>
      `;
    } else {
      waEl.innerHTML = `<span style="font-size:11px;color:var(--red)">${res.error || 'לא ניתן להכין קישור WhatsApp'}</span>`;
    }
  }

  // ── Call session ──────────────────────────────────────────────────────────
  async function startCall() {
    if (!_identity?.lead_id) return;
    const res = await API.startCall(_identity.lead_id);
    if (!res.success) { Toast.error('שגיאה בפתיחת שיחה'); return; }
    _callId     = res.data.call_id;
    _callActive = true;
    document.getElementById('bfCallStatus').className = 'call-status cs-active';
    document.getElementById('bfCallStatus').innerHTML = `<span class="call-dot"></span> שיחה פעילה · ${_callId.slice(0,8)}`;
    document.getElementById('bfStartCall').style.display = 'none';
    document.getElementById('bfEndCall').style.display   = '';
    document.getElementById('bfPostCall').style.display  = 'block';
  }

  function endCallFlow() {
    _callActive = false;
    document.getElementById('bfCallStatus').className   = 'call-status';
    document.getElementById('bfCallStatus').innerHTML   = '⬤ &nbsp;שיחה הסתיימה — מלא עדכון';
    document.getElementById('bfEndCall').style.display  = 'none';
    document.getElementById('bfStartCall').style.display = '';
    document.getElementById('bfPostCall').style.display  = 'block';
    document.getElementById('bfNotes')?.focus();
  }

  async function savePostCall() {
    if (!_callId && !_identity?.lead_id) return;
    const btn     = document.getElementById('bfSaveCall');
    const result  = document.getElementById('bfSaveResult');
    const outcome = document.getElementById('bfOutcome')?.value  || 'follow_up';
    const notes   = document.getElementById('bfNotes')?.value    || '';
    const dur     = parseInt(document.getElementById('bfDuration')?.value || '0', 10);

    btn.disabled = true; btn.textContent = '...שומר';
    let res;
    if (_callId) {
      res = await API.endCall(_callId, notes, outcome, dur, 'operator', _identity?.lead_id || '');
    } else {
      res = await API.logActivity(_identity.lead_id, {
        activity_type: 'call', direction: 'outbound', outcome, notes, duration_sec: dur,
      });
    }
    if (res.success) {
      result.textContent = '✅ עסקה עודכנה בהצלחה';
      result.style.color  = 'var(--green)';
      document.getElementById('bfNotes').value    = '';
      document.getElementById('bfDuration').value = '';
      _callId = null; _callActive = false;
      const ctxRes = await API.briefingContext(_identity.lead_id, _ctxLimit);
      if (ctxRes.success) showContext(ctxRes.data?.events || [], ctxRes.data?.total || 0);
    } else {
      result.textContent = res.error || 'שגיאה בשמירה';
      result.style.color  = 'var(--red)';
    }
    btn.disabled = false; btn.textContent = '💾 שמור ועדכן';
  }

  // ── Clear ─────────────────────────────────────────────────────────────────
  function clearAll() {
    _identity = null; _summary = null; _callId = null;
    _callActive = false; _ctxLimit = 8;
    document.getElementById('bfPhone').value = '';
    document.getElementById('bfCallerCard').innerHTML = `<div style="text-align:center;color:var(--muted);font-size:12px;padding:8px 0">הכנס מספר טלפון ולחץ "זהה"</div>`;
    document.getElementById('bfRiskStrip').innerHTML   = '';
    ['bfSummarySection','bfContextSection','bfNextSection','bfCallSection','bfActionsSection']
      .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
  }

  return { render, init, prefillLead, loadMoreContext,
           toggleNoteForm, toggleMeetingForm, submitNote, submitMeeting, sendWhatsApp };
})();
