#!/usr/bin/env python3
"""PreToolUse (Bash): the plugin's read-only agents run read-only git/gh only.

A plugin agent cannot carry its own `hooks:` frontmatter (Claude Code ignores
it), so this is a plugin-level hook that looks at `agent_type` in the payload.
Outside the agents named in READ_ONLY_AGENTS it does nothing.

Inside one, every subcommand of the Bash call must be a read-only `git` or
`gh` invocation. Anything else (other programs, command substitution, output
redirection, git/gh writes) is denied with a reason. The guard fails CLOSED
there: a command it cannot parse is denied, because those agents only ever
need simple git/gh reads.
"""
import json
import re
import shlex
import sys

PLUGIN = "flow"
READ_ONLY_AGENTS = {"code-reviewer", "epic-verifier", "docs-auditor"}

GIT_READ = {
    "diff", "log", "show", "status", "rev-parse", "ls-files", "ls-tree", "grep",
    "blame", "merge-base", "cat-file", "describe", "shortlog", "rev-list",
    "name-rev", "for-each-ref", "branch", "tag", "remote", "worktree",
}
# `git branch` / `tag` are read-only only in their listing forms, so this is a
# positive allowlist: any other flag (-d, -m, --set-upstream-to=, ...) is rejected.
BRANCH_TAG_FLAGS = {
    "-a", "--all", "-r", "--remotes", "-v", "-vv", "--verbose", "-l", "--list",
    "--show-current", "--contains", "--merged", "--no-merged", "--format", "--sort",
}
# Flags whose value may be the next token (`--contains <sha>`, `--format <fmt>`).
BRANCH_TAG_VALUE_FLAGS = {"--contains", "--merged", "--no-merged", "--format", "--sort"}
GH_READ_VERBS = {"view", "list", "diff", "checks", "status"}
# `gh auth status --show-token` prints the token; no read-only agent needs gh auth.
GH_DENIED_NOUNS = {"auth"}
GH_GET_FLAGS_BAD = {"-f", "-F", "--field", "--raw-field", "--input"}
# Every shell operator that chains or backgrounds a command. Safe redirects
# (2>&1) are blanked out before splitting so their `&` is not mistaken for the
# background operator.
SEPARATORS = re.compile(r"\s*(?:&&|\|\||\|&|\||;;|;|&|\r|\n)\s*")
SAFE_REDIRECTS = re.compile(r"(?<!\S)(?:2>&1|2>/dev/null|>/dev/null)(?!\S)")


def is_read_only_agent(agent_type):
    """True for this plugin's read-only agents: `flow:code-reviewer`.

    The plugin prefix is required, so another plugin's or a project's own
    `code-reviewer` is left alone.
    """
    if not isinstance(agent_type, str):
        return False
    prefix, _, name = agent_type.rpartition(":")
    return prefix == PLUGIN and name in READ_ONLY_AGENTS


def branch_tag_ok(rest):
    """`git branch` / `git tag` listing forms only. A positional is allowed only
    as a --list pattern; without --list a bare name would create a branch or tag."""
    listing = "--list" in rest or "-l" in rest
    i = 0
    while i < len(rest):
        arg = rest[i]
        name = arg.split("=", 1)[0]
        if arg.startswith("-"):
            if name not in BRANCH_TAG_FLAGS:
                return False
            takes_value = arg in BRANCH_TAG_VALUE_FLAGS
            if takes_value and i + 1 < len(rest) and not rest[i + 1].startswith("-"):
                i += 1
        elif not listing:
            return False
        i += 1
    return True


def remote_ok(rest):
    # `git remote [-v] add|rename|remove|set-url ...` writes config, and the -v
    # may come first, so strip it before looking at the subcommand.
    while rest and rest[0] in ("-v", "--verbose"):
        rest = rest[1:]
    return not rest or rest[0] in ("show", "get-url")


def git_ok(args):
    # Global options: -C <path> and --no-pager only. -c is not allowed (it sets config).
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            i += 2
        elif args[i] in ("--no-pager", "--no-optional-locks"):
            i += 1
        else:
            return False
    if i >= len(args) or args[i] not in GIT_READ:
        return False
    sub, rest = args[i], args[i + 1:]
    if sub == "worktree":
        return rest[:1] == ["list"]
    if sub == "remote":
        return remote_ok(rest)
    if sub in ("branch", "tag"):
        return branch_tag_ok(rest)
    # --output writes a file; `git grep -O<cmd>` runs a pager program.
    if any(a.startswith("--output") for a in rest):
        return False
    if sub == "grep" and any(
        a.startswith("-O") or a.startswith("--open-files-in-pager") for a in rest
    ):
        return False
    return True


def gh_api_ok(rest):
    for j, arg in enumerate(rest):
        name = arg.split("=", 1)[0]
        if name in GH_GET_FLAGS_BAD:
            return False
        # Joined short field flags: -fkey=val / -Fkey=val (a body means POST).
        if not arg.startswith("--") and (arg.startswith("-f") or arg.startswith("-F")):
            return False
        # The method: -X GET, -XGET, -X=GET, --method GET, --method=GET. Only GET.
        if arg.startswith("-X") or name == "--method":
            if arg in ("-X", "--method"):
                method = rest[j + 1] if j + 1 < len(rest) else ""
            elif arg.startswith("-X"):
                method = arg[2:].lstrip("=")
            else:
                method = arg.split("=", 1)[1] if "=" in arg else ""
            if method.upper() != "GET":
                return False
    return True


def gh_ok(args):
    if not args or args[0] in GH_DENIED_NOUNS:
        return False
    if args[0] == "api":
        return gh_api_ok(args[1:])
    if args[0] == "search":
        return True
    # gh <noun> <verb> ...  e.g. gh pr view 12
    return len(args) >= 2 and args[1] in GH_READ_VERBS


def segment_ok(segment):
    tokens = shlex.split(segment)
    if not tokens:
        return True
    prog, args = tokens[0], tokens[1:]
    if prog == "git":
        return git_ok(args)
    if prog == "gh":
        return gh_ok(args)
    return False


def decide(command):
    """The reason `command` is refused, or None when it is allowed."""
    if not command.strip():
        return "empty command"
    if "$(" in command or "`" in command or "<(" in command:
        return "command substitution is not allowed"
    stripped = SAFE_REDIRECTS.sub(" ", command)
    if re.search(r"[<>]", stripped):
        return "redirection is not allowed"
    if re.search(r"(?<!&)&(?!&)", stripped):
        return "backgrounding (&) is not allowed"
    try:
        segments = [s for s in SEPARATORS.split(stripped.strip()) if s.strip()]
        bad = [s for s in segments if not segment_ok(s)]
    except ValueError:
        return "command could not be parsed"
    if bad:
        return f"only read-only git/gh commands are allowed here (rejected: {bad[0][:120]!r})"
    return None


def deny(reason):
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.stdout.flush()


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return  # no payload: cannot tell which agent this is, so stay out of the way
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return
    if not is_read_only_agent(payload.get("agent_type")):
        return
    try:
        command = (payload.get("tool_input") or {}).get("command") or ""
        reason = decide(command)
    except Exception as exc:  # fail closed inside a read-only agent
        reason = f"guard error: {exc}"
    if reason:
        deny(f"Read-only agent: {reason}.")


if __name__ == "__main__":
    main()
    sys.exit(0)
