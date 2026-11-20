---
name: docs-audit
disable-model-invocation: true
description: Check the living docs against the code. Read-only agents check every factual claim, the user sees the full findings report and confirms once, then one issue and one PR fix the prose. Use before a release or on a cadence.
argument-hint: "[<path>...] [--dry-run]"
allowed-tools: Agent, Read, Grep, Glob, Bash(git fetch:*), Bash(git worktree list:*), Bash(git worktree add --detach:*), Bash(git rev-parse:*), Bash(git ls-files:*), Bash(gh issue view:*), Bash(gh issue list:*)
---

You are the **driver** of a docs audit. `$ARGUMENTS` limits the sweep to paths;
empty means every living doc. `--dry-run` stops after the report. Nothing is
filed or edited before the one confirm in step 4; the only thing this run
creates before it is its own scratch worktree, which it also removes.

Read the `## Docs` section of `.claude/flow.md` first (shape and defaults:
`${CLAUDE_PLUGIN_ROOT}/references/project-contract.md`).

## 1. Baseline and doc list

- Fetch the base branch. A path argument that does not exist there is reported
  as not found and is not audited.
- Leave every other `.claude/worktrees/docs-audit-*` worktree alone: it may be
  another session's audit. List each in the step 4 report with its
  `git worktree remove --force <path>` command, for the owner to run.
- Add a detached worktree for the auditors, since the main checkout may be
  stale or dirty:
  `git worktree add --detach .claude/worktrees/docs-audit-<YYYY-MM-DD>-<HHMMSS>-<short sha> origin/<base>`.
  It is this run's own, and is removed after step 3, on every path.
- Take the living docs from the contract's docs index in that worktree. Skip
  dated records and generated sections. With no contract, take every tracked
  `*.md` except `CHANGELOG.md`.
- Split the docs into groups of related files, about ten docs or fewer each.

## 2. Audit, one `flow:docs-auditor` per group

Launch the groups in parallel, one `flow:docs-auditor` agent each. Give it the
worktree path, the group's doc list, and anything the contract says CI already
checks (dead links, generated tables), so it does not spend reads there.

A reply without its json block, or with docs under `not_reached`, means those
docs were not audited. Run them once more, split in two. If that fails too,
report them as not covered. An auditor's `needs_human: true` goes into the
step 4 report as a decision standing alone, with its `reason`.

## 3. Spot-check before trusting

Audits are wrong sometimes. Before the report, open the evidence for a sample
of findings yourself: at least two per group, and every finding that would
delete a section, change a security or data claim, or rests on a count. Correct
a wrong line number. Drop a wrong finding.

When more than a third of a group's sample is wrong, run that group once more.
If it is still over a third, report the group as unreliable: its findings are
listed but not fixed.

Then remove the auditors' worktree.

## 4. Full report, then one confirm

Show the whole report before asking anything, in the shape of
`${CLAUDE_PLUGIN_ROOT}/references/review-report-format.md`:

- One line: docs read, findings, docs found correct, groups not covered or
  unreliable.
- Findings per doc: `doc:line`, claim, evidence, correction.
- The spot-check result: how many checked, how many failed, per group.
- Claims nobody could verify, grouped by reason.
- Every issue that will be filed, drafted with title, labels and body: the
  prose fix issue (body: the finding list), one per finding that needs new
  code, one per `code_bug` finding.

A decision the user must make goes in its own block above the findings: what it
is, why it matters, the options, your recommendation. That covers keeping or
deleting a doc, which of two conflicting sources wins, and each auditor's
`needs_human`. Never as a footnote.

Then ask once. Say that a yes covers filing those issues, the fix PR, and
merging it once its review is clean and every required check is green. A no, or
`--dry-run`, ends the run with no mutation. A clean audit ends with the report
and no question.

## 5. Fix (only after the yes)

- **Issues.** File the drafted issues per
  `${CLAUDE_PLUGIN_ROOT}/skills/create-issue/SKILL.md`. Fix the doc to match
  the code. Never change code in the prose PR.
- **One PR**, run the way the `drive` skill runs an issue: a `flow:issue-owner`
  agent in its own worktree, given the issue and the checked findings. Tell it
  to check each finding against the code again before editing, and to skip any
  that does not hold, saying why in the PR body. Every number it writes
  carries, in the PR body, the command that produced it.
- **Independent review** by `flow:code-reviewer`, dispatched by you, with
  `origin/<base>` as the base after a `git fetch`. Ask it to
  read each changed doc whole, not only the hunks: a deletion can leave half a
  table behind. A reviewer that stops without a verdict is not a pass.
- Merge under the `drive` skill's Merging section.

## 6. Handoff

Close with `${CLAUDE_PLUGIN_ROOT}/references/handoff-format.md`:

- Fixed findings and docs: **What shipped** (counts; the list is in the PR).
- A finding left unfixed: **Follow-ups filed**, or **Caught, not filed** when
  it was dropped on re-check, with the evidence.
- Unverified claims and groups not covered or unreliable:
  **Untracked: file these?**, grouped by reason.

A dry run, a no at the gate, or a clean audit ends with the step 4 report.
