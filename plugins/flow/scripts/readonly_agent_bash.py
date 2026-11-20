#!/usr/bin/env python3
"""PreToolUse (Bash): the plugin's read-only agents run read-only git/gh only.

A plugin agent cannot carry its own `hooks:` frontmatter (Claude Code ignores
it), so this is a plugin-level hook that looks at `agent_type` in the payload.
Outside the agents named in READ_ONLY_AGENTS it does nothing.

Inside one, every subcommand of the Bash call must be a read-only `git` or
`gh` invocation. Anything else is denied with a reason: other programs, any
shell expansion, redirection, git or gh writes, options that run a program or
write a file, and requests to a host other than GitHub. The guard fails CLOSED
there: a command it cannot parse is denied, because those agents only ever
need simple git/gh reads.

The guard reads the command the way bash will. Bash expands words after the
point a simple tokenizer looks at them (`{a,b}`, `$IFS`, `$'..'`, globs), so
every character that can trigger an expansion is refused outright unless it
sits inside single quotes, where bash leaves it alone.
"""
import json
import os
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
REMOTE_NAME = re.compile(r"^[\w.-]+$")

# gh: only these command groups (an unknown first word could be an extension or
# an alias, which is an arbitrary program), and only their read verbs.
GH_NOUNS = {"pr", "issue", "run", "repo", "release", "workflow", "label"}
GH_READ_VERBS = {"view", "list", "diff", "checks", "status"}
# `gh api`: a positive allowlist. A flag not listed here is refused, which also
# refuses every bundled short form (`-iXDELETE`, `-ifbody=x`).
GH_API_FLAGS = {"-i", "--include", "--paginate", "--slurp", "--silent", "--verbose"}
GH_API_VALUE_FLAGS = {
    "-H", "--header", "-q", "--jq", "-t", "--template", "--cache", "-p", "--preview",
}
GH_API_METHOD_FLAGS = {"-X", "--method"}

SAFE_REDIRECTS = re.compile(r"(?<!\S)(?:2>&1|2>/dev/null|>/dev/null)(?!\S)")
# Outside quotes these start an expansion, a substitution, a subshell or a redirect.
UNQUOTED_FORBIDDEN = set("$`\\{}*?[]()<>")
# Inside double quotes bash still expands these.
DOUBLE_QUOTED_FORBIDDEN = set("$`\\")


def is_read_only_agent(agent_type):
    """True for this plugin's read-only agents: `flow:code-reviewer`.

    The plugin prefix is required, so another plugin's or a project's own
    `code-reviewer` is left alone. The `<plugin>:<agent>` form of `agent_type`
    was confirmed by loading the plugin and watching the hook deny a write.
    """
    if not isinstance(agent_type, str):
        return False
    prefix, _, name = agent_type.rpartition(":")
    return prefix == PLUGIN and name in READ_ONLY_AGENTS


def split_commands(command):
    """Split on the shell's control operators, honouring quotes.

    Returns (segments, None), or (None, reason) when the command holds anything
    bash would expand or redirect. A separator inside quotes is an argument,
    not a separator, so it must not split: otherwise the words after it would
    be checked as a command of their own instead of as arguments of this one.
    """
    segments, current, quote, i = [], [], None, 0
    while i < len(command):
        char = command[i]
        if quote == "'":
            quote = None if char == "'" else quote
            current.append(char)
        elif quote == '"':
            if char in DOUBLE_QUOTED_FORBIDDEN:
                return None, "expansion inside double quotes is not allowed"
            quote = None if char == '"' else quote
            current.append(char)
        elif char in "'\"":
            quote = char
            current.append(char)
        elif char in UNQUOTED_FORBIDDEN:
            return None, f"shell expansion or redirection ({char!r}) is not allowed"
        elif char in ";|&\r\n":
            pair = command[i:i + 2]
            if pair in ("&&", "||", "|&", ";;"):
                i += 1
            elif char == "&":
                return None, "backgrounding (&) is not allowed"
            segments.append("".join(current))
            current = []
        else:
            current.append(char)
        i += 1
    if quote:
        return None, "unbalanced quote"
    segments.append("".join(current))
    return [s for s in segments if s.strip()], None


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
    if not rest:
        return True
    if rest[0] not in ("show", "get-url"):
        return False
    # A configured remote's name only: a URL here would send a request to any host.
    return all(arg.startswith("-") or REMOTE_NAME.match(arg) for arg in rest[1:])


def grep_runs_a_pager(rest):
    """`git grep -O<cmd>` / `--open-files-in-pager=<cmd>` runs a program. Git
    accepts the short flag inside a bundle (`-nO<cmd>`) and the long one
    abbreviated (`--open=<cmd>`)."""
    for arg in rest:
        if arg == "--":
            return False
        name = arg.split("=", 1)[0]
        if re.match(r"^-[^-]*O", arg):
            return True
        if len(name) >= 4 and "--open-files-in-pager".startswith(name):
            return True
    return False


def git_ok(args, cwd):
    # Global options: -C <path> and --no-pager only. -c is not allowed (it sets config).
    i, where = 0, cwd
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            where = os.path.join(where, args[i + 1])
            # A checkout or a worktree has a `.git` entry. A bare repository does
            # not, and one committed inside a branch under review would bring its
            # own config (diff.external, core.fsmonitor), which git would run.
            if not os.path.exists(os.path.join(where, ".git")):
                return False
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
    # --output writes a file.
    if any(a.startswith("--output") for a in rest):
        return False
    if sub == "grep" and grep_runs_a_pager(rest):
        return False
    return True


def gh_api_ok(rest):
    endpoints, i = 0, 0
    while i < len(rest):
        arg = rest[i]
        name, has_value, value = arg.partition("=")
        if not arg.startswith("-"):
            # GitHub's own API only: a full URL would send the request, and
            # anything put in it, to another host.
            if "://" in arg:
                return False
            endpoints += 1
        elif arg in GH_API_FLAGS:
            pass
        elif name in GH_API_METHOD_FLAGS or name in GH_API_VALUE_FLAGS:
            if name.startswith("--") and has_value:
                given = value
            elif not has_value and i + 1 < len(rest):
                given = rest[i + 1]
                i += 1
            else:
                return False
            if name in GH_API_METHOD_FLAGS and given.upper() != "GET":
                return False
        else:
            return False
        i += 1
    return endpoints == 1


def gh_ok(args):
    if not args:
        return False
    # --web opens a browser; -w is its short form and may sit in a bundle.
    if any(a == "--web" or re.match(r"^-[A-Za-z]*w", a) for a in args):
        return False
    if args[0] == "api":
        return gh_api_ok(args[1:])
    if args[0] == "search":
        return len(args) >= 2 and not args[1].startswith("-")
    # gh <noun> <verb> ...  e.g. gh pr view 12
    return args[0] in GH_NOUNS and len(args) >= 2 and args[1] in GH_READ_VERBS


def segment_ok(segment, cwd):
    tokens = shlex.split(segment)
    if not tokens:
        return True
    prog, args = tokens[0], tokens[1:]
    if prog == "git":
        return git_ok(args, cwd)
    if prog == "gh":
        return gh_ok(args)
    return False


def decide(command, cwd=None):
    """The reason `command` is refused, or None when it is allowed."""
    if not command.strip():
        return "empty command"
    segments, reason = split_commands(SAFE_REDIRECTS.sub(" ", command))
    if reason:
        return reason
    if not segments:
        return "empty command"
    try:
        bad = [s for s in segments if not segment_ok(s, cwd or os.getcwd())]
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
        cwd = payload.get("cwd")
        reason = decide(command, cwd if isinstance(cwd, str) else None)
    except Exception as exc:  # fail closed inside a read-only agent
        reason = f"guard error: {exc}"
    if reason:
        deny(f"Read-only agent: {reason}.")


if __name__ == "__main__":
    main()
    sys.exit(0)
