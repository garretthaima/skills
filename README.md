# skills

A Claude Code plugin marketplace. One plugin so far: `flow`, which takes work
from an issue to a merged PR.

## Install

```bash
claude plugin marketplace add garretthaima/skills
claude plugin install flow@garretthaima-skills
```

To turn it on for everyone who opens a repo, add this to that repo's
`.claude/settings.json`:

```json
{
    "extraKnownMarketplaces": {
        "garretthaima-skills": {
            "source": { "source": "github", "repo": "garretthaima/skills" }
        }
    },
    "enabledPlugins": { "flow@garretthaima-skills": true }
}
```

Then, once per repo, run `/flow:init`. It writes `.claude/flow.md`, the one
file that tells the plugin how this repo works: its check command, its labels,
how to serve it. Without the file the skills fall back to defaults and say so.

## What `flow` has

| Skill | What it does |
| ----- | ------------ |
| `/flow:init` | Drafts `.claude/flow.md` from what the repo already has |
| `/flow:create-issue` | Files a GitHub issue with the right labels, after checking it is not already tracked |
| `/flow:drive` | Takes issue numbers, an epic or plain descriptions to merged PRs: one agent per issue, an independent review, then merge |
| `/flow:pre-merge-review` | Runs the repo's checks and reviews the branch against the repo's own rules |
| `/flow:close-epic` | Verifies an epic's scope shipped, files follow-ups for gaps, closes it |
| `/flow:docs-audit` | Checks every claim in the docs against the code, then fixes the prose in one PR |

| Agent | Role |
| ----- | ---- |
| `flow:issue-owner` | Owns one issue up to an open, green PR |
| `flow:code-reviewer` | Reviews a diff it did not write. Read-only |
| `flow:epic-verifier` | Verifies one epic scope item in code. Read-only |
| `flow:docs-auditor` | Checks doc claims against a checkout. Read-only |

The three read-only agents are held to read-only `git` and `gh` by a hook
(`plugins/flow/scripts/readonly_agent_bash.py`). It does nothing outside those
agents. It needs `python3` on the PATH: if the hook cannot run, Claude Code
blocks the Bash call instead of letting an unguarded one through.

## What is not here, on purpose

- **Project rules.** A plugin cannot ship `.claude/rules/`. Rules stay in each
  repo; the skills read them.
- **Edit hooks** (format on save, protected files). They depend on the repo's
  formatter and paths, so they live in the repo.
- **Anything tied to one app**: its deploy, its seed logins, its cluster.

## Layout

```
.claude-plugin/marketplace.json   the catalog
plugins/flow/
  .claude-plugin/plugin.json
  skills/<name>/SKILL.md
  agents/<name>.md
  hooks/hooks.json
  scripts/                        hook scripts
  references/                     formats the skills share
tests/                            hook tests
```

## Working on it

```bash
python3 -m unittest discover tests
claude plugin validate .
claude --plugin-dir plugins/flow
```

Bump `version` in `plugins/flow/.claude-plugin/plugin.json` with every change
that should reach installed copies; an install stays on its version until that
changes.
