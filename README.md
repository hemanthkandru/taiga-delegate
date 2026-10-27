# taiga-delegate

**Delegate your Taiga board to AI agents — without handing them the keys to everything.**

taiga-delegate is an [MCP](https://modelcontextprotocol.io) server for [Taiga](https://taiga.io) (self-hosted or taiga.io cloud). It gives Claude Code, Claude Desktop, or any MCP client full project-management tools — epics, stories, tasks, issues, sprints, wiki, comments, search — and is built around making that delegation safe:

- **Scoped tokens** — confine an agent or external collaborator to *just the epics you hand over* (one or several): the epics themselves, their linked stories, their bugs. Everything else is invisible and denied with an explanation, not an opaque error.
- **Attribution without accounts** — scoped collaborators share one Taiga identity but every comment is signed `**[name]**` and everything they create is tagged `by-<name>`, so the board always shows who did what.
- **Usage metering** — every tool call is logged per token to a durable JSONL file; an owner-only `mcp_usage_stats` tool reports calls, denials, and top tools per collaborator.

## Why

A tracker connection is normally an all-or-nothing grant: whoever holds the credentials can do everything the account can. That's the right amount of trust for your own agent — and more than you want to extend to anyone else. taiga-delegate narrows the grant per session and keeps the board legible while agents work it:

- **Least access.** Each session gets exactly the slice it needs: the full board with the owner token, one epic with a scoped token. Out-of-scope items are hidden from the tool listing, and out-of-scope calls are denied with an explanation the calling model can act on instead of retrying.
- **Legible history.** Several agents and collaborators can share one Taiga identity without blurring together: comments are signed `**[name]**`, created items carry a `by-<name>` tag, and the usage log ties every call to its token.
- **Safe writes.** Updates patch only the fields being changed, carrying the object version — so assignees, sprint placements, and concurrent human edits survive agent activity.
- **Economical transport.** Results are serialized once, at the boundary, into compact JSON with empty fields stripped (~44% smaller) — tool output that an LLM re-reads on every turn is the most expensive payload there is.

All of it is enforced in the server, not by instructions to the client — which matters, because you don't control what a collaborator connects with.

## Quick start (stdio, local)

Examples throughout use Claude Code because that's what this was built with — but the server is client-agnostic MCP; any MCP-capable agent connects the same way (see [Any MCP client](#any-mcp-client--or-no-client-at-all)).

Requires Python 3.11+.

```bash
pip install git+https://github.com/hemanthkandru/taiga-delegate

claude mcp add taiga \
  --env TAIGA_URL=https://taiga.example.com \
  --env TAIGA_USERNAME=my-agent-user \
  --env TAIGA_PASSWORD=... \
  -- taiga-delegate
```

That's it — Claude Code spawns the server per session and gets 34 Taiga tools.

**taiga.io cloud** works the same way with `TAIGA_URL=https://api.taiga.io`. If your taiga.io account uses GitHub/GitLab/Google sign-in, either set a password in Taiga (user settings → password) or use an auth token via `TAIGA_TOKEN` instead of username/password.

> **Tip:** create a dedicated Taiga user for the agent (e.g. `my-agent`) and add it to the projects it should manage. Keeps the audit trail clean and your own account out of the loop.

## Quick start (HTTP, server deployment)

For a shared server — your team or external collaborators connect from anywhere:

```bash
cp .env.example .env    # fill in Taiga credentials + MCP_AUTH_TOKEN
docker compose up -d --build
```

Then from any machine:

```bash
claude mcp add --transport http taiga https://your-host/mcp \
  --header "Authorization: Bearer <MCP_AUTH_TOKEN>"
```

The container serves the MCP streamable-HTTP protocol on port 8765 at `/mcp`. Put your reverse proxy (nginx, Caddy, Traefik) in front for TLS; every request must carry a valid bearer token or it is rejected with 401 before reaching the protocol layer.

Environment:

| Variable | Meaning |
|---|---|
| `TAIGA_URL` | Taiga API base URL (`https://taiga.example.com` or `https://api.taiga.io`) |
| `TAIGA_USERNAME` / `TAIGA_PASSWORD` | agent account credentials |
| `TAIGA_TOKEN` | alternative to username/password |
| `MCP_TRANSPORT` | `stdio` (default) or `http` |
| `MCP_PORT` | HTTP port, default 8765 |
| `MCP_AUTH_TOKEN` | full-access bearer token — **required** in HTTP mode |
| `MCP_SCOPED_TOKENS` | scoped collaborator tokens, see below |
| `MCP_USAGE_LOG` | usage JSONL path, default `usage.jsonl` (compose mounts a volume at `/data`) |

## Scoped tokens: delegate epics, not the board

Give an outside developer (or a second AI agent) access to exactly the epics you choose:

```bash
MCP_SCOPED_TOKENS="alex:3f8a...48-hex...:2:117;vendor:b41c...:3:99,104"
#                  label:token:project_id:epic_id[,epic_id...][;more]
```

A session authenticated with a scoped token can:

- see **only** that project, those epics, their linked stories, and issues tagged `epic-<id>`
- create stories (auto-linked to the epic) and bugs (auto-tagged) — a multi-epic token passes `epic_id` to say which epic a new item belongs to; a single-epic token never has to
- update and comment on items inside the scope

Everything else — other epics, other projects, deletes, sprints, wiki, project admin — is hidden from `tools/list` and denied with a message that explains the boundary, so the calling model course-corrects instead of retrying blindly.

Collaborators set their own display name per session with an `X-Collaborator-Name` header:

```bash
claude mcp add --transport http taiga https://your-host/mcp \
  --header "Authorization: Bearer <scoped-token>" \
  --header "X-Collaborator-Name: Alex"
```

Comments then appear as `**[Alex]** looks done, closing`, and created items carry a `by-alex` tag — attribution without creating a Taiga account or managing roles. The token label (not the self-set name) is what appears in the usage log, so metering stays authoritative.

Generate tokens however you like, e.g. `openssl rand -hex 24`.

### Any MCP client — or no client at all

Scoping, signing, tagging, and metering are all enforced server-side, so they hold no matter what the collaborator connects with. Claude Code is shown above; any other MCP-capable tool (Cursor, Windsurf, a custom Agent SDK app) uses its standard HTTP server config:

```json
{
  "mcpServers": {
    "taiga": {
      "type": "http",
      "url": "https://your-host/mcp",
      "headers": {
        "Authorization": "Bearer <scoped-token>",
        "X-Collaborator-Name": "Alex"
      }
    }
  }
}
```

The endpoint is stateless JSON-RPC, so even a plain script works:

```bash
curl -s https://your-host/mcp \
  -H "Authorization: Bearer <scoped-token>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"taiga_list_user_stories","arguments":{}}}'
```

Either way, the server decides what the token can see and do: untrusted header values are decoded defensively (UTF-8 with replacement), the self-set display name is sanitized before it can reach board content (markup and non-printable characters stripped, length-capped), token comparison is constant-time, and malformed arguments come back as structured errors rather than taking anything down.

## Usage metering

Every tool call is appended to a JSONL log (`{"ts": ..., "label": "alex", "tool": "taiga_create_issue", "ok": true}`). The owner token gets an extra tool:

```
mcp_usage_stats(days=7)
→ per label: total calls, denied/failed, first/last seen, top 10 tools
```

Scoped sessions can't see or call it.

## Tools

34 tools across projects, epics, user stories, tasks, issues, sprints, wiki, comments, and search — list/get/create/update/delete plus `taiga_resolve_ref` (UI `#ref` → internal id), `taiga_link_story_to_epic`, and bulk story creation. Noteworthy behaviors, all learned the hard way against a live board:

- **Updates are minimal PATCHes** with the object version — python-taiga's own `update()` does a full PUT that silently wipes the assignee and sprint of anything you touch.
- **A `comment` parameter on update tools** posts the comment atomically with the change — one call instead of two, which halves tracking cost for agent workflows.
- **Expired-token recovery** — Taiga sessions expire (typically daily); the executor re-authenticates and retries once, so long-running HTTP deployments don't need restarts.
- **Comments actually work on epics** (the REST endpoint exists; most clients miss it).
- **Compact results** — JSON with separators collapsed and empty fields stripped; `False`/`0` are kept.

## Agent workflow templates

`templates/` has drop-in instruction files for Claude Code:

- `templates/CLAUDE-tracking.md` — a policy block for your `CLAUDE.md` that makes the agent track its own work automatically: features become epics + stories (two status calls per story), bug fixes become issues with test-case checklists.
- `templates/commands/fix-issue.md`, `templates/commands/new-feature.md` — slash commands forcing each workflow.
- `templates/collaborator-CLAUDE.md` — give this to a scoped collaborator; their Claude then knows to work only inside the delegated epic.

The templates target Claude Code's `CLAUDE.md` and slash-command formats, but they're plain markdown instructions — adapt them to your agent's equivalent (Cursor rules, `AGENTS.md`, a system prompt) and the server behaves identically. Scoping and attribution don't depend on the agent following them; they're enforced server-side either way.

## Architecture

```
src/taiga_delegate/
├── config.py          # every env var parsed exactly once, validated at startup
├── scope/             # domain: Scope model + pure policy (no I/O, fully unit-testable)
├── usage/             # durable JSONL usage log + aggregation
├── taiga/
│   ├── client.py      # Taiga session, expiry recovery, raw REST gaps (PATCH, epic links)
│   ├── serialization.py  # wire objects → compact JSON, at the boundary
│   └── tools/         # one module per domain; registry pattern — adding a tool edits no dispatcher
└── server/            # MCP wiring: auth middleware, handlers, stdio/http entrypoints
```

Dependencies point inward: `scope/` knows nothing about Taiga or MCP; the policy checks ownership through an injected `BoardInspector` protocol. Tests run without a Taiga server.

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/ruff check src tests
```

## License

MIT
