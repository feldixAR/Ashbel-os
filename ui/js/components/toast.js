/**
 * toast.js — lightweight toast notifications
 */
const Toast = (() => {
  let wrap = null;

  function init() {
    wrap = document.createElement('div');
    wrap.className = 'toast-wrap';
    document.body.appendChild(wrap);
  }

  function show(message, type = 'info', duration = 3000) {
    if (!wrap) init();
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    wrap.appendChild(el);
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transition = 'opacity .3s';
      setTimeout(() => el.remove(), 300);
    }, duration);
  }

  return {
    success: (msg) => show(msg, 'success'),
    error:   (msg) => show(msg, 'error', 4000),
    info:    (msg) => show(msg, 'info'),
  };
})();
