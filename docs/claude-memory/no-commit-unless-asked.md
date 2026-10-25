---
name: no-commit-unless-asked
description: "Never commit, push, or create PRs in CRM_Core unless the user explicitly asks, and never ask or offer to commit/push"
metadata:
  node_type: memory
  pinned: true
  originSessionId: 18d84e84-4ce3-421a-8411-3e8f632df09b
  modified: 2026-09-27T10:43:22.268Z
---

In the CRM_Core project, the user handles commits and pull requests themselves. After finishing any code or doc change, leave the changes uncommitted in the working tree and report what changed. Do not run `git commit`, `git push`, or `gh pr create` unless the user explicitly asks for that action in the current request. A request to commit once does not carry over to later work in the same or future sessions.

Also do not ask whether to commit or push, and do not propose commit plans or commit messages as a question at the end of a change. The user said: "커밋푸시는 질문하지말것 필요하면 내가 요구함" (don't ask about commit/push; I will request it when needed). Even when an earlier message said "commit after approval", a later approval of the diff alone is not a commit request if the user has restated this rule.

Why: the user said directly that commits and PRs are theirs to make, and that Claude should not commit or ask about committing unless they request it.

Related context the user gave at the same time: the project is currently in development only and is not being deployed to AWS, so deploy-related steps (Release PRs, `make prtrigger`) are not part of the normal flow.
