# Spike 1.3 — Hosts and timeouts (local notes, not committed)

Server: `spikes/1.3-hosts/server.py` (tools `sleep_plain`, `sleep_progress`) on http://127.0.0.1:8000/mcp.

| Host | sleep_plain | sleep_progress | Notes |
|---|---|---|---|
| FastMCP Python client | cuts at its own `timeout` | does not reset the clock | server only notices via closed connection |
| Claude Code (`claude -p`, haiku) | OK at 90 s (95 s total) | not measured | real limit > 90 s |
| Inspector CLI (Windows npx -> WSL localhost) | OK at 50 s; cuts at 60 s (70 s call) | cuts at 60 s (90 s call), 0 progress events delivered | 60 s = SDK default; GUI "Reset Timeout on Progress" untested |
| Inspector GUI | cut a 60 s call at 60000 ms | pending | |
| Cursor | pending | pending | |
| Claude Desktop (npx mcp-remote) | pending | pending | |

- Windows reaches the WSL server through `localhost:8000`: OK.
- Working assumption until Cursor/Desktop are measured: smallest timeout = 60 s, so one call must finish under ~30 s.

## 1.3b — draft-like loop latency (gpt-6-luna, reasoning low)
4 sequential LLM calls inside one HTTP tool, 3 runs: total 13.5 / 15.8 / 14.9 s (wall 14.2 / 15.7 / 14.9 s).
First call (200-word writer) 8-9 s; review/edit calls 1.5-2.5 s each.
Fits one call under the ~30 s budget with ~2x margin. A real loop with longer drafts or more iterations may not: keep bounded steps.

## Claude Desktop (Windows, Store install) — local connection attempt, 2026-11-22
- Not verified end to end: the connection was never confirmed; paused on purpose, to be tested against the Azure URL (spike 1.8).
- Server and bridge are fine: initialize handshake OK; `npx mcp-remote http://localhost:8000/mcp` run from Windows connects and "Proxy established successfully".
- Why it never showed up: this Store build reads its config from `%LOCALAPPDATA%\Claude-Data\<package>\claude_desktop_config.json`
  (the file that already holds `preferences`), NOT from `%APPDATA%\Claude` nor from `Packages\<package>\LocalCache\Roaming\Claude`. Found via `Local\Claude\logs\main.log`
  (userData path). The app must be fully quit (tray -> Quit) before editing, and restarted after.
- State left: `mcpServers.spike` added to that file; backup next to it as `claude_desktop_config.json.bak-before-mcp`. Remove the key if the failed entry is annoying.
- main.log also warned `session_stale_relogin` (sign-in too old); may ask to log in again.
- Product conclusion: the simple path for other people is a remote custom connector (Settings -> Connectors -> Add custom connector with the public HTTPS URL), phase 8; the local JSON route is only for developers.

### Update 2026-11-22 (later): Claude Desktop connected
After restarting with the config in `Claude-Data`: `Connected to spike (3 tools)`. Calls made: sleep_plain 5 s, 40 s, 70 s; all returned,
no cancellation or timeout in mcp-server-spike.log (no per-call timestamps in that log; durations are as reported by the user).
So Claude Desktop (via mcp-remote 0.16.7) waits at least 70 s: it did NOT cut at 60 s like Inspector. Upper bound not measured.
Smallest measured timeout stays Inspector's 60 s -> the 30 s-per-call design budget is unchanged. Cursor still pending.
