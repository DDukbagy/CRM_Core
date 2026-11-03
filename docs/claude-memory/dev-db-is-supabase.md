---
name: dev-db-is-supabase
description: "CRM_Core development uses the remote Supabase DB; tests stay on the local container, and remote schema changes need explicit approval"
metadata:
  node_type: memory
  pinned: false
  originSessionId: a768d9da-e5e9-4459-96d2-84b31697f25d
  modified: 2026-10-01T07:03:39.463Z
---

The user decided (2026-10-01, decision D1) that CRM_Core development uses the remote Supabase Postgres database, configured through `backend/.env`. That database holds real data, so treat it as an operational asset: run only read-only checks unless the user approves a change, and apply Alembic migrations to it only after explicit approval (CLAUDE.md §9). Never read or print `backend/.env`; let the code load it.

Automated tests and one-click verification stay on the local Docker Postgres (`make apitest`, `make apiverify`, settings from `backend/scripts/local_env.sh`) so they never touch Supabase data.

Why: the user said "db는 supabase로 쓸꺼야" while also choosing to develop and test locally without AWS deployment, so the remote DB is shared real data and the local container is the safe place for tests.
