---
description: Summarise my recent work for the team chat
argument-hint: [days, default 2]
---

Summarise the current member's recent work for a short team-chat standup.

1. Use the window `$ARGUMENTS` days (default 2).
2. Run `git config user.email`, then `git log --all --author="<that email>" --since="<N> days ago" --oneline`.
3. Check uncommitted work with `git status --short`. If `gh` is available, also run `gh pr list --author @me --state all --limit 10`.
4. Map the work to capabilities (C1–C12) using `context/mvp.md`.

Output a message ready to paste, at most 8 lines, plain text:
- **Done:** items, each with its capability.
- **Doing:** in-progress items.
- **Blocked / need:** decisions (D1–D7), reviews, or help needed.
- **Heads-up:** any change to `context/contracts.md`.

Don't include personal data, phone numbers or transcript content.
