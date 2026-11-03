---
name: keep-existing-features
description: "CRM_Core cleanup never removes features, placeholder pages, or buttons, and never changes features/UI on its own; only completely dead code may be deleted"
metadata:
  node_type: memory
  type: feedback
  originSessionId: a768d9da-e5e9-4459-96d2-84b31697f25d
  modified: 2026-10-02T09:46:34.481Z
---

In CRM_Core, the cleanup goal is defect fixing and structural organization, not feature reduction.

- Do not delete existing features, pages, or buttons. This includes "준비 중" (placeholder) pages such as the customer 스토어 tab and the admin web stub.
- Only completely dead things may be removed. That means code with no entry point, for example files that nothing imports or Expo template leftovers. It also covers things that only produce errors and serve no purpose.
- Never modify a feature or UI on Claude's own initiative. That includes menus, labels, layout, and hiding or adding menu items. Propose the change and wait for the user to decide.
- When code is duplicated, merge or restructure it so every capability is preserved.

**Why:**
- On 2026-09-27, Claude suggested removing the unused posts domain. The user answered "지금 있는 기능에서 삭제할건 없어 내가 하고 싶은건 결함해결, 구조 정리야".
- On 2026-10-02, after a frontend review proposed deleting or hiding things, the user set three rules:
  1. "준비중인 페이지라고 해서 지우지말것"
  2. "기존의 기능이나 버튼들은 완전히 죽은기능이지않는이상 살려둘것"
  3. "기능이나 UI를 임의로 수정하지말것"

**How to apply:** Sort every cleanup candidate into one of three groups:
- Completely dead (zero references, unreachable): delete.
- Reachable or visible: keep.
- Visible problem (for example, a menu link that returns 404): report it and ask; do not fix it unilaterally.

- When a backend feature has no screen and git history shows the screen existed before (e.g. likes removed in 6eb6a4b, feedback-consent switch removed in fbd5e3a, both March 2026), treat it as an existing feature to restore — not as something to leave out or re-decide.

Related: [[no-commit-unless-asked]]
