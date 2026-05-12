#!/usr/bin/env bash
# pipeline/scripts/helpers/env.sh — Shared environment bootstrap for all pipeline scripts.
#
# USAGE: Source this file AFTER setting ROOT_DIR in the calling script:
#
#   ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
#   source "$ROOT_DIR/pipeline/scripts/helpers/env.sh"
#
# Exports after sourcing:
#   SYS_PYTHON   — system Python binary (python3.13 > python3.12 > python3.11 > python3)
#   VENV         — path to the virtual environment root (.venv in project root)
#   VENV_BIN     — path to venv's bin/ (Unix) or Scripts/ (Windows / Git-Bash)
#
# Functions provided:
#   check_python_version
#     Verifies that SYS_PYTHON is Python 3.11–3.13. Exits with error on mismatch.
#
#   activate_venv [--auto-create [EXTRAS]]
#     Activates the venv. With --auto-create creates it and runs
#     `pip install -e "pipeline/[EXTRAS]"` (default extras: gui).
#
#   resolve_venv_python
#     Sets PYTHON to the venv's python executable.

# ── Locate project root ───────────────────────────────────────────────────────
# Fallback: two levels up from scripts/helpers/ → pipeline/ → project root
ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# ── Platform helpers ──────────────────────────────────────────────────────────
# shellcheck source=platform.sh
source "$(dirname "${BASH_SOURCE[0]}")/platform.sh"

# ── Detect system Python (prefer 3.13, accept 3.11–3.13) ─────────────────────
_find_python() {
  for candidate in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

if ! SYS_PYTHON="$(_find_python)"; then
  echo "❌ Python not found. Please install Python 3.11–3.13." >&2
  echo "   macOS: brew install python@3.13" >&2
  return 1 2>/dev/null || exit 1
fi

# ── Venv paths ────────────────────────────────────────────────────────────────
VENV="$ROOT_DIR/.venv"
if is_windows; then
  VENV_BIN="$VENV/Scripts"
else
  VENV_BIN="$VENV/bin"
fi

# ── check_python_version ──────────────────────────────────────────────────────
# Verifies SYS_PYTHON is Python 3.11–3.13 (vpype requirement).
check_python_version() {
  local major minor
  major="$("$SYS_PYTHON" -c 'import sys; print(sys.version_info.major)')"
  minor="$("$SYS_PYTHON" -c 'import sys; print(sys.version_info.minor)')"
  if [[ "$major" -ne 3 || "$minor" -lt 11 || "$minor" -ge 14 ]]; then
    echo "❌ Unsupported Python version: $("$SYS_PYTHON" --version 2>&1)" >&2
    echo "   vpype 1.15.x requires Python >=3.11, <3.14." >&2
    echo "   Install Python 3.13:  brew install python@3.13" >&2
    echo "   Then retry: PYTHON=python3.13 $0" >&2
    return 1 2>/dev/null || exit 1
  fi
}

# ── activate_venv [--auto-create [EXTRAS]] ────────────────────────────────────
# Activates the venv. With --auto-create it will create it and install the
# pipeline package if the venv does not exist yet.
# EXTRAS defaults to "gui" (e.g. pass "gui,diffusers" for SD backends).
activate_venv() {
  local auto_create=false
  local extras="gui"

  if [[ "${1:-}" == "--auto-create" ]]; then
    auto_create=true
    [[ -n "${2:-}" ]] && extras="$2"
  fi

  if [[ ! -f "$VENV_BIN/activate" ]]; then
    if $auto_create; then
      echo "🔧 Virtual environment not found — creating it now..."
      check_python_version
      "$SYS_PYTHON" -m venv "$VENV"
      # Refresh VENV_BIN (Windows path may differ after creation)
      if is_windows; then VENV_BIN="$VENV/Scripts"; else VENV_BIN="$VENV/bin"; fi
      # shellcheck source=/dev/null
      source "$VENV_BIN/activate"
      echo "📦 Installing pipeline[${extras}] from pyproject.toml..."
      "$VENV_BIN/pip" install --upgrade pip --quiet
      "$VENV_BIN/pip" install -e "$ROOT_DIR/pipeline[${extras}]"
    else
      echo "❌ Virtual environment not found at $VENV" >&2
      echo "   Run setup first:  ./pipeline/scripts/setup_pipeline.sh" >&2
      return 1 2>/dev/null || exit 1
    fi
  else
    # shellcheck source=/dev/null
    source "$VENV_BIN/activate"
  fi
}

# ── resolve_venv_python ───────────────────────────────────────────────────────
# Sets PYTHON to the venv's Python executable. Call after activate_venv.
resolve_venv_python() {
  if is_windows; then
    PYTHON="$VENV_BIN/python.exe"
    if [[ ! -x "$PYTHON" && -x "$VENV_BIN/python3.exe" ]]; then
      PYTHON="$VENV_BIN/python3.exe"
    fi
  else
    PYTHON="$VENV_BIN/python"
    if [[ ! -x "$PYTHON" && -x "$VENV_BIN/python3" ]]; then
      PYTHON="$VENV_BIN/python3"
    fi
  fi
  export PYTHON
}
