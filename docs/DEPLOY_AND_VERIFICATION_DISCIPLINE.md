# AshbelOS — Deploy and Verification Discipline

> Binding rules for all deployment, commit, and release work.

---

## Branch Model

| Branch | Role |
|--------|------|
| `master` | Production-ready. Railway auto-deploys from this branch. |
| `fix/*` | Hotfix branches. Must be merged to master before deploy. |
| `feat/*` | Feature branches. Must be reviewed before merge to master. |
| `claude/*` | Agent-managed branches. Work committed here must also be pushed to master. |

**Railway deploys exclusively from `master`.** No other branch triggers production deploy.

---

## Commit Discipline

Every commit must:
1. Be on `master` (or merged to master before deploy)
2. Have a descriptive message (what changed + why)
3. Include the session URL as trailer
4. Never include secrets (`.env`, credentials, API keys)
5. Never skip pre-commit hooks (`--no-verify` is forbidden)

---

## Push Discipline

Always push to BOTH:
```bash
git push origin master                                    # Railway deploy branch
git push -u origin master:claude/review-and-continue-*  # Feature branch (if active)
```

---

## Build Trigger

Railway builds are triggered by push to master. To force a redeploy without code changes:
```json
// railway.json
"_buildTrigger": <unix_timestamp>  // increment by ~10000 per session
```

---

## Version Cache-Busting

Increment `?v=p<N>` on all static asset URLs in `ui/index.html` with every meaningful UI release.
Current pattern: `?v=p20` → bump to `?v=p21` etc.

---

## Health Check

Production endpoint: `GET /api/health`
Expected response: `{"success": true, "data": {"status": "ok", "db": true}}`

Verify before declaring deploy complete.

---

## QA Discipline

Minimum QA checklist before any release:
- [ ] `python -m pytest tests/ -q --tb=no` — all tests pass (minus known pre-existing failures)
- [ ] `GET /api/health` → 200 OK + db: true
- [ ] Key routes exercised via Flask test client or curl
- [ ] UI smoke check: home, leads, discovery, tasks, approvals, agents
- [ ] Mobile layout check: sidebar toggles, no overflow, tap targets accessible

---

## Done Criteria

A feature or fix is NOT done until:
1. All required code is committed to `master`
2. `master` is pushed to `origin/master`
3. Railway build is triggered
4. `GET /api/health` returns 200 with `db: true`
5. Changed UI is visibly live (version bump visible in page source)

"Tests passed" alone is NOT done. "Code written" alone is NOT done.

---

## Current Production State

- Production URL: `https://ashbel-os-production.up.railway.app`
- Deploy branch: `master`
- Last verified commit: `ba4e9b2` (2026-04-12 session)
- Active feature branch: `claude/review-and-continue-tjI3K`
- Railway config: `railway.json` at repo root
