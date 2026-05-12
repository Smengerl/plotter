#!/usr/bin/env bash
# pipeline/scripts/helpers/platform.sh — Platform detection helpers
#
# USAGE: source this file, then use is_windows / is_macos / is_linux.

is_windows() {
  case "$(uname -s)" in
    CYGWIN*|MINGW*|MSYS*) return 0 ;;
    *) return 1 ;;
  esac
}

is_macos() {
  [[ "$(uname -s)" == "Darwin" ]]
}

is_linux() {
  [[ "$(uname -s)" == "Linux" ]]
}
