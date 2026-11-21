---
name: pre-merge-review
description: Full review of the current branch before merge. Runs the project's checks, then reviews the diff against the repo's own rules, security basics and database changes. Use when the user asks to review a branch or says it is ready to merge.
context: fork
allowed-tools: Read, Grep, Glob, Bash(git diff:*), Bash(git log:*), Bash(git status:*), Bash(git rev-parse:*), Bash(git merge-base:*), Bash(git fetch:*), Bash(gh pr view:*), Bash(npm run:*), Bash(npm test:*), Bash(npm audit:*), Bash(make:*), Bash(wc:*)
---

Review the current branch before merge. Follow every step in order. You do not
edit code.

## 1. What changed, and against what

- Read `.claude/flow.md` (shape and defaults:
  `${CLAUDE_PLUGIN_ROOT}/references/project-contract.md`). Take the base branch
  from `## Base`.
- `git fetch`, then `git diff origin/<base>...HEAD --stat` and
  `git log origin/<base>..HEAD --oneline`. The local base branch may be stale.

## 2. Run the checks

Run the commands under `## Checks` in the contract, exactly as written. With no
contract, use the check command named in `CLAUDE.md`. Report failures with the
real counts. A test that fails and then passes on a second run is a finding,
not green. A check command outside npm and make is not pre-approved and asks
for permission; that is expected.

## 3. Review the diff against the repo's own rules

The standard is the repo's, not yours. Read, then apply to each changed file:

- `CLAUDE.md`;
- every file in `.claude/rules/` whose `paths:` cover a changed file, plus the
  ones with no `paths:`;
- each checklist under `## Review` in the contract that covers a changed file.

Cite the rule file in each finding, so the comment teaches the rule. Do not
report a preference the repo has not written down as anything above `INFO`.

Always check, whatever the rules say:

- file and function length against the repo's limits (`wc -l` on changed files);
- leftover debug output, commented-out code and dead exports the diff leaves
  behind;
- a new or changed user-facing flow has a test for it in the same diff.

## 4. Database changes (when the diff has migrations or queries)

- An applied migration is never edited; a change is a new migration.
- The migration can be undone the way the repo's rules require.
- Queries are parameterized. No request value is concatenated into SQL.

## 5. Security

- No secret, token or credential in the diff, and no `.env` file staged.
- Every new endpoint validates its input and has an authorization check, or a
  comment saying why it is public.
- No user input reaches a shell, `eval`, a file path or raw HTML unescaped.
- If a `package.json` changed, run `npm audit` in that directory and report
  high and critical findings.

## 6. Before the PR

- The branch is up to date with the base branch.
- Commit and PR titles follow the repo's git rules.
- The PR description has a summary and a test plan.

## 7. Report

Per `${CLAUDE_PLUGIN_ROOT}/references/review-report-format.md`:

- one-line summary (branch, files changed);
- verdict: `READY` or `NEEDS_FIXES`;
- findings grouped by severity, each as **SEV** `file:line`: issue. Fix: fix;
- check results with real counts;
- next steps.
