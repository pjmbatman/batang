# batang-mcp

Local MCP bridge to [Batang](https://github.com/pjmbatman/batang), the standardized battery ageing and fault
database.

The tools live on the Batang server (`https://api.batanghub.com/mcp`). This program connects to it with your
Batang token and offers exactly the server's tools and instructions to your assistant over stdio, so it always
matches the server. It adds three local tools:

| Tool | What it does |
|---|---|
| `login` | sign in through your browser: it opens a link and shows a code to approve with your account; the token (7 days) is kept in `~/.config/batang/token` (readable only by you) |
| `whoami` | whether you are signed in and when the token expires |
| `save_link` | save a result or file link from an answer (`/mcp/results/…`, `/mcp/files/…`) to a path on your computer |

The server's tools (`info`, `find_records`, `describe`, `stats`, `cycles`, `cycle_samples`, `schema`, `query`,
`download`) read Batang release 2.0 and use the column, file and view names of schema 2.0
([DATA_FORMAT.md](../DATA_FORMAT.md)): for example `cycle_time_s`, `voltage_min_v`, `efc`, `size_code`, `device_id`,
the SQL views `cells`, `devices`, `cycles`, `segments`, `samples`, `device_samples` and the macros
`cycle_samples()`, `segment_samples()`. `find_records` takes `kind` `cell`, `device` or `session`; filters are
`tasks`, `size_code`, `level`, `setting`, ranges of temperature, C-rate, cycle count, last SOH and EFC, and `sort`
(`cycles`, `efc`, `soh`) with `limit` for a first look; `stats` takes `grain` (`record`, `cycle`, `segment`). For release 2.0 the
server also accepts the 1.x names in tool arguments (`task`, `cell_format`, `unit_level`, `domain`,
`stats(level="cycle")`, `v_min` ...), translates them and lists them under `renamed` in the answer. The bridge forwards everything
unchanged, so version 0.3 differs from 0.2 only in this documentation; both work with release 2.0.

## Two ways to connect

**Remote (recommended).** No install; the assistant handles the sign-in.

```bash
claude mcp add --transport http batang https://api.batanghub.com/mcp
```

claude.ai or Claude Desktop: Settings → Connectors → Add custom connector → `https://api.batanghub.com/mcp`.

**Local bridge (this package).** Needs [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
claude mcp add batang -- uvx --from "git+https://github.com/pjmbatman/batang#subdirectory=mcp" batang-mcp
```

```jsonc
// Claude Desktop: Settings → Developer → Edit Config (claude_desktop_config.json)
{
  "mcpServers": {
    "batang": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/pjmbatman/batang#subdirectory=mcp", "batang-mcp"]
    }
  }
}
```

Then ask the assistant to log in to Batang. When the token expires, the next call says so; log in again.

## Access and limits

- A Batang account: sign up at https://batanghub.com/signup (Yonsei accounts at once; other researchers apply there).
- Read-only. Use is limited per person (requests per minute, query time and data per day), not per tool.
- Each dataset keeps its own licence: check `license` and `commercial_use` and cite the original source.

Environment: `BATANG_MCP_URL` (default `https://api.batanghub.com/mcp`), `BATANG_TOKEN` (a token to use instead of
`login`, e.g. on a server).

MIT licence ([LICENSE](LICENSE)).
