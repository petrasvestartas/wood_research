#!/usr/bin/env bash
# Bring every repo here onto the latest session kernel, then rebuild what compiles against it.
#
#   bash/update_session.sh            update session_cpp, rebuild wood and wood_nano, update Python deps
#   bash/update_session.sh --no-build only update the sources and the Python packages
#
# Safe to re-run: every step is a no-op when already up to date. One build at a time,
# bounded to 4 parallel jobs - see wood/CLAUDE.md for why nothing here runs concurrently.
set -euo pipefail

# ../ because this lives in bash/ alongside pull.sh, push.sh and publish_scene.sh; every path
# below is anchored to the superproject root, not to this folder.
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SESSION_CPP="$HERE/session_cpp"          # the submodule, see README.md
BUILD=1
[[ "${1:-}" == "--no-build" ]] && BUILD=0

step() { printf '\n== %s ==\n' "$*"; }

# ── 1. session_cpp: the one kernel checkout that wood and wood_nano both compile ────────
# This moves session_cpp alone. bash/pull.sh is the whole-stack version - every submodule
# onto its branch - and is what to run after a fresh clone.
step "session_cpp"
if [ ! -e "$SESSION_CPP/CMakeLists.txt" ]; then
    echo "no session_cpp at $SESSION_CPP - the submodule is not checked out. Run:"
    echo "  bash/pull.sh"
    exit 1
fi
if git -C "$SESSION_CPP" symbolic-ref -q HEAD >/dev/null; then
    git -C "$SESSION_CPP" pull --ff-only
else
    # A submodule checkout sits on a detached HEAD; move it to the tip of main.
    git -C "$SESSION_CPP" fetch -q origin
    git -C "$SESSION_CPP" checkout -q --detach origin/main
fi
git -C "$SESSION_CPP" submodule update --init --recursive
echo "session_cpp: $(git -C "$SESSION_CPP" log --oneline -1)"

# ── 2. Python packages that mirror the kernel (session_py, session_rhino) ───────────────
step "session_py / session_rhino in the venvs"
for repo in wood_nano compas_wood; do
    py="$HERE/$repo/.venv/bin/python"
    if [ -x "$py" ]; then
        uv pip install -q -U session_py session_rhino --python "$py"
        # session_py ships no __version__ attribute; ask the installed distribution.
        echo "$repo: session_py $("$py" -c 'from importlib.metadata import version; print(version("session_py"))')"
    else
        echo "$repo: no .venv yet (see $repo/SETUP.md)"
    fi
done

[ "$BUILD" = 1 ] || exit 0

# ── 3. wood: the C++ core. Reconfigure so a new kernel source file is picked up ───────────
step "wood"
cmake -S "$HERE/wood" -B "$HERE/wood/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$HERE/wood/build" --parallel 4

# ── 4. wood_nano: recompiles ../wood and ../session_cpp into the Python extension ─────────
step "wood_nano"
if [ -x "$HERE/wood_nano/.venv/bin/python" ]; then
    (cd "$HERE/wood_nano" && CMAKE_BUILD_PARALLEL_LEVEL=4 uv pip install --no-build-isolation -e .)
    "$HERE/wood_nano/.venv/bin/python" -c "import wood_nano, wood_nano._build_info as b; print('wood_nano', wood_nano.__version__, '| wood', b.WOOD_SHA, '| session_cpp', b.SESSION_SHA)"
else
    echo "wood_nano: no .venv yet (see wood_nano/SETUP.md)"
fi

# compas_wood is pure Python on top of wood_nano; step 2 covered it. To run it against the
# wood_nano just built instead of the PyPI wheel:
#   uv pip install --no-build-isolation -e wood_nano --python compas_wood/.venv/bin/python
