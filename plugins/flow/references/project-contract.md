# The project contract: `.claude/flow.md`

The skills and agents in this plugin are the same in every repo. What differs
per repo (its check command, its labels, how to serve it) lives in one file in
that repo: `.claude/flow.md`. Every skill reads it first.

`/flow:init` drafts the file from what the repo already has. Edit it by hand
afterwards; it is the project's, not the plugin's.

## Shape

Markdown with these headings, in this order. A heading may be left out; the
default in the right-hand column then applies. Write `None.` under a heading to
say the project has no such thing, which is different from leaving it out.

| Heading | What it holds | Default when left out |
| ------- | ------------- | --------------------- |
| `## Base` | The branch PRs target, and the merge method | The repo's default branch; squash merge |
| `## Checks` | The exact commands an author runs before opening a PR, and any limit while several agents share the machine (worker counts, shared database) | The check or test command named in `CLAUDE.md`; if none, `npm test` or the repo's obvious equivalent |
| `## Review` | Files the reviewer applies beyond `CLAUDE.md` and `.claude/rules/`: checklists, with the paths they apply to | `CLAUDE.md` and `.claude/rules/` only |
| `## Issues` | Label taxonomy, title or epic-prefix convention, where the label definitions live, the board command if there is one | Labels that exist in the repo (`gh label list`); no title prefix; no board |
| `## Verify` | How to serve the branch and exercise a change in the running app, and how to tear it down | No runtime check; tests only |
| `## Never merge` | Cases where the driver stops for the owner, added to the plugin's own list | The plugin's list only |
| `## Docs` | The index of living docs, which docs are dated records, any generated sections | Every tracked `*.md` outside `CHANGELOG.md` |

## Example

```markdown
# Flow contract

## Base
`main`, squash merge. Conventional Commit PR titles.

## Checks
- `npm run check` from the repo root (type-check, lint, format check, tests).
- A browser-facing change also runs `npm run test:e2e`.
- Agents sharing the machine: nothing extra; each test run starts its own database.

## Review
- `web/DESIGN.md` when the diff touches `web/**`.

## Issues
- Labels: one `type:` and one `priority:`; defined in `.github/labels.yml`.
- No epic prefix. Milestones group the work.
- Board: None.

## Verify
- `npm run dev:db`, `npm run dev:server`, `npm run dev:web`, then open :5173.
- Stop the three processes by PID when done.

## Never merge
- A change to `deploy/chart/**` (it reaches the cluster).

## Docs
- Living docs: `README.md`, `web/DESIGN.md`, `.claude/rules/*.md`.
```

## Rules for skills that read it

- The contract wins over a skill's default, and the repo's `CLAUDE.md` and
  `.claude/rules/` win over both where they are stricter.
- Never guess a command the contract does not give. Fall back to the default
  in the table, and say in the report which default was used.
- A missing file is not an error. Use the defaults and suggest `/flow:init`
  once, in the final report.
