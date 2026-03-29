/**
 * calendar.js — Calendar View (Batch 11)
 * Weekly Revenue Calendar: events + deals due + revenue at risk per day
 */
const CalendarPanel = (() => {

  const DAY_HE = { 0:'ראשון', 1:'שני', 2:'שלישי', 3:'רביעי', 4:'חמישי', 5:'שישי', 6:'שבת' };
  const todayStr = new Date().toISOString().slice(0,10);

  const ils = n => UI.ils(n);

  function render() {
    return `
      <div class="ws-split">

        <!-- LEFT: Calendar main -->
        <div class="ws-main" style="padding:22px">

          <!-- Header -->
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
            <div>
              <div class="section-title">יומן שבועי</div>
              <div class="section-sub" id="calWeekLabel">טוען...</div>
            </div>
            <div style="display:flex;gap:10px;align-items:center">
              <div style="text-align:left">
                <div style="font-family:var(--mono);font-size:13px;font-weight:600;color:var(--ils)" id="calPipeTotal">—</div>
                <div style="font-size:9px;color:var(--muted)">Pipeline בסיכון השבוע</div>
              </div>
              <button class="btn btn-ghost" id="calRefresh" style="font-size:12px">↻</button>
            </div>
          </div>

          <!-- Week grid -->
          <div class="week-grid" id="weekGrid">
            ${Array(7).fill(`<div class="day-col"><span class="skel skel-h12 skel-w60" style="display:block;margin-bottom:6px"></span><span class="skel skel-h20" style="display:block"></span></div>`).join('')}
          </div>

          <!-- Create event form -->
          <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:14px">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
              <div class="cell-title" style="margin-bottom:0">+ צור אירוע</div>
              <button class="btn btn-ghost" id="calToggleForm" style="font-size:11px">הצג ▾</button>
            </div>
            <div id="calForm" style="display:none">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">
                <div>
                  <div class="form-label">כותרת האירוע</div>
                  <input class="form-input" id="evTitle" placeholder="פגישה עם לקוח..." />
                </div>
                <div>
                  <div class="form-label">מזהה ליד (lead_id)</div>
                  <input class="form-input" id="evLeadId" placeholder="uuid..." />
                </div>
                <div>
                  <div class="form-label">תאריך ושעה</div>
                  <input class="form-input" id="evStartsAt" type="datetime-local" />
                </div>
                <div>
                  <div class="form-label">סוג אירוע</div>
                  <select class="form-select" id="evType">
                    <option value="meeting">פגישה</option>
                    <option value="call">שיחה</option>
                    <option value="demo">הדגמה</option>
                    <option value="site_visit">ביקור אתר</option>
                    <option value="other">אחר</option>
                  </select>
                </div>
                <div style="grid-column:1/-1">
                  <div class="form-label">מיקום / הערות</div>
                  <input class="form-input" id="evNotes" placeholder="כתובת, קישור זום..." />
                </div>
              </div>
              <div style="display:flex;gap:8px;align-items:center">
                <button class="btn btn-primary" id="evSubmit">📅 צור אירוע</button>
                <span id="evResult" style="font-size:11px;color:var(--muted)"></span>
              </div>
            </div>
          </div>

        </div>

        <!-- RIGHT: Day detail panel -->
        <div class="ws-right">
          <div class="ws-right-label">פרטי יום</div>

          <div id="dayDetail">
            <div class="no-select" style="padding:40px 0">
              <div style="font-size:24px;margin-bottom:8px">📅</div>
              <div style="font-size:11px;color:var(--muted)">לחץ על יום בלוח</div>
            </div>
          </div>
        </div>

      </div>
    `;
  }

  async function init() {
    await load();
    document.getElementById('calRefresh')?.addEventListener('click', load);
    document.getElementById('calToggleForm')?.addEventListener('click', () => {
      const f = document.getElementById('calForm');
      const b = document.getElementById('calToggleForm');
      const show = f.style.display === 'none';
      f.style.display = show ? 'block' : 'none';
      b.textContent = show ? 'הסתר ▴' : 'הצג ▾';
    });
    document.getElementById('evSubmit')?.addEventListener('click', submitEvent);
  }

  async function load() {
    const res = await API.weeklyCalendar();
    if (!res.success) {
      document.getElementById('weekGrid').innerHTML = `<div style="grid-column:1/-1">${UI.error(res.error||'לא ניתן לטעון יומן')}</div>`;
      return;
    }
    const cal = res.data;
    document.getElementById('calWeekLabel').textContent = `${cal.week_start} — ${cal.week_end}`;
    document.getElementById('calPipeTotal').textContent = ils(cal.total_pipeline||0);

    renderWeekGrid(cal.days || []);
  }

  function renderWeekGrid(days) {
    const grid = document.getElementById('weekGrid');
    grid.innerHTML = days.map(day => {
      const isToday = day.date_str === todayStr;
      const dateNum = day.date_str.slice(8);
      const events  = day.events || [];
      const deals   = day.deals_due || [];
      const rev     = day.revenue_at_risk || 0;

      return `
        <div class="day-col ${isToday?'today-col':''}"
             onclick="CalendarPanel.selectDay(${JSON.stringify(day).replace(/"/g,'&quot;')})"
             style="cursor:pointer">
          <div class="day-head">
            <div class="day-name">${day.weekday||''}</div>
            <div class="day-date">${dateNum}</div>
          </div>
          ${events.slice(0,3).map(ev=>`<div class="ev-chip" title="${ev.title||''}">${(ev.starts_at_il||'').slice(11,16)} ${ev.title||'אירוע'}</div>`).join('')}
          ${deals.slice(0,2).map(d=>`<div class="dl-chip" title="${d.title||''}">💰 ${d.title||'עסקה'}</div>`).join('')}
          ${rev>0?`<div class="day-rev">${ils(rev)}</div>`:''}
          ${events.length>3?`<div style="font-size:8px;color:var(--muted)">+${events.length-3} עוד</div>`:''}
        </div>`;
    }).join('');
  }

  function selectDay(day) {
    const panel  = document.getElementById('dayDetail');
    const events = day.events || [];
    const deals  = day.deals_due || [];

    const dateHe = new Date(day.date_str).toLocaleDateString('he-IL',{weekday:'long',day:'numeric',month:'long'});

    panel.innerHTML = `
      <div style="margin-bottom:14px">
        <div style="font-size:14px;font-weight:700">${dateHe}</div>
        <div style="font-size:10px;color:var(--muted)">${day.date_str}</div>
      </div>

      <div class="ap-block">
        <div class="ap-lbl">אירועים (${events.length})</div>
        ${events.length
          ? events.map(ev=>`
              <div style="padding:7px 0;border-bottom:1px solid rgba(34,39,49,.4)">
                <div style="font-size:12px;font-weight:500">${ev.title||'אירוע'}</div>
                <div style="font-size:10px;color:var(--muted)">${(ev.starts_at_il||'').slice(11,16)} · ${ev.event_type||''}</div>
              </div>`).join('')
          : '<div style="font-size:11px;color:var(--muted)">אין אירועים</div>'}
      </div>

      <div class="ap-block">
        <div class="ap-lbl">עסקאות לסגירה (${deals.length})</div>
        ${deals.length
          ? deals.map(d=>`
              <div style="padding:7px 0;border-bottom:1px solid rgba(34,39,49,.4)">
                <div style="font-size:12px;font-weight:500">${d.title||'עסקה'}</div>
                <div style="font-size:10px;color:var(--muted)">
                  <span style="color:var(--ils)">${ils(d.value_ils||0)}</span>
                  · שווי משוקלל: <span style="color:var(--copper)">${ils(d.weighted_value||0)}</span>
                </div>
              </div>`).join('')
          : '<div style="font-size:11px;color:var(--muted)">אין עסקאות</div>'}
      </div>

      ${day.revenue_at_risk>0?`
        <div class="ap-block">
          <div class="ap-lbl">הכנסה בסיכון</div>
          <div style="font-family:var(--mono);font-size:16px;font-weight:600;color:var(--ils)">${ils(day.revenue_at_risk)}</div>
        </div>`:``}

      <div class="ap-btn-col">
        <button class="ap-btn ap-primary" onclick="
          document.getElementById('evStartsAt').value='${day.date_str}T10:00';
          document.getElementById('calForm').style.display='block';
          document.getElementById('calToggleForm').textContent='הסתר ▴';
        ">+ אירוע ביום זה</button>
      </div>
    `;
  }

  async function submitEvent() {
    const btn = document.getElementById('evSubmit');
    const res = document.getElementById('evResult');
    const title   = document.getElementById('evTitle').value.trim();
    const leadId  = document.getElementById('evLeadId').value.trim();
    const starts  = document.getElementById('evStartsAt').value;
    const etype   = document.getElementById('evType').value;
    const notes   = document.getElementById('evNotes').value.trim();

    if (!title || !leadId || !starts) {
      res.textContent = 'נדרש: כותרת, מזהה ליד, ותאריך';
      res.style.color = 'var(--red)';
      return;
    }
    btn.disabled = true;
    btn.textContent = '...יוצר';
    const r = await API.createCalEvent({
      title, lead_id: leadId, starts_at_il: starts,
      event_type: etype, notes,
    });
    if (r.success) {
      res.textContent = '✅ אירוע נוצר';
      res.style.color = 'var(--green)';
      document.getElementById('evTitle').value = '';
      await load();
    } else {
      res.textContent = r.error || 'שגיאה';
      res.style.color = 'var(--red)';
    }
    btn.disabled = false;
    btn.textContent = '📅 צור אירוע';
  }

  return { render, init, selectDay };
})();
