/**
 * leads.js — Leads Intelligence Panel
 */
const LeadsPanel = (() => {

  // Delegates to shared UI primitives
  const scoreClass  = s => s >= 70 ? 'score-hot' : s >= 40 ? 'score-warm' : 'score-cold';
  const statusPill  = status => UI.leadPill(status);

  function render() {
    return `
      <!-- Widget bar -->
      <div class="panel-widgets" id="lwWidgets">
        <div class="pw-chip">
          <div class="pw-val" id="lwTotal">—</div>
          <div class="pw-label">סה"כ לידים</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-red" id="lwHot">—</div>
          <div class="pw-label">לידים חמים</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-amber" id="lwNew">—</div>
          <div class="pw-label">לידים חדשים</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-green" id="lwWon">—</div>
          <div class="pw-label">סגורים זכה</div>
        </div>
      </div>

      <div class="section-head">
        <div>
          <div class="section-title">לידים / בינה מכירתית</div>
          <div class="section-sub" id="leadCount">טוען...</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <input class="cmd-input" id="leadSearch" placeholder="חיפוש שם, טלפון, עיר..."
                 style="width:200px;font-size:12px;padding:7px 10px" />
          <button class="btn btn-ghost" id="toggleAddLead">+ הוסף ליד</button>
        </div>
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

      <!-- Filter row -->
      <div class="leads-filter" id="leadsFilterRow">
        <button class="filter-pill active" data-f="all">הכל</button>
        <button class="filter-pill" data-f="חם">🔥 חם</button>
        <button class="filter-pill" data-f="בטיפול">בטיפול</button>
        <button class="filter-pill" data-f="חדש">חדש</button>
        <button class="filter-pill" data-f="קר">קר</button>
        <button class="filter-pill" data-f="סגור_זכה">זכה</button>
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
              <th>פעולה הבאה</th>
            </tr>
          </thead>
          <tbody id="leadsBody">
            <tr><td colspan="7" style="text-align:center;color:var(--muted);padding:24px;">
              <span class="spinner"></span> טוען...
            </td></tr>
          </tbody>
        </table>
      </div>
    `;
  }

  let _allLeads = [];
  let _filter   = 'all';

  async function load() {
    const res  = await API.leads({ limit: 300 });
    const cnt  = document.getElementById('leadCount');
    if (!res.success) {
      document.getElementById('leadsBody').innerHTML =
        `<tr><td colspan="7" style="color:var(--red);padding:16px;">שגיאה בטעינת לידים</td></tr>`;
      return;
    }
    _allLeads = res.data.leads || [];
    cnt.textContent = `${_allLeads.length} לידים`;

    // Update widgets
    const hot  = _allLeads.filter(l => l.status === 'חם').length;
    const nw   = _allLeads.filter(l => l.status === 'חדש').length;
    const won  = _allLeads.filter(l => l.status === 'סגור_זכה').length;
    _setText('lwTotal', _allLeads.length);
    _setText('lwHot',   hot);
    _setText('lwNew',   nw);
    _setText('lwWon',   won);

    renderTable();
  }

  function renderTable() {
    const body  = document.getElementById('leadsBody');
    const q     = (document.getElementById('leadSearch')?.value || '').toLowerCase();
    let list    = _allLeads;

    if (_filter !== 'all') list = list.filter(l => l.status === _filter);
    if (q) list = list.filter(l =>
      (l.name  || '').toLowerCase().includes(q) ||
      (l.phone || '').includes(q) ||
      (l.city  || '').toLowerCase().includes(q)
    );

    // Sort by score desc
    list = [...list].sort((a, b) => (b.priority_score || b.score || 0) - (a.priority_score || a.score || 0));

    if (!list.length) {
      body.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:24px;">אין לידים</td></tr>`;
      return;
    }
    body.innerHTML = list.map(l => {
      const score = l.priority_score || l.score || 0;
      const isOverdue = l.next_action_due && new Date(l.next_action_due) < new Date();
      return `
        <tr style="cursor:pointer" onclick="App.switchTo('briefing')">
          <td style="font-weight:600;">${l.name || '—'}</td>
          <td>${l.city || '—'}</td>
          <td><span style="font-family:var(--mono);font-size:11px;direction:ltr;display:inline-block">${l.phone || '—'}</span></td>
          <td>${l.source || '—'}</td>
          <td>${statusPill(l.status)}</td>
          <td><span class="score ${scoreClass(score)}">${Math.round(score) || '—'}</span></td>
          <td style="font-size:11px;color:${isOverdue ? 'var(--red)' : 'var(--muted)'}">
            ${l.next_action
              ? `${l.next_action.slice(0, 30)}${l.next_action.length > 30 ? '…' : ''}`
              : '<span style="color:var(--red);font-size:10px">⚠ חסרה</span>'}
          </td>
        </tr>
      `;
    }).join('');
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

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

    // Filter pills
    document.querySelectorAll('#leadsFilterRow .filter-pill').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#leadsFilterRow .filter-pill').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _filter = btn.dataset.f;
        renderTable();
      });
    });

    // Search
    document.getElementById('leadSearch')?.addEventListener('input', renderTable);

    load();
  }

  return { render, init, reload: () => load() };
})();
