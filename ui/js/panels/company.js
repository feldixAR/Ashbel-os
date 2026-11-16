/**
 * Company work surface: persisted events, concrete department outputs and work.
 * All IO goes through API. Source content is rendered as text, never HTML.
 */
const CompanyPanel = (() => {
  'use strict';
  const departments = {sales:'מכירות', engineering:'הנדסה ותמחור', procurement:'רכש וספקים',
    finance:'כספים', marketing:'איתור ושיווק', strategy:'אסטרטגיה', pmo:'לשכה וניהול',
    knowledge:'ידע מקצועי', auditor:'ביקורת עצמאית'};
  const statuses = {pending:'ממתין לניתוח', processing:'בניתוח', analyzed:'נותח ונבדק',
    blocked:'חסום', retry:'ממתין לניסיון נוסף', dead_letter:'נדרש טיפול בתקלה',
    review_required:'נדרשת ביקורת', created:'פתוח', approval_pending:'ממתין לאישור',
    reported_complete:'בוצע לפי דיווח — לא אומת עצמאית', cancelled:'בוטל',
    prepared:'מוכן לקליטה', committed:'קליטה אומתה', duplicate:'קיים במאגר',
    uncertain:'נדרשת בדיקת כתיבה', no_change:'אין שינוי', missing_data:'חסר מידע', action:'נדרש טיפול'};
  const labels = {title:'תוצר',summary:'סיכום',missing:'מידע חסר',steps:'הצעדים הבאים',
    checklist:'רשימת בדיקה',opening_schedule:'ריכוז פתחים',quotes:'הצעות להשוואה',
    scenarios:'תרחישי תמחור',open_loops:'מעקבים פתוחים',draft_text:'טיוטה',draft:'טיוטה',
    name:'שם',subject:'נושא',description:'פירוט',action:'פעולה',status:'מצב',label:'פרט',
    amount:'סכום',cost:'עלות',price:'מחיר',quantity:'כמות',unit:'יחידה',
    source_ref:'מקור',evidence_ref:'אסמכתה',source_url:'מקור',next_action:'הפעולה הבאה',
    city:'יישוב',project_type:'סוג פרויקט',project_stage:'שלב הפרויקט',aluminum_need:'צורך באלומיניום',phone:'טלפון',email:'דוא״ל',
    code:'סוג פעולה',manufacturing:'ייצור',installation:'התקנה',ancillary_costs:'עלויות נלוות',
    payment_terms:'תנאי תשלום',warranty:'אחריות',profit:'רווח',revenue:'מחיר מכירה',
    collected_ils:'גבייה מאומתת',verified_contractor_profit_ils:'רווח קבלני מאומת'};
  const hiddenKeys = new Set(['permissions','task_id','agent_id','source_fingerprint','context_fingerprint',
    'mode','execution','execution_scope','model_used','fingerprint','business_id']);
  let generation = 0;
  const busy = new Set();

  function element(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = String(text);
    if (cls) el.className = cls;
    return el;
  }
  function button(text, action, primary=false) {
    const b = element('button', text, 'btn ' + (primary?'btn-primary':'btn-ghost'));
    b.type = 'button'; b.addEventListener('click', action); return b;
  }
  function link(text, target) {
    const el = element('a', text);
    try {
      const url = new URL(target);
      if (!['https:','http:'].includes(url.protocol)) return element('span', 'אין קישור מקור תקין');
      el.href=url.href; el.target='_blank'; el.rel='noopener noreferrer';
    } catch (_) { return element('span', 'אין קישור מקור תקין'); }
    return el;
  }
  function message(host,text) { host.replaceChildren(element('p',text,'company-message')); }
  function reason(response) {
    if (response?._status===401) return 'נדרשת כניסה מורשית למערכת.';
    if (response?._status===409) return 'הנתונים השתנו. רענן לפני פעולה נוספת.';
    if (response?._status===503) return 'החיבור או התהליך עדיין אינם פעילים. יש להשלים את ההגדרה.';
    return 'הפעולה לא אומתה. רענן ובדוק את המצב לפני ניסיון נוסף.';
  }
  function section(title) {
    const el=element('section',null,'company-section');
    el.append(element('h3',title)); return el;
  }
  function details(value, depth=0) {
    if (value===null || value===undefined) return element('span','לא אומת');
    if (typeof value !== 'object') return element('span',typeof value==='boolean'?(value?'כן':'לא'):String(value));
    const list=element('dl',null,'company-artifact');
    if (depth>4) return element('span','פרטים נוספים זמינים בתיעוד האירוע.');
    Object.entries(value).filter(([k])=>!hiddenKeys.has(k)).forEach(([key,child])=>{
      if (key==='title'||key==='summary') return;
      const label=Array.isArray(value)?'פרט ' + (Number(key)+1):(labels[key]||key.replace(/_/g,' '));
      const term=element('dt',label), description=element('dd');
      description.append(details(child,depth+1)); list.append(term,description);
    });
    return list;
  }
  function artifact(data) {
    const wrap=element('div',null,'company-output');
    if (!data) {wrap.append(element('p','טרם נשמר תוצר למחלקה.'));return wrap;}
    if (data.title) wrap.append(element('h4',data.title));
    if (data.summary) wrap.append(element('p',data.summary));
    wrap.append(details(data)); return wrap;
  }
  function status(text) { return element('span',statuses[text]||text||'לא אומת','pill pill-steel'); }

  async function reviewForm(card,item,action,onVerified) {
    card.querySelector('.company-review')?.remove();
    const form=element('form',null,'company-review');
    const noteLabel=element('label','מה בוצע או מה השתנה?');
    const note=element('textarea'); note.required=true; note.maxLength=2000; noteLabel.append(note);
    const evidenceLabel=element('label','קישור לאסמכתה או לתיעוד');
    const evidence=element('input'); evidence.type='url'; evidence.maxLength=2000;
    evidence.required=action==='report_complete'; evidenceLabel.append(evidence);
    const notice=element('p','דיווח ביצוע נשמר כדיווח. הוא אינו אישור למסירה, גבייה או התחייבות.');
    const save=element('button','שמור דיווח','btn btn-primary'); save.type='submit';
    const feedback=element('p'); feedback.setAttribute('role','status');
    form.append(noteLabel,evidenceLabel,notice,save,button('סגור',()=>form.remove()),feedback);
    form.addEventListener('submit',async event=>{
      event.preventDefault();
      if (busy.has(item.id)) return;
      busy.add(item.id); save.disabled=true;
      try {
        const response=await API.post('/business_events/work_items/'+encodeURIComponent(item.id)+'/review',
          {expected_version:item.version,action,note:note.value,evidence_ref:evidence.value});
        if (!response.success) {feedback.textContent=reason(response);return;}
        const posted=response.data?.item;
        const read=await API.get('/business_events/work_items?limit=100');
        const stored=(read.data?.items||[]).find(x=>x.id===item.id);
        const expected={report_complete:'reported_complete',cancel:'cancelled',reopen:'created'}[action];
        const evidenceMatches=action!=='report_complete'||(
          posted?.completion_evidence?.note===note.value.trim()&&
          posted?.completion_evidence?.evidence_ref===evidence.value.trim()&&
          JSON.stringify(stored?.completion_evidence)===JSON.stringify(posted.completion_evidence));
        if (!read.success || !posted || posted.id!==item.id || posted.version!==item.version+1 ||
            !stored || stored.version!==posted.version || stored.status!==expected || !evidenceMatches) {
          feedback.textContent='הבקשה התקבלה, אך השמירה טרם אומתה. רענן לפני פעולה נוספת.';return;
        }
        feedback.textContent='השמירה אומתה בקריאה חוזרת.'; onVerified();
      } finally {busy.delete(item.id);save.disabled=false;}
    });
    card.append(form); note.focus();
  }
  function workCard(item,onVerified) {
    const card=element('article',null,'company-card');
    card.append(element('h4',(departments[item.department]||item.department||'משימה')+' · '+(item.subject||'טיפול באירוע')));
    card.append(status(item.status));
    if (item.source_ref) card.append(link('פתח מקור',item.source_ref));
    card.append(artifact(item.artifact));
    if (item.missing?.length) card.append(element('p','חסר: '+item.missing.join(' · '),'company-missing'));
    const actions=element('div',null,'company-actions');
    if (!['reported_complete','cancelled'].includes(item.status)) {
      actions.append(button('דווח ביצוע',()=>reviewForm(card,item,'report_complete',onVerified),true));
    } else actions.append(button('פתח מחדש',()=>reviewForm(card,item,'reopen',onVerified)));
    if(item.status!=='cancelled') actions.append(button('בטל משימה',()=>reviewForm(card,item,'cancel',onVerified)));
    card.append(actions); return card;
  }
  function eventCard(event) {
    const card=element('article',null,'company-card');
    card.append(element('h4',event.output?.ceo_decision?.summary||'אירוע שנקלט לבדיקה'),status(event.status));
    if (event.source_ref) card.append(link('פתח מקור',event.source_ref));
    if(event.last_error_code) card.append(element('p','נדרש טיפול בתקלה. האירוע נשמר ולא סומן כהושלם.','company-missing'));
    const roles=event.output?.departments||{};
    if(Object.keys(roles).length) {
      const expander=element('details'),title=element('summary','תוצרי המחלקות והביקורת');
      expander.append(title);
      for(const [role,result] of Object.entries(roles)) {
        const group=section(departments[role]||role);
        group.append(element('p',result.summary||''),status(result.status),artifact(result.artifact));
        expander.append(group);
      }
      const verdict=event.output?.independent_auditor;
      if(verdict) expander.append(element('p',verdict.passed?'הביקורת לא מצאה הפרה בשלב הניתוח.':'הביקורת דורשת טיפול לפני המשך.'));
      card.append(expander);
    }
    return card;
  }

  function candidateCard(candidate, feedback, refresh) {
    const card=element('article',null,'company-card');
    card.append(element('h4',candidate.title||candidate.name||'מועמד לבדיקה'));
    if(candidate.source_url)card.append(link('פתח מקור לבדיקה',candidate.source_url));
    card.append(element('p','המועמד טרם נשמר ב־CRM. פרטי קשר פומביים אינם הרשאת פנייה.'));
    if(!candidate.task_id)return card;
    const expanded=element('details'); expanded.append(element('summary','בדוק פרטים והכן קליטה'));
    const form=element('form'), inputs={};
    const field=(key,label,value,type='text')=>{
      const wrap=element('label',label), input=element('input'); input.type=type;
      input.value=value||''; input.maxLength=1000;
      input.required=!['phone','email','published_at','details'].includes(key);
      wrap.append(input);form.append(wrap);inputs[key]=input;
    };
    const found=new Date(candidate.found_at);
    if(!Number.isFinite(found.getTime())){
      card.append(element('p','חסר תאריך איתור תקין; יש לבדוק את המקור לפני קליטה.'));return card;
    }
    const foundDate=found.toLocaleDateString('en-CA',{timeZone:'Asia/Jerusalem'});
    const published=new Date(candidate.source_published_text||'');
    const publishedDate=Number.isFinite(published.getTime())?published.toISOString().slice(0,10):'';
    field('name','שם האדם או החברה',candidate.title||'');
    field('city','יישוב','לא אומת');
    field('project_type','סוג פרויקט','לא אומת');
    field('project_stage','שלב הפרויקט','לא אומת');
    field('aluminum_need','הצורך באלומיניום לפי המקור','לא אומת');
    field('next_action','הפעולה הבאה','בדיקת התאמה והכנת הצעד הבא לאישור');
    field('quality','איכות ההזדמנות','נמוכה — טרם הוכשרה');
    field('confidence','רמת ביטחון בפרטים','נמוכה');
    field('published_at','תאריך פרסום, אם מופיע במקור',publishedDate,'date');
    field('phone','טלפון שפורסם במקור','', 'tel');
    field('email','דוא״ל שפורסם במקור','', 'email');
    const entityLabel=element('label','סוג רשומה'),entity=element('select');
    ['לקוח','ספק','מתקין','שותף עסקי'].forEach(value=>{
      const option=element('option',value);option.value=value;entity.append(option);
    });entityLabel.append(entity);form.append(entityLabel);
    const confirmationLabel=element('label',null,'company-confirmation'),confirmation=element('input');
    confirmation.type='checkbox';confirmation.required=true;
    confirmationLabel.append(confirmation,element('span','בדקתי את המקור ואימתתי את הפרטים שמופיעים כאן, כולל פרטי קשר שפורסמו בו.'));
    form.append(confirmationLabel);
    const submit=element('button','אמת מקור והצג תצוגה מקדימה','btn btn-primary');submit.type='submit';
    const localFeedback=element('p');localFeedback.setAttribute('role','status');
    const previewArea=element('div');form.append(submit,localFeedback,previewArea);
    let preview=null;
    form.addEventListener('input',()=>{preview=null;previewArea.replaceChildren();});
    form.addEventListener('submit',async event=>{
      event.preventDefault();
      if(busy.has(candidate.task_id))return;
      busy.add(candidate.task_id);submit.disabled=true;preview=null;previewArea.replaceChildren();
      try {
        const facts={source_key:'PUBLIC-'+candidate.task_id,source_url:candidate.source_url,
          found_at:foundDate,entity_type:entity.value};
        Object.entries(inputs).forEach(([key,input])=>facts[key]=input.value.trim());
        const review=await API.post('/source_discovery/candidates/'+encodeURIComponent(candidate.task_id)+'/verify',
          {candidate:facts,review_confirmed:confirmation.checked});
        if(!review.success){localFeedback.textContent=reason(review);return;}
        const response=await API.post('/source_sync/preview',{candidate:review.data.candidate});
        if(!response.success){localFeedback.textContent=reason(response);return;}
        preview=response.data;
        if(preview.status==='duplicate'){
          localFeedback.textContent='נמצאה רשומה קיימת. המועמד לא ייקלט כליד חדש.';return;
        }
        if(preview.status!=='prepared'||!preview.operation_id||!preview.preview_hash||!Array.isArray(preview.row)){
          localFeedback.textContent='לא התקבלה תצוגה מקדימה תקינה; לא תתבצע כתיבה.';return;
        }
        localFeedback.textContent='המקור נקרא והפרטים נקשרו לתצוגה זו. עדיין לא נכתבה רשומה.';
        const box=section('הפרטים שיישמרו ב־CRM');
        const row=preview.row;
        box.append(details({name:row[7],city:row[5],project_type:row[34],project_stage:row[3],
          aluminum_need:row[35],next_action:row[10],phone:row[15],email:row[16],source_url:row[28]}));
        box.append(element('p','הרשאת פנייה: לא אומתה. קליטה זו אינה שולחת הודעה.'));
        const commit=button('אשר קליטה של רשומה זו',async()=>{
          const exact=preview;
          if(!exact||busy.has(candidate.task_id))return;
          busy.add(candidate.task_id);commit.disabled=true;
          preview=null; // one attempt only; reconcile ambiguous writes before any new preview
          try{
            const result=await API.post('/source_sync/'+encodeURIComponent(exact.operation_id)+'/commit',
              {preview_hash:exact.preview_hash});
            if(!result.success){localFeedback.textContent=reason(result);return;}
            const state=result.data?.status;
            if(state==='committed'){
              const check=await API.get('/source_sync/status');
              const stored=(check.data?.operations||[]).find(x=>x.id===exact.operation_id);
              if(check.success&&stored?.status==='committed'){
                feedback.textContent='קליטת הרשומה אומתה במאגר.';refresh();
              }else localFeedback.textContent='הבקשה התקבלה; יש לרענן ולאמת את מצב הקליטה לפני ניסיון נוסף.';
            }else if(state==='duplicate')localFeedback.textContent='הרשומה כבר קיימת; לא נוסף ליד חדש.';
            else if(state==='uncertain')localFeedback.textContent='מצב הכתיבה אינו ודאי. אין לשלוח שוב; השתמש בבדיקת הרשומה שנשמרה.';
            else localFeedback.textContent='לא אומתה קליטה. רענן ובדוק את החסם לפני ניסיון נוסף.';
            preview=null;
          }finally{busy.delete(candidate.task_id);commit.disabled=true;}
        },true);
        box.append(commit);previewArea.append(box);
      }finally{busy.delete(candidate.task_id);submit.disabled=false;}
    });
    form.className='company-review';expanded.append(form);card.append(expanded);return card;
  }

  async function render(host) {
    const current=++generation;
    host.replaceChildren();
    const root=element('div',null,'company-panel'); root.dir='rtl';
    const heading=section('החברה — החלטות ותוצרים');
    heading.append(element('p','מה נדרש עכשיו, מי מטפל, ואילו תוצרים נשמרו. אישור טיוטה או ניתוח אינם ביצוע עסקי.'));
    const controls=element('div',null,'company-actions');
    const feedback=element('p'); feedback.setAttribute('role','status');
    const poll=button('בדוק כעת את המקורות והאירועים',async()=>{
      if(busy.has('poll'))return;
      busy.add('poll');poll.disabled=true;
      try {
        const result=await API.post('/business_events/poll',{});
        if(!result.success){feedback.textContent=reason(result);return;}
        if(result.data?.source_health && result.data.source_health!=='read_ok'){
          feedback.textContent='מקור הנתונים אינו מחובר או אינו זמין; לא הוצג ביצוע חדש.';return;
        }
        render(host);
      } finally {busy.delete('poll');poll.disabled=false;}
    },true);
    controls.append(poll,button('רענן תוצרים',()=>render(host)));
    heading.append(controls,feedback);root.append(heading);host.append(root);
    const pending=element('p','טוען תיעוד שמור...');root.append(pending);
    const [events,work,discovery,sync]=await Promise.all([
      API.get('/business_events'),API.get('/business_events/work_items?limit=100'),
      API.get('/source_discovery'),API.get('/source_sync/status')]);
    if(current!==generation || !root.isConnected)return;
    pending.remove();
    const state=section('מצב עכשיו');
    const eventsData=events.success?(events.data?.events||[]):null;
    const workData=work.success?(work.data?.items||[]):null;
    state.append(element('p',eventsData===null?'תור האירועים אינו פעיל או אינו זמין.':eventsData.length+' אירועים מתועדים'));
    state.append(element('p',workData===null?'תוצרי העבודה אינם זמינים.':workData.filter(x=>!['reported_complete','cancelled'].includes(x.status)).length+' משימות פתוחות'));
    if(!events.success)state.append(element('p',reason(events),'company-missing'));
    const newest=eventsData?.find(e=>e.output?.ceo_decision);
    if(newest)state.append(element('p','הפעולה המומלצת: '+newest.output.ceo_decision.summary));
    else state.append(element('p','הצעד הבא: בדוק את חיבור המקורות, ואז הפעל בדיקה אחת.'));
    root.append(state);
    const workSection=section('משימות המחלקות');
    if(workData?.length)workData.forEach(item=>workSection.append(workCard(item,()=>render(host))));
    else workSection.append(element('p',workData===null?'אין אפשרות לקרוא את תור העבודה כעת.':'טרם הופקו משימות; בדיקת מקור אמיתי תפיק תוצרים לפי הצורך.'));
    root.append(workSection);
    const sources=section('איתור ממקורות חיצוניים');
    if(discovery.success){
      const candidates=discovery.data?.candidates||[];
      sources.append(element('p',candidates.length+' מועמדים לבדיקה. מועמד אינו ליד מאומת.'));
      const scan=button('סרוק מקורות מוגדרים',async()=>{
        if(busy.has('scan'))return;busy.add('scan');scan.disabled=true;
        try{const r=await API.post('/source_discovery/scan',{});if(r.success)render(host);else feedback.textContent=reason(r);}
        finally{busy.delete('scan');scan.disabled=false;}
      });
      sources.append(scan);
      candidates.forEach(candidate=>sources.append(candidateCard(candidate,feedback,()=>render(host))));
    }else sources.append(element('p','סריקת המקורות טרם חוברה או אינה זמינה.'));
    const operations=sync.success?(sync.data?.operations||[]):null;
    if(operations){
      sources.append(element('p',sync.data?.writer_configured?'חיבור הכתיבה מוגדר; כל קליטה דורשת אימות.':'חיבור כתיבה ל־CRM טרם הוגדר.'));
      operations.forEach(operation=>{
        const line=element('div',null,'company-card');
        line.append(status(operation.status));
        if(operation.result?.source_url)line.append(link('מקור הרשומה',operation.result.source_url));
        if(operation.status==='uncertain'){
          line.append(element('p','הכתיבה אינה ודאית. אין לשלוח שוב; יש לבדוק את המאגר.'));
          const reconcile=button('בדוק אם הרשומה נשמרה',async()=>{
            if(busy.has(operation.id))return;busy.add(operation.id);reconcile.disabled=true;
            try{const r=await API.post('/source_sync/'+encodeURIComponent(operation.id)+'/reconcile',{});if(r.success)render(host);else feedback.textContent=reason(r);}
            finally{busy.delete(operation.id);reconcile.disabled=false;}
          });line.append(reconcile);
        }
        sources.append(line);
      });
    }
    root.append(sources);
    const history=section('אירועים וביקורת');
    if(eventsData?.length)eventsData.forEach(event=>history.append(eventCard(event)));
    else history.append(element('p','אין אירוע זמין לתצוגה. השתמש בבדיקה של המקורות כדי להתחיל.'));
    root.append(history);
  }
  return {render};
})();
