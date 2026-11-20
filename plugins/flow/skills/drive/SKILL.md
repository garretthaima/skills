---
name: drive
disable-model-invocation: true
description: Drive a list of issues or problems to merged PRs. One agent per issue, an independent review, then merge. Use when the user types the drive command with issue numbers, an epic number, or plain descriptions of what to fix. Also the path for one small fix.
argument-hint: "<issue numbers | epic number | problem descriptions>"
---

You are the **driver**. `$ARGUMENTS` is the work: issue numbers, an epic, or
problems in plain words. Typing this command is the owner's authority to merge
under the rules below. This is a brief, not a procedure: decide the steps
yourself and follow the repo's rules (`CLAUDE.md`, `.claude/rules/`).

Read `.claude/flow.md` first. Its shape and the defaults for a missing section
are in `${CLAUDE_PLUGIN_ROOT}/references/project-contract.md`.

## Done, per issue

- A PR into the base branch with the title the repo's git rules ask for,
  `Closes #<n>`, a summary and a test plan.
- An independent review with every finding fixed or answered.
- Every required check green on the PR's current head, and no other check left
  red without a reason.
- Merged by the contract's method, issue closed, worktree and branch removed.

## How the work is shaped

- **Tracked first.** A problem with no issue gets one before work starts
  (`${CLAUDE_PLUGIN_ROOT}/skills/create-issue/SKILL.md`). For an epic, file
  each child when you reach it, not up front.
- **One small issue: do it yourself**, in a worktree, meeting the same Done
  list as the `flow:issue-owner` agent. No agents except the reviewer.
- **Several issues, or a large one: one `flow:issue-owner` agent per issue**,
  at most three running at once. Give each the issue number and anything you
  know that the issue body does not say. Start issues that touch the same files
  one after the other, not together.
- **Review is yours to dispatch**, never the author's: send `flow:code-reviewer`
  the worktree path and the base branch once the PR is open. Send findings back
  to the same author agent (SendMessage; if it is gone, a fresh
  `flow:issue-owner` on the same worktree and PR), then have the changed parts
  reviewed again.
- **Clean means a parsed `verdict: READY` with nothing left to fix.** A
  reviewer reply with no json block gets one re-ask, then counts as
  `NEEDS_FIXES`. A reviewer's `needs_human`, or an agent that ended without its
  report, is a stopped item, never a pass.
- **Run state lives on GitHub**: the PR, the issue, the epic's checklist, the
  board if the contract names one. A long run must survive your context being
  summarized.

## Merging

Merge with `gh pr merge <n> --squash --match-head-commit <sha>` (or the
contract's method) when review is clean and every required check on that sha is
green. A check that never reported is not green:
`gh pr view <n> --json mergeStateStatus` must read `CLEAN`. `BLOCKED` with
nothing failing means a required check is missing. When two PRs touch the same
file, update the second onto the base branch and let its checks run again
first. After merging, confirm the PR reads `MERGED` and the issue closed, then
remove the worktree and branch.

**The fix round.** Every MEDIUM and LOW finding, and every INFO that is a small
edit, goes back to the same author agent to fix in the same PR, under a `READY`
verdict too. `flow:code-reviewer` re-checks the delta (never the author, never
you). Review is clean when a re-check reads `READY` with nothing left to fix.
An INFO that is no small edit goes in the handoff's **Caught, not filed**. A
finding that changes the PR's scope gets a follow-up issue. Severities:
`${CLAUDE_PLUGIN_ROOT}/references/review-report-format.md`.

**Never merge, and stop for the owner instead:**

- a release PR, or anything that deploys;
- a migration or schema change whose tests against a real database have not
  run on the branch;
- a PR whose review left a finding that needs the owner's eye or taste;
- a PR still drawing findings after three review rounds: bring the owner the
  open findings, do not file them away;
- anything where the issue leaves a product decision open;
- closing an epic or umbrella issue, even with every child done
  (`close-epic` does that);
- anything under the contract's `## Never merge`.

A stopped item does not stop the run: park it and carry on with the rest.

## Reporting

- Stay quiet while work is moving. Interrupt only for a decision that blocks
  everything.
- Close with the handoff in `${CLAUDE_PLUGIN_ROOT}/references/handoff-format.md`,
  one **Status** pair per issue.
- A correction the owner gives during the run that should outlive it goes into
  the matching rule file in one of this run's PRs, not into memory.
- If `.claude/flow.md` was missing, say which defaults you used and suggest
  the `init` skill, once.
