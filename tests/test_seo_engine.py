"""
Tests for SEOEngine — deterministic content, no AI.
"""
import pytest
from engines.seo_engine import SEOEngine, build_seo_structure, suggest_keywords


def test_meta_descriptions_all_pages():
    engine = SEOEngine()
    meta = engine.generate_meta_descriptions()
    for key in ("home", "products", "about", "process", "knowledge", "contact"):
        assert key in meta
        assert len(meta[key]) <= 155
        assert len(meta[key]) > 0


def test_city_pages_structure():
    engine = SEOEngine()
    pages = engine.generate_city_pages()
    assert len(pages) >= 1
    for page in pages:
        assert "slug" in page
        assert "title" in page
        assert "h1" in page
        assert "content" in page
        assert "keywords" in page
        assert isinstance(page["keywords"], list)


def test_blog_posts_structure():
    engine = SEOEngine()
    posts = engine.generate_blog_posts()
    assert len(posts) == 3
    for post in posts:
        assert "slug" in post
        assert "title" in post
        assert "meta" in post
        assert "h1" in post
        assert "content" in post
        assert len(post["content"]) > 100


def test_image_prompts_structure():
    engine = SEOEngine()
    prompts = engine.generate_image_prompts()
    assert len(prompts) == 8
    for p in prompts:
        assert "name" in p
        assert "prompt" in p
        assert len(p["prompt"]) > 50


def test_meta_length_constraint():
    engine = SEOEngine()
    for key, val in engine.generate_meta_descriptions().items():
        assert len(val) <= 155, f"Meta for {key} too long: {len(val)}"


def test_legacy_build_seo_structure():
    result = build_seo_structure("חלונות", ["חלונות אלומיניום"])
    assert "title" in result
    assert "meta_description" in result
    assert "h1" in result


def test_legacy_suggest_keywords():
    kws = suggest_keywords("חלונות")
    assert isinstance(kws, list)
    assert len(kws) > 0
