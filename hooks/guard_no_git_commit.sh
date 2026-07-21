#!/usr/bin/env bash
# gateflow guard (PreToolUse:Bash). Blocks `git commit` — committing is the USER's action, never the
# assistant's. The assistant may stage (`git add`) with approval and DRAFT a commit message, but the user
# always runs the commit themselves. Precise by design: only the `commit` / `commit-tree` subcommand is
# blocked; add / status / diff / log / restore / push / branch / etc. pass untouched, across && / ; / |
# chains, and a `git commit` that appears only inside a quoted string (e.g. `echo "git commit"`) is NOT
# blocked (shlex keeps it a single token). Global options and their args (`-C <path>`, `-c k=v`) are
# skipped so `git -C /repo commit` is still caught.
# Reads the PreToolUse JSON on stdin; exit 2 = block (stderr is fed back to the model); exit 0 = allow.
# NOTE: the JSON is passed to python via an env var — the heredoc already occupies python's stdin, so
# python must NOT read the payload from sys.stdin (that scar is why an early version of this hook no-op'd).
input=$(cat)
HOOK_INPUT="$input" python3 - <<'PY'
import os, sys, json, shlex, re
try:
    cmd = json.loads(os.environ.get("HOOK_INPUT", "")).get("tool_input", {}).get("command", "")
except Exception:
    sys.exit(0)

WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix"}

def is_git_commit(cmd):
    for seg in re.split(r"&&|\|\||[;&|\n]", cmd):          # one git invocation per shell segment
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = seg.split()                            # unbalanced quotes: fall back, err toward blocking
        k = 0
        while k < len(toks) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[k]):
            k += 1                                         # skip leading VAR=val env assignments
        for i in range(k, len(toks)):
            t = toks[i]
            if t == "git" or t.endswith("/git"):
                j = i + 1
                while j < len(toks):
                    tj = toks[j]
                    if tj in WITH_ARG:                     # global option that consumes the next token
                        j += 2; continue
                    if tj.startswith("-"):                 # any other global option/flag
                        j += 1; continue
                    if tj in ("commit", "commit-tree"):    # first positional = the subcommand
                        return True
                    break                                  # some other subcommand → allow
                break                                      # only the first git in the segment matters
    return False

if is_git_commit(cmd):
    sys.stderr.write(
        "BLOCKED (gateflow guard): 'git commit' is the USER's action, never the assistant's. "
        "Stage with 'git add' (on approval) and DRAFT the commit message for the user to run "
        "themselves — do not attempt the commit. See gateflow NORMS.md.\n")
    sys.exit(2)
sys.exit(0)
PY
