/**
 * console.js — AshbelOS Main Work Surface
 * Four tab panels: Leads | Approvals | Queue | Growth
 * Renders into #workPane, managed by Shell.switchTab().
 */
const Console = (() => {
  'use strict';

  const _cache = {};         // tab → rendered flag
  let   _pane  = null;

  function _el() {
    if (!_pane) _pane = document.getElementById('workPane');
    return _pane;
  }

  // ── Tab router ────────────────────────────────────────────────────────────
  function render(tabId) {
    const el = _el();
    if (!el) return;
    el.innerHTML = `<div class="work-loading"><div class="wl-spinner"></div></div>`;
    const fn = { leads: _leads, approvals: _approvals, queue: _queue, growth: _growth }[tabId];
    if (fn) fn(el);
  }

  function reload(tabId) {
    delete _cache[tabId];
    if (Shell.currentTab() === tabId) render(tabId);
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  const ils   = n => n ? '₪' + Math.round(n).toLocaleString('he-IL') : '—';
  const esc   = s => (s || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');

  function _scoreCls(s) {
    s = s || 0;
    return s >= 70 ? 'score-hot' : s >= 40 ? 'score-warm' : 'score-cold';
  }

  function _statusPill(status) {
    const map = {
      new:       ['pill-steel',  'חדש'],
      contacted: ['pill-amber',  'ביצירת קשר'],
      hot:       ['pill-green',  'חם 🔥'],
      closed:    ['pill-silver', 'סגור'],
      won:       ['pill-green',  'נסגר ✓'],
      lost:      ['pill-red',    'אבד'],
    };
    const [cls, lbl] = map[status] || ['pill-silver', status || '—'];
    return `<span class="pill ${cls}">${lbl}</span>`;
  }

  function _waPhone(phone) {
    const digits = (phone || '').replace(/\D/g, '');
    return digits.startsWith('0') ? '972' + digits.slice(1) : digits;
  }

  function _section(title, content, actionHtml = '') {
    return `<div class="ws-section">
      <div class="ws-section-hd">
        <span class="ws-section-title">${title}</span>
        ${actionHtml}
      </div>
      ${content}
    </div>`;
  }

  function _empty(msg, cta = '') {
    return `<div class="ws-empty">${msg}${cta ? `<div class="ws-empty-cta">${cta}</div>` : ''}</div>`;
  }

  // ── TAB 1: Leads ─────────────────────────────────────────────────────────
  async function _leads(el) {
    try {
      const res   = await API.leads({ limit: 100 });
      const leads = res.success ? (res.data?.leads || []) : [];

      if (!leads.length) {
        el.innerHTML = _section('לידים',
          _empty('אין לידים במערכת.',
            `<button class="btn btn-primary btn-sm" onclick="UploadModal.open()">📂 יבוא קובץ</button>
             <button class="btn btn-ghost btn-sm" onclick="Shell.switchTab('growth')">🔍 גלה לידים</button>`));
        return;
      }

      // Sort: hot first, then by score
      leads.sort((a, b) => {
        if (a.status === 'hot' && b.status !== 'hot') return -1;
        if (b.status === 'hot' && a.status !== 'hot') return  1;
        return (b.score || b.priority_score || 0) - (a.score || a.priority_score || 0);
      });

      const rows = leads.map(l => {
        const score = Math.round(l.score || l.priority_score || 0);
        const phone = l.phone
          ? `<a href="tel:${esc(l.phone)}" class="lead-phone">${esc(l.phone)}</a>`
          : '<span class="muted">—</span>';
        return `<tr data-status="${esc(l.status || '')}">
          <td><div class="lead-name-cell">
            <div class="lead-name">${esc(l.name || '—')}</div>
            <div class="lead-city muted">${esc(l.city || l.source || '')}</div>
          </div></td>
          <td>${phone}</td>
          <td><span class="score ${_scoreCls(score)}">${score}</span></td>
          <td>${_statusPill(l.status)}</td>
          <td class="muted" style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(l.next_action || '—')}</td>
          <td>
            <div class="lead-actions">
              <button class="btn btn-xs btn-primary"
                onclick="DraftModal && DraftModal.open({id:'${esc(l.id)}',name:'${esc(l.name)}',phone:'${esc(l.phone||'')}',email:'${esc(l.email||'')}',score:${score}},null)"
                title="נסח פנייה">✉</button>
              <button class="btn btn-xs btn-ghost"
                onclick="Console._showLeadMenu('${esc(l.id)}','${esc(l.name)}')"
                title="עוד פעולות">⋮</button>
            </div>
          </td>
        </tr>`;
      }).join('');

      const newCount      = leads.filter(l => l.status === 'new').length;
      const hotCount      = leads.filter(l => l.status === 'hot').length;
      const contactedCount= leads.filter(l => l.status === 'contacted').length;

      el.innerHTML = `
        <div class="leads-stats-row">
          <span class="ls-chip">סה"כ <strong>${leads.length}</strong></span>
          <span class="ls-chip ls-hot">חמים <strong>${hotCount}</strong></span>
          <span class="ls-chip ls-new">חדשים <strong>${newCount}</strong></span>
          <span class="ls-chip">ביצירת קשר <strong>${contactedCount}</strong></span>
          <div style="flex:1"></div>
          <button class="btn btn-xs btn-ghost" onclick="UploadModal.open()">📂 יבוא</button>
        </div>
        <div class="leads-tbl-wrap">
          <table class="leads-tbl">
            <thead><tr>
              <th>שם</th><th>טלפון</th><th>ציון</th><th>סטטוס</th><th>הצעד הבא</th><th>פעולות</th>
            </tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    } catch (e) {
      el.innerHTML = _section('לידים', _empty(`שגיאה: ${e.message || e}`));
    }
  }

  // ── TAB 2: Approvals ─────────────────────────────────────────────────────
  async function _approvals(el) {
    try {
      const res   = await API.approvals();
      const items = res.success ? (res.data?.approvals || []).filter(a => a.status === 'pending') : [];

      if (!items.length) {
        el.innerHTML = _section('אישורים ממתינים', _empty('✓ אין אישורים ממתינים כרגע'));
        return;
      }

      const cards = items.map(a => `
        <div class="appr-card" id="appr-${esc(a.id)}">
          <div class="appr-card-hd">
            <div>
              <div class="appr-action">${esc(a.action || '—')}</div>
              <div class="appr-meta muted">${esc(a.created_at ? a.created_at.slice(0,10) : '')} · סיכון: ${esc(a.risk_level || '—')}</div>
            </div>
            <span class="pill pill-amber">ממתין</span>
          </div>
          ${a.preview ? `<div class="appr-preview">${esc(a.preview).slice(0, 300)}</div>` : ''}
          ${a.body    ? `<div class="appr-preview">${esc(a.body).slice(0, 300)}</div>` : ''}
          <div class="appr-actions">
            <button class="btn btn-primary btn-sm" onclick="Console._approve('${esc(a.id)}')">✓ אשר</button>
            <button class="btn btn-ghost btn-sm"   onclick="Console._deny('${esc(a.id)}')">✗ דחה</button>
          </div>
        </div>`).join('');

      el.innerHTML = `<div class="appr-list">${cards}</div>`;
    } catch (e) {
      el.innerHTML = _section('אישורים', _empty(`שגיאה: ${e.message || e}`));
    }
  }

  async function _approve(id) {
    const card = document.getElementById('appr-' + id);
    if (card) card.style.opacity = '0.5';
    try {
      const res = await API.approve(id, '');
      if (res.success) {
        if (card) card.remove();
        Toast.success('אושר');
        Shell.switchTab('approvals');
        Shell.refreshTodayStrip?.();
      } else {
        Toast.error(res.error || 'שגיאה');
      }
    } catch (e) {
      Toast.error(`שגיאה: ${e.message || e}`);
      if (card) card.style.opacity = '';
    }
  }

  async function _deny(id) {
    const card = document.getElementById('appr-' + id);
    if (card) card.style.opacity = '0.5';
    try {
      const res = await API.deny(id, '');
      if (res.success) {
        if (card) card.remove();
        Toast.success('נדחה');
      } else {
        Toast.error(res.error || 'שגיאה');
        if (card) card.style.opacity = '';
      }
    } catch (e) {
      Toast.error(`שגיאה: ${e.message || e}`);
      if (card) card.style.opacity = '';
    }
  }

  // ── TAB 3: Queue (Manual Send + Follow-up) ────────────────────────────────
  async function _queue(el) {
    try {
      const res   = await API.leads({ limit: 150 });
      const leads = res.success ? (res.data?.leads || []) : [];

      // Manual send queue: ready to contact (score ≥40, status new/hot/contacted)
      const manualQ = leads
        .filter(l => ['new','hot','contacted'].includes(l.status) && (l.score || 0) >= 40)
        .sort((a, b) => (b.score || 0) - (a.score || 0));

      // Follow-up queue: already contacted or hot
      const followupQ = leads
        .filter(l => l.status === 'contacted' || l.status === 'hot')
        .sort((a, b) => (b.score || 0) - (a.score || 0));

      const manualRows = manualQ.length
        ? manualQ.slice(0, 15).map(l => {
            const score = Math.round(l.score || 0);
            const phone = l.phone || l.email || '';
            const ch    = l.phone ? 'WhatsApp' : l.email ? 'Email' : 'ידני';
            const waBtnHtml = l.phone
              ? `<a class="btn btn-xs btn-ghost" href="https://wa.me/${_waPhone(l.phone)}" target="_blank" title="פתח WhatsApp">💬</a>`
              : '';
            return `<div class="q-item">
              <div class="q-item-info">
                <div class="q-name">${esc(l.name || '—')}</div>
                <div class="q-meta muted">${esc(phone)} · ${ch}</div>
              </div>
              <span class="score ${_scoreCls(score)}">${score}</span>
              ${waBtnHtml}
              <button class="btn btn-xs btn-primary"
                onclick="DraftModal && DraftModal.open({id:'${esc(l.id)}',name:'${esc(l.name)}',phone:'${esc(l.phone||'')}',email:'${esc(l.email||'')}',score:${score}},null)"
                title="נסח ושלח">✉</button>
            </div>`;
          }).join('')
        : _empty('תור שליחה ריק — יבוא לידים כדי להתחיל');

      const followupRows = followupQ.length
        ? followupQ.slice(0, 15).map(l => {
            const score   = Math.round(l.score || 0);
            const urgency = l.status === 'hot' ? 'pill-green' : 'pill-amber';
            const urgLbl  = l.status === 'hot' ? '🔥 חם' : 'מעקב';
            const waBtnHtml = l.phone
              ? `<a class="btn btn-xs btn-ghost" href="https://wa.me/${_waPhone(l.phone)}" target="_blank" title="פתח WhatsApp">💬</a>`
              : '';
            return `<div class="q-item">
              <div class="q-item-info">
                <div class="q-name">${esc(l.name || '—')}</div>
                <div class="q-meta muted">${esc(l.phone || l.email || '')} · ${esc(l.city || '')}</div>
              </div>
              <span class="pill ${urgency}">${urgLbl}</span>
              ${waBtnHtml}
              <button class="btn btn-xs btn-primary"
                onclick="DraftModal && DraftModal.open({id:'${esc(l.id)}',name:'${esc(l.name)}',phone:'${esc(l.phone||'')}',email:'${esc(l.email||'')}',score:${score}},'follow_up')"
                title="נסח מעקב">↩</button>
            </div>`;
          }).join('')
        : _empty('אין מעקב פתוח כרגע ✓');

      el.innerHTML = `
        <div class="queue-cols">
          <div class="queue-col">
            <div class="queue-col-hd">
              <span class="queue-col-title">📤 תור שליחה ידנית</span>
              <span class="pill pill-steel">${manualQ.length}</span>
            </div>
            <div class="queue-list">${manualRows}</div>
          </div>
          <div class="queue-col">
            <div class="queue-col-hd">
              <span class="queue-col-title">↩ תור מעקב</span>
              <span class="pill pill-amber">${followupQ.length}</span>
            </div>
            <div class="queue-list">${followupRows}</div>
          </div>
        </div>`;
    } catch (e) {
      el.innerHTML = _section('תור', _empty(`שגיאה: ${e.message || e}`));
    }
  }

  // ── TAB 4: Growth (Marketing + SEO + Discover) ───────────────────────────
  async function _growth(el) {
    el.innerHTML = `<div class="work-loading"><div class="wl-spinner"></div></div>`;
    try {
      const [mktRes, chanRes, seoMetaRes, seoCitiesRes] = await Promise.all([
        API.get('/marketing/weekly').catch(() => ({ success: false })),
        API.get('/channels/status').catch(() => ({ success: false })),
        API.seoMeta().catch(() => ({ success: false })),
        API.seoCities().catch(() => ({ success: false })),
      ]);

      const recs     = mktRes.success ? (mktRes.data?.recommendations || []) : [];
      const drafts   = mktRes.success ? (mktRes.data?.post_drafts || []) : [];
      const channels = chanRes.success ? (chanRes.data?.channels || []) : [];
      const seoMeta  = seoMetaRes.success ? (seoMetaRes.data?.meta_descriptions || seoMetaRes.data || {}) : {};
      const seoCities= seoCitiesRes.success ? (seoCitiesRes.data?.city_pages || seoCitiesRes.data || []) : [];

      // Marketing recommendations
      const recsHtml = recs.length
        ? recs.map(r => `
          <div class="growth-card">
            <div class="gc-meta muted">${esc(r.category || '')} · ${esc(r.channel || '')}</div>
            <div class="gc-title">${esc(r.title || '—')}</div>
            <div class="gc-body muted">${esc(r.body || '')}</div>
            ${r.cta ? `<div class="gc-cta">${esc(r.cta)}</div>` : ''}
          </div>`).join('')
        : _empty('אין המלצות שיווק כרגע');

      // Post drafts
      const draftsHtml = drafts.length
        ? drafts.map(d => `
          <div class="growth-card growth-draft">
            <div class="gc-meta muted">${esc(d.platform || d.channel || 'פוסט')}</div>
            <div class="gc-body">${esc((d.content || d.body || '').slice(0, 200))}</div>
          </div>`).join('')
        : '';

      // Channel readiness
      const chHtml = channels.map(ch => {
        const st  = ch.status || 'unknown';
        const cls = st === 'active' ? 'ch-active' : st === 'readiness' ? 'ch-ready' : 'ch-blocked';
        const lbl = st === 'active' ? 'פעיל' : st === 'readiness' ? 'מוכן לשליחה ידנית' : 'ממתין credentials';
        return `<div class="ch-row"><span class="ch-dot ${cls}"></span><span>${esc(ch.channel || '—')}</span><span class="muted" style="margin-right:auto">${lbl}</span></div>`;
      }).join('') || _empty('לא ניתן לטעון סטטוס ערוצים');

      // Discover form
      const discoverHtml = `
        <div class="growth-discover">
          <div class="gd-label">🔍 גלה לידים חדשים</div>
          <div class="gd-row">
            <input class="gd-input" id="growthDiscoverInput" dir="rtl"
              placeholder="מטרה / סוג לקוח: אדריכלים בתל אביב, קבלנים..." />
            <button class="btn btn-primary" id="growthDiscoverBtn" onclick="Console._discover()">גלה →</button>
          </div>
          <div id="growthDiscoverResult" style="margin-top:8px"></div>
        </div>`;

      // SEO workbench
      const seoMetaHtml = Object.keys(seoMeta).length
        ? Object.entries(seoMeta).slice(0, 6).map(([k, v]) =>
            `<div class="seo-meta-row"><span class="seo-meta-key">${esc(k)}</span>: ${esc(String(v).slice(0, 120))}</div>`
          ).join('')
        : '<div class="muted" style="font-size:11px">META descriptions יוצרו לפי פרופיל העסק</div>';

      const seoCitiesHtml = Array.isArray(seoCities) && seoCities.length
        ? seoCities.slice(0, 6).map(c =>
            `<div class="seo-city-row">
              <span>${esc(c.title || c.h1 || c.city || '—')}</span>
              <span class="muted" style="font-size:10px">${esc(c.slug || '')}</span>
            </div>`
          ).join('')
        : '<div class="muted" style="font-size:11px">דפי ערים יוצרו לפי פרופיל העסק</div>';

      const seoHtml = `
        <div class="seo-block">
          <div class="seo-block-title">🔍 META Descriptions</div>
          ${seoMetaHtml}
        </div>
        <div class="seo-block">
          <div class="seo-block-title">📍 דפי ערים מומלצים</div>
          ${seoCitiesHtml}
        </div>`;

      el.innerHTML = `
        <div class="growth-layout">
          <div class="growth-main">
            <div class="ws-section-title" style="margin-bottom:8px">📣 המלצות שיווק שבועיות</div>
            <div class="growth-recs">${recsHtml}</div>
            ${draftsHtml ? `<div class="ws-section-title" style="margin:16px 0 8px">✏️ טיוטות פוסטים</div><div class="growth-recs">${draftsHtml}</div>` : ''}
            ${discoverHtml}
          </div>
          <div class="growth-side">
            <div class="ws-section-title" style="margin-bottom:8px">📡 ערוצים</div>
            <div class="ch-list">${chHtml}</div>
            <div class="ws-section-title" style="margin:16px 0 8px">🌐 SEO & תוכן</div>
            ${seoHtml}
          </div>
        </div>`;
    } catch (e) {
      el.innerHTML = _section('צמיחה', _empty(`שגיאה: ${e.message || e}`));
    }
  }

  async function _discover() {
    const input = document.getElementById('growthDiscoverInput');
    const btn   = document.getElementById('growthDiscoverBtn');
    const res_el= document.getElementById('growthDiscoverResult');
    if (!input || !res_el) return;
    const goal = input.value.trim();
    if (!goal) return;
    btn.disabled = true;
    btn.textContent = '...';
    res_el.innerHTML = '<div class="ir-loading">מגלה לידים...</div>';
    try {
      const res = await API.post('/lead_ops/discover', { goal, signals: [] });
      if (!res.success) {
        res_el.innerHTML = `<div class="ws-empty">שגיאה: ${esc(res.error || res.message || 'נסה שוב')}</div>`;
        return;
      }
      const queue = res.work_queue || res.data?.work_queue || [];
      res_el.innerHTML = queue.length
        ? `<div class="ir-empty" style="color:var(--green)">✓ נמצאו ${queue.length} לידים — ממתינים לבדיקה</div>`
        : `<div class="ir-empty">לא נמצאו לידים. נסה מטרה אחרת.</div>`;
      if (queue.length) {
        input.value = '';
        setTimeout(() => Shell.switchTab('leads'), 1500);
      }
    } catch (e) {
      res_el.innerHTML = `<div class="ws-empty">שגיאה: ${e.message || e}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = 'גלה →';
    }
  }

  // ── Lead context menu ─────────────────────────────────────────────────────
  function _showLeadMenu(id, name) {
    // Close any existing menu
    document.querySelectorAll('.lead-ctx-menu').forEach(m => m.remove());

    const menu = document.createElement('div');
    menu.className = 'lead-ctx-menu';
    menu.innerHTML = `
      <div class="lead-ctx-item" onclick="Console._setStatus('${esc(id)}','contacted')">📞 סמן: ביצירת קשר</div>
      <div class="lead-ctx-item" onclick="Console._setStatus('${esc(id)}','hot')">🔥 סמן: חם</div>
      <div class="lead-ctx-item" onclick="Console._setStatus('${esc(id)}','closed')">✓ סמן: סגור</div>
    `;
    // Position near the clicked button
    const btn = event?.target?.closest('button');
    if (btn) {
      const rect = btn.getBoundingClientRect();
      menu.style.cssText = `position:fixed;top:${rect.bottom + 4}px;left:${rect.left}px;`;
    }
    document.body.appendChild(menu);
    setTimeout(() => document.addEventListener('click', () => menu.remove(), { once: true }), 50);
  }

  async function _setStatus(id, status) {
    try {
      const res = await API.updateLead(id, { status });
      if (res.success) {
        Toast.success('סטטוס עודכן');
        Console.reload('leads');
        Console.reload('queue');
      } else { Toast.error(res.error || 'שגיאה'); }
    } catch (e) { Toast.error(`שגיאה: ${e.message || e}`); }
  }

  return { render, reload, _approve, _deny, _discover, _showLeadMenu, _setStatus };
})();
