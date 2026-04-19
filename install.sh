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
warn() { [ "$QUIET" -eq 0 ] && printf '  \033[33m⚠  %s\033[0m\n' "$*" ; }
bold() { [ "$QUIET" -eq 0 ] && printf '\033[1m%s\033[0m\n' "$*" ; }

bold "ATLAST ECP installer"

# ── 1. Locate a working python3 ───────────────────────────────────────────
# Preference order:
#   (a) macOS: /usr/bin/python3 first (Apple system Python — avoids Homebrew's
#       PEP 668 externally-managed-environment, which forces users into
#       --break-system-packages and contributes to multi-Python pollution)
#   (b) python3 in PATH (Linux / Windows / non-macOS)
#   (c) python  (legacy fallback)
# Every candidate must be >= 3.9.
PY=""
candidates="python3 python"
if [ "$(uname -s 2>/dev/null)" = "Darwin" ] && [ -x /usr/bin/python3 ]; then
    candidates="/usr/bin/python3 python3 python"
fi
for candidate in $candidates; do
    if command -v "$candidate" >/dev/null 2>&1 || [ -x "$candidate" ]; then
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
PYPATH="$(command -v "$PY" 2>/dev/null || readlink -f "$PY" 2>/dev/null || echo "$PY")"
log "Python: $PYPATH (v$PYVER)"

# ── 1b. Detect atlast-ecp already installed in OTHER Python interpreters ──
# We've seen users accumulate three copies of atlast-ecp across system,
# Homebrew, and pyenv Pythons over time. Each `pip install` picks whichever
# pip is first in PATH, so upgrades leak and `atlast doctor` reports whichever
# interpreter happens to run — often not the latest. Warn loudly so users can
# uninstall from the others before we add a fourth.
OTHER_PYTHONS="/usr/bin/python3 /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.9 /opt/homebrew/bin/python3.10 /opt/homebrew/bin/python3.11 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.14 /usr/local/bin/python3"
found_other_installs=0
current_canonical="$(readlink -f "$PY" 2>/dev/null || echo "$PY")"
for other_py in $OTHER_PYTHONS; do
    [ -x "$other_py" ] || continue
    other_canonical="$(readlink -f "$other_py" 2>/dev/null || echo "$other_py")"
    [ "$other_canonical" = "$current_canonical" ] && continue
    other_ver=$("$other_py" -c 'from importlib.metadata import version; print(version("atlast-ecp"))' 2>/dev/null)
    if [ -n "$other_ver" ]; then
        if [ "$found_other_installs" -eq 0 ]; then
            warn "atlast-ecp also installed under OTHER Python interpreters:"
            found_other_installs=1
        fi
        log "   $other_py → v$other_ver"
    fi
done
if [ "$found_other_installs" -eq 1 ]; then
    log ""
    log "   Multiple installs cause version drift ('atlast doctor' reports the"
    log "   wrong one; LaunchAgents point at stale binaries)."
    log "   After this installer finishes, recommend cleaning up with:"
    log "     atlast doctor --fix"
    log "   or manually: <other-python> -m pip uninstall atlast-ecp"
    log ""
fi

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

# ── 4. Check: is pip's --user bin on the user's interactive PATH? ─────────
# pip prints a one-line WARNING for this, which almost everyone skims past.
# Users then see "atlast: command not found" and think the install failed.
# On macOS we append the user-bin to ~/.zprofile automatically (the common
# convention: zprofile is sourced for login shells, unlike .zshrc which is
# only interactive). On Linux we print the line to add; distros vary too
# widely to auto-edit safely.
if [ "$IN_VENV" = "0" ]; then
    user_bin=$("$PY" -c 'import site; print(site.getuserbase())' 2>/dev/null)/bin
    if [ -n "$user_bin" ] && [ -d "$user_bin" ]; then
        if ! echo ":$PATH:" | grep -q ":$user_bin:"; then
            if [ "$(uname -s 2>/dev/null)" = "Darwin" ]; then
                zprofile="$HOME/.zprofile"
                if ! grep -qF "$user_bin" "$zprofile" 2>/dev/null; then
                    {
                        echo ""
                        echo "# Added by atlast-ecp installer ($(date +%Y-%m-%d))"
                        echo "# Ensures CLI tools installed via pip --user are on PATH."
                        echo "export PATH=\"$user_bin:\$PATH\""
                    } >> "$zprofile"
                    log ""
                    log "PATH: added $user_bin to ~/.zprofile"
                    log "      Restart your shell, or run: source ~/.zprofile"
                else
                    log ""
                    log "PATH: $user_bin already in ~/.zprofile — restart your shell to pick it up."
                fi
            else
                log ""
                warn "$user_bin is not on PATH."
                log "   Add this line to ~/.bashrc (or ~/.zshrc):"
                log "     export PATH=\"$user_bin:\$PATH\""
            fi
        fi
    fi
fi

# ── 5. Show next step ─────────────────────────────────────────────────────
if [ "$QUIET" -eq 0 ]; then
    echo
    bold "Next steps"
    echo "  atlast init              # create identity + wire Claude Code hooks"
    echo "  atlast dashboard         # open the evidence dashboard"
    echo "  atlast --help            # see all commands"
    if [ "$found_other_installs" -eq 1 ]; then
        echo
        warn "Don't forget: atlast doctor --fix"
    fi
fi
