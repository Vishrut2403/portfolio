#!/usr/bin/env bash
# Usage:
#   bash build.sh serve        live preview at http://localhost:1313 (auto-reloads on save)
#   bash build.sh [baseURL]    refresh GitHub data and build the site into public/
# Either way, Hugo is downloaded first if it isn't installed.
set -euo pipefail
cd "$(dirname "$0")"   # works from any directory
HUGO_VERSION="0.166.0"
BIN="${TMPDIR:-/tmp}/hugo-bin"
export PATH="$BIN:$PATH"

if ! command -v hugo >/dev/null; then
  case "$(uname -s)-$(uname -m)" in
    Linux-aarch64|Linux-arm64) A=linux-arm64 ;;
    Darwin-*) A=darwin-universal ;;
    *) A=linux-amd64 ;;
  esac
  mkdir -p "$BIN"
  curl -fsSL "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_${HUGO_VERSION}_${A}.tar.gz" | tar -xz -C "$BIN" hugo
fi

if [ "${1:-}" = "serve" ]; then
  exec hugo server --disableFastRender --baseURL http://localhost:1313/   # preview at the root, not /portfolio/
fi

python3 scripts/fetch_github.py || echo "warn: GitHub refresh failed, using committed data"
hugo --gc --minify ${1:+--baseURL "$1"}
