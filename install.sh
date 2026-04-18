#!/usr/bin/env bash
# ATLAST ECP one-line installer.
#
# Works across:
#   - macOS with Apple Python (/usr/bin/python3)
#   - macOS with Homebrew Python (PEP 668 externally-managed)
#   - Linux with system Python (Debian 12+/Ubuntu 23+ PEP 668)
#   - Any active venv / conda env / pyenv
#
# Usage:
#   curl -sSL https://weba0.com/install.sh | bash
#   curl -sSL https://weba0.com/install.sh | bash -s -- --proxy
#
# Flags:
#   --proxy    install the [proxy] extra (aiohttp for Layer-0 proxy)
#   --all      install the [all] extra (crypto + proxy + otel)
#   --upgrade  pass --upgrade to pip
#   --quiet    suppress progress output
#
# Exit codes:
#   0  installed (or already up-to-date)
#   1  fatal — no suitable Python / pip available
#   2  install attempted but failed

set -u

EXTRAS=""
UPGRADE_FLAG=""
QUIET=0

while [ $# -gt 0 ]; do
    case "$1" in
        --proxy)   EXTRAS="[proxy]"          ; shift ;;
        --all)     EXTRAS="[all]"            ; shift ;;
        --upgrade) UPGRADE_FLAG="--upgrade"  ; shift ;;
        --quiet)   QUIET=1                   ; shift ;;
        *) printf 'unknown flag: %s\n' "$1" >&2 ; exit 1 ;;
    esac
done

log()  { [ "$QUIET" -eq 0 ] && printf '  %s\n' "$*" ; }
err()  { printf '  ERROR: %s\n' "$*" >&2 ; }
bold() { [ "$QUIET" -eq 0 ] && printf '\033[1m%s\033[0m\n' "$*" ; }

bold "ATLAST ECP installer"

# ── 1. Locate a working python3 ───────────────────────────────────────────
PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' 2>/dev/null; then
            PY="$candidate"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    err "Python 3.9 or newer is required but not found."
    err "Install from https://www.python.org/downloads/ and re-run."
    exit 1
fi

PYVER="$("$PY" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
PYPATH="$(command -v "$PY")"
log "Python: $PYPATH (v$PYVER)"

# ── 2. Pick the right pip install target ──────────────────────────────────
# Priority:
#   a. If the user is inside a venv/conda/pyenv → install into the env.
#   b. Else try --user (bypasses PEP 668 on Homebrew + most distros).
#   c. Fall back to --break-system-packages --user (locked-down distros).
IN_VENV=$("$PY" -c 'import sys; print("1" if sys.prefix != sys.base_prefix else "0")')

PKG_SPEC="atlast-ecp${EXTRAS}"
BASE_CMD="$PY -m pip install $UPGRADE_FLAG --disable-pip-version-check"

attempt() {
    local tag="$1"; shift
    log "Trying: $tag"
    "$@" 2>/tmp/atlast_install_err.log
    local rc=$?
    if [ "$rc" -eq 0 ]; then
        return 0
    fi
    local msg
    msg=$(tail -n 3 /tmp/atlast_install_err.log 2>/dev/null)
    log "  ↳ failed: ${msg:0:200}"
    return "$rc"
}

installed=0
if [ "$IN_VENV" = "1" ]; then
    log "Detected active virtual environment — installing into it."
    attempt "venv install" $BASE_CMD "$PKG_SPEC" && installed=1
else
    # Sequence: --user first, then --user --break-system-packages
    attempt "user install (--user)" $BASE_CMD --user "$PKG_SPEC" && installed=1
    if [ "$installed" -eq 0 ]; then
        attempt "user install (--user --break-system-packages)" \
            $BASE_CMD --user --break-system-packages "$PKG_SPEC" && installed=1
    fi
fi

if [ "$installed" -eq 0 ]; then
    err "Could not install atlast-ecp with any strategy."
    err "Last error:"
    sed 's/^/    /' /tmp/atlast_install_err.log >&2
    echo
    err "Workarounds:"
    err "  • Create a venv:"
    err "      python3 -m venv ~/.atlast-venv && source ~/.atlast-venv/bin/activate"
    err "      pip install atlast-ecp"
    err "  • Or use pipx (CLI only):"
    err "      brew install pipx && pipx install atlast-ecp"
    exit 2
fi

# ── 3. Verify ─────────────────────────────────────────────────────────────
if "$PY" -c 'import atlast_ecp; print("  Version:  atlast-ecp", atlast_ecp.__version__)' 2>/dev/null; then
    :
else
    err "Installed but 'import atlast_ecp' failed."
    err "The package may be in a location not on PYTHONPATH."
    err "Try: $PY -m atlast_ecp.cli --version"
    exit 2
fi

# ── 4. Show next step ─────────────────────────────────────────────────────
if [ "$QUIET" -eq 0 ]; then
    echo
    bold "Next steps"
    echo "  atlast init              # create identity + wire Claude Code hooks"
    echo "  atlast dashboard         # open the evidence dashboard"
    echo "  atlast --help            # see all commands"
fi
