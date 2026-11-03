---
name: demo-vs-production-deploy
description: CRM_Core demo (portfolio) runs on Render + Vercel + a separate demo Supabase; real launch will use AWS Copilot
metadata:
  node_type: memory
  type: project
  originSessionId: a768d9da-e5e9-4459-96d2-84b31697f25d
  modified: 2026-10-14T13:59:16.970Z
---

On 2026-10-14 a **temporary demo for the portfolio** was deployed:
- Backend on Render (`render.yaml`).
- Three Vercel projects: `crm-core-demo-web`, `crm-core-demo-customer`, `crm-core-demo-instructor`.
- A **separate demo Supabase project**.
- Everything tracks the `staging` branch.

The **real launch will be on AWS Copilot**, which is currently offline because of cost. Render is not the release path.

**Why:** The user wanted a public demo without AWS cost. Demo data must not mix with dev/prod, because payments and passes are retained for 5 years and cannot be cleaned up.

**How to apply:**
- Never treat Render or `render.yaml` as the production deploy target.
- Demo secrets live only in the Render and Vercel dashboards, never in `backend/.env` (that is the dev DB, see [[dev-db-is-supabase]]).
- After a staging merge, check that each Vercel project's top **Production** deployment is on the latest staging commit. Branch Tracking must be `staging` in every project; the web project was once left on `main`.
- Full steps: `docs/operations/demo-deploy.md`.
