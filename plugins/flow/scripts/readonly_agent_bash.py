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
# `git branch` / `git tag`: listing only, and only with these flags. No flag
# that takes a value and no positional is accepted. Git hands the next word to
# a value flag whatever it looks like (`--format -l name` creates `name`), so
# the only form that cannot be misread is one with no values in it. Use
# `git for-each-ref` to filter or format.
BRANCH_FLAGS = {
    "-a", "--all", "-r", "--remotes", "-v", "-vv", "--verbose", "-l", "--list",
    "--show-current",
}
TAG_FLAGS = {"-l", "--list", "-n"}
CAT_FILE_FLAGS = {"-p", "-t", "-s", "-e"}
REMOTE_NAME = re.compile(r"^[\w-]+$")

# gh: only these command groups (an unknown first word could be an extension or
# an alias, which is an arbitrary program), and only their read verbs.
GH_NOUNS = {"pr", "issue", "run", "repo", "release", "workflow", "label"}
GH_READ_VERBS = {"view", "list", "diff", "checks", "status"}
# `gh api`: a positive allowlist. A flag not listed here is refused, which also
# refuses every bundled short form (`-iXDELETE`, `-ifbody=x`).
GH_API_FLAGS = {"-i", "--include", "--paginate", "--slurp", "--silent", "--verbose"}
GH_API_VALUE_FLAGS = {"-q", "--jq", "-t", "--template", "--cache", "-p", "--preview"}
GH_API_HEADER_FLAGS = {"-H", "--header"}
GH_API_METHOD_FLAGS = {"-X", "--method"}
# Fields turn the request into a POST unless the method is given as GET.
GH_API_FIELD_FLAGS = {"-f", "--raw-field", "-F", "--field"}
# A header can ask a server to treat a GET as another method, so only these.
GH_API_HEADERS = re.compile(r"^(accept|x-github-api-version)\s*:", re.I)
# OWNER/REPO. gh also takes HOST/OWNER/REPO, which sends the request elsewhere.
OWNER_REPO = re.compile(r"^[\w.-]+/[\w.-]+$")
HOST_OWNER_REPO = re.compile(r"^[\w.-]+(/[\w.-]+){2,}$")
# `git@host:o/r`, `user@host/o/r` and `host:443/o/r` name a host too.
HOST_IN_WORD = re.compile(r"@[\w.-]+[:/]|^[\w.-]+:\d+/")
# `gh repo view` reads its positional as a repository on any host, so its
# arguments are parsed in full: these flags, each with a value, and one repo.
GH_REPO_VIEW_VALUE_FLAGS = {"--json", "-q", "--jq", "-t", "--template", "-b", "--branch"}
GITHUB_URL = "https://github.com/"
# jq's `env` and `$ENV` print the process environment, tokens included.
JQ_ENVIRONMENT = re.compile(r"\benv\b|\$ENV")

SAFE_REDIRECT = re.compile(r"(?:2>&1|2>[ \t]*/dev/null|>[ \t]*/dev/null)(?=[ \t;|&\n]|$)")
# Outside quotes these start an expansion, a substitution, a subshell, a
# redirect or a comment. A comment matters: bash drops the words after `#`,
# so the guard would be checking words that never reach the program.
UNQUOTED_FORBIDDEN = set("$`\\{}*?[]()<>#")
# Inside double quotes bash still expands these.
DOUBLE_QUOTED_FORBIDDEN = set("$`\\")
QUOTE_HINT = "single-quote the argument if it is meant literally"


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
        # Bash and this parser disagree about control characters (a carriage
        # return is an ordinary character to bash), so none are accepted.
        if char not in "\n\t" and (ord(char) < 32 or ord(char) == 127):
            return None, "control characters are not allowed"
        if quote == "'":
            quote = None if char == "'" else quote
            current.append(char)
        elif quote == '"':
            if char in DOUBLE_QUOTED_FORBIDDEN:
                return None, f"expansion inside double quotes is not allowed; {QUOTE_HINT}"
            quote = None if char == '"' else quote
            current.append(char)
        elif char in "'\"":
            quote = char
            current.append(char)
        elif char in "2>" and (i == 0 or command[i - 1] in " \t") and SAFE_REDIRECT.match(command, i):
            current.append(" ")
            i = SAFE_REDIRECT.match(command, i).end()
            continue
        elif char == "~" and not (i and re.match(r"[\w^~@.-]", command[i - 1])):
            # Bash expands `~`, `~+` and `~user` at the start of a word and after
            # `=` or `:`, so the program would get another path than the one
            # checked here. `HEAD~1` is not an expansion.
            return None, f"tilde expansion is not allowed; {QUOTE_HINT}"
        elif char in UNQUOTED_FORBIDDEN:
            return None, (
                f"shell expansion, redirection or comment ({char!r}) is not allowed; {QUOTE_HINT}"
            )
        elif char in ";|&\n":
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


def remote_ok(rest):
    # `git remote [-v]` and `git remote get-url <name>` only. add, rename,
    # remove and set-url write config. `show` contacts the remote, and git
    # reads a name that is not configured as a path: a folder committed in the
    # branch under review.
    while rest and rest[0] in ("-v", "--verbose"):
        rest = rest[1:]
    if not rest:
        return True
    return rest[0] == "get-url" and len(rest) == 2 and bool(REMOTE_NAME.match(rest[1]))


def grep_runs_a_pager(rest):
    """`git grep -O<cmd>` / `--open-files-in-pager=<cmd>` runs a program. Git
    accepts the short flag inside a bundle (`-nO<cmd>`) and the long one
    abbreviated (`--open=<cmd>`). Checked on every word, `--` or not: git reads
    a `--` that follows `-e` as the pattern, not as the end of the options."""
    for arg in rest:
        name = arg.split("=", 1)[0]
        if re.match(r"^-[^-]*O", arg):
            return True
        if len(name) >= 4 and "--open-files-in-pager".startswith(name):
            return True
    return False


def looks_like_git_dir(path):
    return any(os.path.exists(os.path.join(path, name)) for name in ("HEAD", "objects", "refs"))


def inside_checkout(path):
    """True when git, started in `path`, would find a checkout or a worktree.

    Git walks up from `path` and stops at the first repository, bare ones
    included. A bare repository committed inside a branch under review would
    bring its own config (diff.external, core.fsmonitor), which git would run,
    so the walk must reach a `.git` entry before anything laid out like one.
    """
    path = os.path.realpath(path)
    if not os.path.isdir(path):
        return False
    while True:
        if os.path.exists(os.path.join(path, ".git")):
            return True
        if looks_like_git_dir(path):
            return False
        parent = os.path.dirname(path)
        if parent == path:
            return False
        path = parent


def git_ok(args, cwd):
    """None when this git call is a read, otherwise why it is refused."""
    # Global options: -C <path> and --no-pager only. -c is not allowed (it sets config).
    i, where = 0, cwd
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            where = os.path.join(where, args[i + 1])
            if not inside_checkout(where):
                return "git -C must point inside a checkout or a worktree"
            i += 2
        elif args[i] in ("--no-pager", "--no-optional-locks"):
            i += 1
        else:
            return f"git global option {args[i]!r} is not allowed"
    if i >= len(args) or args[i] not in GIT_READ:
        return "not a read-only git subcommand"
    sub, rest = args[i], args[i + 1:]
    if sub == "worktree":
        return None if rest[:1] == ["list"] else "only `git worktree list` is allowed"
    if sub == "remote":
        return None if remote_ok(rest) else "only `git remote -v` and `git remote get-url <name>` are allowed"
    if sub in ("branch", "tag"):
        flags = BRANCH_FLAGS if sub == "branch" else TAG_FLAGS
        if all(arg in flags for arg in rest):
            return None
        return f"only plain listing forms of `git {sub}` are allowed; use `git for-each-ref`"
    if sub == "cat-file":
        # --filters and --textconv run the repo's filters, which a committed
        # file can point at another host.
        flags = [a for a in rest if a.startswith("-")]
        return None if all(a in CAT_FILE_FLAGS for a in flags) else "git cat-file takes -p, -t, -s or -e only"
    if "--ext-diff" in rest:
        return "--ext-diff runs a program"
    # --output writes a file. Git does not accept it abbreviated.
    if any(a == "--output" or a.startswith("--output=") for a in rest):
        return "--output writes a file"
    if sub == "grep" and grep_runs_a_pager(rest):
        return "git grep must not open a pager program"
    return None


def gh_api_ok(rest):
    endpoints, fields, method, i = 0, False, None, 0
    while i < len(rest):
        arg = rest[i]
        name, has_value, value = arg.partition("=")
        if not arg.startswith("-"):
            # GitHub's own API only: a full URL would send the request, and
            # anything put in it, to another host.
            if "://" in arg:
                return "gh api takes an endpoint path, not a URL"
            if arg.lstrip("/").lower().startswith("graphql"):
                return "gh api graphql is not allowed"
            endpoints += 1
            i += 1
            continue
        if arg.upper() == "-XGET":
            method = "GET"
            i += 1
            continue
        known = (GH_API_METHOD_FLAGS | GH_API_VALUE_FLAGS | GH_API_HEADER_FLAGS
                 | GH_API_FIELD_FLAGS)
        if arg in GH_API_FLAGS:
            i += 1
            continue
        if name not in known:
            return f"gh api flag {name!r} is not allowed"
        if name.startswith("--") and has_value:
            given = value
        elif not has_value and i + 1 < len(rest):
            given = rest[i + 1]
            i += 1
        else:
            return f"gh api flag {name!r} needs its value as a separate word"
        if name in GH_API_METHOD_FLAGS:
            method = given.upper()
            if method != "GET":
                return "gh api may only GET"
        elif name in GH_API_HEADER_FLAGS and not GH_API_HEADERS.match(given):
            return "gh api header is not allowed (Accept and X-GitHub-Api-Version only)"
        elif name in GH_API_FIELD_FLAGS:
            fields = True
            # `key=@file` uploads a local file.
            if "=" not in given or given.split("=", 1)[1].startswith("@"):
                return "gh api field must be key=value and must not read a file"
        i += 1
    if fields and method != "GET":
        return "gh api fields make a POST unless `-X GET` is given"
    return None if endpoints == 1 else "gh api needs exactly one endpoint"


def gh_host_reason(args):
    """Why these gh arguments would reach a host other than github.com, or None."""
    i = 0
    while i < len(args):
        arg = args[i]
        if "://" in arg and not arg.startswith(GITHUB_URL):
            return "only https://github.com/ URLs are allowed"
        repo = None
        if arg.startswith("--repo="):
            repo = arg.split("=", 1)[1]
        elif arg == "--repo" or re.match(r"^-[A-Za-z]*R$", arg):
            repo = args[i + 1] if i + 1 < len(args) else ""
            i += 1
        elif re.match(r"^-[A-Za-z]*R.", arg):
            repo = arg.split("R", 1)[1].lstrip("=")
        elif not arg.startswith("-") and (HOST_OWNER_REPO.match(arg) or HOST_IN_WORD.search(arg)):
            return "HOST/OWNER/REPO is not allowed; name the repo as OWNER/REPO"
        if repo is not None and not OWNER_REPO.match(repo):
            return "--repo must be OWNER/REPO"
        i += 1
    return None


def gh_repo_view_reason(rest):
    repos, i = 0, 0
    while i < len(rest):
        arg = rest[i]
        if arg.startswith("-"):
            if arg.split("=", 1)[0] not in GH_REPO_VIEW_VALUE_FLAGS:
                return f"gh repo view flag {arg!r} is not allowed"
            if "=" not in arg:
                i += 1
        elif OWNER_REPO.match(arg) or arg.startswith(GITHUB_URL):
            repos += 1
        else:
            return "gh repo view takes OWNER/REPO or a https://github.com/ URL"
        i += 1
    return None if repos <= 1 else "gh repo view takes one repository"


def jq_reads_environment(args):
    """A jq filter that uses `env` or `$ENV`, which print the environment.

    Looks at every flag word (covers `--jq=…` and the attached `-q…`) and at
    the word after `--jq` or after a short flag bundle holding `q`.
    """
    for i, arg in enumerate(args):
        if not arg.startswith("-"):
            continue
        takes_next = arg == "--jq" or (not arg.startswith("--") and "q" in arg)
        following = args[i + 1] if takes_next and i + 1 < len(args) else ""
        if JQ_ENVIRONMENT.search(arg) or JQ_ENVIRONMENT.search(following):
            return True
    return False


def gh_ok(args):
    """None when this gh call is a read of github.com, otherwise why it is refused."""
    if not args:
        return "bare gh"
    if jq_reads_environment(args):
        return "jq `env` and `$ENV` are not allowed (they print the environment)"
    if args[0] == "api":
        return gh_api_ok(args[1:])
    # --web opens a browser; -w is its short form and may sit in a bundle.
    # `gh run list -w` is --workflow, and that command has no --web.
    short_w = args[:2] != ["run", "list"]
    if any(a.startswith("--web") or (short_w and re.match(r"^-[A-Za-z]*w", a)) for a in args):
        return "--web opens a browser"
    reason = gh_host_reason(args[1:])
    if reason:
        return reason
    if args[0] == "search":
        ok = len(args) >= 2 and not args[1].startswith("-")
        return None if ok else "gh search needs a type"
    if args[:2] == ["repo", "view"]:
        return gh_repo_view_reason(args[2:])
    # gh <noun> <verb> ...  e.g. gh pr view 12
    if args[0] in GH_NOUNS and len(args) >= 2 and args[1] in GH_READ_VERBS:
        return None
    return "not a read-only gh command"


def segment_reason(segment, cwd):
    tokens = shlex.split(segment)
    if not tokens:
        return None
    prog, args = tokens[0], tokens[1:]
    if prog == "git":
        return git_ok(args, cwd)
    if prog == "gh":
        return gh_ok(args)
    return "only git and gh may run"


def decide(command, cwd=None):
    """The reason `command` is refused, or None when it is allowed."""
    if not command.strip():
        return "empty command"
    segments, reason = split_commands(command)
    if reason:
        return reason
    if not segments:
        return "empty command"
    for segment in segments:
        try:
            reason = segment_reason(segment, cwd or os.getcwd())
        except ValueError:
            return "command could not be parsed"
        if reason:
            return f"{reason} (rejected: {segment.strip()[:120]!r})"
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
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        # Unreadable payload. Stay out of the way unless it names one of the
        # read-only agents, where the guard fails closed.
        if any(f"{PLUGIN}:{name}" in raw for name in READ_ONLY_AGENTS):
            deny("Read-only agent: the hook payload could not be read.")
        return
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
