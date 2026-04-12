# AshbelOS — UI/UX and Mobile Rules

> Binding design and implementation rules for all AshbelOS UI work.

---

## Design System

### Colors (CSS Variables)
```css
--bg:       #f0f4f8    /* page background — light blue-grey */
--surface:  #ffffff    /* card/panel surface */
--surface2: #f7f9fc    /* secondary surface */
--border:   #dde3ec    /* standard border */
--border2:  #c8d0db    /* stronger border */
--text:     #1a2233    /* primary text */
--muted:    #6b7a99    /* secondary text */
--accent:   #2563eb    /* primary accent blue */
--green:    #16a34a    /* positive / active */
--amber:    #d97706    /* warning */
--red:      #dc2626    /* alert / error */
--mono:     'JetBrains Mono', monospace
--radius:   8px
```

### Typography
- Panel titles: 14px, font-weight 700
- Section titles: 12px, font-weight 600
- Body text: 12–13px
- Labels/meta: 10–11px, color: var(--muted)
- Numbers/scores: font-family: var(--mono)

### Component Hierarchy

| Component | Class | Use |
|-----------|-------|-----|
| Primary CTA | `btn btn-primary` | Main next action |
| Secondary | `btn btn-secondary` | Alternative action |
| Ghost | `btn btn-ghost` | Utility / filter |
| Insight strip | `UI.insightStrip()` | State summary chips |
| Next action | `UI.nextAction()` | Primary recommended action |
| Guided empty | `UI.guidedEmpty()` | Empty state with CTA |
| Widget bar | `UI.widgetBar()` | Key metric chips |
| Score badge | `UI.scoreBadge()` | Lead/deal score |

---

## Mobile-First Rules (≤640px)

### Shell
- Sidebar: `position: fixed`, `right: -260px` default, `right: 0` when `.sidebar-open`
- Overlay backdrop: `#sidebarOverlay` shows when sidebar open
- Main area fills 100% width when sidebar closed
- Header shows hamburger button `#sidebarToggle`

### Layout
- Single-column layouts: no multi-column grids on ≤640px
- Tables → cards: hide table `<thead>`, convert `<tr>` to flex column cards
- No horizontal overflow: all content wraps or truncates
- Panel padding: 12px on mobile (16-20px desktop)

### Touch Targets
- All buttons: `min-height: 40px`
- Filter pills: `min-height: 36px`, `padding: 8px 14px`
- Form inputs: `min-height: 44px`, `font-size: 16px` (prevents iOS zoom)
- Nav items: `padding: 12px 16px`

### Typography
- Minimum readable size: 11px
- No text smaller than 10px that conveys critical information
- Long strings: `text-overflow: ellipsis`, `overflow: hidden`, `white-space: nowrap`

---

## Empty States (Mandatory Guided)

```javascript
// NEVER use plain UI.empty() for primary content areas
// ALWAYS use guided empty with CTA

// Good:
UI.guidedEmpty(
  'אין לידים במערכת',
  '◎',
  '📂 יבא קובץ לידים',
  'UploadModal.open()'
)

// Bad:
UI.empty('אין לידים', '○')  // no CTA — not allowed for primary content
```

---

## State → Recommendation → Action Pattern

Every data-bearing panel must render this pattern on load:

```javascript
// 1. Widget bar (state numbers)
UI.widgetBar([...])

// 2. Insight strip (what matters)
UI.insightStrip([{ icon, text, cls }])

// 3. Next action (what to do)
UI.nextAction(description, buttonLabel, onclickJs)

// 4. Content list/grid
```

---

## Navigation Rules

- Primary work surfaces: rendered first in nav, no group separator needed
- Secondary/admin: demoted to bottom group, smaller visual weight
- `command.js`, `workspace.js`: hidden from nav (legacy)
- Active nav item: `nav-item active` class

---

## Modal Rules

- Overlay: `position: fixed`, `inset: 0`, `z-index: 200`, backdrop `rgba(0,0,0,0.4)`
- Modal box: `max-width: 500px`, `max-height: 85vh`, `overflow-y: auto`
- Close: top-right ✕ button + click-outside-to-close
- Mobile: `width: calc(100% - 32px)`, `margin: 16px auto`

---

## RTL Rules

- All content containers: `dir="rtl"`
- Text alignment: right by default
- Icon placement: right of text for Hebrew labels
- Flex row direction: adjust for RTL where needed (`flex-direction: row-reverse` for LTR items)
- Phone numbers: `direction: ltr`, `display: inline-block`

---

## Performance Rules

- No blocking synchronous operations in `render()`
- `init()` triggers all async data loads
- Show `UI.loading()` immediately while loading
- No layout shift after data loads (pre-size containers where possible)
- `?v=p<N>` cache-busting on all static assets — bump on every meaningful release
