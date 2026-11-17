#!/bin/bash
set -uo pipefail

WORKSPACE="${1:-$PWD}"
CDP_URL="http://127.0.0.1:9222/json/version"
BRIDGE_URL="http://127.0.0.1:8080/mcp"
BRIDGE_PROBE='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"bot","version":"0"}}}'

chrome_up() { curl -s -m 2 "$CDP_URL" >/dev/null 2>&1; }
bridge_up() { [ "$(curl -s -m 2 -o /dev/null -w '%{http_code}' -X POST "$BRIDGE_URL" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d "$BRIDGE_PROBE")" != "000" ]; }

if ! chrome_up; then
  case "$(uname)" in
    Darwin)
      open -na "Google Chrome" --args --headless=new --remote-debugging-port=9222 --user-data-dir="$WORKSPACE/chrome-profile" --no-first-run --no-default-browser-check || exit 1
      ;;
    Linux)
      command -v google-chrome >/dev/null || { echo "google-chrome not found" >&2; exit 1; }
      nohup google-chrome --headless=new --remote-debugging-port=9222 --user-data-dir="$WORKSPACE/chrome-profile" >/dev/null 2>&1 &
      ;;
    *)
      echo "Unsupported platform: $(uname)" >&2
      exit 1
      ;;
  esac
fi

if ! bridge_up; then
  command -v npx >/dev/null || { echo "npx not found" >&2; exit 1; }
  nohup npx -y mcp-proxy --host 127.0.0.1 --port 8080 -- npx -y chrome-devtools-mcp@latest --browserUrl=http://127.0.0.1:9222 --filesystemRoot="$WORKSPACE" > "$WORKSPACE/chrome-mcp.log" 2>&1 &
fi

for _ in $(seq 1 60); do
  if chrome_up && bridge_up; then
    exit 0
  fi
  sleep 1
done

echo "Chrome or the MCP bridge did not come up in time" >&2
exit 1
