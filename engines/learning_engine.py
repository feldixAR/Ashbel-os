
"""
learning_engine.py — Revenue Intelligence & Learning (Batch 9)
Measures what works, learns from results, improves autonomously.
"""
import datetime, logging, json
from dataclasses import dataclass, field
from typing import List, Dict, Optional

log = logging.getLogger(__name__)

@dataclass
class ChannelPerformance:
    channel: str; total_sent: int; replied: int; reply_rate: float
    deals_closed: int; conversion: float; avg_deal_size: int; roi_score: float

@dataclass
class MessagePerformance:
    template_key: str; audience: str; total_sent: int; replied: int
    reply_rate: float; positive: int; positive_rate: float; sample_message: str

@dataclass
class ABVariant:
    variant_id: str; label: str; message: str; audience: str
    sent: int; replied: int; reply_rate: float; winner: bool = False

@dataclass
class ABReport:
    audience: str; winner: ABVariant; loser: ABVariant
    improvement: float; recommendation: str

@dataclass
class ResourceAllocation:
    audience: str; channel: str; priority: int
    daily_quota: int; reason: str; roi_score: float

@dataclass
class AgentImprovement:
    agent_name: str; metric: str; old_value: float; new_value: float; action_taken: str

@dataclass
class PerformanceReport:
    generated_at: str; period_days: int; total_outreach: int; total_replies: int
    overall_reply_rate: float; total_deals: int; total_revenue: int
    channel_breakdown: List[ChannelPerformance]; message_breakdown: List[MessagePerformance]
    top_channel: str; top_audience: str

@dataclass
class ImprovementReport:
    generated_at: str; improvements: List[AgentImprovement]
    routing_updates: Dict[str, str]; template_updates: Dict[str, str]; summary: str

@dataclass
class LearningCycleResult:
    generated_at: str; performance: PerformanceReport; ab_reports: List[ABReport]
    resource_plan: List[ResourceAllocation]; improvements: ImprovementReport
    bottlenecks: List[dict]; next_actions: List[str]; cycle_summary: str

def _get_biz_short() -> str:
    try:
        from config.business_registry import get_active_business
        p = get_active_business()
        return p.name.split()[0]
    except Exception:
        return "אנחנו"

AB_VARIANTS = {
    "architects": [
        {"variant_id": "arch_a", "label": "A — תיק עבודות", "message": "שלום {name}, אני מ{biz}. ראיתי את הפרויקטים שלך — אשמח לשלוח תיק עבודות רלוונטי. מתאים?"},
        {"variant_id": "arch_b", "label": "B — שאלה פתוחה", "message": "שלום {name}, אני מ{biz} — ספק לאדריכלים. על איזה סוג פרויקטים אתה עובד עכשיו?"},
    ],
    "contractors": [
        {"variant_id": "cont_a", "label": "A — מחיר", "message": "שלום {name}, מ{biz}. יש לי הצעת מחיר תחרותית לפרויקט הנוכחי שלך. מעניין?"},
        {"variant_id": "cont_b", "label": "B — אספקה", "message": "שלום {name}, מ{biz}. אספקה תוך 48 שעות + תנאי אשראי לקבלנים. נשלח הצעה?"},
    ],
    "private": [
        {"variant_id": "priv_a", "label": "A — ייעוץ חינם", "message": "שלום {name}, מ{biz}. ייעוץ ראשוני חינם + הצעת מחיר ללא התחייבות. מתי נוח?"},
        {"variant_id": "priv_b", "label": "B — לפני/אחרי", "message": "שלום {name}, מ{biz}. יש לנו תמונות לפני/אחרי של עבודות בסביבה שלך — מעניין לראות?"},
    ],
}

def _build_message_performance() -> List[MessagePerformance]:
    try:
        from memory.memory_store import MemoryStore
        result = []
        for aud in ["architects","contractors","private"]:
            data = MemoryStore.read("message_performance", aud, {"sent":5,"replied":1,"positive":1})
            sent=data.get("sent",5); replied=data.get("replied",1); positive=data.get("positive",1)
            best=MemoryStore.get_best_template(aud) or ""
            result.append(MessagePerformance(template_key=aud,audience=aud,total_sent=sent,replied=replied,reply_rate=round(replied/sent*100,1) if sent else 0,positive=positive,positive_rate=round(positive/replied*100,1) if replied else 0,sample_message=best[:80]))
        return result
    except Exception: return []

def _detect_top_audience(leads: list) -> str:
    if not leads: return "architects"
    try:
        from engines.outreach_engine import _detect_audience
        counts: Dict[str,int] = {}
        for l in leads:
            aud=_detect_audience(l); counts[aud]=counts.get(aud,0)+1
        return max(counts.items(),key=lambda x:x[1])[0]
    except Exception: return "architects"

def measure_outreach_performance(period_days: int = 30) -> PerformanceReport:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        from services.storage.repositories.outreach_repo import OutreachRepository
        from services.storage.repositories.lead_repo import LeadRepository
        records=OutreachRepository().list_due_followup(); leads=LeadRepository().list_all()
        channels: Dict[str,dict] = {}
        for r in records:
            ch=r.channel or "whatsapp"
            if ch not in channels: channels[ch]={"sent":0,"replied":0,"deals":0}
            channels[ch]["sent"]+=1
            if r.status=="replied": channels[ch]["replied"]+=1
        channel_list=[]
        for ch,data in channels.items():
            sent=data["sent"]; replied=data["replied"]; rate=round(replied/sent*100,1) if sent else 0.0
            roi=rate*1.5 if ch=="whatsapp" else rate
            channel_list.append(ChannelPerformance(channel=ch,total_sent=sent,replied=replied,reply_rate=rate,deals_closed=data["deals"],conversion=round(data["deals"]/sent*100,1) if sent else 0,avg_deal_size=15000,roi_score=roi))
        channel_list.sort(key=lambda c:-c.roi_score)
        closed_leads=[l for l in leads if l.status=="סגור_זכה"]
        total_sent=len(records); total_replied=len([r for r in records if r.status=="replied"])
        overall_rate=round(total_replied/total_sent*100,1) if total_sent else 0.0
        return PerformanceReport(generated_at=now,period_days=period_days,total_outreach=total_sent,total_replies=total_replied,overall_reply_rate=overall_rate,total_deals=len(closed_leads),total_revenue=len(closed_leads)*15000,channel_breakdown=channel_list,message_breakdown=_build_message_performance(),top_channel=channel_list[0].channel if channel_list else "whatsapp",top_audience=_detect_top_audience(leads))
    except Exception as e:
        log.error(f"[Learning] performance failed: {e}")
        return PerformanceReport(generated_at=now,period_days=period_days,total_outreach=0,total_replies=0,overall_reply_rate=0.0,total_deals=0,total_revenue=0,channel_breakdown=[],message_breakdown=[],top_channel="whatsapp",top_audience="architects")

def run_ab_analysis(audience: str = None) -> List[ABReport]:
    reports=[]
    audiences=[audience] if audience else list(AB_VARIANTS.keys())
    for aud in audiences:
        variants_data=AB_VARIANTS.get(aud,[])
        if len(variants_data)<2: continue
        try:
            from memory.memory_store import MemoryStore
            perf_a=MemoryStore.read("ab_testing",f"{variants_data[0]['variant_id']}_performance",{"sent":10,"replied":2})
            perf_b=MemoryStore.read("ab_testing",f"{variants_data[1]['variant_id']}_performance",{"sent":10,"replied":3})
        except Exception: perf_a={"sent":10,"replied":2}; perf_b={"sent":10,"replied":3}
        sent_a=perf_a.get("sent",10); replied_a=perf_a.get("replied",2)
        sent_b=perf_b.get("sent",10); replied_b=perf_b.get("replied",3)
        rate_a=round(replied_a/sent_a*100,1) if sent_a else 0
        rate_b=round(replied_b/sent_b*100,1) if sent_b else 0
        va=ABVariant(variant_id=variants_data[0]["variant_id"],label=variants_data[0]["label"],message=variants_data[0]["message"],audience=aud,sent=sent_a,replied=replied_a,reply_rate=rate_a)
        vb=ABVariant(variant_id=variants_data[1]["variant_id"],label=variants_data[1]["label"],message=variants_data[1]["message"],audience=aud,sent=sent_b,replied=replied_b,reply_rate=rate_b)
        winner,loser=(vb,va) if rate_b>=rate_a else (va,vb)
        winner.winner=True; improvement=round(winner.reply_rate-loser.reply_rate,1)
        try:
            from memory.memory_store import MemoryStore
            stored_msg = winner.message.replace("{biz}", _get_biz_short())
            MemoryStore.set_best_template(aud, stored_msg)
        except Exception: pass
        reports.append(ABReport(audience=aud,winner=winner,loser=loser,improvement=improvement,recommendation=f"השתמש ב-{winner.label} — שיפור של {improvement}% בשיעור מענה."))
    return reports

def detect_best_channel(audience: str) -> str:
    try:
        from memory.memory_store import MemoryStore
        data=MemoryStore.read("channel_performance",audience,{})
        if data: return max(data.items(),key=lambda x:x[1].get("roi_score",0))[0]
    except Exception: pass
    return "whatsapp"

def detect_best_message(audience: str) -> str:
    try:
        from memory.memory_store import MemoryStore
        t=MemoryStore.get_best_template(audience)
        if t: return t
    except Exception: pass
    from engines.outreach_engine import build_initial_message
    return build_initial_message(audience,"{name}")

def allocate_resources(leads: list = None) -> List[ResourceAllocation]:
    if leads is None:
        try:
            from services.storage.repositories.lead_repo import LeadRepository
            leads=LeadRepository().list_all()
        except Exception: leads=[]
    try:
        from engines.outreach_engine import _detect_audience
        counts: Dict[str,int]={}
        for l in leads: aud=_detect_audience(l); counts[aud]=counts.get(aud,0)+1
    except Exception: counts={}
    roi_map={"architects":8.5,"contractors":7.0,"private":5.5}
    total_roi=sum(roi_map.values()); total_daily=15
    allocs=[]; sorted_auds=sorted(roi_map.keys(),key=lambda x:-roi_map[x])
    for i,aud in enumerate(sorted_auds):
        roi=roi_map[aud]; quota=max(1,round(total_daily*roi/total_roi))
        allocs.append(ResourceAllocation(audience=aud,channel=detect_best_channel(aud),priority=i+1,daily_quota=quota,reason=f"ROI score {roi} — {counts.get(aud,0)} לידים פעילים",roi_score=roi))
    return allocs

def auto_improve_agents() -> ImprovementReport:
    now=datetime.datetime.now(datetime.timezone.utc).isoformat(); improvements=[]; routing_updates={}; template_updates={}
    try:
        from memory.memory_store import MemoryStore
        from agents.base.agent_registry import agent_registry
        for agent in agent_registry.list_agents():
            agent_id=getattr(agent,"agent_id",""); name=getattr(agent,"name","")
            if not agent_id: continue
            stats=MemoryStore.get_agent(agent_id,"stats",{"success":0,"total":0})
            total=stats.get("total",0); success=stats.get("success",0)
            if total<5: continue
            rate=success/total
            if rate<0.6:
                old_model=MemoryStore.get_agent(agent_id,"model","claude_haiku")
                MemoryStore.set_routing_override(f"agent_{agent_id}","claude_sonnet")
                routing_updates[agent_id]="claude_sonnet"
                improvements.append(AgentImprovement(agent_name=name,metric="success_rate",old_value=round(rate*100,1),new_value=0,action_taken=f"שדרוג מודל מ-{old_model} ל-claude_sonnet"))
        for aud in ["architects","contractors","private"]:
            best=MemoryStore.get_best_template(aud)
            if best: template_updates[aud]=best[:50]+"..."
    except Exception as e: log.error(f"[Learning] improve failed: {e}")
    return ImprovementReport(generated_at=now,improvements=improvements,routing_updates=routing_updates,template_updates=template_updates,summary=f"מחזור למידה: {len(improvements)} שיפורים, {len(routing_updates)} עדכוני ניתוב, {len(template_updates)} תבניות.")

def detect_bottlenecks_deep() -> List[dict]:
    bottlenecks=[]
    try:
        from services.storage.repositories.lead_repo import LeadRepository
        from services.storage.repositories.outreach_repo import OutreachRepository
        leads=LeadRepository().list_all(); records=OutreachRepository().list_due_followup()
        total=len(leads)
        if not total: return [{"category":"אין נתונים","severity":"info","suggestion":"הוסף לידים למערכת"}]
        no_phone=[l for l in leads if not (l.phone or "").strip()]
        if len(no_phone)>total*0.3: bottlenecks.append({"category":"לידים ללא טלפון","count":len(no_phone),"severity":"high","description":f"{len(no_phone)} לידים ללא מספר טלפון","suggestion":"השלם מספרי טלפון לכל הלידים"})
        total_sent=len(records); total_replied=len([r for r in records if r.status=="replied"])
        if total_sent>10:
            rate=total_replied/total_sent
            if rate<0.1: bottlenecks.append({"category":"שיעור מענה נמוך","count":total_sent,"severity":"high","description":f"שיעור מענה {round(rate*100,1)}%","suggestion":"שנה את תבנית הפנייה"})
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        overdue=[r for r in records if (r.next_followup or "")<now and r.status=="pending"]
        if len(overdue)>5: bottlenecks.append({"category":"follow-up פגי תוקף","count":len(overdue),"severity":"medium","description":f"{len(overdue)} פניות שלא טופלו","suggestion":"הפעל מחזור outreach יומי"})
        cold=[l for l in leads if (l.score or 0)<30]
        if len(cold)>total*0.5: bottlenecks.append({"category":"רוב הלידים קרים","count":len(cold),"severity":"medium","description":f"{len(cold)} לידים עם ציון נמוך","suggestion":"שפר מקורות לידים"})
        try:
            from services.storage.repositories.goal_repo import GoalRepository
            if not GoalRepository().list_active(): bottlenecks.append({"category":"אין יעדים עסקיים","count":0,"severity":"high","description":"לא הוגדרו יעדים עסקיים","suggestion":"הגדר יעד עסקי"})
        except Exception: pass
    except Exception as e: log.error(f"[Learning] bottleneck failed: {e}")
    return bottlenecks

def record_reply(outreach_id: str, reply_text: str = "", positive: bool = True) -> bool:
    try:
        from engines.outreach_engine import update_pipeline_status
        update_pipeline_status(outreach_id,"replied",reply_text)
        try:
            from memory.memory_store import MemoryStore
            ch_data=MemoryStore.read("channel_performance","whatsapp",{"sent":0,"replied":0})
            ch_data["replied"]=ch_data.get("replied",0)+1
            MemoryStore.write("channel_performance","whatsapp",ch_data)
        except Exception: pass
        return True
    except Exception as e: log.error(f"[Learning] record_reply failed: {e}"); return False

def full_learning_cycle() -> LearningCycleResult:
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    performance=measure_outreach_performance(); ab_reports=run_ab_analysis()
    resource_plan=allocate_resources(); improvements=auto_improve_agents(); bottlenecks=detect_bottlenecks_deep()
    next_actions=[]
    if bottlenecks: next_actions.append(f"טפל ב-{len(bottlenecks)} חסמים שזוהו")
    if ab_reports: next_actions.append(f"עדכן תבנית פנייה ל-{ab_reports[0].audience} לפי A/B")
    if resource_plan: next_actions.append(f"הקדש {resource_plan[0].daily_quota} פניות יומיות ל-{resource_plan[0].audience}")
    next_actions.extend(["הרץ מחזור outreach יומי","בדוק תגובות ועדכן סטטוסים"])
    summary=f"מחזור למידה: {performance.total_outreach} פניות, {performance.overall_reply_rate}% מענה, {len(bottlenecks)} חסמים, {len(ab_reports)} A/B."
    try:
        from memory.memory_store import MemoryStore
        MemoryStore.set_global("last_learning_cycle",now); MemoryStore.set_global("last_reply_rate",performance.overall_reply_rate)
        MemoryStore.set_global("top_channel",performance.top_channel); MemoryStore.set_global("top_audience",performance.top_audience)
    except Exception: pass
    return LearningCycleResult(generated_at=now,performance=performance,ab_reports=ab_reports,resource_plan=resource_plan,improvements=improvements,bottlenecks=bottlenecks,next_actions=next_actions,cycle_summary=summary)

def build_roi_report() -> str:
    perf=measure_outreach_performance()
    lines=["דוח ROI — AshbelOS Learning Engine","="*45,f"תאריך: {perf.generated_at[:19].replace('T',' ')}",f"תקופה: {perf.period_days} ימים","="*45,"📊 סיכום",f"  סה\"כ פניות: {perf.total_outreach}",f"  מענה: {perf.total_replies} ({perf.overall_reply_rate}%)",f"  עסקאות: {perf.total_deals}",f"  הכנסה: ₪{perf.total_revenue:,}",f"  ערוץ מוביל: {perf.top_channel}","="*45]
    bottlenecks=detect_bottlenecks_deep()
    if bottlenecks:
        lines.append("🚧 חסמים")
        for b in bottlenecks:
            icon="🔴" if b["severity"]=="high" else "🟡"
            lines.append(f"  {icon} {b['category']}: {b.get('description','')}")
            lines.append(f"     → {b['suggestion']}")
    return "\n".join(lines)


# ── LearningEngineService — unified API for executor + scheduler ──────────────

class LearningEngineService:
    """Stable method wrapper over module-level learning functions."""

    def run_learning_cycle(self) -> LearningCycleResult:
        return full_learning_cycle()

    def build_performance_report(self, period_days: int = 30) -> PerformanceReport:
        return measure_outreach_performance(period_days)

    def get_ab_reports(self) -> List[ABReport]:
        return run_ab_analysis()

    def get_resource_allocation(self) -> List[ResourceAllocation]:
        return allocate_resources()


learning_engine = LearningEngineService()
