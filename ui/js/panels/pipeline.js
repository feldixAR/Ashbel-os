/**
 * pipeline.js — Outreach pipeline panel (Batch 8)
 */
const PipelinePanel = (() => {

  function statusPill(s) {
    const map = { pending: 'pill-steel', sent: 'pill-amber', replied: 'pill-green', closed: 'pill-red' };
    const label = { pending: 'ממתין', sent: 'נשלח', replied: 'ענה', closed: 'נסגר' };
    return `<span class="pill ${map[s] || ''}">${label[s] || s}</span>`;
  }

  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">צנרת — פניות יוצאות</div>
          <div class="section-sub" id="pipelineCount">טוען...</div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-primary" id="sendOutreachBtn">📤 שלח פניות</button>
          <button class="btn btn-secondary" id="followupBtn">🔄 תור Follow-up</button>
        </div>
      </div>
      <div id="pipeInsight" style="margin:8px 0 4px"></div>
      <div id="pipeNextAction" style="margin-bottom:8px"></div>
      <div id="pipelineTable"><div class="empty-state"><span>⏳</span><p>טוען נתונים...</p></div></div>
    `;
  }

  async function init() {
    await loadPipeline();
    document.getElementById('sendOutreachBtn')?.addEventListener('click', sendOutreach);
    document.getElementById('followupBtn')?.addEventListener('click', loadFollowupQueue);
  }

  async function loadPipeline() {
    const res = await API.get('/outreach/pipeline');
    const records = res.success ? (res.data.pipeline || res.data.records || []) : [];
    document.getElementById('pipelineCount').textContent = `${records.length} רשומות`;

    // ── Mission Control: State → Insight → Next Action ──────────────────
    const pending  = records.filter(r => r.status === 'pending').length;
    const sent     = records.filter(r => r.status === 'sent').length;
    const replied  = records.filter(r => r.status === 'replied').length;
    const iChips   = [];
    if (records.length) iChips.push({ icon: '⊳', text: `${records.length} בצנרת`,      cls: ''              });
    if (pending > 0)    iChips.push({ icon: '○', text: `${pending} ממתינות`,             cls: 'insight-warn'  });
    if (sent > 0)       iChips.push({ icon: '✉', text: `${sent} נשלחו`,                 cls: 'insight-good'  });
    if (replied > 0)    iChips.push({ icon: '↩', text: `${replied} ענו`,                cls: 'insight-alert' });
    if (!iChips.length) iChips.push({ icon: '✓', text: 'אין פניות בצנרת',              cls: 'insight-warn'  });
    const iEl = document.getElementById('pipeInsight');
    if (iEl) iEl.innerHTML = UI.insightStrip(iChips);

    const naEl = document.getElementById('pipeNextAction');
    const nextFu = records.filter(r => r.next_followup)
      .sort((a, b) => (a.next_followup || '').localeCompare(b.next_followup || ''))[0];
    if (naEl && nextFu) {
      naEl.innerHTML = UI.nextAction(`follow-up: ${nextFu.contact_name || '—'} — ${(nextFu.next_followup || '').slice(0,10)}`);
    } else if (naEl && pending > 0) {
      naEl.innerHTML = UI.nextAction(`שלח פניות ל-${pending} ליד ממתין`, 'שלח', `document.getElementById('sendOutreachBtn')?.click()`);
    } else if (naEl) { naEl.innerHTML = ''; }
    const tbody = records.length ? records.map(r => `
      <tr>
        <td>${r.contact_name || '—'}</td>
        <td>${r.channel || 'whatsapp'}</td>
        <td>${statusPill(r.status)}</td>
        <td>${r.attempt || 1}</td>
        <td>${(r.sent_at || '').slice(0, 10) || '—'}</td>
        <td>${(r.next_followup || '').slice(0, 10) || '—'}</td>
        <td><a href="${r.deep_link || '#'}" target="_blank" class="btn btn-xs">📱 פתח</a></td>
      </tr>`).join('') : '<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">אין רשומות</td></tr>';
    document.getElementById('pipelineTable').innerHTML = `
      <table class="data-table">
        <thead><tr><th>איש קשר</th><th>ערוץ</th><th>סטטוס</th><th>ניסיון</th><th>נשלח</th><th>follow-up</th><th></th></tr></thead>
        <tbody>${tbody}</tbody>
      </table>`;
  }

  async function sendOutreach() {
    document.getElementById('sendOutreachBtn').textContent = '...שולח';
    const res = await API.post('/command', { command: 'שלח פניות' });
    Toast.show(res.success ? `✅ ${res.data?.message || res.message}` : `❌ ${res.data?.message || res.message || 'שגיאה'}`, res.success ? 'success' : 'error');
    document.getElementById('sendOutreachBtn').textContent = '📤 שלח פניות';
    await loadPipeline();
  }

  async function loadFollowupQueue() {
    const res = await API.post('/command', { command: 'תור follow-up' });
    Toast.show(res.success ? res.data?.message || res.message : '❌ שגיאה', res.success ? 'info' : 'error');
  }

  return { render, init };
})();
