/**
 * api.js — all HTTP calls to AshbalOS API.
 * Every function returns { success, data, error }.
 * No fetch call exists anywhere else in the UI.
 */

const API = (() => {
  const BASE    = '/api';
  const SS_KEY  = 'ashbal_api_key';   // current sessionStorage key name
  const LS_OLD  = 'api_key';          // legacy localStorage key — purge on load

  // ── One-time: flush stale key from old localStorage name ─────────────────
  try { localStorage.removeItem(LS_OLD); } catch (_) {}

  function getKey() {
    // Read from sessionStorage only — no truncation, no fallback
    const k = sessionStorage.getItem(SS_KEY) || '';
    return k;
  }

  function headers() {
    return {
      'Content-Type': 'application/json',
      'X-API-Key': getKey(),
    };
  }

  async function request(method, path, body = null) {
    try {
      const key  = getKey();
      console.log('Outbound Key Len:', key.length, '| Path:', path);
      const opts = { method, headers: { 'Content-Type': 'application/json', 'X-API-Key': key } };
      if (body) opts.body = JSON.stringify(body);
      const res  = await fetch(BASE + path, opts);
      const json = await res.json();
      return json;
    } catch (e) {
      return { success: false, data: null, error: e.message };
    }
  }

  return {
    setKey(key) {
      // Store exactly what is provided — app.js already calls .trim() before this
      sessionStorage.setItem(SS_KEY, key);
      console.log('Key stored. Len:', key.length);
    },
    clearKey()  { sessionStorage.removeItem(SS_KEY); },
    hasKey()    { return !!getKey(); },

    // Generic helpers used by panels
    get:  (path)        => request('GET',  path),
    post: (path, body)  => request('POST', path, body),

    // System
    health:  ()     => request('GET', '/health'),
    status:  ()     => request('GET', '/status'),

    // Command — two endpoints (legacy + new)
    command: (cmd)  => request('POST', '/command', { command: cmd }),

    // Leads
    leads:   (params = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request('GET', '/leads' + (qs ? '?' + qs : ''));
    },
    createLead:  (data)    => request('POST', '/leads', data),
    updateLead:  (id, data)=> request('PATCH', `/leads/${id}`, data),

    // Agents
    agents:  (dept)  => {
      const qs = dept ? '?department=' + dept : '';
      return request('GET', '/agents' + qs);
    },

    // Tasks
    tasks:   (status) => {
      const qs = status ? `?status=${status}` : '';
      return request('GET', `/tasks${qs}`);
    },
    task:    (id) => request('GET', `/tasks/${id}`),

    // Approvals
    approvals: ()           => request('GET', '/approvals'),
    approve:   (id, note)   => request('POST', `/approvals/${id}`, { action: 'approve', note }),
    deny:      (id, note)   => request('POST', `/approvals/${id}`, { action: 'deny',    note }),

    // Reports
    dailyReport: () => request('GET', '/reports/daily'),

    // ── CRM — Deals ──────────────────────────────────────────────────────────
    deals: (params = {}) => {
      const qs = new URLSearchParams(params).toString();
      return request('GET', '/crm/deals' + (qs ? '?' + qs : ''));
    },
    deal:            (id)         => request('GET',  `/crm/deals/${id}`),
    createDeal:      (data)       => request('POST', '/crm/deals', data),
    updateDeal:      (id, data)   => request('PUT',  `/crm/deals/${id}`, data),
    transitionStage: (dealId, stage, reason = '', changedBy = 'operator') =>
      request('POST', `/crm/deals/${dealId}/stage`, { stage, reason, changed_by: changedBy }),

    // ── CRM — Activities ─────────────────────────────────────────────────────
    logActivity: (leadId, data)  => request('POST', `/crm/leads/${leadId}/activities`, data),
    activities:  (leadId)        => request('GET',  `/crm/leads/${leadId}/activities`),

    // ── CRM — Timeline ───────────────────────────────────────────────────────
    timeline: (leadId, limit = 20) =>
      request('GET', `/crm/leads/${leadId}/timeline?limit=${limit}`),

    // ── CRM — Calendar ───────────────────────────────────────────────────────
    dailyPlan:    (budget = 240) => request('GET', `/crm/calendar/today?budget_minutes=${budget}`),
    weeklyCalendar: ()           => request('GET', '/crm/calendar/week'),
    createCalEvent: (data)       => request('POST', '/crm/calendar/events', data),

    // ── CRM — Lead Full Record View (Batch 7) ────────────────────────────────
    leadFull: (leadId) => request('GET', `/crm/leads/${leadId}/full`),

    // ── Dashboard Command Center (Batch 7) ───────────────────────────────────
    dashboardSummary: () => request('GET', '/dashboard/summary'),

    // ── Briefing ─────────────────────────────────────────────────────────────
    identifyCaller:  (phone)       => request('POST', '/briefing/identify', { phone }),
    customerSummary: (leadId)      => request('GET',  `/briefing/summary/${leadId}`),
    briefingContext: (leadId, n=5) => request('GET',  `/briefing/context/${leadId}?limit=${n}`),
    startCall:       (leadId, callId='') =>
      request('POST', '/briefing/call/start', { lead_id: leadId, call_id: callId }),
    endCall: (callId, notes, outcome, durationSec = 0, performedBy = 'operator') =>
      request('POST', '/briefing/call/end',
        { call_id: callId, notes, outcome, duration_sec: durationSec, performed_by: performedBy }),
  };
})();
