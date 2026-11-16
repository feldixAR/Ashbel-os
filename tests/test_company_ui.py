"""Real Chromium smoke checks of the new owner work surface, using synthetic API data."""
import os
from pathlib import Path

import pytest

if os.getenv("RUN_COMPANY_UI_TESTS") != "1":
    pytest.skip("Chromium UI job runs separately", allow_module_level=True)

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def page():
    with sync_playwright() as browser_runtime:
        browser = browser_runtime.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        page.set_content('<html lang="he" dir="rtl"><body><main id="workPane"></main></body></html>')
        page.add_style_tag(content=(ROOT / "ui/css/app.css").read_text())
        page.add_style_tag(content=(ROOT / "ui/css/company.css").read_text())
        page.add_script_tag(content="""
window.apiCalls = [];
window.reviewFails = false;
window.pollHealth = 'read_ok';
window.candidates = []; window.operations = [];
window.work = {id:'synthetic-work',department:'engineering',code:'review_spec',
 subject:'בדיקת מפרט סינתטי',status:'created',version:1,
 source_ref:'https://example.invalid/source',
 artifact:{title:'<img src=x onerror="window.injected=true">',summary:'מפרט לבדיקה',missing:['זיגוג']},
 missing:['זיגוג']};
window.API = {
 async get(path) {
   window.apiCalls.push({method:'GET',path});
   if(path.startsWith('/business_events/work_items')) return {success:true,data:{items:[{...window.work}]}};
   if(path==='/business_events') return {success:true,data:{events:[{id:'synthetic-event',status:'analyzed',source_ref:'javascript:window.injected=true',output:{ceo_decision:{summary:'בדוק מפרט לפני תמחור'},departments:{}}}]}};
   if(path==='/source_discovery') return {success:true,data:{enabled:true,sources:[],candidates:window.candidates}};
   if(path==='/source_sync/status') return {success:true,data:{writer_configured:false,operations:window.operations}};
   return {success:false,_status:404};
 },
 async post(path,body) {
   window.apiCalls.push({method:'POST',path,body});
   if(path.endsWith('/review')){
     if(window.reviewFails) return {success:false,_status:409};
     window.work={...window.work,status:'reported_complete',version:2,completion_evidence:{note:body.note.trim(),evidence_ref:body.evidence_ref.trim(),kind:'owner_reported'}};
     return {success:true,data:{item:{...window.work}}};
   }
   if(path==='/business_events/poll')return {success:true,data:{source_health:window.pollHealth}};
   return {success:false,_status:503};
 }
};
""")
        page.add_script_tag(content=(ROOT / "ui/js/panels/company.js").read_text())
        page.evaluate("CompanyPanel.render(document.getElementById('workPane'))")
        yield page
        context.close()
        browser.close()


def test_read_only_render_and_untrusted_source_content_are_safe(page):
    assert page.get_by_text("בדוק מפרט לפני תמחור", exact=False).count() >= 1
    assert page.locator(".company-output img").count() == 0
    assert page.locator('a[href^="javascript:"]').count() == 0
    assert page.evaluate("window.injected") is None
    assert page.evaluate("window.apiCalls.every(call=>call.method==='GET')") is True
    assert page.get_by_text("חיבור כתיבה ל־CRM טרם הוגדר.", exact=True).is_visible()


def test_specific_work_review_uses_version_and_readback(page):
    page.get_by_role("button", name="דווח ביצוע", exact=True).click()
    page.get_by_label("מה בוצע או מה השתנה?").fill("נבדק המפרט הסינתטי")
    page.get_by_label("קישור לאסמכתה או לתיעוד").fill("https://example.invalid/evidence")
    page.get_by_role("button", name="שמור דיווח", exact=True).click()
    page.get_by_text("בוצע לפי דיווח — לא אומת עצמאית", exact=True).wait_for()
    calls = page.evaluate("window.apiCalls")
    writes = [call for call in calls if call["method"] == "POST"]
    assert len(writes) == 1
    assert writes[0]["body"] == {
        "expected_version": 1, "action": "report_complete",
        "note": "נבדק המפרט הסינתטי", "evidence_ref": "https://example.invalid/evidence",
    }
    assert any(call["method"] == "GET" and "work_items" in call["path"]
               for call in calls[calls.index(writes[0])+1:])
    assert page.get_by_role("button", name="דווח ביצוע", exact=True).count() == 0


def test_conflict_does_not_claim_verified_completion_or_retry(page):
    page.evaluate("window.reviewFails=true")
    page.get_by_role("button", name="דווח ביצוע", exact=True).click()
    page.get_by_label("מה בוצע או מה השתנה?").fill("בדיקה")
    page.get_by_label("קישור לאסמכתה או לתיעוד").fill("https://example.invalid/evidence")
    page.get_by_role("button", name="שמור דיווח", exact=True).click()
    page.get_by_text("הנתונים השתנו. רענן לפני פעולה נוספת.", exact=True).wait_for()
    assert page.evaluate("window.apiCalls.filter(call=>call.method==='POST').length") == 1
    assert page.get_by_text("השמירה אומתה בקריאה חוזרת.", exact=True).count() == 0
    assert page.evaluate("window.work.status") == "created"


def test_missing_source_and_mobile_layout_are_explicit(page):
    page.evaluate("window.pollHealth='not_configured'")
    page.get_by_role("button", name="בדוק כעת את המקורות והאירועים", exact=True).click()
    page.get_by_text("מקור הנתונים אינו מחובר או אינו זמין; לא הוצג ביצוע חדש.", exact=True).wait_for()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    for button in page.get_by_role("button").all():
        assert button.bounding_box()["height"] >= 39
    output = ROOT / "test-results"
    output.mkdir(exist_ok=True)
    page.screenshot(path=str(output / "company-mobile.png"), full_page=True)


def prepare_candidate_preview(page):
    page.evaluate("""
window.candidates=[{task_id:'synthetic-candidate',title:'הזדמנות סינתטית',source_url:'https://example.invalid/primary',found_at:'2026-11-17T08:00:00Z'}];
const originalPost=window.API.post.bind(window.API);
window.API.post=async(path,body)=>{
 if(path.includes('/candidates/')){window.apiCalls.push({method:'POST',path,body});return {success:true,data:{candidate:{...body.candidate,verification_id:'verified-primary'}}};}
 if(path==='/source_sync/preview'){
  window.apiCalls.push({method:'POST',path,body});
  const row=Array(44).fill('');row[7]='הזדמנות סינתטית';row[28]='https://example.invalid/primary';
  window.operations=[{id:'exact-operation',status:'prepared'}];
  return {success:true,data:{operation_id:'exact-operation',status:'prepared',preview_hash:'server-preview-fingerprint',row}};
 }
 if(path.endsWith('/commit')){
  window.apiCalls.push({method:'POST',path,body});
  window.operations=[{id:'exact-operation',status:'committed'}];
  return {success:true,data:{status:'committed'}};
 }
 return originalPost(path,body);
};
""")
    page.evaluate("CompanyPanel.render(document.getElementById('workPane'))")
    page.get_by_text("בדוק פרטים והכן קליטה", exact=True).click()
    page.locator('input[type=checkbox]').check()
    page.get_by_role("button", name="אמת מקור והצג תצוגה מקדימה", exact=True).click()
    page.get_by_role("button", name="אשר קליטה של רשומה זו", exact=True).wait_for()


def test_source_review_is_preview_only_until_exact_commit_and_readback(page):
    prepare_candidate_preview(page)
    assert page.evaluate("window.apiCalls.filter(c=>c.path.endsWith('/commit')).length") == 0
    page.get_by_role("button", name="אשר קליטה של רשומה זו", exact=True).click()
    page.wait_for_function("window.operations[0]?.status==='committed'")
    calls=page.evaluate("window.apiCalls")
    commits=[call for call in calls if call["path"].endswith("/commit")]
    assert commits == [{"method":"POST","path":"/source_sync/exact-operation/commit",
                        "body":{"preview_hash":"server-preview-fingerprint"}}]
    verify=[call for call in calls if "/candidates/" in call["path"]][0]
    assert verify["body"]["review_confirmed"] is True
    assert "content_sha256" not in verify["body"]["candidate"]
    assert "verification" not in verify["body"]["candidate"]
    assert any(call["method"]=="GET" and call["path"]=="/source_sync/status"
               for call in calls[calls.index(commits[0])+1:])


def test_editing_candidate_invalidates_exact_preview(page):
    prepare_candidate_preview(page)
    page.get_by_label("יישוב", exact=True).fill("יישוב סינתטי")
    assert page.get_by_role("button", name="אשר קליטה של רשומה זו", exact=True).count()==0
    assert page.evaluate("window.apiCalls.filter(c=>c.path.endsWith('/commit')).length")==0


def test_concurrent_change_cannot_be_mistaken_for_own_review_readback(page):
    page.evaluate("""
const originalGet=window.API.get.bind(window.API);
window.API.get=async(path)=>{
 const result=await originalGet(path);
 if(path.includes('/work_items')&&window.work.version===2)result.data.items[0]={...window.work,version:3};
 return result;
};
""")
    page.get_by_role("button", name="דווח ביצוע", exact=True).click()
    page.get_by_label("מה בוצע או מה השתנה?").fill("בדיקה")
    page.get_by_label("קישור לאסמכתה או לתיעוד").fill("https://example.invalid/evidence")
    page.get_by_role("button", name="שמור דיווח", exact=True).click()
    page.get_by_text("הבקשה התקבלה, אך השמירה טרם אומתה. רענן לפני פעולה נוספת.", exact=True).wait_for()
    assert page.get_by_text("השמירה אומתה בקריאה חוזרת.", exact=True).count()==0
