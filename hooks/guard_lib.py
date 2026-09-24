"""Shared helpers for the gateflow PreToolUse guards (guard_destructive.py, guard_protected_paths.py).

The guards stop an unattended session (including one in bypass-permissions mode) from making the common
destructive or self-disarming mistakes. They match on command TEXT, so they cannot see what a script or a
Python heredoc does once it runs; they are a seatbelt against slips, not a sandbox.

Protocol (Claude Code PreToolUse hooks): the tool-call JSON arrives on stdin; exit 2 blocks the call and
stderr is shown to the model; exit 0 lets the call through.
"""
import json
import os
import re
import sys

# HOME: the user's home directory, used to resolve ~ and to anchor the user-level protected paths.
HOME = os.path.expanduser("~")

# PROTECTED_UNDER: directories whose whole subtree is protected (the guards, plugins, and git hook dirs).
PROTECTED_UNDER = (
    os.path.join(HOME, ".claude", "plugins"),
    os.path.join(HOME, ".claude", "hooks"),
    os.path.join(HOME, ".config", "git"),
)

# PROTECTED_EXACT: single files that configure hooks or permissions at user level.
PROTECTED_EXACT = (
    os.path.join(HOME, ".gitconfig"),
)

# PROTECTED_ANCESTORS: directories that are not protected to read, but moving/copying/removing them as a
# whole would take a protected path with them, so a WRITER that names one of them is blocked.
PROTECTED_ANCESTORS = ("/", "/home", HOME, os.path.join(HOME, ".claude"), os.path.join(HOME, ".config"))

# ANY_REPO_PATTERNS: protected paths that can sit in any project: the project-level Claude settings and
# hooks, and a repo's git hooks and git config (core.hooksPath would disarm the git hooks).
ANY_REPO_PATTERNS = (
    re.compile(r"(^|/)\.claude/settings(\.local)?\.json$"),
    re.compile(r"(^|/)\.claude/hooks(/|$)"),
    re.compile(r"(^|/)\.git/hooks(/|$)"),
    re.compile(r"(^|/)\.git/config$"),
)

# GLOB_CHARS: shell glob metacharacters; a globbed path is judged by the directory the glob sits in.
GLOB_CHARS = "*?["


def read_payload():
    """Parses the PreToolUse JSON from stdin; used by both guards. Returns {} on unreadable input."""
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def block(reason):
    """Writes the refusal to stderr and exits 2 (Claude Code blocks the call); used by both guards."""
    sys.stderr.write("BLOCKED (gateflow guard): " + reason + "\n")
    sys.exit(2)


def resolve(token, cwd):
    """Turns a command-line token into an absolute normalized path, or None if it cannot be resolved
    (unexpanded $VAR / backtick). Used by both guards to judge every path-like argument."""
    token = os.path.expandvars(token)
    if "$" in token or "`" in token:
        return None
    token = os.path.expanduser(token)
    if not os.path.isabs(token):
        token = os.path.join(cwd or os.getcwd(), token)
    path = os.path.normpath(token)
    cut = min((path.find(c) for c in GLOB_CHARS if c in path), default=-1)
    if cut >= 0:
        path = os.path.dirname(path[:cut] + "x")
    return path


def is_protected(path):
    """True if writing `path` could disarm a guard or rewrite permissions/hooks; used by both guards."""
    if path is None:
        return False
    if path in PROTECTED_EXACT:
        return True
    for root in PROTECTED_UNDER:
        if path == root or path.startswith(root + "/"):
            return True
    return any(p.search(path) for p in ANY_REPO_PATTERNS)


def is_protected_for_writer(path):
    """is_protected plus the ancestor directories (moving ~/.claude moves its settings too); used by the
    Bash guard for commands that can write."""
    return is_protected(path) or path in PROTECTED_ANCESTORS


def under_tmp(path):
    """True if `path` is inside /tmp (which holds the session scratchpads); used for rm -r / find -delete."""
    return path is not None and path.startswith("/tmp/")
