"""gateflow guard (PreToolUse:Edit|Write|MultiEdit|NotebookEdit): blocks file edits that could disarm the
guards or rewrite permissions: Claude settings (user or project), hook directories, installed plugins,
git hooks, and git config (core.hooksPath). The user edits those files themselves.
Internal errors fail CLOSED (block), matching guard_destructive.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard_lib as g  # noqa: E402


def main():
    """Entry point: reads the file-tool call and exits 0 (allow) or 2 (block)."""
    payload = g.read_payload()
    tool_input = payload.get("tool_input", {})
    target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not target:
        sys.exit(0)
    try:
        path = g.resolve(target, payload.get("cwd") or os.getcwd())
        if path is None or g.is_protected(os.path.realpath(path)) or g.is_protected(path):
            g.block("editing " + target + " is the user's action (settings, hooks, plugins and git config "
                    "are protected so an unattended session cannot disarm its own guards).")
    except SystemExit:
        raise
    except Exception as e:  # fail closed
        g.block("guard_protected_paths.py internal error (" + type(e).__name__ + ": " + str(e) + ").")
    sys.exit(0)


if __name__ == "__main__":
    main()
