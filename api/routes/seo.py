"""
seo.py — SEO content endpoints

GET /api/seo/meta    — meta descriptions per page
GET /api/seo/cities  — city landing pages content
GET /api/seo/blog    — blog posts
GET /api/seo/images  — Adobe Firefly image prompts
"""
from flask import Blueprint
from api.middleware import require_auth, log_request, ok

bp = Blueprint("seo", __name__)


@bp.route("/seo/meta", methods=["GET"])
@require_auth
@log_request
def seo_meta():
    from engines.seo_engine import seo_engine
    return ok({"meta": seo_engine.generate_meta_descriptions()})


@bp.route("/seo/cities", methods=["GET"])
@require_auth
@log_request
def seo_cities():
    from engines.seo_engine import seo_engine
    pages = seo_engine.generate_city_pages()
    return ok({"pages": pages, "total": len(pages)})


@bp.route("/seo/blog", methods=["GET"])
@require_auth
@log_request
def seo_blog():
    from engines.seo_engine import seo_engine
    posts = seo_engine.generate_blog_posts()
    return ok({"posts": posts, "total": len(posts)})


@bp.route("/seo/images", methods=["GET"])
@require_auth
@log_request
def seo_images():
    from engines.seo_engine import seo_engine
    prompts = seo_engine.generate_image_prompts()
    return ok({"prompts": prompts, "total": len(prompts)})
