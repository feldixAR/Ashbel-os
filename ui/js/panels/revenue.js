/**
 * revenue.js — Revenue Plan View (Batch 11)
 * Daily Revenue Plan: priorities, time blocks, pipeline value, today's events
 */
const RevenuePanel = (() => {

  const STAGE_HE = { new:'חדש', qualified:'כשיר', proposal:'הצעה', negotiation:'משא ומתן', won:'זכה', lost:'הפסיד' };

  function ils(n) { return '₪' + (Number(n)||0).toLocaleString('he-IL'); }

  function render() {
    return `
      <div class="ws-split">

        <!-- LEFT: Main content -->
        <div class="ws-main" style="padding:22px">

          <!-- Summary bar -->
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px">
            <div>
              <div class="section-title" id="revDate">תוכנית יומית</div>
              <div class="section-sub" id="revSub">טוען...</div>
            </div>
            <div style="display:flex;gap:8px;align-items:center">
              <div style="text-align:left">
                <div class="revenue-big" id="revPipeline">—</div>
                <div class="rev-label">Pipeline פעיל</div>
              </div>
              <button class="btn btn-ghost" id="revRefresh" style="font-size:12px">↻</button>
            </div>
          </div>

          <!-- Priority list -->
          <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:14px;margin-bottom:16px">
            <div class="cell-title">
              סדר עדיפויות יומי
              <span class="live-dot"></span>
            </div>
            <ul class="priority-list" id="revPriority">
              <li style="padding:16px;text-align:center;color:var(--muted);font-size:12px">טוען...</li>
            </ul>
          </div>

          <!-- Time blocks -->
          <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:14px;margin-bottom:16px">
            <div class="cell-title">הקצאת זמן<span style="font-family:var(--mono);font-size:9px;color:var(--silver-dim)" id="revBudget"></span></div>
            <div id="revBlocks">
              <div style="color:var(--muted);font-size:12px;padding:12px">טוען...</div>
            </div>
          </div>

          <!-- Today's events -->
          <div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:14px">
            <div class="cell-title">אירועי היום 📅</div>
            <div id="revEvents">
              <div style="color:var(--muted);font-size:12px;padding:8px">טוען...</div>
            </div>
          </div>

        </div>

        <!-- RIGHT: Action panel -->
        <div class="ws-right">
          <div class="ws-right-label">הצעד המרכזי היום</div>

          <div class="ap-block">
            <div id="revTopAction">
              <span class="skel skel-h20 skel-w80" style="display:block"></span>
              <span class="skel skel-h12 skel-w60" style="display:block;margin-top:6px"></span>
            </div>
          </div>

          <!-- Revenue scoring queue -->
          <div class="ap-block">
            <div class="ap-lbl">תור ציון הכנסה <span class="live-dot" style="display:inline-block"></span></div>
            <div id="revScoreQueue">
              <span class="skel skel-h12 skel-w80" style="display:block;margin-bottom:5px"></span>
              <span class="skel skel-h12 skel-w60" style="display:block;margin-bottom:5px"></span>
            </div>
          </div>

          <div class="ap-block">
            <div class="ap-lbl">Pipeline לפי שלב</div>
            <div id="revPipeRight">
              <span class="skel skel-h12 skel-w80" style="display:block;margin-bottom:5px"></span>
              <span class="skel skel-h12 skel-w60" style="display:block;margin-bottom:5px"></span>
              <span class="skel skel-h12 skel-w40" style="display:block"></span>
            </div>
          </div>

          <div class="ap-block">
            <div class="ap-lbl">פעולות מהירות</div>
            <div class="ap-btn-col">
              <button class="ap-btn" onclick="App.switchTo('crm')">📋 פתח עסקאות</button>
              <button class="ap-btn" onclick="App.switchTo('leads')">👥 לידים חמים</button>
              <button class="ap-btn" onclick="App.switchTo('calendar')">📅 יומן שבועי</button>
            </div>
          </div>
        </div>

      </div>
    `;
  }

  async function init() {
    await load();
    document.getElementById('revRefresh')?.addEventListener('click', load);
  }

  async function load() {
    const [planRes, dealsRes, revRes] = await Promise.all([
      API.dailyPlan(240),
      API.deals(),
      API.dailyRevenue().catch(() => ({ success: false })),
    ]);

    const plan     = planRes.success  ? (planRes.data  || {}) : {};
    const deals    = dealsRes.success ? (dealsRes.data?.deals || []) : [];
    const revQueue = revRes.success   ? (revRes.data?.queue || []) : [];

    renderHeader(plan);
    renderPriority(plan.priority_items || []);
    renderBlocks(plan.time_blocks || []);
    renderEvents(plan.todays_events || []);
    renderTopAction(plan.top_action || '');
    renderScoreQueue(revQueue);
    renderRightPipe(deals);
  }

  function renderHeader(plan) {
    const today = new Date().toLocaleDateString('he-IL', { weekday:'long', day:'numeric', month:'long' });
    document.getElementById('revDate').textContent  = today;
    document.getElementById('revSub').textContent   = `${plan.total_deals||0} עסקאות · ${plan.total_leads||0} לידים`;
    document.getElementById('revPipeline').textContent = ils(plan.pipeline_value||0);
  }

  function renderPriority(items) {
    const el = document.getElementById('revPriority');
    if (!items.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-state-icon">✅</div><div class="empty-state-msg">אין פריטים לסדר עדיפויות</div></div>';
      return;
    }
    el.innerHTML = items.map((it, i) => {
      const pct = Math.round(it.score||0);
      return `
        <li class="priority-item">
          <span class="p-rank">${i+1}</span>
          <div class="p-info">
            <div class="p-title">${it.title}</div>
            <div class="p-sub">${it.reason||''}</div>
          </div>
          <span class="p-score">${pct}</span>
          <div class="p-bar"><div class="p-bar-fill" style="width:${pct}%"></div></div>
          <span class="p-mins">${(it.metadata||{}).minutes ? (it.metadata.minutes+'ד')  : ''}</span>
        </li>`;
    }).join('');
  }

  function renderBlocks(blocks) {
    const el = document.getElementById('revBlocks');
    if (!blocks.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-state-msg">אין הקצאת זמן</div></div>';
      return;
    }
    const total = blocks.reduce((s,b)=>s+(b.minutes||0),0);
    document.getElementById('revBudget').textContent = `  ${total} דק' מתוזמנות`;

    el.innerHTML = blocks.map(b => {
      const pct = Math.min(100, ((b.minutes||0)/60)*100);
      return `
        <div class="tb-item">
          <span class="tb-clock">${offsetToTime(b.start_offset||0)}</span>
          <div class="tb-track">
            <div class="tb-bar" style="width:${Math.max(30,pct)}%">
              <span>${b.action||b.title}</span>
            </div>
          </div>
          <span class="tb-dur">${b.minutes||0}ד'</span>
        </div>`;
    }).join('');
  }

  function renderEvents(events) {
    const el = document.getElementById('revEvents');
    if (!events.length) {
      el.innerHTML = '<div style="font-size:11px;color:var(--muted);padding:6px 0">אין אירועים מתוזמנים להיום</div>';
      return;
    }
    el.innerHTML = events.map(ev => `
      <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid rgba(34,39,49,.4)">
        <span style="font-size:14px">📅</span>
        <div style="flex:1">
          <div style="font-size:12px;font-weight:500">${ev.title||''}</div>
          <div style="font-size:10px;color:var(--muted)">${(ev.starts_at_il||'').slice(11,16)} · ${ev.event_type||'פגישה'}</div>
        </div>
        <span class="pill pill-steel" style="font-size:9px">${ev.status||'מתוכנן'}</span>
      </div>`).join('');
  }

  function renderTopAction(action) {
    document.getElementById('revTopAction').innerHTML = action
      ? `<div class="next-action-box">${action}</div>`
      : `<div style="font-size:11px;color:var(--muted)">אין פעולה מרכזית</div>`;
  }

  function renderScoreQueue(queue) {
    const el = document.getElementById('revScoreQueue');
    if (!el) return;
    if (!queue.length) {
      el.innerHTML = '<div style="font-size:11px;color:var(--muted)">אין לידים בתור הכנסה</div>';
      return;
    }
    el.innerHTML = queue.slice(0, 5).map((item, i) => {
      const score  = Math.round(item.score || item.priority_score || 0);
      const name   = item.lead_name || item.name || '—';
      const reason = item.reason    || item.next_action || '';
      const bar    = Math.min(score, 100);
      return `
        <div style="padding:6px 0;border-bottom:1px solid rgba(34,39,49,.35)">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
            <span style="font-size:11px;font-weight:600">${i+1}. ${name}</span>
            <span class="score ${score>=70?'score-hot':score>=40?'score-warm':'score-cold'}">${score}</span>
          </div>
          ${reason ? `<div style="font-size:9px;color:var(--muted);margin-bottom:3px">${reason.slice(0,45)}</div>` : ''}
          <div style="height:3px;background:rgba(255,255,255,.07);border-radius:2px">
            <div style="height:3px;background:var(--accent);border-radius:2px;width:${bar}%"></div>
          </div>
        </div>`;
    }).join('');
  }

  function renderRightPipe(deals) {
    const stages = ['new','qualified','proposal','negotiation'];
    const cls    = ['','pf-q','pf-p','pf-n'];
    const totals = stages.map(s => deals.filter(d=>d.stage===s).reduce((sum,d)=>sum+(d.value_ils||0),0));
    const max    = Math.max(...totals,1);
    document.getElementById('revPipeRight').innerHTML = stages.map((s,i)=>`
      <div class="pipe-row">
        <span class="pipe-label" style="font-size:9px">${STAGE_HE[s]}</span>
        <div class="pipe-track"><div class="pipe-fill ${cls[i]}" style="width:${(totals[i]/max*100).toFixed(0)}%"></div></div>
        <span class="pipe-val" style="font-size:9px">${ils(totals[i])}</span>
      </div>`).join('');
  }

  function offsetToTime(offsetMin) {
    const h = Math.floor(offsetMin/60);
    const m = offsetMin%60;
    return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
  }

  return { render, init };
})();
