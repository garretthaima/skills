#!/usr/bin/env python3
"""Static checks CI can run without Claude Code installed.

`claude plugin validate .` is the authoritative check; run it locally. This
covers what breaks most often: bad JSON, a marketplace entry that does not match
its plugin, a skill or agent with no usable frontmatter, a reference to a file
that is not in the plugin, and personal or project details in a public repo.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")
# Fields Claude Code ignores on an agent shipped in a plugin.
IGNORED_AGENT_FIELDS = {"hooks", "mcpServers", "permissionMode", "initialPrompt"}
# This repo is public. Nothing from a private project belongs in it.
PRIVATE = re.compile(r"password|secret[_-]?key|@[a-z0-9-]+\.(com|net|org)\b", re.I)

errors = []


def fail(path, message):
    errors.append(f"{path.relative_to(ROOT)}: {message}")


def load_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        fail(path, f"not valid JSON ({exc})")
        return None


def frontmatter(path):
    """The top-level keys of a file's YAML frontmatter, or None when it has none."""
    lines = path.read_text().splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return None
    block = lines[1:lines.index("---", 1)]
    return {m.group(1) for line in block if (m := re.match(r"([A-Za-z][\w-]*):", line))}


def check_markdown(path, plugin_dir, required, forbidden=()):
    keys = frontmatter(path)
    if keys is None:
        fail(path, "no frontmatter")
        return
    for key in required:
        if key not in keys:
            fail(path, f"frontmatter has no `{key}`")
    for key in forbidden:
        if key in keys:
            fail(path, f"`{key}` is ignored on a plugin agent; use a plugin hook")
    check_text(path, plugin_dir)


def check_text(path, plugin_dir):
    text = path.read_text()
    for ref in REFERENCE.findall(text):
        if not (plugin_dir / ref.rstrip(".")).exists():
            fail(path, f"refers to a file that is not in the plugin: {ref}")
    for number, line in enumerate(text.splitlines(), 1):
        if PRIVATE.search(line):
            fail(path, f"line {number} looks like a private detail")


def check_plugin(plugin_dir, entry_name):
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest = load_json(manifest_path)
    if manifest is None:
        return
    if manifest.get("name") != entry_name:
        fail(manifest_path, f"name is not the marketplace entry name `{entry_name}`")
    if not manifest.get("version"):
        fail(manifest_path, "no version")
    hooks_path = plugin_dir / "hooks" / "hooks.json"
    if hooks_path.exists():
        hooks = load_json(hooks_path)
        if hooks is not None and "hooks" not in hooks:
            fail(hooks_path, "needs a top-level `hooks` key")
        check_text(hooks_path, plugin_dir)
    for skill_dir in sorted((plugin_dir / "skills").glob("*")):
        skill = skill_dir / "SKILL.md"
        if not skill.exists():
            fail(skill_dir, "no SKILL.md")
            continue
        check_markdown(skill, plugin_dir, required=("name", "description"))
    for agent in sorted((plugin_dir / "agents").glob("*.md")):
        check_markdown(agent, plugin_dir, ("name", "description"), IGNORED_AGENT_FIELDS)
    for reference in sorted((plugin_dir / "references").glob("*.md")):
        check_text(reference, plugin_dir)


def main():
    marketplace_path = ROOT / ".claude-plugin" / "marketplace.json"
    marketplace = load_json(marketplace_path)
    if marketplace is not None:
        for key in ("name", "owner", "plugins"):
            if key not in marketplace:
                fail(marketplace_path, f"no `{key}`")
        for entry in marketplace.get("plugins", []):
            source = entry.get("source")
            if not isinstance(source, str) or not source.startswith("./") or ".." in source:
                fail(marketplace_path, f"entry `{entry.get('name')}` needs a ./ source")
                continue
            plugin_dir = ROOT / source
            if not plugin_dir.is_dir():
                fail(marketplace_path, f"source does not exist: {source}")
                continue
            check_plugin(plugin_dir, entry.get("name"))
    if errors:
        print("\n".join(errors))
        return 1
    print("plugins ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
