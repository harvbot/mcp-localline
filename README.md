# mcp-localline

Local Line integration boundary as a dedicated MCP project.

## Architecture boundary
- **mcp-localline** owns Local Line auth + API interactions.
- **accounting** consumes structured outputs (JSON/CSV) from this boundary.
- No plaintext secrets are stored in repo files.

## Setup
```bash
cd ~/repos/mcp-localline
python3 -m venv .venv
./.venv/bin/python -m pip install -e .
```

## Auth bootstrap (env-only credentials)
```bash
export LOCALLINE_USERNAME='...'
export LOCALLINE_PASSWORD='...'
./.venv/bin/mcp-localline auth-bootstrap
```
Stores refresh token in macOS Keychain service `mcp.localline` by default.

## Commands
```bash
./.venv/bin/mcp-localline auth-status
./.venv/bin/mcp-localline picklists-create --start-date 2026-02-24 --end-date 2026-02-25
./.venv/bin/mcp-localline orders-export --start-date 2026-02-10 --end-date 2026-02-16
./.venv/bin/mcp-localline customers-email-proof --subject 'Proof' --body '<p>Preview</p>'
./.venv/bin/mcp-localline customers-email-send-all --subject 'Weekly' --body '<p>Hello</p>'
```

## MCP server
```bash
./.venv/bin/mcp-localline-server
```
Tools:
- `auth.status`
- `auth.bootstrap`
- `picklists.create(start_date,end_date)`
- `orders.export(start_date,end_date)`
- `customers.email.proof`
- `customers.email.send_all`

## Runbook / fallback
If command returns `AUTH_FAILED`:
1) export `LOCALLINE_USERNAME` + `LOCALLINE_PASSWORD`
2) run `mcp-localline auth-bootstrap`
3) rerun operational command
