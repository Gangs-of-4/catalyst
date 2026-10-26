---
description: Suggest useful next work based on the roadmap, recent commits and open PRs
---

Suggest what would be most useful to work on next in Catalyst. This is advisory: the member chooses.

1. Read `context/roadmap.md` and `context/mvp.md`.
2. Run `git fetch --quiet`, then `git log --oneline -20 origin/main`, then `git branch -r --sort=-committerdate | head -15`.
3. If the `gh` CLI is available, run `gh pr list --state open --limit 20`. If it isn't, skip this step and say so.
4. Read `context/decisions.md` → Open decisions, and `context/spikes.md`.

Then reply in at most 15 lines:
- **Where we are:** the current milestone(s) and which capabilities are ticked.
- **In flight:** open PRs and active branches, mapped to capabilities/modules.
- **3 suggestions:** for each, name the capability it moves forward, the module, why now, and whether it overlaps anything in flight. Prefer unblocking work: spikes, D1/D2 inputs, contract stubs that others build on.
- If $ARGUMENTS names an area (A–D from `context/team.md`) or a module, focus the suggestions there.

Don't start any work. Just suggest.
