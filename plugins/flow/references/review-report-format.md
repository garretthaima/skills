# Review Report Format

Shared output contract for the review-type skills and agents in this plugin
(`pre-merge-review`, `code-reviewer`, `close-epic`, `epic-verifier`,
`docs-audit`).

## Severity

| Severity | Meaning |
| -------- | ------- |
| `CRITICAL` | Security hole, data loss, broken auth. Blocks everything |
| `HIGH` | Must fix before merge or epic close |
| `MEDIUM` | Should fix; in a branch or PR review, fixed in the same PR before merge |
| `LOW` | Style or consistency; in a branch or PR review, fixed in the same PR before merge |
| `INFO` | Observation; in a branch or PR review, fixed in the same PR when it is a small edit |

In a branch or PR review, a follow-up issue is only for a finding that changes
the PR's scope. A finding that needs the owner's judgment stops the PR for the
owner. An epic closeout files follow-ups for its gaps.

## Finding shape

Fields: `severity`, `file`, `line`, `issue`, `fix`.

- JSON keeps `file` (string) and `line` (integer) separate.
- Markdown renders the location as `file:line`.

```json
{ "severity": "HIGH", "file": "server/src/modules/foo/service.ts", "line": 42, "issue": "", "fix": "" }
```

Markdown finding line:

- **HIGH** `server/src/modules/foo/service.ts:42`: issue text. Fix: fix text.

When a finding enforces a written rule, cite the rule file, so the comment
teaches the rule.

## Verdicts

- Branch review: `READY` | `NEEDS_FIXES`. `READY` means no CRITICAL or HIGH
  finding. A `READY` can still list MEDIUM, LOW and INFO findings.
- Epic closeout: `CLOSED` | `HELD_OPEN`.
- Docs audit: `CLEAN` | `FINDINGS`.

## Report skeleton (markdown)

1. One-line summary: what was reviewed and how much.
2. **Verdict**.
3. Findings grouped by severity, highest first. Omit empty groups.
4. Test results, only when tests were run, with real counts.
5. Next steps: the fix list, follow-up issues filed, or "none".

## Agent envelope

An agent in this plugin ends its reply with exactly one fenced json block:

```json
{ "result": {}, "needs_human": false, "reason": "" }
```

`result` is the agent's own shape. `needs_human: true` with a `reason` means
the agent could not settle something and a person must. A reply with no json
block is not a pass: the caller re-asks once, then treats it as a failure.
