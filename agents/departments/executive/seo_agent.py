"""
SEOAgent — Website SEO analysis, gap detection, and content generation.

Handles:
    (seo, analyze_website)
    (seo, generate_seo_content)
    (seo, seo_report)
    (seo, city_pages)
    (seo, blog_posts)
"""
import logging
from services.storage.models.task import TaskModel
from services.execution.executor  import ExecutionResult
from agents.base.base_agent       import BaseAgent

log = logging.getLogger(__name__)

_HANDLED = {
    ("seo", "analyze_website"),
    ("seo", "generate_seo_content"),
    ("seo", "seo_report"),
    ("seo", "city_pages"),
    ("seo", "blog_posts"),
    ("seo", "meta_tags"),
}


class SEOAgent(BaseAgent):
    agent_id   = "builtin_seo_agent_v1"
    name       = "SEO Agent"
    department = "executive"
    version    = 1

    def can_handle(self, task_type: str, action: str) -> bool:
        return (task_type, action) in _HANDLED

    def execute(self, task: TaskModel) -> ExecutionResult:
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[SEOAgent] error: {e}", exc_info=True)
            return ExecutionResult(success=False, message=f"שגיאה: {e}", output={"error": str(e)})

    def _run(self, task: TaskModel) -> ExecutionResult:
        from engines.seo_engine import SEOEngine
        from config.business_registry import get_active_business

        profile = get_active_business()
        engine  = SEOEngine()
        params  = self._input_params(task)

        if task.action == "city_pages":
            pages = engine.generate_city_pages()
            return ExecutionResult(success=True,
                                   message=f"נוצרו {len(pages)} עמודי עיר",
                                   output={"city_pages": pages, "count": len(pages)})

        if task.action == "blog_posts":
            posts = engine.generate_blog_posts()
            return ExecutionResult(success=True,
                                   message=f"נוצרו {len(posts)} פוסטי בלוג",
                                   output={"blog_posts": posts, "count": len(posts)})

        if task.action == "meta_tags":
            metas = engine.generate_meta_descriptions()
            return ExecutionResult(success=True,
                                   message=f"נוצרו {len(metas)} תגי meta",
                                   output={"meta_tags": metas})

        if task.action == "analyze_website":
            site_url = params.get("site_url") or profile.site_url or ""
            analysis = {}
            suggestions = []
            try:
                from skills.website_growth import site_audit, seo_intelligence
                audit = site_audit(site_url) if site_url else None
                if audit:
                    intel = seo_intelligence(audit, profile.service_areas[:5])
                    analysis = {"score": audit.score, "title": audit.title,
                                "missing_schema": intel.missing_schema}
            except Exception:
                pass
            return ExecutionResult(
                success=True,
                message=f"ניתוח אתר: {site_url or profile.name}",
                output={"site_url": site_url, "analysis": analysis,
                        "keywords": profile.site_keywords},
            )

        if task.action == "generate_seo_content":
            city_pages    = engine.generate_city_pages()
            blog_posts    = engine.generate_blog_posts()
            meta_tags     = engine.generate_meta_descriptions()
            image_prompts = engine.generate_image_prompts()
            return ExecutionResult(
                success=True,
                message=f"תוכן SEO: {len(city_pages)} עמודי עיר, {len(blog_posts)} פוסטים, {len(meta_tags)} meta",
                output={"city_pages": city_pages, "blog_posts": blog_posts,
                        "meta_tags": meta_tags, "image_prompts": image_prompts},
            )

        # seo_report (default)
        metas  = engine.generate_meta_descriptions()
        cities = engine.generate_city_pages()
        posts  = engine.generate_blog_posts()
        report_lines = [
            f"=== דוח SEO — {profile.name} ===",
            f"אתר: {profile.site_url or '(לא מוגדר)'}",
            f"מילות מפתח: {', '.join(profile.site_keywords[:5])}",
            "",
            f"תגי Meta: {len(metas)} עמודים",
            f"עמודי עיר: {len(cities)} עמודים",
            f"פוסטי בלוג: {len(posts)} פוסטים",
            "",
            f"אזורי שירות: {', '.join(profile.service_areas[:5])}",
        ]
        return ExecutionResult(
            success=True,
            message="\n".join(report_lines),
            output={"meta_count": len(metas), "city_count": len(cities),
                    "blog_count": len(posts), "site_url": profile.site_url,
                    "keywords": profile.site_keywords, "service_areas": profile.service_areas},
        )
