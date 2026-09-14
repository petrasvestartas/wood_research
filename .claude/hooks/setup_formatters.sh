#!/usr/bin/env bash
# SessionStart hook: make sure the formatters format.sh needs are installed, without sudo.
# Installs what is missing (uv tool / pip --user / rustup) and prints one WARNING line per
# tool it could not install - that line lands in Claude's context, so it is reported.
#
#   ruff          Python   uv tool install ruff          | pip install --user ruff
#   clang-format  C++      uv tool install clang-format  | pip install --user clang-format
#   rustfmt       Rust     rustup component add rustfmt
set -u
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
# uv puts tool binaries where XDG says, which under a snap-launched VS Code is not ~/.local/bin.
command -v uv >/dev/null 2>&1 && PATH="$(uv tool dir --bin 2>/dev/null):$PATH"

install_py_tool() {        # $1 = package / binary name
    if command -v uv >/dev/null 2>&1; then uv tool install -q "$1" >/dev/null 2>&1 && return 0; fi
    python3 -m pip install -q --user "$1" >/dev/null 2>&1
}

missing=()
for tool in ruff clang-format; do
    command -v "$tool" >/dev/null 2>&1 && continue
    install_py_tool "$tool" && command -v "$tool" >/dev/null 2>&1 \
        && echo "formatters: installed $tool" || missing+=("$tool")
done
if ! command -v rustfmt >/dev/null 2>&1; then
    { command -v rustup >/dev/null 2>&1 && rustup component add rustfmt >/dev/null 2>&1; } \
        && echo "formatters: installed rustfmt" || missing+=("rustfmt")
fi

for tool in "${missing[@]}"; do
    case "$tool" in
        rustfmt) echo "WARNING: rustfmt is not installed and rustup is missing - install Rust from https://rustup.rs, then \`rustup component add rustfmt\`. Rust files will not be auto-formatted." ;;
        *)       echo "WARNING: $tool could not be installed (no uv, and pip --user failed) - install it by hand: \`uv tool install $tool\`. Files it formats will not be auto-formatted." ;;
    esac
done
exit 0
