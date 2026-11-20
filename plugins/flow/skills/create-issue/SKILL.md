---
name: create-issue
description: Create a well-formed GitHub issue with the right labels, after checking it is not already tracked. Use when the user wants to file an issue, capture a bug, feature or task, or turn a finding into tracked work.
allowed-tools: Read, Bash(gh:*), Bash(git:*)
---

Create a GitHub issue that is clear, correctly labeled and not a duplicate.
Read the `## Issues` section of `.claude/flow.md` first (contract and defaults:
`${CLAUDE_PLUGIN_ROOT}/references/project-contract.md`).

## 1. Check it is not already tracked (before writing anything)

Tracking lives in three places, and a search of issue titles alone misses two
of them. Check all three:

```bash
# a. open issues: title AND body
gh issue list --state open --limit 100 \
  --search "<distinctive term> in:title,body" \
  --json number,title -q '.[] | "#\(.number) \(.title)"'

# b. epic or tracking-issue checklists: a plan-of-record line IS tracking and
#    never appears in a title search
gh issue view <epic> --json body -q .body | grep -i "<distinctive term>"

# c. recently closed issues: the fix may already have landed
gh issue list --state closed --limit 30 --search "<distinctive term>" \
  --json number,title,closedAt \
  -q '.[] | "#\(.number) \(.closedAt[0:10]) \(.title)"'
```

Pick the distinctive term: a class name, selector, endpoint, file path or error
string. Not a generic word like "overflow" or "mobile".

Then classify, and say which in your report:

- **Already an open issue**: do not file. Add new evidence as a comment there.
- **An unchecked line in an epic body**: file it as realizing that line, and
  edit the epic line to link the new issue, so it is not tracked twice.
- **Recently closed or fixed**: do not file. Say the plan of record may be stale.
- **Untracked**: file it.

## 2. Shape the issue

- A specific **title** in the imperative. No `[Bug]` or `[Feature]` tag; the
  label says that. Apply the project's title or prefix convention if the
  contract gives one.
- A **body** with the problem or goal, the context (file paths, error text,
  repro steps for a bug) and acceptance criteria when they are not obvious.
- If the request is too vague to title, ask one question first.

## 3. Pick labels

Use the taxonomy in the contract. With no contract, use only labels that exist
(`gh label list`), at most one per dimension the repo has (type, area,
priority).

Never invent a label. If one is missing, propose adding it where the repo
defines its labels.

## 4. Create and link

```bash
gh issue create --title "<title>" \
  --body "<body>" --label "<a>,<b>"
```

- Parent: `gh issue edit <n> --parent <epic>` when it belongs to an epic.
- Blocked by an open issue: `gh issue edit <n> --add-blocked-by <m>`.
- Board: run the contract's board command when it gives one.
- Do not set assignees or milestones unless asked.

## 5. Report

The issue number and URL. If it relates to the current branch, say a PR can
close it with `Closes #<n>`.

For a batch of issues, show the whole list with labels and confirm once before
creating any.
