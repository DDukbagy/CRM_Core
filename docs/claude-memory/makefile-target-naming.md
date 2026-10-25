---
name: makefile-target-naming
description: "CRM_Core Makefile targets must use short <target><action> lowercase names like iweb, clear enough to know what they do"
metadata:
  node_type: memory
  pinned: false
  originSessionId: a768d9da-e5e9-4459-96d2-84b31697f25d
  modified: 2026-10-01T05:38:13.413Z
---

In CRM_Core, Makefile target names follow one rule the user asked for: short and simple like `iweb`, but clear about what they do. The form is `<대상><동작>` in lowercase with no separators. The target prefixes are `api` (backend), `web` (admin/instructor Next.js web), `c` (customer app), `i` (instructor app), `db`, `mig` (Alembic), `dock` (Docker), `git` (branch/release), `aws`, and `stg` / `prod` (Copilot environments). Examples: `apitest`, `apiverify`, `webcheck`, `ccheck`, `dbreset`, `migcheck`, `gitpr`. The only exceptions are `help`, `check` (all checks) and `grep`.

Why: the user said the names should be "iweb처럼 간략하고 간단하게 하되 뭔지 확실히 알 수 있게끔 통일" (short and simple like iweb, but unmistakable, and unified). When adding or renaming a target, follow this rule and update CLAUDE.md §8, the READMEs and docs/operations/dev-runbook.md in the same change.
