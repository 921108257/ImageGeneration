#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
if ! codex plugin marketplace list | grep -q '^image-generation[[:space:]]'; then
  codex plugin marketplace add "$repo"
fi
codex plugin add gpt-image-2-assets@image-generation
echo "Codex plugin installed. Start a new task to load its MCP server and skill."
