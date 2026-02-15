# New Relic MCP Server

MCP server that executes [NRQL](https://docs.newrelic.com/docs/insights/nrql-new-relic-query-language/) queries against New Relic via the [NerdGraph](https://docs.newrelic.com/docs/apis/nerdgraph/get-started/introduction-new-relic-nerdgraph/) GraphQL API.

## Tools

- **`execute_nrql`** — Run an NRQL query against a single New Relic account. Parameters: `query` (required), `account_id` (optional if `NEW_RELIC_ACCOUNT_ID` is set), `timeout_seconds` (optional, 1–70).

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A New Relic [user API key](https://docs.newrelic.com/docs/apis/intro-apis/new-relic-api-keys/) with NerdGraph access

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NEW_RELIC_API_KEY` | Yes | New Relic user API key for NerdGraph. Create at [one.newrelic.com](https://one.newrelic.com/nr1-core/api-keys). |
| `NEW_RELIC_REGION` | No | `us` (default) or `eu` for NerdGraph endpoint. |
| `NEW_RELIC_ACCOUNT_ID` | No | Default account ID when not passed to `execute_nrql`. |

Copy [.env.example](.env.example) to `.env` and set `NEW_RELIC_API_KEY` (and optionally the others).

## Install and run

From the project root:

```bash
# Install dependencies (with uv)
uv sync

# Run the MCP server (stdio; for Cursor/IDE)
uv run main.py
```

Or via the script entry point: `uv run newrelic-mcp`.

For local debugging with HTTP transport:

```bash
MCP_TRANSPORT=http uv run main.py
```

Then connect to `http://localhost:8000/mcp` (or the printed URL) with the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) or another MCP client.

## Cursor setup

1. Open **Cursor Settings** → **Features** → **MCP**.
2. Add a new MCP server; choose **stdio**.
3. Set the command to run the server, for example:
   - **Command:** `uv`
   - **Args:** `run`, `main.py` (or `--directory`, `/path/to/newrelic-mcp`, `run`, `main.py` if needed)
   - **Cwd:** path to this repo (e.g. `/Users/you/newrelic-mcp`).
4. Add environment variables (or use a shell that loads `.env`):
   - `NEW_RELIC_API_KEY` = your API key
   - Optionally: `NEW_RELIC_REGION`, `NEW_RELIC_ACCOUNT_ID`

Example config (in Cursor MCP JSON, if supported):

```json
{
  "mcpServers": {
    "newrelic": {
      "command": "uv",
      "args": ["--directory", "/path/to/newrelic-mcp", "run", "main.py"],
      "env": {
        "NEW_RELIC_API_KEY": "YOUR_API_KEY",
        "NEW_RELIC_REGION": "us"
      }
    }
  }
}
```

Do not commit `.env` or any file containing your API key.

## Example prompts

Use these in Cursor (or any MCP client) to run NRQL via the New Relic MCP server:

- **Run a simple query:**  
  *"Run this NRQL: `SELECT count(*) FROM Transaction SINCE 1 HOUR AGO`"*

- **Query by account:**  
  *"Execute `SELECT average(duration) FROM Transaction FACET name SINCE 1 day ago` for account ID 1234567"*

- **By Adobe Commerce project:**  
  *"Query New Relic for project abc123: show me transaction errors in the last 24 hours"*  
  *"Get the last 100 logs for project xyz789"*  
  *"List Redis samples for project my-project in the last hour"*

- **Explore an entity:**  
  *"What attributes are available on the Log entity? Run a discovery query."*  
  *"Show me one Transaction row so I can see the fields"*

- **Aggregations and facets:**  
  *"Count transactions per app name in the last 6 hours"*  
  *"Average response time by transaction name for the last day"*

- **Time range:**  
  *"Run: SELECT * FROM Log WHERE message IS NOT NULL SINCE 2 days ago LIMIT 50"*

Set `NEW_RELIC_ACCOUNT_ID` in the MCP config (or pass it in the prompt) when you are not using an Adobe Commerce project ID; the agent can resolve project ID → account ID when needed.

## NRQL and rate limits

- Queries must be valid [NRQL](https://docs.newrelic.com/docs/insights/nrql-new-relic-query-language/using-nrql/introduction-nrql/) (e.g. `SELECT count(*) FROM Transaction SINCE 1 HOUR AGO`).
- New Relic enforces [NRQL rate limits](https://docs.newrelic.com/docs/query-your-data/nrql-new-relic-query-language/get-started/rate-limits-nrql-queries/). This server does not retry; failed requests surface as tool errors.

## License

MIT
