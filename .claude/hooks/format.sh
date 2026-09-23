#!/usr/bin/env bash
# PostToolUse(Edit|Write): format the file Claude just wrote, per language.
#   .py           ruff format        style from the nearest pyproject.toml [tool.ruff]
#   .rs           rustfmt            style from rustfmt.toml, defaults otherwise
#   .cpp .h .hpp  clang-format       ONLY when a .clang-format is found above the file
#                                    (--fallback-style=none); LLVM defaults would rewrite the kernel.
# A missing formatter is a one-line warning, never an error: setup_formatters.sh (SessionStart)
# installs them, and a machine where that failed must still be able to edit.
set -u
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
# uv puts tool binaries where XDG says, which under a snap-launched VS Code is not ~/.local/bin.
command -v uv >/dev/null 2>&1 && PATH="$(uv tool dir --bin 2>/dev/null):$PATH"

f=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)
[ -n "$f" ] && [ -f "$f" ] || exit 0

need() { command -v "$1" >/dev/null 2>&1 && return 0; echo "WARNING: $1 not installed - $f left unformatted (run .claude/hooks/setup_formatters.sh)"; return 1; }

# The edition of the nearest Cargo.toml above the file; a wrong one re-sorts every import in it.
edition() {
    local d
    d=$(dirname "$1")
    while [ "$d" != "/" ] && [ ! -f "$d/Cargo.toml" ]; do d=$(dirname "$d"); done
    sed -n 's/^edition *= *"\([0-9]*\)".*/\1/p' "$d/Cargo.toml" 2>/dev/null | head -1 | grep . || echo 2021
}

case "$f" in
    *.py)             need ruff         && ruff format -q "$f" ;;
    # through stdin: rustfmt on a path also reformats every module file that one declares
    *.rs)             need rustfmt      && out=$(rustfmt --edition "$(edition "$f")" --emit stdout < "$f" 2>/dev/null) && [ -n "$out" ] && printf '%s\n' "$out" > "$f" ;;
    *.cpp|*.h|*.hpp)  need clang-format && clang-format -i --style=file --fallback-style=none "$f" ;;
esac
exit 0
