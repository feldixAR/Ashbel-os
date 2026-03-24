/**
 * api.js — all HTTP calls to AshbalOS API.
 * Every function returns { success, data, error }.
 * No fetch call exists anywhere else in the UI.
 */

const API = (() => {
  const BASE = '/api';

  function getKey() {
    return sessionStorage.getItem('ashbal_api_key') || '';
  }

  function headers() {
    return {
      'Content-Type': 'application/json',
      'X-API-Key': getKey(),
    };
  }

  async function request(method, path, body = null) {
    try {
      const opts = { method, headers: headers() };
      if (body) opts.body = JSON.stringify(body);
      const res  = await fetch(BASE + path, opts);
      const json = await res.json();
      return json;
    } catch (e) {
      return { success: false, data: null, error: e.message };
    }
  }

  return {
    setKey(key) { sessionStorage.setItem('ashbal_api_key', key); },
    clearKey()  { sessionStorage.removeItem('ashbal_api_key'); },
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
  };
})();
