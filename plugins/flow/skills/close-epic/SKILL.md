---
name: close-epic
disable-model-invocation: true
description: Audit an epic whose sub-issues are all closed and close it out. Verifies the scope was delivered in code, files follow-ups for gaps, closes with a summary comment. With no argument, sweeps the repo's open epics for ready ones.
argument-hint: "[<n> | <owner>/<repo>#<n>]"
allowed-tools: Agent, Read, Grep, Glob, Bash(gh --version), Bash(gh repo view:*), Bash(gh issue view:*), Bash(gh issue list:*), Bash(gh pr view:*), Bash(gh api graphql:*)
---

Close out an epic, or sweep for ready ones. Runs inline. Pause for exactly ONE
confirmation before any mutation. Output follows
`${CLAUDE_PLUGIN_ROOT}/references/review-report-format.md` (verdicts `CLOSED`,
`HELD_OPEN`). Read the `## Issues` section of `.claude/flow.md` first.

Only the reads above are pre-approved. Every command that changes GitHub asks
for permission in the normal way, after the one confirmation in step 5.

## 1. Resolve targets

- `<n>` is an epic in this repo. `<owner>/<repo>#<n>` is one elsewhere. No
  argument is sweep mode.
- Preflight: `gh --version` must be 2.94 or later (native sub-issues). Stop
  with a clear message otherwise.
- Sweep: `gh issue list --label epic --state open --json number,title` (or the
  contract's epic label), then per epic fetch sub-issue progress:

```bash
gh api graphql \
  -f query='query($owner:String!,$repo:String!,$n:Int!){
    repository(owner:$owner,name:$repo){ issue(number:$n){
      subIssuesSummary{ total completed }
      subIssues(first:50){ nodes{ number title state url
        labels(first:10){ nodes{ name } } } } } } }' \
  -f owner=<owner> -f repo=<repo> -F n=<epic-number>
```

  Take `<owner>` and `<repo>` from the argument when it names a repo,
  otherwise from `gh repo view --json owner,name`. Keep each epic's URL: every
  later command names the epic by URL, never by bare number.

- **Readiness gate: `total > 0 && completed == total`.**
  - `total == 0`: report "no children yet (skipped)". Never audit a 0/0 epic.
    Its scope has not been sliced, and an audit would file follow-ups for the
    whole unstarted epic.
  - `completed < total`: a progress line only:
    `#<n>: <completed>/<total>, open: #<x>, #<y>`.
  - The summary counts only children linked as sub-issues.
- A single epic that is not ready gets the same progress line and no mutation.
- A target without the epic label: if it has sub-issues, warn and continue only
  when the user confirms. Otherwise stop.

## 2. Gather evidence (per ready epic)

- From the epic body, extract the scope: vision bullets, checklists, scope
  sections. Each promised behaviour is one scope item.
- Per sub-issue, the delivering PRs:

```bash
gh api graphql \
  -f query='query($owner:String!,$repo:String!,$n:Int!){
    repository(owner:$owner,name:$repo){ issue(number:$n){
      closedByPullRequestsReferences(first:10){
        nodes{ number title merged mergedAt url } } } } }' \
  -f owner=<owner> -f repo=<repo> -F n=<child-number>
```

- A child labeled `wontfix` or `duplicate` is resolved on purpose. Its scope
  items are not gaps.

## 3. Map scope to delivery

A table: scope item, child issues, merged PRs. An item with no delivering child
or merged PR is a candidate gap.

Dedup now, before anything is drafted: a gap already covered by a sub-issue in
any state, including closed, gets no follow-up. It is listed at the gate with
the issue that covers it, so a second audit does not file the same gaps again.

## 4. Verify in code

- Two items or fewer: verify inline (read the shipped code and its tests). No
  agents.
- Otherwise one `flow:epic-verifier` agent per scope item, in parallel, with a
  model that fits the item: the smallest for an existence check (a file, route
  or column exists or is gone), a mid one for one subsystem's behaviour, the
  strongest for cross-cutting or security-sensitive judgment.
- `delivered: "partial"`, `"false"` or `needs_human` is a gap.

## 5. Full report, verdict, one confirm

Per epic decide `CLOSED` (no gaps) or `HELD_OPEN` (gaps). Show the full report
before asking anything: summary, verdict per epic, gaps by severity with the
evidence, what was left out on purpose. With it, show the drafted mutations,
batched into one confirmation in sweep mode:

- `CLOSED`: the drafted closing comment (scope to delivery table, PR links).
- `HELD_OPEN`: the drafted follow-up issues (title, body, labels per the
  contract), the gaps skipped because an issue already covers them, and the
  drafted audit comment.

Declining means zero mutations. Never mutate before this gate.

## 6. Execute (only after the yes)

**`HELD_OPEN`:**

- File exactly the follow-ups shown at the gate. Reference the already
  covered gaps in the audit comment.
- File each follow-up in the epic's repo, then link it by URL (a bare number
  resolves against the wrong repo across repos):
  `gh issue edit <follow-up-url> --parent <epic-url>`.
- Put it on the board when the contract names a board command.
- Post the audit comment: `gh issue comment <epic-url> --body-file <file>`.
  Leave the epic open.

**`CLOSED`:**

- Post the closing summary: `gh issue comment <epic-url> --body-file <file>`.
- `gh issue close <epic-url> -r completed`. Always the URL: a bare number
  closes that number in the current repo, which is the wrong issue for an
  epic in another repo.

## 7. Receipt

Short. The full report already ran at the gate, so do not restate the findings.
List what was mutated (comment URL, issues filed and their parent links, epics
closed), any skipped or progress lines from step 1, and next steps.
