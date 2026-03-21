/**
 * leads.js — CRM panel
 */
const LeadsPanel = (() => {

  function scoreClass(s) {
    if (s >= 70) return 'score-hot';
    if (s >= 40) return 'score-warm';
    return 'score-cold';
  }

  function statusPill(status) {
    const map = {
      'חדש': 'pill-steel',
      'מתעניין': 'pill-green',
      'ניסיון קשר': 'pill-amber',
      'סגור_זכה': 'pill-green',
      'סגור_הפסיד': 'pill-red',
    };
    const cls = map[status] || '';
    return `<span class="pill ${cls}">${status || '—'}</span>`;
  }

  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">לידים / CRM</div>
          <div class="section-sub" id="leadCount">טוען...</div>
        </div>
        <button class="btn btn-ghost" id="toggleAddLead">+ הוסף ליד</button>
      </div>

      <div id="addLeadForm" class="cmd-box hidden" style="margin-bottom:16px;">
        <div class="cmd-label">ליד חדש</div>
        <div class="form-grid">
          <div class="form-field">
            <label class="form-label">שם *</label>
            <input class="form-input" id="lfName" placeholder="שם מלא" />
          </div>
          <div class="form-field">
            <label class="form-label">עיר</label>
            <input class="form-input" id="lfCity" placeholder="עיר" />
          </div>
          <div class="form-field">
            <label class="form-label">טלפון</label>
            <input class="form-input" id="lfPhone" placeholder="05X-XXXXXXX" />
          </div>
          <div class="form-field">
            <label class="form-label">מקור</label>
            <select class="form-select" id="lfSource">
              <option value="manual">ידני</option>
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
              <option value="website">אתר</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="referral">המלצה</option>
            </select>
          </div>
        </div>
        <div class="form-field" style="margin-bottom:12px;">
          <label class="form-label">הערות</label>
          <input class="form-input" id="lfNotes" placeholder="הערות אופציונליות" />
        </div>
        <button class="btn btn-primary" id="addLeadBtn">שמור ליד</button>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>שם</th>
              <th>עיר</th>
              <th>טלפון</th>
              <th>מקור</th>
              <th>סטטוס</th>
              <th>ציון</th>
            </tr>
          </thead>
          <tbody id="leadsBody">
            <tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px;">
              <span class="spinner"></span> טוען...
            </td></tr>
          </tbody>
        </table>
      </div>
    `;
  }

  async function load() {
    const res  = await API.leads();
    const body = document.getElementById('leadsBody');
    const cnt  = document.getElementById('leadCount');
    if (!res.success) {
      body.innerHTML = `<tr><td colspan="6" style="color:var(--red);padding:16px;">שגיאה בטעינת לידים</td></tr>`;
      return;
    }
    const leads = res.data.leads || [];
    cnt.textContent = `${leads.length} לידים`;
    if (!leads.length) {
      body.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px;">אין לידים עדיין</td></tr>`;
      return;
    }
    body.innerHTML = leads.map(l => `
      <tr>
        <td style="font-weight:600;">${l.name || '—'}</td>
        <td>${l.city || '—'}</td>
        <td><span style="font-family:var(--mono);font-size:11px;">${l.phone || '—'}</span></td>
        <td>${l.source || '—'}</td>
        <td>${statusPill(l.status)}</td>
        <td><span class="score ${scoreClass(l.score || 0)}">${l.score ?? '—'}</span></td>
      </tr>
    `).join('');
  }

  function init() {
    const toggle = document.getElementById('toggleAddLead');
    const form   = document.getElementById('addLeadForm');
    const addBtn = document.getElementById('addLeadBtn');

    toggle.onclick = () => {
      form.classList.toggle('hidden');
      toggle.textContent = form.classList.contains('hidden') ? '+ הוסף ליד' : '✕ ביטול';
    };

    addBtn.onclick = async () => {
      const name = document.getElementById('lfName').value.trim();
      if (!name) { Toast.error('שם הליד חובה'); return; }
      addBtn.disabled = true;
      const res = await API.createLead({
        name,
        city:   document.getElementById('lfCity').value.trim(),
        phone:  document.getElementById('lfPhone').value.trim(),
        source: document.getElementById('lfSource').value,
        notes:  document.getElementById('lfNotes').value.trim(),
      });
      addBtn.disabled = false;
      if (res.success) {
        Toast.success('ליד נוסף בהצלחה');
        form.classList.add('hidden');
        toggle.textContent = '+ הוסף ליד';
        ['lfName','lfCity','lfPhone','lfNotes'].forEach(id => {
          document.getElementById(id).value = '';
        });
        await load();
      } else {
        Toast.error(res.error || 'שגיאה בהוספת ליד');
      }
    };

    load();
  }

  return { render, init, reload: () => load() };
})();
