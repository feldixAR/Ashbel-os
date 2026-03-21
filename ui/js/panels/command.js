/**
 * command.js — command center panel
 */
const CommandPanel = (() => {
  const QUICK = [
    'הצג לידים',
    'דרג לידים',
    'סטטוס',
    'דוח יומי',
    'הצג סוכנים',
    'עזרה',
  ];

  function render() {
    return `
      <div class="section-head">
        <div>
          <div class="section-title">מרכז פקודות</div>
          <div class="section-sub">הכנס פקודה בעברית או אנגלית</div>
        </div>
      </div>

      <div class="cmd-box">
        <div class="cmd-label">פקודה</div>
        <div class="cmd-row">
          <input class="cmd-input" id="cmdInput" placeholder="לדוגמה: הוסף ליד שם=יוסי כהן עיר=תל אביב טלפון=0501234567"
                 autocomplete="off" spellcheck="false" />
          <button class="btn btn-primary" id="cmdSubmit">שלח</button>
        </div>
        <div class="quick-cmds" id="quickCmds"></div>
      </div>

      <div class="cmd-label" style="margin-bottom:8px;">תוצאה</div>
      <div class="output-box" id="cmdOutput" dir="rtl">ממתין לפקודה...</div>
      <div class="output-meta hidden" id="cmdMeta"></div>
    `;
  }

  function init() {
    const input  = document.getElementById('cmdInput');
    const submit = document.getElementById('cmdSubmit');
    const output = document.getElementById('cmdOutput');
    const meta   = document.getElementById('cmdMeta');
    const quickEl= document.getElementById('quickCmds');

    // Quick command buttons
    QUICK.forEach(q => {
      const btn = document.createElement('button');
      btn.className = 'qcmd';
      btn.textContent = q;
      btn.onclick = () => { input.value = q; runCommand(); };
      quickEl.appendChild(btn);
    });

    submit.onclick = runCommand;
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') runCommand();
    });

    async function runCommand() {
      const cmd = input.value.trim();
      if (!cmd) return;

      output.textContent = '⏳ מעבד...';
      output.classList.add('loading');
      meta.classList.add('hidden');
      submit.disabled = true;

      const res = await API.command(cmd);

      output.classList.remove('loading');
      submit.disabled = false;

      if (!res.success && res.error === 'unauthorized') {
        output.textContent = '⛔ מפתח API שגוי. רענן את הדף.';
        return;
      }

      const d = res.data || {};

      if (d.needs_approval) {
        output.textContent = `⏸ הפעולה דורשת אישור.\n${d.message || ''}`;
        Toast.info('הפעולה ממתינה לאישור');
        App.refreshBadge();
        return;
      }

      if (!res.success) {
        output.textContent = `❌ ${d.message || res.error || 'שגיאה לא ידועה'}`;
        Toast.error('הפקודה נכשלה');
        return;
      }

      // Format output
      let text = d.message || '✅ בוצע';
      const out = d.output || {};
      if (Object.keys(out).length) {
        text += '\n\n';
        for (const [k, v] of Object.entries(out)) {
          if (typeof v === 'object') continue;
          text += `${k}: ${v}\n`;
        }
      }
      // Special: message content
      if (out.message) {
        text = d.message + '\n\n' + '─'.repeat(40) + '\n' + out.message;
      }
      // Special: report
      if (out.report) {
        text = out.report;
      }

      output.textContent = text;
      Toast.success('בוצע בהצלחה');

      meta.classList.remove('hidden');
      meta.textContent = `intent: ${d.intent}  |  task: ${d.task_id?.slice(0,8) || '—'}  |  trace: ${d.trace_id?.slice(0,8) || '—'}`;

      // Refresh relevant panels
      App.refreshBadge();
    }
  }

  return { render, init };
})();
