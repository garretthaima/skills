---
name: init
disable-model-invocation: true
description: Draft this repo's .claude/flow.md, the project contract the flow skills read (check commands, review checklists, labels, how to serve the app). Use once per repo, or to refresh it.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(gh:*)
---

Draft `.claude/flow.md` for this repo. The shape and the defaults are in
`${CLAUDE_PLUGIN_ROOT}/references/project-contract.md`. Read that first.

## 1. Collect, from the repo only

Never invent a command. Each line you write must point at something that
exists.

- **Base**: `gh repo view --json defaultBranchRef,squashMergeAllowed,mergeCommitAllowed`.
- **Checks**: `CLAUDE.md`, `package.json` scripts, `Makefile` targets, the jobs
  in `.github/workflows/`. Prefer the one command the repo documents as its
  pre-commit check. Note a limit that matters when several agents share the
  machine (a shared local database, a worker cap).
- **Review**: checklists and design docs the repo already has (`.claude/references/`,
  `docs/`, a `DESIGN.md`), each with the paths it applies to.
- **Issues**: `gh label list --limit 100`, `.github/labels.yml` if present, the
  titles of the last 20 issues for a prefix convention, a board script if one
  exists.
- **Verify**: how the repo documents running itself locally (`README.md`,
  `CLAUDE.md`, dev scripts), and the teardown.
- **Never merge**: anything the repo's rules already say needs the owner
  (release PRs, deploy config, migrations).
- **Docs**: a docs index if there is one; otherwise list the living docs you
  found.

## 2. Show the draft, then write

Show the whole draft. Mark each line you could not ground in the repo as a
question instead of guessing. Ask once, then write `.claude/flow.md`.

If the file already exists, show a diff of what you would change and why, and
keep every line the owner wrote that is still true.

## 3. Receipt

One line: the path written, and any heading left on its default.
