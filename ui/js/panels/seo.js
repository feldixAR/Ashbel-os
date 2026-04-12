/**
 * seo.js — SEO Engine Panel
 * Sources: GET /api/seo/meta, /seo/cities, /seo/blog, /seo/images
 */
const SEOPanel = (() => {

  function render() {
    return `
      <!-- Widget bar -->
      <div class="panel-widgets">
        <div class="pw-chip">
          <div class="pw-val pv-accent" id="seowPages">—</div>
          <div class="pw-label">עמודי עיר</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val pv-green" id="seowPosts">—</div>
          <div class="pw-label">פוסטים</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val" id="seowImages">—</div>
          <div class="pw-label">פרומפטי תמונה</div>
        </div>
        <div class="pw-chip">
          <div class="pw-val" id="seowMeta">—</div>
          <div class="pw-label">מטא-תיאורים</div>
        </div>
      </div>

      <div id="seoInsight" style="margin:8px 0 4px"></div>

      <div class="section-head">
        <div>
          <div class="section-title">SEO Engine — אשבל אלומיניום</div>
          <div class="section-sub">תוכן ממוטב לקידום אורגני · ללא AI · גנרציה דטרמיניסטית</div>
        </div>
        <button class="btn btn-ghost" onclick="SEOPanel.reload()">↻ רענן</button>
      </div>

      <!-- Tab bar -->
      <div class="leads-filter" id="seoTabs">
        <button class="filter-pill active" data-tab="meta">מטא</button>
        <button class="filter-pill" data-tab="cities">עמודי עיר</button>
        <button class="filter-pill" data-tab="blog">בלוג</button>
        <button class="filter-pill" data-tab="images">תמונות AI</button>
      </div>

      <div id="seoMeta"   style="margin-top:12px">${UI.loading('טוען...')}</div>
      <div id="seoCities" style="display:none;margin-top:12px">${UI.loading('טוען...')}</div>
      <div id="seoBlog"   style="display:none;margin-top:12px">${UI.loading('טוען...')}</div>
      <div id="seoImages" style="display:none;margin-top:12px">${UI.loading('טוען...')}</div>
    `;
  }

  let _activeTab = 'meta';

  async function init() {
    await load();
    document.querySelectorAll('#seoTabs .filter-pill').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#seoTabs .filter-pill').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _activeTab = btn.dataset.tab;
        ['meta', 'cities', 'blog', 'images'].forEach(t => {
          const el = document.getElementById('seo' + t.charAt(0).toUpperCase() + t.slice(1));
          if (el) el.style.display = t === _activeTab ? '' : 'none';
        });
      });
    });
  }

  async function load() {
    const [metaRes, citiesRes, blogRes, imagesRes] = await Promise.all([
      API.seoMeta(),
      API.seoCities(),
      API.seoBlog(),
      API.seoImages(),
    ]);

    // ── Widgets ───────────────────────────────────────────────────────────
    const cities = citiesRes.success ? (citiesRes.data?.pages || []) : [];
    const posts  = blogRes.success   ? (blogRes.data?.posts   || []) : [];
    const images = imagesRes.success ? (imagesRes.data?.prompts|| []) : [];
    const meta   = metaRes.success   ? Object.keys(metaRes.data?.meta || {}).length : 0;
    _setText('seowPages',  cities.length);
    _setText('seowPosts',  posts.length);
    _setText('seowImages', images.length);
    _setText('seowMeta',   meta);

    // ── Mission Control: State → Insight ────────────────────────────────
    const iChips = [];
    if (cities.length) iChips.push({ icon: '🏙', text: `${cities.length} עמודי עיר`,    cls: 'insight-good' });
    if (posts.length)  iChips.push({ icon: '📝', text: `${posts.length} פוסטים`,          cls: 'insight-good' });
    if (images.length) iChips.push({ icon: '🖼', text: `${images.length} פרומפטים`,        cls: ''             });
    if (!iChips.length) iChips.push({ icon: '○', text: 'אין תוכן SEO עדיין',             cls: 'insight-warn' });
    const iEl = document.getElementById('seoInsight');
    if (iEl) iEl.innerHTML = UI.insightStrip(iChips);

    // ── Meta descriptions ─────────────────────────────────────────────────
    const metaEl = document.getElementById('seoMeta');
    if (metaEl) {
      if (!metaRes.success) { metaEl.innerHTML = UI.error('שגיאה בטעינת מטא-תיאורים'); }
      else {
        const entries = Object.entries(metaRes.data?.meta || {});
        metaEl.innerHTML = entries.length
          ? entries.map(([page, desc]) => `
            <div style="background:var(--surface-2,rgba(0,0,0,.04));border:1px solid var(--border);border-radius:8px;padding:12px 14px;margin-bottom:10px;direction:rtl">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                <span style="font-weight:600;font-size:12px;color:var(--accent)">${page}</span>
                <span style="font-size:9px;color:var(--muted)">${desc.length}/155 תווים</span>
              </div>
              <div style="font-size:12px;color:var(--text);margin-bottom:8px">${desc}</div>
              <button class="btn btn-ghost" style="font-size:10px;padding:3px 8px"
                      onclick="navigator.clipboard.writeText(${JSON.stringify(desc)}).then(()=>Toast.success('הועתק'))">
                העתק
              </button>
            </div>`).join('')
          : UI.empty('אין מטא-תיאורים', '○');
      }
    }

    // ── City pages ────────────────────────────────────────────────────────
    const citiesEl = document.getElementById('seoCities');
    if (citiesEl) {
      if (!citiesRes.success) { citiesEl.innerHTML = UI.error('שגיאה בטעינת עמודי עיר'); }
      else {
        citiesEl.innerHTML = cities.length
          ? cities.map(p => `
            <div style="background:var(--surface-2,rgba(0,0,0,.04));border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:12px;direction:rtl">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
                <div>
                  <div style="font-weight:600;font-size:13px">${p.title}</div>
                  <div style="font-size:10px;color:var(--muted);font-family:var(--mono)">/${p.slug}</div>
                </div>
                <button class="btn btn-ghost" style="font-size:10px;padding:3px 8px"
                        onclick="navigator.clipboard.writeText(${JSON.stringify(p.content)}).then(()=>Toast.success('הועתק'))">
                  העתק תוכן
                </button>
              </div>
              <div style="font-size:12px;font-weight:600;color:var(--accent);margin-bottom:6px">${p.h1}</div>
              <div style="font-size:11px;color:var(--text);margin-bottom:8px;max-height:80px;overflow:hidden">${p.content.slice(0,300)}...</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap">
                ${(p.keywords||[]).map(k => `<span style="background:rgba(99,102,241,.15);color:var(--accent);border-radius:4px;padding:2px 8px;font-size:10px">${k}</span>`).join('')}
              </div>
            </div>`).join('')
          : UI.empty('אין עמודי עיר', '○');
      }
    }

    // ── Blog posts ────────────────────────────────────────────────────────
    const blogEl = document.getElementById('seoBlog');
    if (blogEl) {
      if (!blogRes.success) { blogEl.innerHTML = UI.error('שגיאה בטעינת פוסטים'); }
      else {
        blogEl.innerHTML = posts.length
          ? posts.map(p => `
            <div style="background:var(--surface-2,rgba(0,0,0,.04));border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:12px;direction:rtl">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
                <div>
                  <div style="font-weight:600;font-size:13px">${p.title}</div>
                  <div style="font-size:10px;color:var(--muted);font-family:var(--mono)">/${p.slug}</div>
                </div>
                <button class="btn btn-ghost" style="font-size:10px;padding:3px 8px"
                        onclick="navigator.clipboard.writeText(${JSON.stringify(p.content)}).then(()=>Toast.success('הועתק'))">
                  העתק
                </button>
              </div>
              <div style="font-size:11px;color:var(--muted);margin-bottom:8px">${p.meta}</div>
              <div style="font-size:12px;font-weight:600;margin-bottom:8px">${p.h1}</div>
              <div style="font-size:11px;color:var(--text);max-height:100px;overflow:hidden">${p.content.slice(0,400)}...</div>
            </div>`).join('')
          : UI.empty('אין פוסטים', '○');
      }
    }

    // ── Image prompts ─────────────────────────────────────────────────────
    const imagesEl = document.getElementById('seoImages');
    if (imagesEl) {
      if (!imagesRes.success) { imagesEl.innerHTML = UI.error('שגיאה בטעינת פרומפטים'); }
      else {
        const fireflyUrl = 'https://firefly.adobe.com/generate/images';
        imagesEl.innerHTML = images.length
          ? `
            <div style="margin-bottom:12px;padding:10px;background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.3);border-radius:8px;font-size:11px;direction:rtl">
              פרומפטים לשימוש עם <strong>Adobe Firefly</strong> —
              <a href="${fireflyUrl}" target="_blank" style="color:var(--accent)">פתח Adobe Firefly</a>
            </div>` +
            images.map(p => `
            <div style="background:var(--surface-2,rgba(0,0,0,.04));border:1px solid var(--border);border-radius:8px;padding:12px 14px;margin-bottom:10px;direction:rtl">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                <span style="font-weight:600;font-size:12px">${p.name}</span>
                <div style="display:flex;gap:6px">
                  <button class="btn btn-ghost" style="font-size:10px;padding:3px 8px"
                          onclick="navigator.clipboard.writeText(${JSON.stringify(p.prompt)}).then(()=>Toast.success('הועתק'))">
                    העתק פרומפט
                  </button>
                  <a href="${fireflyUrl}" target="_blank" class="btn btn-primary" style="font-size:10px;padding:3px 8px;text-decoration:none">
                    Firefly ↗
                  </a>
                </div>
              </div>
              <div style="font-size:11px;color:var(--muted);font-family:var(--mono);line-height:1.5">${p.prompt}</div>
            </div>`).join('')
          : UI.empty('אין פרומפטי תמונה', '○');
      }
    }
  }

  function _setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

  return { render, init, reload: load };
})();
