"""Checks the gateflow PreToolUse guards against a table of tool calls: each row must be BLOCKed (exit 2)
or ALLOWed (exit 0). Run after any guard edit and after installing on a new box:
    python3 tests/test_guards.py
Prints one line per case and exits 1 if any case is wrong.
"""
import json
import os
import subprocess
import sys

# HOOKS: this checkout's hooks directory (the guards under test).
HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
# REPO: a stand-in project directory used as the session cwd.
REPO = "/home/user/proj"
# H: the home directory the guards will resolve ~ against.
H = os.path.expanduser("~")

# BASH_CASES: (command, expected) for guard_destructive.py (plus the commit guard for `git commit`).
BASH_CASES = [
    # everyday work passes
    ("source scripts/env/activate_pacer.sh && pytest -q 2>&1 | tail -5", "ALLOW"),
    ("git status && git diff HEAD && git log --oneline -3", "ALLOW"),
    ("git add src/x.py", "ALLOW"),
    ("git restore --staged src/x.py", "ALLOW"),
    ("git checkout -b feature", "ALLOW"),
    ("git branch -d merged-branch", "ALLOW"),
    ("rm -f /tmp/x.log build.log", "ALLOW"),
    ("rm -rf /tmp/claude-1002/scratch/out", "ALLOW"),
    ("cd /tmp && rm -r deckx", "ALLOW"),
    ("find /tmp/pk -name '*.jpg' -delete", "ALLOW"),
    ("awk -F / '{print $1}' f.txt | sort | uniq -c", "ALLOW"),
    ("ls ~/.claude/plugins && cat ~/.claude/settings.json", "ALLOW"),
    ("python3 -m json.tool ~/.claude/settings.json > /dev/null && echo OK", "ALLOW"),
    ("sed -n '1,20p' ~/.claude/settings.json", "ALLOW"),
    ("git -C ~/.claude/plugins/marketplaces/gateflow log --oneline -3", "ALLOW"),
    ("systemd-run --user --collect --unit=pacer-x --working-directory=/home/user/proj "
     "bash -lc 'OUT=/tmp/pacer_x bash /home/user/proj/scripts/run/run_e3_g.sh tests/a.py'", "ALLOW"),
    ("systemctl --user reset-failed pacer-x", "ALLOW"),
    ("chmod -R u+x scripts", "ALLOW"),
    ("kill -9 12345", "ALLOW"),
    ("pkill -f pytest", "ALLOW"),
    ("timeout 20 git ls-remote https://github.com/x/y.git", "ALLOW"),
    ("echo $CLAUDECODE", "ALLOW"),
    ("gh pr view 12", "ALLOW"),
    ("claude plugin list", "ALLOW"),
    ("for f in ~/.claude/settings.json ~/.claude/settings.local.json; do cat $f; done", "ALLOW"),
    ("cd ~/.claude/plugins && find . -name hooks.json", "ALLOW"),
    ("git clone -q ~/.claude/plugins/marketplaces/gateflow /home/user/gateflow", "ALLOW"),
    ("echo \"CLAUDECODE=[${CLAUDECODE:-unset}]\"", "ALLOW"),
    ("find ~/.claude/plugins -name '*.sh' -exec chmod -x {} +", "BLOCK"),
    ("git clone https://github.com/x/y.git ~/.claude/plugins/evil", "BLOCK"),
    ("export CLAUDECODE=0; git push", "BLOCK"),
    ("bash -c 'CLAUDECODE= git commit -m x'", "BLOCK"),
    # publishing / losing work
    ("git push origin main", "BLOCK"),
    ("git -C /home/user/proj push", "BLOCK"),
    ("cd sub && git push --force", "BLOCK"),
    ("git reset --hard HEAD~1", "BLOCK"),
    ("git clean -fdx", "BLOCK"),
    ("git checkout -- .", "BLOCK"),
    ("git restore src/x.py", "BLOCK"),
    ("git branch -D old", "BLOCK"),
    ("git stash drop", "BLOCK"),
    ("git commit -m x", "BLOCK"),
    ("git commit --no-verify -m x", "BLOCK"),
    ("git -c core.hooksPath=/dev/null push", "BLOCK"),
    ("git config core.hooksPath /tmp/none", "BLOCK"),
    ("bash -c 'git push'", "BLOCK"),
    ("eval \"git push\"", "BLOCK"),
    ("(cd sub && git push)", "BLOCK"),
    ("echo $(git push)", "BLOCK"),
    # deletes outside /tmp
    ("rm -rf ~", "BLOCK"),
    ("rm -r build/", "BLOCK"),
    ("rm -Rf /home/user/proj/data", "BLOCK"),
    ("sudo rm -rf /", "BLOCK"),
    ("xargs rm -r < list.txt", "BLOCK"),
    ("rm -rf $SOMEDIR", "BLOCK"),
    ("find . -name '*.pyc' -delete", "BLOCK"),
    ("find ~ \\( -name '*.py' \\) -delete", "BLOCK"),
    ("find src -exec rm {} \\;", "BLOCK"),
    ("cd /tmp && cd ~ && rm -r stuff", "BLOCK"),
    # system-level damage
    ("dd if=/dev/zero of=/dev/nvme0n1", "BLOCK"),
    ("mkfs.ext4 /dev/sda1", "BLOCK"),
    ("chmod -R 777 /home/user", "BLOCK"),
    ("systemctl stop docker", "BLOCK"),
    ("kill -9 -1", "BLOCK"),
    ("pkill -u richie", "BLOCK"),
    ("crontab -r", "BLOCK"),
    ("reboot", "BLOCK"),
    ("gh pr merge 12", "BLOCK"),
    ("gh api -X DELETE repos/x/y", "BLOCK"),
    # disarming the guards
    ("echo '{}' > ~/.claude/settings.json", "BLOCK"),
    ("cp /tmp/x .claude/settings.local.json", "BLOCK"),
    ("sed -i 's/a/b/' ~/.claude/settings.json", "BLOCK"),
    ("rm .git/hooks/pre-push", "BLOCK"),
    ("chmod -x .git/hooks/pre-commit", "BLOCK"),
    ("mv ~/.claude ~/.claude.bak", "BLOCK"),
    ("tee ~/.claude/hooks/x.sh < /tmp/x", "BLOCK"),
    ("claude plugin disable gateflow@gateflow", "BLOCK"),
    ("unset CLAUDECODE; git commit -m x", "BLOCK"),
    ("env -u CLAUDECODE git push", "BLOCK"),
    ("CLAUDECODE= git push", "BLOCK"),
]

# FILE_CASES: (tool, path, expected) for guard_protected_paths.py.
FILE_CASES = [
    ("Edit", REPO + "/src/x.py", "ALLOW"),
    ("Write", "/tmp/claude-1002/scratch/a.sh", "ALLOW"),
    ("Edit", H + "/.claude/projects/-home-user-proj/memory/MEMORY.md", "ALLOW"),
    ("Write", H + "/gateflow/hooks/guard_lib.py", "ALLOW"),
    ("Edit", H + "/.claude/settings.json", "BLOCK"),
    ("Write", H + "/.claude/settings.local.json", "BLOCK"),
    ("Edit", REPO + "/.claude/settings.local.json", "BLOCK"),
    ("Write", REPO + "/.claude/hooks/x.sh", "BLOCK"),
    ("Edit", H + "/.claude/plugins/cache/gateflow/gateflow/0.2.0/hooks/hooks.json", "BLOCK"),
    ("Write", REPO + "/.git/hooks/pre-push", "BLOCK"),
    ("Edit", REPO + "/.git/config", "BLOCK"),
    ("Edit", H + "/.gitconfig", "BLOCK"),
    ("NotebookEdit", H + "/.claude/hooks/nb.ipynb", "BLOCK"),
]


def run(script, payload):
    """Runs one guard on one payload; returns 'BLOCK' (exit 2), 'ALLOW' (exit 0) or 'ERROR ...'. A
    fail-closed internal error also exits 2, so it is reported as ERROR rather than a correct BLOCK."""
    r = subprocess.run([sys.executable, os.path.join(HOOKS, script)], input=json.dumps(payload),
                       capture_output=True, text=True)
    if "internal error" in r.stderr:
        return "ERROR " + r.stderr.strip()
    return {0: "ALLOW", 2: "BLOCK"}.get(r.returncode, "ERROR %d %s" % (r.returncode, r.stderr.strip()))


def run_commit_guard(payload):
    """Runs the existing guard_no_git_commit.sh; used so `git commit` rows test the combined behavior."""
    r = subprocess.run(["bash", os.path.join(HOOKS, "guard_no_git_commit.sh")], input=json.dumps(payload),
                       capture_output=True, text=True)
    return "BLOCK" if r.returncode == 2 else "ALLOW"


def main():
    """Runs every case and prints PASS/FAIL lines; exits 1 on any failure."""
    failures = 0
    for command, expected in BASH_CASES:
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": REPO}
        got = run("guard_destructive.py", payload)
        if got == "ALLOW" and run_commit_guard(payload) == "BLOCK":
            got = "BLOCK"
        ok = got == expected
        failures += not ok
        print("%s  %-5s  Bash  %s" % ("PASS" if ok else "FAIL", got, command))
    for tool, path, expected in FILE_CASES:
        key = "notebook_path" if tool == "NotebookEdit" else "file_path"
        got = run("guard_protected_paths.py", {"tool_name": tool, "tool_input": {key: path}, "cwd": REPO})
        ok = got == expected
        failures += not ok
        print("%s  %-5s  %-5s %s" % ("PASS" if ok else "FAIL", got, tool, path))
    total = len(BASH_CASES) + len(FILE_CASES)
    print("\n%d/%d cases correct" % (total - failures, total))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
