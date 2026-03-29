/**
 * briefing.js — Live Client Briefing Panel (Batch 11)
 *
 * Caller identification · Customer summary · Deal context ·
 * Recent WhatsApp/email/call/meeting timeline ·
 * Recommended next action · Call session · Post-call update
 */
const BriefingPanel = (() => {

  const STAGE_HE = { new:'חדש', qualified:'כשיר', proposal:'הצעה', negotiation:'משא ומתן', won:'זכה', lost:'הפסיד' };
  const EV_ICON  = { message:'💬', whatsapp:'📱', email:'📧', call:'📞', meeting:'🤝', note:'📝', stage_change:'🔄', calendar:'📅' };

  let _identity = null;
  let _summary  = null;
  let _callId   = null;
  let _callActive = false;

  const ils     = n => UI.ils(n);
  function relTime(s) {
    if (!s) return '';
    const diff = Math.floor((Date.now() - new Date(s)) / 60000);
    if (diff < 2)    return 'כעת';
    if (diff < 60)   return `לפני ${diff} דק'`;
    if (diff < 1440) return `לפני ${Math.floor(diff/60)} שע'`;
    return `לפני ${Math.floor(diff/1440)} ימ'`;
  }

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
            <button class="btn btn-ghost" id="bfClear" style="font-size:11px">נקה</button>
          </div>

          <!-- Caller card — populated after identification -->
          <div id="bfCallerCard">
            <div style="text-align:center;color:var(--muted);font-size:12px;padding:8px 0">
              הכנס מספר טלפון ולחץ "זהה"
            </div>
          </div>
        </div>

        <!-- 2. CUSTOMER SUMMARY (shown after identification) -->
        <div class="bf-section" id="bfSummarySection" style="display:none">
          <div class="bf-sec-title">
            פרופיל לקוח
            <span class="live-indicator"></span>
          </div>
          <div id="bfSummaryContent">
            <div style="color:var(--muted);font-size:12px">טוען...</div>
          </div>
        </div>

        <!-- 3. RECENT CONTEXT TIMELINE -->
        <div class="bf-section" id="bfContextSection" style="display:none">
          <div class="bf-sec-title">
            📋 היסטוריית קשר אחרונה
          </div>
          <div class="tl-feed" id="bfContextFeed">
            <div style="color:var(--muted);font-size:12px">טוען...</div>
          </div>
        </div>

        <!-- 4. RECOMMENDED NEXT ACTION -->
        <div class="bf-section" id="bfNextSection" style="display:none">
          <div class="bf-sec-title">🎯 פעולה מומלצת הבאה</div>
          <div id="bfNextAction">
            <div class="next-action-box">—</div>
          </div>
        </div>

        <!-- 5. CALL SESSION -->
        <div class="bf-section" id="bfCallSection" style="display:none">
          <div class="bf-sec-title">📞 ניהול שיחה</div>

          <div class="call-bar">
            <div class="call-status" id="bfCallStatus">
              ⬤ &nbsp;אין שיחה פעילה
            </div>
            <button class="btn btn-primary"   id="bfStartCall"  style="font-size:11px">▶ פתח שיחה</button>
            <button class="btn btn-danger"    id="bfEndCall"    style="font-size:11px;display:none">■ סיים שיחה</button>
          </div>

          <!-- Post-call update (hidden until call ends or manual open) -->
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
                <textarea class="form-input" id="bfNotes" placeholder="הלקוח מעוניין בחלונות לפרויקט X..." style="height:70px;resize:none;width:100%"></textarea>
              </div>
            </div>

            <div style="display:flex;gap:8px;align-items:center">
              <button class="btn btn-primary" id="bfSaveCall">💾 שמור ועדכן</button>
              <span id="bfSaveResult" style="font-size:11px;color:var(--muted)"></span>
            </div>
          </div>
        </div>

      </div>
    `;
  }

  async function init() {
    _identity   = null;
    _summary    = null;
    _callId     = null;
    _callActive = false;

    document.getElementById('bfIdentify')?.addEventListener('click', identify);
    document.getElementById('bfClear')?.addEventListener('click',    clearAll);
    document.getElementById('bfStartCall')?.addEventListener('click', startCall);
    document.getElementById('bfEndCall')?.addEventListener('click',   endCallFlow);
    document.getElementById('bfSaveCall')?.addEventListener('click',  savePostCall);

    document.getElementById('bfPhone')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') identify();
    });
  }

  // Allow workspace panel to pre-load a lead
  async function prefillLead(leadId) {
    const [summaryRes, contextRes] = await Promise.all([
      API.customerSummary(leadId),
      API.briefingContext(leadId, 5),
    ]);
    _identity = { identified: true, lead_id: leadId, name: summaryRes.data?.name || leadId };
    showIdentified(_identity);
    if (summaryRes.success) showSummary(summaryRes.data);
    if (contextRes.success) showContext(contextRes.data?.events || []);
    showCallSection(_identity.lead_id);
    showNextAction(summaryRes.data);
  }

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
        API.briefingContext(_identity.lead_id, 5),
      ]);
      if (summaryRes.success) { _summary = summaryRes.data; showSummary(_summary); }
      if (contextRes.success) showContext(contextRes.data?.events || []);
      showNextAction(_summary);
      showCallSection(_identity.lead_id);
    }
  }

  function showIdentified(identity) {
    const el = document.getElementById('bfCallerCard');
    if (!identity.identified) {
      el.innerHTML = `
        <div class="caller-unknown">
          <div style="font-size:28px;margin-bottom:6px">❓</div>
          <div style="font-size:13px;font-weight:600;margin-bottom:3px">לא מזוהה</div>
          <div style="font-size:11px">${identity.phone} — לא נמצא במאגר</div>
          <div style="margin-top:10px">
            <button class="btn btn-ghost" style="font-size:11px" onclick="App.switchTo('workspace')">+ צור ליד חדש</button>
          </div>
        </div>`;
      return;
    }

    const init2 = (identity.name||'?').trim().split(/\s+/).map(w=>w[0]).join('').slice(0,2).toUpperCase();
    el.innerHTML = `
      <div class="caller-card">
        <div class="caller-av">${init2}</div>
        <div class="caller-info">
          <div class="caller-name">${identity.name}</div>
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

  function showSummary(s) {
    if (!s) return;
    const sec = document.getElementById('bfSummarySection');
    const con = document.getElementById('bfSummaryContent');
    sec.style.display = 'block';

    const deals = s.open_deals || [];
    con.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
        <div class="ap-row"><span class="ap-key">סקטור</span><span class="ap-val">${s.sector||'—'}</span></div>
        <div class="ap-row"><span class="ap-key">הודעות</span><span class="ap-val">${s.recent_messages||0}</span></div>
        <div class="ap-row"><span class="ap-key">קשר אחרון</span><span class="ap-val">${s.last_interaction||'—'}</span></div>
        <div class="ap-row"><span class="ap-key">עסקאות פתוחות</span><span class="ap-val">${deals.length}</span></div>
      </div>
      ${s.key_notes?`<div style="background:rgba(184,115,51,.06);border:1px solid rgba(184,115,51,.15);border-radius:4px;padding:8px;font-size:11px;line-height:1.6;margin-bottom:10px">${s.key_notes}</div>`:''}
      ${deals.length?`
        <div class="ap-lbl" style="margin-bottom:6px">עסקאות פעילות</div>
        ${deals.map(d=>`
          <div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid rgba(34,39,49,.4)">
            <div style="flex:1;font-size:11px;font-weight:500">${d.title||'עסקה'}</div>
            <span style="font-family:var(--mono);font-size:10px;color:var(--ils)">${ils(d.value_ils)}</span>
            <span class="pill pill-steel" style="font-size:9px">${STAGE_HE[d.stage]||d.stage}</span>
          </div>`).join('')}`:''}
    `;
  }

  function showContext(events) {
    const sec = document.getElementById('bfContextSection');
    const el  = document.getElementById('bfContextFeed');
    sec.style.display = 'block';
    el.innerHTML = events.length
      ? events.map(ev=>`
          <div class="tl-item">
            <div class="tl-icon">${EV_ICON[ev.event_type]||'●'}</div>
            <div class="tl-body">
              <div class="tl-title">${ev.title||ev.description||ev.event_type||'פעילות'}</div>
              <div class="tl-meta">${ev.channel||ev.direction||''} ${ev.body?'· '+ev.body.slice(0,60):''}</div>
            </div>
            <span class="tl-when">${relTime(ev.occurred_at)}</span>
          </div>`).join('')
      : '<div style="color:var(--muted);font-size:11px;padding:8px 0">אין היסטוריית קשר</div>';
  }

  function showNextAction(summary) {
    const sec = document.getElementById('bfNextSection');
    const el  = document.getElementById('bfNextAction');
    sec.style.display = 'block';

    let action = '';
    if (!summary) { action = 'בדוק פרטי הלקוח ותכנן את השיחה'; }
    else if ((summary.open_deals||[]).length > 0) {
      const topDeal = summary.open_deals[0];
      action = `המשך טיפול בעסקה "${topDeal.title}" (${STAGE_HE[topDeal.stage]||topDeal.stage}) — ${ils(topDeal.value_ils)}. שאל על עדכוני פרויקט ותזמן פגישה.`;
    } else if (summary.status === 'חם') {
      action = 'הליד חם — הצג הצעת מחיר, בדוק תקציב ולוח זמנים, הצע פגישה פיזית.';
    } else {
      action = 'חדש פקר, עדכן צרכים ואם יש עניין — פתח עסקה חדשה.';
    }

    el.innerHTML = `<div class="next-action-box">${action}</div>`;
  }

  function showCallSection(leadId) {
    document.getElementById('bfCallSection').style.display = 'block';
  }

  async function startCall() {
    if (!_identity?.lead_id) return;
    const res = await API.startCall(_identity.lead_id);
    if (!res.success) { alert('שגיאה בפתיחת שיחה'); return; }

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
    document.getElementById('bfCallStatus').className = 'call-status';
    document.getElementById('bfCallStatus').innerHTML = '⬤ &nbsp;שיחה הסתיימה — מלא עדכון';
    document.getElementById('bfEndCall').style.display   = 'none';
    document.getElementById('bfStartCall').style.display = '';
    document.getElementById('bfPostCall').style.display  = 'block';
    document.getElementById('bfNotes')?.focus();
  }

  async function savePostCall() {
    if (!_callId && !_identity?.lead_id) return;
    const btn     = document.getElementById('bfSaveCall');
    const result  = document.getElementById('bfSaveResult');
    const outcome = document.getElementById('bfOutcome')?.value || 'follow_up';
    const notes   = document.getElementById('bfNotes')?.value   || '';
    const dur     = parseInt(document.getElementById('bfDuration')?.value || '0', 10);

    btn.disabled = true;
    btn.textContent = '...שומר';

    let res;
    if (_callId) {
      // Pass lead_id as fallback: if call/start and call/end hit different Gunicorn workers,
      // the server-side session dict won't have the call_id — lead_id allows graceful persist.
      res = await API.endCall(_callId, notes, outcome, dur, 'operator', _identity?.lead_id || '');
    } else {
      // Fallback: log activity directly
      res = await API.logActivity(_identity.lead_id, {
        activity_type: 'call', direction: 'outbound', outcome, notes, duration_sec: dur,
      });
    }

    if (res.success) {
      result.textContent = '✅ עסקה עודכנה בהצלחה';
      result.style.color  = 'var(--green)';
      document.getElementById('bfNotes').value    = '';
      document.getElementById('bfDuration').value = '';
      _callId     = null;
      _callActive = false;
      // Refresh timeline
      if (_identity?.lead_id) {
        const ctxRes = await API.briefingContext(_identity.lead_id, 5);
        if (ctxRes.success) showContext(ctxRes.data?.events || []);
      }
    } else {
      result.textContent = res.error || 'שגיאה בשמירה';
      result.style.color  = 'var(--red)';
    }

    btn.disabled = false;
    btn.textContent = '💾 שמור ועדכן';
  }

  function clearAll() {
    _identity   = null;
    _summary    = null;
    _callId     = null;
    _callActive = false;
    document.getElementById('bfPhone').value = '';
    document.getElementById('bfCallerCard').innerHTML = `<div style="text-align:center;color:var(--muted);font-size:12px;padding:8px 0">הכנס מספר טלפון ולחץ "זהה"</div>`;
    document.getElementById('bfSummarySection').style.display = 'none';
    document.getElementById('bfContextSection').style.display = 'none';
    document.getElementById('bfNextSection').style.display    = 'none';
    document.getElementById('bfCallSection').style.display    = 'none';
  }

  return { render, init, prefillLead };
})();
