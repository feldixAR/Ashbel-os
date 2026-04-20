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
    const fn = { leads: _leads, approvals: _approvals, queue: _queue, growth: _growth, meetings: _meetings }[tabId];
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
      new:         ['pill-steel',  'חדש'],
      contacted:   ['pill-amber',  'ביצירת קשר'],
      hot:         ['pill-green',  'חם 🔥'],
      closed:      ['pill-silver', 'סגור'],
      closed_won:  ['pill-green',  'נסגר ✓'],
      closed_lost: ['pill-red',    'אבד'],
      won:         ['pill-green',  'נסגר ✓'],
      lost:        ['pill-red',    'אבד'],
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
      const [leadsRes, queueRes] = await Promise.all([
        API.leads({ limit: 100 }),
        API.dailyRevenue().catch(() => ({ success: false })),
      ]);
      const leads = leadsRes.success ? (leadsRes.data?.leads || []) : [];
      const queue = queueRes.success ? (queueRes.data?.queue || queueRes.queue || []) : [];

      if (!leads.length) {
        el.innerHTML = _section('לידים',
          _empty('אין לידים במערכת.',
            `<button class="btn btn-primary btn-sm" onclick="UploadModal.open()">📂 יבוא קובץ</button>
             <button class="btn btn-ghost btn-sm" onclick="Shell.switchTab('growth')">🔍 גלה לידים</button>
             <button class="btn btn-ghost btn-sm" onclick="Console._showAddLeadForm()">+ ליד חדש</button>`));
        return;
      }

      leads.sort((a, b) => {
        if (a.status === 'hot' && b.status !== 'hot') return -1;
        if (b.status === 'hot' && a.status !== 'hot') return  1;
        return (b.score || b.priority_score || 0) - (a.score || a.priority_score || 0);
      });

      const newCount       = leads.filter(l => l.status === 'new').length;
      const hotCount       = leads.filter(l => l.status === 'hot').length;
      const contactedCount = leads.filter(l => l.status === 'contacted').length;

      // Priority action card (from daily revenue queue)
      const top = queue[0];
      const priorityCard = top ? `
        <div class="priority-card" onclick="DraftModal && DraftModal.open({id:'${esc(top.lead_id||top.id||'')}',name:'${esc(top.lead_name||top.name||'')}',phone:'${esc(top.phone||'')}',score:${top.score||0}},null)">
          <div class="pc-badge">⭐ הפעולה שלך עכשיו</div>
          <div class="pc-name">${esc(top.lead_name || top.name || '—')}</div>
          <div class="pc-reason">${esc(top.reason || top.action || 'ליד עם עדיפות גבוהה')}</div>
          <div class="pc-cta">✉ נסח פנייה עכשיו →</div>
        </div>` : '';

      // Table rows (desktop)
      const tableRows = leads.map(l => {
        const score      = Math.round(l.score || l.priority_score || 0);
        const phone      = l.phone
          ? `<a href="tel:${esc(l.phone)}" class="lead-phone">${esc(l.phone)}</a>`
          : '<span class="muted">—</span>';
        const srch = esc((l.name||'') + ' ' + (l.phone||'') + ' ' + (l.city||''));
        return `<tr data-status="${esc(l.status || '')}" data-search="${srch}">
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

      // Lead cards (mobile)
      const cardRows = leads.map(l => {
        const score    = Math.round(l.score || l.priority_score || 0);
        const initials = (l.name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
        const avBg     = l.status === 'hot' ? '#ef4444' : l.status === 'contacted' ? '#d97706' : '#2563eb';
        const srch     = esc((l.name||'') + ' ' + (l.phone||'') + ' ' + (l.city||''));
        return `<div class="lead-card" data-status="${esc(l.status || '')}" data-search="${srch}">
          <div class="lc-main" onclick="Console._showLeadDetail('${esc(l.id)}')">
            <div class="lc-avatar" style="background:${avBg}">${initials}</div>
            <div class="lc-info">
              <div class="lc-name">${esc(l.name || '—')}</div>
              <div class="lc-city">${esc(l.city || l.source || '')}</div>
            </div>
            <div class="lc-right">
              <span class="score ${_scoreCls(score)}">${score}</span>
              ${_statusPill(l.status)}
            </div>
          </div>
          <div class="lc-footer">
            ${l.phone ? `<a class="btn btn-sm btn-ghost lc-phone" href="tel:${esc(l.phone)}">📞 ${esc(l.phone)}</a>` : '<span style="flex:1"></span>'}
            <button class="btn btn-sm btn-primary lc-draft"
              onclick="DraftModal && DraftModal.open({id:'${esc(l.id)}',name:'${esc(l.name)}',phone:'${esc(l.phone||'')}',email:'${esc(l.email||'')}',score:${score}},null)">✉ נסח</button>
            <button class="btn btn-sm btn-ghost"
              onclick="Console._showLeadMenu('${esc(l.id)}','${esc(l.name)}')">⋮</button>
          </div>
        </div>`;
      }).join('');

      el.innerHTML = `
        ${priorityCard}
        <div class="leads-stats-row">
          <span class="ls-chip ls-filter active" data-f="all">סה"כ <strong>${leads.length}</strong></span>
          <span class="ls-chip ls-filter ls-hot" data-f="hot">🔥 <strong>${hotCount}</strong></span>
          <span class="ls-chip ls-filter ls-new" data-f="new">חדשים <strong>${newCount}</strong></span>
          <span class="ls-chip ls-filter" data-f="contacted">קשר <strong>${contactedCount}</strong></span>
          <div style="flex:1"></div>
          <button class="btn btn-xs btn-primary" onclick="Console._showAddLeadForm()">+ ליד</button>
          <button class="btn btn-xs btn-ghost" onclick="UploadModal.open()">📂</button>
        </div>
        <div class="lead-search-wrap">
          <input class="lead-search" id="leadsSearch" placeholder="🔍  חיפוש לפי שם, טלפון, עיר..." dir="rtl"
            oninput="Console._filterLeads(this.value)" />
        </div>
        <div class="leads-tbl-wrap">
          <table class="leads-tbl">
            <thead><tr>
              <th>שם</th><th>טלפון</th><th>ציון</th><th>סטטוס</th><th>הצעד הבא</th><th>פעולות</th>
            </tr></thead>
            <tbody id="leadsTableBody">${tableRows}</tbody>
          </table>
        </div>
        <div class="leads-cards-mobile" id="leadsCardsMobile">${cardRows}</div>`;

      el.querySelectorAll('.ls-filter').forEach(chip => {
        chip.addEventListener('click', () => {
          el.querySelectorAll('.ls-filter').forEach(c => c.classList.remove('active'));
          chip.classList.add('active');
          _filterLeads(document.getElementById('leadsSearch')?.value || '', chip.dataset.f);
        });
      });

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

      const cards = items.map(a => {
        const det   = a.details || {};
        const title = det.lead_name ? `שליחה ל${esc(det.lead_name)}` : esc(a.action || '—');
        const body  = det.draft_body || det.body || a.preview || a.body || '';
        const editBtn = body ? `<button class="btn btn-ghost btn-sm"
          onclick="DraftModal && DraftModal.open({id:'${esc(det.lead_id||'')}',name:'${esc(det.lead_name||'')}',phone:'${esc(det.phone||'')}',channel:'${esc(det.channel||'')}'},'${esc(det.action_type||'first_contact')}')">✏ ערוך</button>` : '';
        return `<div class="appr-card" id="appr-${esc(a.id)}">
          <div class="appr-card-hd">
            <div>
              <div class="appr-action">${title}</div>
              <div class="appr-meta muted">${esc(a.created_at ? a.created_at.slice(0,10) : '')} · ${esc(det.action_type || a.action || '')} · סיכון: ${esc(String(a.risk_level || '—'))}</div>
            </div>
            <span class="pill pill-amber">ממתין</span>
          </div>
          ${body ? `<div class="appr-preview">${esc(body).slice(0, 300)}</div>` : ''}
          <div class="appr-actions">
            <button class="btn btn-primary btn-sm" onclick="Console._approve('${esc(a.id)}')">✓ אשר</button>
            ${editBtn}
            <button class="btn btn-ghost btn-sm"   onclick="Console._deny('${esc(a.id)}')">✗ דחה</button>
          </div>
        </div>`;
      }).join('');

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
              <button class="btn btn-xs btn-ghost"
                onclick="Console._markSent('${esc(l.id)}','${esc(l.name)}')"
                title="סמן כנשלח + קבע מעקב">✓</button>
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
      const seoMeta  = seoMetaRes.success ? (seoMetaRes.data?.meta || seoMetaRes.data?.meta_descriptions || {}) : {};
      const seoCities= seoCitiesRes.success ? (seoCitiesRes.data?.pages || seoCitiesRes.data?.city_pages || []) : [];

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
          <div class="gd-label" style="margin-top:12px">🌐 ניתוח אתר</div>
          <div class="gd-row">
            <input class="gd-input" id="growthWebsiteInput" dir="ltr"
              placeholder="https://example.co.il" />
            <button class="btn btn-ghost" id="growthWebsiteBtn" onclick="Console._analyzeWebsite()">נתח →</button>
          </div>
          <div id="growthWebsiteResult" style="margin-top:8px"></div>
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

  // ── TAB 5: Meetings / Calendar ────────────────────────────────────────────
  async function _meetings(el) {
    el.innerHTML = `<div class="work-loading"><div class="wl-spinner"></div></div>`;
    try {
      const [planRes, weekRes] = await Promise.all([
        API.dailyPlan().catch(() => ({ success: false })),
        API.weeklyCalendar().catch(() => ({ success: false })),
      ]);

      const plan        = planRes.success ? (planRes.data || {}) : {};
      const items       = plan.priority_items || [];
      const todayEvents = plan.todays_events  || [];
      const pipeline    = plan.pipeline_value  || 0;
      const week        = weekRes.success ? (weekRes.data || {}) : {};
      const days        = week.days            || [];

      // Today's priority actions
      const priorityHtml = items.length
        ? items.slice(0, 6).map(it => `
          <div class="meet-item">
            <div class="meet-item-info">
              <div class="meet-name">${esc(it.lead_name || it.title || '—')}</div>
              <div class="meet-meta muted">${esc(it.action || it.reason || '')} ${it.deal_value ? '· ' + ils(it.deal_value) : ''}</div>
            </div>
            <div class="meet-actions">
              <button class="btn btn-xs btn-primary"
                onclick="DraftModal && DraftModal.open({id:'${esc(it.lead_id||'')}',name:'${esc(it.lead_name||it.title||'')}'},'meeting_request')"
                title="בקש פגישה">📅</button>
              <button class="btn btn-xs btn-ghost"
                onclick="Console._logCall('${esc(it.lead_id||'')}','${esc(it.lead_name||it.title||'')}')"
                title="רשום שיחה">📞</button>
            </div>
          </div>`).join('')
        : _empty('אין פריטי עדיפות להיום',
            `<button class="btn btn-ghost btn-sm" onclick="Shell.switchTab('queue')">📤 עבור לתור שליחה</button>`);

      // Today's calendar events
      const eventsHtml = todayEvents.length
        ? todayEvents.map(ev => `
          <div class="meet-event">
            <span class="meet-event-time">${esc(ev.starts_at_il || ev.time || '')}</span>
            <span class="meet-event-title">${esc(ev.title || ev.event_type || '—')}</span>
            ${ev.location ? `<span class="muted meet-event-loc">· ${esc(ev.location)}</span>` : ''}
          </div>`).join('')
        : '<div class="muted" style="font-size:11px;padding:8px 0">אין אירועים מתוכננים להיום</div>';

      // Weekly overview
      const weekHtml = days.filter(d => d.events?.length).slice(0, 5).map(d => `
        <div class="week-day">
          <div class="week-day-label">${esc(d.weekday || d.date || '')}</div>
          <div class="week-day-events">
            ${(d.events || []).map(ev => `<div class="week-event">${esc(ev.title || ev.event_type || '—')}</div>`).join('')}
          </div>
        </div>`).join('') || '<div class="muted" style="font-size:11px">אין אירועים השבוע</div>';

      // Schedule meeting form
      const scheduleHtml = `
        <div class="meet-schedule-form">
          <div class="gd-label">➕ קבע מפגש</div>
          <div class="meet-form-row">
            <input class="gd-input" id="meetLeadId"   placeholder="מזהה ליד" dir="rtl" />
            <input class="gd-input" id="meetTitle"    placeholder="נושא הפגישה" dir="rtl" />
            <input class="gd-input" id="meetDate"     placeholder="תאריך ושעה (2026-04-20 10:00)" dir="ltr" />
            <button class="btn btn-primary btn-sm" onclick="Console._scheduleMeeting()">קבע ✓</button>
          </div>
          <div id="meetScheduleResult" style="margin-top:6px"></div>
        </div>`;

      el.innerHTML = `
        <div class="meetings-layout">
          <div class="meetings-main">
            <div class="ws-section-hd" style="margin-bottom:10px">
              <span class="ws-section-title">📋 עדיפות היום</span>
              ${pipeline ? `<span class="ls-chip ls-hot">צנרת ${ils(pipeline)}</span>` : ''}
            </div>
            <div class="meet-list">${priorityHtml}</div>
            <div class="ws-section-title" style="margin:16px 0 8px">📅 יומן היום</div>
            <div class="meet-events">${eventsHtml}</div>
            ${scheduleHtml}
          </div>
          <div class="meetings-side">
            <div class="ws-section-title" style="margin-bottom:8px">📆 השבוע</div>
            <div class="week-overview">${weekHtml}</div>
          </div>
        </div>`;
    } catch (e) {
      el.innerHTML = _section('מפגשים', _empty(`שגיאה: ${e.message || e}`));
    }
  }

  async function _scheduleMeeting() {
    const leadId  = document.getElementById('meetLeadId')?.value.trim();
    const title   = document.getElementById('meetTitle')?.value.trim();
    const date    = document.getElementById('meetDate')?.value.trim();
    const res_el  = document.getElementById('meetScheduleResult');
    if (!leadId || !title || !date) { if (res_el) res_el.innerHTML = '<span class="muted">נא למלא כל השדות</span>'; return; }
    try {
      const res = await API.createCalEvent({ lead_id: leadId, title, starts_at_il: date, event_type: 'meeting' });
      if (res.success || res.data?.event_id) {
        Toast.success('מפגש נקבע ✓');
        if (res_el) res_el.innerHTML = '<span style="color:var(--green)">✓ נשמר</span>';
        document.getElementById('meetLeadId').value = '';
        document.getElementById('meetTitle').value  = '';
        document.getElementById('meetDate').value   = '';
      } else {
        if (res_el) res_el.innerHTML = `<span style="color:var(--red)">${esc(res.error || 'שגיאה')}</span>`;
      }
    } catch (e) { if (res_el) res_el.innerHTML = `<span style="color:var(--red)">${esc(e.message || String(e))}</span>`; }
  }

  async function _logCall(leadId, leadName) {
    if (!leadId) { Toast.error('חסר מזהה ליד'); return; }
    try {
      await API.logActivity(leadId, { activity_type: 'call', subject: `שיחה עם ${leadName}`, outcome: 'completed', performed_by: 'owner' });
      Toast.success('שיחה נרשמה ✓');
    } catch (e) { Toast.error('שגיאה ברישום שיחה'); }
  }

  async function _analyzeWebsite() {
    const input  = document.getElementById('growthWebsiteInput');
    const btn    = document.getElementById('growthWebsiteBtn');
    const res_el = document.getElementById('growthWebsiteResult');
    if (!input || !res_el) return;
    const url = input.value.trim();
    if (!url) return;
    btn.disabled = true;
    btn.textContent = '...';
    res_el.innerHTML = '<div class="ir-loading">מנתח אתר...</div>';
    try {
      const res = await API.post('/lead_ops/website', { url });
      if (!res.success) {
        res_el.innerHTML = `<div class="ws-empty">שגיאה: ${esc(res.error || 'נסה שוב')}</div>`;
        return;
      }
      const d = res.data || res;
      const plan = d.priority_plan || [];
      const seoRecs = d.seo?.recommendations || d.seo?.issues || [];
      const score = d.audit_score != null ? `ציון: ${d.audit_score}/100` : '';
      const planHtml = Array.isArray(plan) && plan.length
        ? plan.slice(0, 4).map(p => `<div>· ${esc(typeof p === 'string' ? p : p.action || p.title || JSON.stringify(p))}</div>`).join('')
        : (Array.isArray(seoRecs) && seoRecs.length
          ? seoRecs.slice(0, 4).map(r => `<div>· ${esc(typeof r === 'string' ? r : r.recommendation || JSON.stringify(r))}</div>`).join('')
          : '<div>הניתוח הושלם — פרטים מלאים זמינים</div>');
      res_el.innerHTML = `<div class="appr-preview" style="font-size:11px">${score ? `<strong>${esc(score)}</strong><br>` : ''}${planHtml}</div>`;
    } catch (e) {
      res_el.innerHTML = `<div class="ws-empty">שגיאה: ${esc(e.message || String(e))}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = 'נתח →';
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
      <div class="lead-ctx-item" onclick="Console._setStatus('${esc(id)}','closed_won')">✓ סמן: נסגר</div>
      <div class="lead-ctx-item" onclick="Console._setStatus('${esc(id)}','closed_lost')">✗ סמן: אבד</div>
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

  async function _markSent(id, name) {
    try {
      await API.updateLead(id, { status: 'contacted' });
      Toast.success(`${name || 'ליד'} — סומן כנשלח ✓`);
      Console.reload('queue');
      Console.reload('leads');
      // Prompt: schedule follow-up
      if (id) {
        setTimeout(() => {
          if (confirm(`לקבוע מעקב עם ${name || 'הליד'}?`)) {
            Shell.switchTab('meetings');
            setTimeout(() => {
              const el = document.getElementById('meetLeadId');
              if (el) { el.value = id; el.focus(); }
            }, 400);
          }
        }, 300);
      }
    } catch (e) { Toast.error(`שגיאה: ${e.message || e}`); }
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

  // ── Lead search / filter ──────────────────────────────────────────────────
  let _leadsStatusFilter = 'all';

  function _filterLeads(query, statusF) {
    if (statusF !== undefined) _leadsStatusFilter = statusF;
    const q  = (query || '').toLowerCase();
    const sf = _leadsStatusFilter;
    const test = el => {
      const matchQ = !q || (el.dataset.search || '').toLowerCase().includes(q);
      const matchS = sf === 'all' || (el.dataset.status || '') === sf;
      return matchQ && matchS;
    };
    document.querySelectorAll('#leadsTableBody tr').forEach(r => r.style.display = test(r) ? '' : 'none');
    document.querySelectorAll('#leadsCardsMobile .lead-card').forEach(c => c.style.display = test(c) ? '' : 'none');
  }

  // ── Add Lead ──────────────────────────────────────────────────────────────
  function _showAddLeadForm() {
    document.getElementById('addLeadOverlay')?.remove();
    const overlay = document.createElement('div');
    overlay.id = 'addLeadOverlay';
    overlay.className = 'add-lead-overlay';
    overlay.innerHTML = `
      <div class="add-lead-panel">
        <div class="alp-header">
          <span class="alp-title">+ ליד חדש</span>
          <button class="btn btn-ghost" onclick="document.getElementById('addLeadOverlay').remove()">✕</button>
        </div>
        <div class="alp-body">
          <input class="alp-input" id="alpName"   placeholder="שם מלא *" dir="rtl" />
          <input class="alp-input" id="alpPhone"  placeholder="טלפון" dir="ltr" type="tel" />
          <input class="alp-input" id="alpCity"   placeholder="עיר" dir="rtl" />
          <input class="alp-input" id="alpSource" placeholder="מקור (המלצה / רשת חברתית...)" dir="rtl" />
          <button class="btn btn-primary" style="width:100%;margin-top:4px" onclick="Console._submitAddLead()">שמור ✓</button>
        </div>
        <div id="alpResult"></div>
      </div>`;
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
    setTimeout(() => overlay.classList.add('open'), 10);
    document.getElementById('alpName')?.focus();
  }

  async function _submitAddLead() {
    const name   = document.getElementById('alpName')?.value.trim();
    const phone  = document.getElementById('alpPhone')?.value.trim();
    const city   = document.getElementById('alpCity')?.value.trim();
    const source = document.getElementById('alpSource')?.value.trim();
    const resEl  = document.getElementById('alpResult');
    if (!name) {
      if (resEl) resEl.innerHTML = '<div class="alp-err">שם הוא שדה חובה</div>';
      return;
    }
    try {
      const res = await API.createLead({ name, phone, city, source, status: 'new' });
      if (res.success || res.data?.id || res.id) {
        Toast.success(`${name} נוסף ✓`);
        document.getElementById('addLeadOverlay')?.remove();
        Console.reload('leads');
        Shell.refreshTodayStrip?.();
      } else {
        if (resEl) resEl.innerHTML = `<div class="alp-err">${esc(res.error || 'שגיאה')}</div>`;
      }
    } catch (e) {
      if (resEl) resEl.innerHTML = `<div class="alp-err">שגיאה: ${esc(e.message || String(e))}</div>`;
    }
  }

  // ── Lead Detail Panel ─────────────────────────────────────────────────────
  async function _showLeadDetail(id) {
    document.getElementById('leadDetailOverlay')?.remove();
    const overlay = document.createElement('div');
    overlay.id = 'leadDetailOverlay';
    overlay.className = 'lead-detail-overlay';
    overlay.innerHTML = `
      <div class="lead-detail-panel" id="leadDetailPanel">
        <div class="ldp-header">
          <button class="btn btn-ghost btn-sm" onclick="Console._closeLeadDetail()">← חזור</button>
          <span class="ldp-title">פרופיל ליד</span>
        </div>
        <div class="ldp-body" id="ldpBody"><div class="wl-spinner"></div></div>
      </div>`;
    overlay.addEventListener('click', e => { if (e.target === overlay) _closeLeadDetail(); });
    document.body.appendChild(overlay);
    setTimeout(() => overlay.classList.add('open'), 10);

    try {
      const [fullRes, tlRes] = await Promise.all([
        API.leadFull(id).catch(() => ({ success: false })),
        API.timeline(id, 10).catch(() => ({ success: false })),
      ]);
      const lead     = fullRes.success ? (fullRes.data?.lead || fullRes.data || {}) : {};
      const timeline = tlRes.success   ? (tlRes.data?.timeline || tlRes.data?.events || []) : [];
      const score    = Math.round(lead.score || lead.priority_score || 0);
      const initials = (lead.name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();

      const tlHtml = timeline.length
        ? timeline.map(ev => `
            <div class="ldp-tl-item">
              <span class="ldp-tl-dot"></span>
              <div>
                <div class="ldp-tl-title">${esc(ev.event_type || ev.type || '—')}</div>
                <div class="ldp-tl-meta">${esc(ev.created_at_il || ev.created_at || '')}${ev.body ? ' · ' + esc(String(ev.body).slice(0, 60)) : ''}</div>
              </div>
            </div>`).join('')
        : '<div class="muted" style="font-size:11px;padding:8px 0">אין היסטוריה עדיין</div>';

      document.getElementById('ldpBody').innerHTML = `
        <div class="ldp-hero">
          <div class="ldp-avatar">${initials}</div>
          <div class="ldp-hero-info">
            <div class="ldp-name">${esc(lead.name || '—')}</div>
            <div class="ldp-sub">${esc(lead.city || '')}${lead.city && lead.source ? ' · ' : ''}${esc(lead.source || '')}</div>
          </div>
          <span class="score ${_scoreCls(score)}" style="font-size:18px">${score}</span>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">
          ${_statusPill(lead.status)}
          ${lead.sector  ? `<span class="pill pill-steel">${esc(lead.sector)}</span>`  : ''}
          ${lead.company ? `<span class="pill pill-steel">${esc(lead.company)}</span>` : ''}
        </div>
        <div class="ldp-actions">
          ${lead.phone ? `<a class="btn btn-primary btn-sm" href="tel:${esc(lead.phone)}">📞 ${esc(lead.phone)}</a>` : ''}
          <button class="btn btn-primary btn-sm"
            onclick="DraftModal && DraftModal.open({id:'${esc(id)}',name:'${esc(lead.name||'')}',phone:'${esc(lead.phone||'')}',email:'${esc(lead.email||'')}',score:${score}},null);Console._closeLeadDetail()">✉ נסח פנייה</button>
          <button class="btn btn-ghost btn-sm"
            onclick="Console._showLeadMenu('${esc(id)}','${esc(lead.name||'')}')">⋮ פעולות</button>
        </div>
        ${lead.next_action ? `<div class="ldp-next"><strong>הצעד הבא:</strong> ${esc(lead.next_action)}</div>` : ''}
        <div class="ldp-section-title">היסטוריה</div>
        <div class="ldp-timeline">${tlHtml}</div>`;
    } catch (e) {
      const bodyEl = document.getElementById('ldpBody');
      if (bodyEl) bodyEl.innerHTML = `<div class="ws-empty">שגיאה: ${esc(e.message || String(e))}</div>`;
    }
  }

  function _closeLeadDetail() {
    const overlay = document.getElementById('leadDetailOverlay');
    if (overlay) {
      overlay.classList.remove('open');
      setTimeout(() => overlay.remove(), 280);
    }
  }

  return { render, reload, _approve, _deny, _discover, _analyzeWebsite, _scheduleMeeting, _logCall, _markSent, _showLeadMenu, _setStatus, _filterLeads, _showAddLeadForm, _submitAddLead, _showLeadDetail, _closeLeadDetail };
})();
