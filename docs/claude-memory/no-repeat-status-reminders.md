---
name: no-repeat-status-reminders
description: "Don't keep appending the same pending-status reminder (e.g. \"PR not merged yet\") to every reply once the user knows"
metadata:
  node_type: memory
  type: feedback
  originSessionId: a768d9da-e5e9-4459-96d2-84b31697f25d
  modified: 2026-10-14T09:40:48.031Z
---

Once the user has been told something is pending (e.g. a PR is not merged yet), don't repeat that reminder in later replies.

**Why:** The user said "머지하지않았다는건 그만 알려줘도돼" (2026-10-14) after the same note was appended to several answers in a row.

**How to apply:** State a pending item once. Mention it again only when it changes, blocks the current step, or the user asks. Related: [[no-commit-unless-asked]]
