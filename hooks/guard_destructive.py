"""gateflow guard (PreToolUse:Bash): blocks destructive or guard-disarming shell commands.

What it refuses, per shell segment (split on && || ; | & newline, $( and backticks):
  - git: push, reset --hard, clean -f, checkout/restore that discards work-tree changes, branch -D,
    stash drop/clear, filter-branch/filter-repo, reflog expire/delete, update-ref -d, --no-verify, and
    anything touching core.hooksPath (each of those loses work, publishes, or disarms the git hooks);
  - rm -r, and find -delete / -exec rm, outside /tmp;
  - disk-level tools (dd of=/dev/..., mkfs*, wipefs, fdisk, sfdisk, parted, shred), chmod/chown -R
    outside the repo and /tmp, system (non --user) systemctl state changes, reboot/shutdown/poweroff/halt,
    kill -1 / pkill -u / killall -u, crontab -r;
  - outward-facing gh calls (repo/pr/release/issue writes, non-GET gh api);
  - disarming the guards: writes that name a protected path (settings, hooks, plugins, git config),
    `claude plugin disable/uninstall/remove`, `claude config`, and unsetting CLAUDECODE (the variable the
    git hooks key on).
It recurses into `bash -c '...'` / `sh -c` / `eval` strings. `git commit` is left to guard_no_git_commit.sh.
Internal errors fail CLOSED (block), so a bug stalls a session visibly instead of silently disarming.
"""
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard_lib as g  # noqa: E402

# SEGMENT_SPLIT: shell operators that start a new command; quotes are ignored on purpose, so text inside
# `bash -c '...'` is also exposed as segments. Parentheses are NOT split (find's \( \) grouping would cut
# -delete off its find); tokenize strips subshell parens from the words instead.
SEGMENT_SPLIT = re.compile(r"&&|\|\||\$\(|[;&|\n`]")

# WRAPPERS: commands that run another command; the guard judges the wrapped command instead.
WRAPPERS = {"sudo", "doas", "env", "nohup", "nice", "ionice", "time", "command", "exec", "builtin",
            "stdbuf", "timeout", "xargs", "setsid", "unbuffer", "systemd-run", "watch", "then", "do",
            "else", "{", "!"}

# SHELLS: interpreters whose -c string is itself a command line to check.
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}

# READERS: commands that cannot modify a path they name (output redirection is checked separately).
READERS = {"cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "rg", "ls", "stat", "file",
           "wc", "diff", "cmp", "md5sum", "sha1sum", "sha256sum", "jq", "readlink", "realpath", "basename",
           "dirname", "test", "[", "tree", "du", "echo", "printf", "cd", "pushd", "popd", "source", ".",
           "for", "while", "until", "if", "case", "select"}

# FIND_ACTIONS: find primaries that run a command or delete; without them find only reads.
FIND_ACTIONS = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprintf", "-fls"}

# MOVERS: commands that can carry a whole directory tree away or rewrite its permissions; for these,
# naming an ancestor of a protected path (~, ~/.claude, /) is enough to block.
MOVERS = {"mv", "cp", "rsync", "ln", "install", "chmod", "chown", "chgrp", "tar"}

# GIT_READS: git subcommands that do not write the files they name (for the protected-path check only;
# the destructive git forms are judged separately in check_git).
GIT_READS = {"status", "log", "diff", "show", "remote", "rev-parse", "ls-files", "ls-remote", "branch",
             "config", "blame", "grep", "shortlog", "describe", "tag", "check-ignore", "cat-file", "reflog",
             "fetch"}

# GIT_WITH_ARG: git global options that consume the following token.
GIT_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix"}

# GH_WRITES: gh (GitHub CLI) subcommand pairs that change something on GitHub.
GH_WRITES = {
    "repo": {"create", "delete", "edit", "rename", "archive", "fork", "sync"},
    "pr": {"create", "merge", "close", "edit", "ready", "review", "comment", "reopen"},
    "release": {"create", "delete", "edit", "upload"},
    "issue": {"create", "close", "delete", "comment", "edit", "reopen", "transfer"},
}

# SYSTEMCTL_CHANGES: systemctl verbs that change system state (allowed only with --user).
SYSTEMCTL_CHANGES = {"start", "stop", "restart", "reload", "enable", "disable", "mask", "unmask", "kill",
                     "isolate", "poweroff", "reboot", "halt", "suspend", "hibernate", "edit", "set-property",
                     "daemon-reload", "reset-failed"}

# DISK_TOOLS: commands that destroy data at the device or file-content level.
DISK_TOOLS = {"wipefs", "fdisk", "sfdisk", "parted", "shred", "reboot", "shutdown", "poweroff", "halt",
              "killall5"}

# REDIRECT: an output redirection token (>, >>, 2>, &>), optionally with its target attached.
REDIRECT = re.compile(r"^(\d*|&)>>?\|?(.*)$")


def tokenize(segment):
    """Splits one shell segment into words; falls back to whitespace split (quotes stripped) when the
    quotes are unbalanced, which happens whenever SEGMENT_SPLIT cut through a quoted string."""
    try:
        toks = shlex.split(segment)
    except ValueError:
        toks = [t.strip("'\"") for t in segment.split()]
    if toks:
        toks[0] = toks[0].lstrip("({")
    toks = [t.rstrip(")") if len(t) > 1 else t for t in toks]
    return [t for t in toks if t]


def unwrap(toks):
    """Drops env assignments and wrapper commands (with their options/durations) from the front, so the
    guard judges the command that actually runs; used by check_segment."""
    i = 0
    while i < len(toks):
        t = toks[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            i += 1
        elif os.path.basename(t) in WRAPPERS:
            i += 1
            while i < len(toks) and (toks[i].startswith("-") or re.match(r"^[\d.]+[smhd]?$", toks[i])):
                i += 2 if toks[i] in ("-u", "-n", "-p", "-s", "-k", "--unit", "--property") else 1
        else:
            break
    return toks[i:]


def git_subcommand(args):
    """Returns (subcommand, its arguments) from the tokens after `git`, skipping global options; used by
    check_git and the protected-path reader test."""
    j = 0
    while j < len(args):
        if args[j] in GIT_WITH_ARG:
            j += 2
        elif args[j].startswith("-"):
            j += 1
        else:
            return args[j], args[j + 1:]
    return "", []


def check_git(args, cwd):
    """Blocks the git subcommands/options that publish, discard work, or disarm hooks; args = tokens
    after `git`."""
    if "core.hookspath" in " ".join(args).lower():
        g.block("changing core.hooksPath would disarm the git hooks.")
    if "--no-verify" in args:
        g.block("--no-verify skips the git hooks that refuse commits/pushes from Claude sessions.")
    sub, rest = git_subcommand(args)
    if not sub:
        return
    flags = {a for a in rest if a.startswith("-")}
    if sub == "push":
        g.block("'git push' publishes; pushing is the user's action.")
    if sub == "reset" and "--hard" in flags:
        g.block("'git reset --hard' discards uncommitted work.")
    if sub == "clean" and any(f == "--force" or (not f.startswith("--") and "f" in f) for f in flags):
        g.block("'git clean -f' deletes untracked files.")
    if sub == "checkout" and ("--" in rest or "." in rest or flags & {"-f", "--force"}):
        g.block("'git checkout -- <path>' / '-f' discards work-tree changes.")
    if sub == "restore" and not ("--staged" in flags or "-S" in flags) or (
            sub == "restore" and flags & {"--worktree", "-W"}):
        g.block("'git restore' of the work tree discards changes (--staged alone is allowed).")
    if sub == "branch" and any(f == "-D" or (not f.startswith("--") and "D" in f) for f in flags):
        g.block("'git branch -D' deletes an unmerged branch.")
    if sub == "branch" and "--delete" in flags and "--force" in flags:
        g.block("'git branch --delete --force' deletes an unmerged branch.")
    if sub == "stash" and rest[:1] and rest[0] in ("drop", "clear"):
        g.block("'git stash drop/clear' deletes stashed work.")
    if sub in ("filter-branch", "filter-repo"):
        g.block("history rewriting is the user's action.")
    if sub == "reflog" and rest[:1] and rest[0] in ("expire", "delete"):
        g.block("'git reflog expire/delete' removes the recovery log.")
    if sub == "update-ref" and flags & {"-d", "--delete"}:
        g.block("'git update-ref -d' deletes a ref.")


def check_paths_for_writer(cmd, args, cwd):
    """Blocks a non-reader command that names a protected path (or an ancestor of one); used by
    check_segment for every command not in READERS."""
    for a in args:
        target = a.split("=", 1)[1] if a.startswith("-") and "=" in a else a
        if target.startswith("-") or not target:
            continue
        path = g.resolve(target, cwd)
        if path is None and re.search(r"\.claude|\.git|gitconfig", target):
            g.block(cmd + " names an unresolvable path that may be a protected one: " + target)
        hit = g.is_protected_for_writer(path) if cmd in MOVERS else g.is_protected(path)
        if path is not None and hit:
            g.block(cmd + " would modify a protected path (settings, hooks, plugins, git config): " + path)


def is_reader(cmd, args):
    """True if the command cannot modify the paths it names: READERS, sed without -i, python's json.tool,
    and read-only git subcommands; used by check_segment to skip the protected-path check."""
    if cmd in READERS:
        return True
    if cmd == "sed":
        return not any(a.startswith("-i") or a.startswith("--in-place") for a in args)
    if cmd.startswith("python") and args[:2] == ["-m", "json.tool"]:
        return True
    if cmd == "find":
        return not any(a in FIND_ACTIONS for a in args)
    if cmd == "git":
        return git_subcommand(args)[0] in GIT_READS
    return False


def check_redirects(toks, cwd):
    """Blocks output redirection into a protected path, whatever the command; used by check_segment."""
    for i, t in enumerate(toks):
        m = REDIRECT.match(t)
        if not m:
            continue
        target = m.group(2) or (toks[i + 1] if i + 1 < len(toks) else "")
        path = g.resolve(target, cwd) if target else None
        if path is not None and g.is_protected_for_writer(path):
            g.block("output redirection into a protected path: " + path)


def outside_tmp(paths_args, cwd):
    """Returns the first argument that does not resolve inside /tmp (or '' if all do); used for the
    recursive-delete rules."""
    for a in paths_args:
        if not g.under_tmp(g.resolve(a, cwd)):
            return a
    return ""


def check_segment(segment, cwd, depth=0):
    """Checks one shell segment; returns the working directory after it (a `cd` moves it for the segments
    that follow). Recurses into shell -c strings and eval."""
    toks = tokenize(segment)
    check_claudecode(toks)
    check_redirects(toks, cwd)
    toks = [t for t in unwrap(toks) if not REDIRECT.match(t)]
    if not toks:
        return cwd
    cmd, args = os.path.basename(toks[0]), toks[1:]

    if depth < 4:
        for i, t in enumerate(toks[:-2]):
            if os.path.basename(t) in SHELLS and toks[i + 1].startswith("-") and "c" in toks[i + 1]:
                check_command(toks[i + 2], cwd, depth + 1)
        if cmd == "eval":
            check_command(" ".join(args), cwd, depth + 1)

    if cmd == "cd":
        return g.resolve(args[0], cwd) or cwd if args else g.HOME
    if cmd == "git":
        check_git(args, cwd)
    if cmd == "rm":
        opts = [a for a in args if a.startswith("-") and a != "--"]
        recursive = any(o in ("--recursive",) or (not o.startswith("--") and ("r" in o or "R" in o))
                        for o in opts)
        if recursive:
            bad = outside_tmp([a for a in args if not a.startswith("-")], cwd)
            if bad:
                g.block("'rm -r' outside /tmp (" + bad + "); recursive deletes are limited to /tmp.")
    if cmd == "find" and ("-delete" in args or any(
            a in ("-exec", "-execdir", "-ok") and i + 1 < len(args)
            and os.path.basename(args[i + 1]) in ("rm", "shred", "unlink") for i, a in enumerate(args))):
        roots = []
        for a in args:
            if a.startswith("-") or a in ("(", "!"):
                break
            roots.append(a)
        bad = outside_tmp(roots or ["."], cwd)
        if bad:
            g.block("'find -delete / -exec rm' outside /tmp (" + bad + ").")
    if cmd == "dd" and any(a.startswith("of=/dev/") and a != "of=/dev/null" for a in args):
        g.block("'dd of=/dev/...' writes a raw device.")
    if cmd.startswith("mkfs") or cmd in DISK_TOOLS:
        g.block("'" + cmd + "' is a disk-level or power command.")
    if cmd in ("chmod", "chown", "chgrp") and any(a in ("-R", "--recursive") or
                                                   (re.match(r"^-[a-zA-Z]+$", a) and "R" in a) for a in args):
        for a in args:
            if a.startswith("-"):
                continue
            p = g.resolve(a, cwd)
            if p is not None and not (g.under_tmp(p) or p == cwd or p.startswith(os.path.join(cwd, ""))):
                g.block("recursive " + cmd + " outside the repo and /tmp: " + a)
    if cmd == "systemctl" and "--user" not in args and any(a in SYSTEMCTL_CHANGES for a in args):
        g.block("system-level systemctl state change (only --user units are allowed).")
    if cmd == "kill" and "-1" in args[1:]:
        g.block("'kill ... -1' signals every process you own.")
    if cmd in ("pkill", "killall") and any(a in ("-u", "--user") or a.startswith("--user=") for a in args):
        g.block("'" + cmd + " -u' kills every process of a user.")
    if cmd == "crontab" and "-r" in args:
        g.block("'crontab -r' deletes the crontab.")
    if cmd == "gh" and len(args) >= 2 and args[1] in GH_WRITES.get(args[0], ()):
        g.block("'gh " + args[0] + " " + args[1] + "' changes GitHub; that is the user's action.")
    if cmd == "gh" and args[:1] == ["api"] and any(
            a in ("-X", "--method") and i + 1 < len(args) and args[i + 1].upper() != "GET"
            or a.startswith("--method=") and a.split("=", 1)[1].upper() != "GET"
            or a in ("-f", "-F", "--field", "--raw-field", "--input") for i, a in enumerate(args)):
        g.block("non-GET 'gh api' call changes GitHub.")
    if cmd == "claude" and args[:1] == ["plugin"] and any(a in ("disable", "uninstall", "remove") for a in args):
        g.block("disabling/removing a Claude Code plugin would remove the guards.")
    if cmd == "claude" and args[:1] == ["config"]:
        g.block("'claude config' changes Claude Code settings; that is the user's action.")
    if cmd == "git" and git_subcommand(args)[0] == "clone":
        positional = [a for a in git_subcommand(args)[1] if not a.startswith("-")]
        check_paths_for_writer("git clone", positional[-1:] if len(positional) > 1 else [], cwd)
    elif not is_reader(cmd, args):
        check_paths_for_writer(cmd, args, cwd)
    return cwd


def check_claudecode(toks):
    """Blocks assigning, exporting or unsetting CLAUDECODE (the variable the git hooks key on); judged on
    words, so the name inside a quoted string or an echo is fine. Used by check_segment."""
    lead = True
    for i, t in enumerate(toks):
        prev = toks[i - 1] if i else ""
        is_assign = re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t) is not None
        if t.startswith("CLAUDECODE=") and (lead or prev in ("export", "declare", "typeset", "local",
                                                              "readonly", "env") or prev.startswith("-")):
            g.block("changing CLAUDECODE would disarm the git hooks that refuse Claude commits/pushes.")
        if t == "CLAUDECODE" and (prev in ("unset", "-u", "-v", "-n") or (toks[:1] == ["unset"])):
            g.block("unsetting CLAUDECODE would disarm the git hooks that refuse Claude commits/pushes.")
        if t in ("-uCLAUDECODE", "--unset=CLAUDECODE"):
            g.block("unsetting CLAUDECODE would disarm the git hooks that refuse Claude commits/pushes.")
        lead = lead and (is_assign or os.path.basename(t) in WRAPPERS)


def check_command(command, cwd, depth=0):
    """Checks a whole command line, segment by segment, carrying `cd` forward; used by main and by the
    shell -c / eval recursion."""
    for segment in SEGMENT_SPLIT.split(command):
        if segment.strip():
            cwd = check_segment(segment, cwd, depth)


def main():
    """Entry point: reads the Bash tool call and exits 0 (allow) or 2 (block)."""
    payload = g.read_payload()
    command = payload.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)
    try:
        check_command(command, payload.get("cwd") or os.getcwd())
    except SystemExit:
        raise
    except Exception as e:  # fail closed: a guard bug must be visible, not a silent pass
        g.block("guard_destructive.py internal error (" + type(e).__name__ + ": " + str(e) +
                "); fix the guard or run the command yourself.")
    sys.exit(0)


if __name__ == "__main__":
    main()
