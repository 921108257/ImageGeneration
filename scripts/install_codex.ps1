$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
if (-not (codex plugin marketplace list | Select-String -Pattern '^image-generation\s')) {
    codex plugin marketplace add $repo
}
codex plugin add gpt-image-2-assets@image-generation
Write-Host "Codex plugin installed. Start a new task to load its MCP server and gpt-image-2-assets skill."
