# Handoff Report Format

Shared output contract for the **final message** of any skill that completes a
unit of work (`drive`, `docs-audit`, `close-epic`).

Sibling contract: `review-report-format.md` governs findings. This one governs
"the work is done, here is the state".

## Why it is rigid

The owner skims the top blocks for what needs their attention, then reads down
only when they want depth. That works only if the blocks are in the same order
every time. Do not reorder, rename, merge or improve the sections for one run.

## The contract

Emit exactly these blocks, in this order. Above the rule is skim material and
stays terse. Depth goes below it.

```markdown
## Handoff

**Status**: <type>: <summary> · PR #<N>
<STATE> (<sha>) · #<issue> <closed|open>

**Needs you**
1. <decision or action only the owner can take>

**Follow-ups filed**
#<N>: <title>

**Untracked: file these?**
<finding>: <one line on why it matters>

**Already tracked**
#<N>: <finding, in your words>

---

**What shipped**
At most three sentences.

**Verified**
<suite counts, coverage>
<checks: green or red>

**Caught, not filed**
<finding>: <why not> · <file:line, or a command that shows it>

**Cleanup**
<exact command, or "Done.">
```

## Rules per block

- **Status**: one line of what, one line of where it stands. `<STATE>` is one
  of `MERGED`, `PR OPEN`, `BLOCKED`, `RELEASED`. Always include the PR and the
  issue's state. One Status pair per issue when a run covered several.
- **Needs you**: the most important block. Numbered, each an action or decision
  only the owner can make, each standing alone: what it is, why it is blocked,
  what happens either way, the exact action wanted. Write `Nothing.` when there
  is none. Never omit the block. An FYI goes below the rule.
- **Follow-ups filed**: issues created this run, or `None.` Not issues you
  only commented on.
- **Untracked: file these?**: real findings you did not file, with no open
  issue and on no epic checklist. The owner says file or skip. `None.` when
  empty. Something you investigated and found to be correct behaviour goes
  under **Caught, not filed**.
- **Already tracked**: findings that have an existing home, so the owner does
  not triage them again. Includes an unchecked line in an epic body (cite the
  epic). `None.` when empty.

  Classify every finding before writing the report: search open issue bodies
  as well as titles, the epic bodies it could belong to, and recently closed
  issues. The procedure is step 1 of the `create-issue` skill.
- **What shipped**: three sentences at most. The diff is on the PR.
- **Verified**: what ran, with real numbers. Never "tests pass" without
  counts. Say what did not run.
- **Caught, not filed**: findings you looked into and chose not to file. Each
  entry carries a pointer the reader can check in under a minute: a `file:line`
  holding the rule that makes it correct, or a command that reproduces it. If
  you cannot give a pointer, move the item to **Untracked: file these?**. Omit
  the block when empty.
- **Cleanup**: the exact command, or `Done.`

## Hard rules

- Chat only. No published page for a handoff.
- No tables above the rule.
- Never claim a state you did not verify. `MERGED` means you checked.
- The blocks are fixed: same order, same names, including when half of them
  say `Nothing.` or `None.`
