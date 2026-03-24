/**
 * calendar.js — Calendar & Time Layer panel (Batch 10 / Section 8.2)
 * Shows upcoming tasks/meetings and allows quick event creation.
 */
const CalendarPanel = (() => {

  const today = new Date().toISOString().slice(0, 10);

  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">יומן עסקי</div>
          <div class="section-sub" id="calDate">${today}</div>
        </div>
        <button class="btn btn-primary" id="calNewBtn">+ אירוע חדש</button>
      </div>

      <!-- New event form (hidden by default) -->
      <div id="calForm" class="card" style="display:none;margin-bottom:16px">
        <div style="font-weight:600;margin-bottom:12px">יצירת אירוע / פגישה</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div>
            <label style="font-size:12px;color:var(--text-muted)">כותרת</label>
            <input class="modal-input" id="calTitle" placeholder="פגישה עם אדריכל..." style="margin-top:4px" />
          </div>
          <div>
            <label style="font-size:12px;color:var(--text-muted)">שם איש קשר</label>
            <input class="modal-input" id="calContact" placeholder="שם..." style="margin-top:4px" />
          </div>
          <div>
            <label style="font-size:12px;color:var(--text-muted)">תאריך</label>
            <input class="modal-input" id="calDateInput" type="date" value="${today}" style="margin-top:4px" />
          </div>
          <div>
            <label style="font-size:12px;color:var(--text-muted)">שעה</label>
            <input class="modal-input" id="calTime" type="time" value="10:00" style="margin-top:4px" />
          </div>
          <div>
            <label style="font-size:12px;color:var(--text-muted)">משך (דקות)</label>
            <input class="modal-input" id="calDuration" type="number" value="60" style="margin-top:4px" />
          </div>
          <div>
            <label style="font-size:12px;color:var(--text-muted)">טלפון</label>
            <input class="modal-input" id="calPhone" placeholder="050..." style="margin-top:4px" />
          </div>
        </div>
        <textarea class="modal-input" id="calNotes" placeholder="הערות..." style="margin-top:10px;height:60px;resize:vertical"></textarea>
        <div style="display:flex;gap:8px;margin-top:12px">
          <button class="btn btn-primary"   id="calSubmitBtn">📅 צור אירוע</button>
          <button class="btn btn-secondary" id="calCancelBtn">ביטול</button>
        </div>
        <div id="calResult" style="margin-top:10px"></div>
      </div>

      <!-- Upcoming tasks/meetings pulled from system -->
      <div style="font-weight:600;font-size:13px;color:var(--text-muted);margin-bottom:10px">📋 משימות ופגישות קרובות</div>
      <div id="calUpcoming"><div style="color:var(--text-muted);font-size:13px">טוען...</div></div>

      <!-- Follow-up calendar from outreach -->
      <div style="font-weight:600;font-size:13px;color:var(--text-muted);margin:20px 0 10px">🔄 Follow-ups מתוזמנים</div>
      <div id="calFollowups"><div style="color:var(--text-muted);font-size:13px">טוען...</div></div>
    `;
  }

  async function init() {
    await Promise.all([loadUpcoming(), loadFollowups()]);

    document.getElementById('calNewBtn')?.addEventListener('click', () => {
      document.getElementById('calForm').style.display = 'block';
      document.getElementById('calNewBtn').style.display = 'none';
    });
    document.getElementById('calCancelBtn')?.addEventListener('click', () => {
      document.getElementById('calForm').style.display = 'none';
      document.getElementById('calNewBtn').style.display = '';
    });
    document.getElementById('calSubmitBtn')?.addEventListener('click', submitEvent);
  }

  async function loadUpcoming() {
    // Pull pending tasks that represent meetings/follow-ups
    const res = await API.get('/tasks?status=created');
    const tasks = res.success ? (res.data?.tasks || []) : [];
    const meetings = tasks.filter(t =>
      t.action === 'draft_meeting' || t.action === 'set_reminder' || t.type === 'assistant'
    );
    document.getElementById('calUpcoming').innerHTML = meetings.length
      ? meetings.slice(0, 8).map(t => `
          <div style="display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--border)">
            <span style="font-size:18px">📅</span>
            <div style="flex:1">
              <div style="font-size:13px;font-weight:500">${t.action === 'set_reminder' ? '⏰ תזכורת' : '🤝 פגישה'} — ${t.type}</div>
              <div style="font-size:11px;color:var(--text-muted)">${(t.created_at || '').slice(0,16)}</div>
            </div>
            <span class="pill pill-steel" style="font-size:11px">${t.status}</span>
          </div>`).join('')
      : '<div style="color:var(--text-muted);font-size:13px">אין פגישות מתוזמנות</div>';
  }

  async function loadFollowups() {
    const res = await API.get('/outreach/summary');
    const pipeline = res.success ? (res.data?.pipeline || []) : [];
    const withDate = pipeline.filter(p => p.next_followup).sort((a, b) =>
      (a.next_followup || '').localeCompare(b.next_followup || '')
    );
    document.getElementById('calFollowups').innerHTML = withDate.length
      ? withDate.slice(0, 10).map(p => {
          const date = (p.next_followup || '').slice(0, 10);
          const isPast = date < today;
          return `
            <div style="display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--border)">
              <span style="font-size:18px">${isPast ? '⚠️' : '🔄'}</span>
              <div style="flex:1">
                <div style="font-size:13px;font-weight:500">${p.lead_name}</div>
                <div style="font-size:11px;color:var(--text-muted)">ניסיון #${p.attempt} · ${p.status}</div>
              </div>
              <span style="font-size:12px;color:${isPast ? 'var(--danger)' : 'var(--text-muted)'}">${date}</span>
            </div>`;
        }).join('')
      : '<div style="color:var(--text-muted);font-size:13px">אין follow-ups מתוזמנים</div>';
  }

  async function submitEvent() {
    const btn = document.getElementById('calSubmitBtn');
    btn.textContent = '...יוצר';

    const payload = {
      command: `קבע פגישה ${document.getElementById('calTitle').value} עם ${document.getElementById('calContact').value} בתאריך ${document.getElementById('calDateInput').value} בשעה ${document.getElementById('calTime').value}`,
    };
    const res = await API.post('/command', payload);
    const result = document.getElementById('calResult');

    if (res.success && res.data?.data?.deep_link) {
      result.innerHTML = `
        <div style="color:var(--green);margin-bottom:8px">✅ טיוטת אירוע נוצרה</div>
        <a href="${res.data.data.deep_link}" target="_blank" class="btn btn-primary">📅 פתח ב-Google Calendar</a>`;
    } else {
      result.innerHTML = `<div style="color:var(--text-muted);white-space:pre-wrap;font-size:13px">${res.data?.message || res.data?.message || res.message || 'נוצרה בקשה'}</div>`;
    }
    btn.textContent = '📅 צור אירוע';
    await loadFollowups();
  }

  return { render, init };
})();
