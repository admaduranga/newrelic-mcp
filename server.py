"""
New Relic MCP server: execute NRQL queries via NerdGraph.
"""
import json
import os
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

GRAPHQL_URL_US = "https://api.newrelic.com/graphql"
GRAPHQL_URL_EU = "https://api.eu.newrelic.com/graphql"
DEFAULT_REQUEST_TIMEOUT = 60

# Single-account NRQL query (variables avoid injection).
# Variable $nrql is type Nrql!; pass the NRQL string as the variable value. Argument name is "query".
NRQL_SINGLE_ACCOUNT_QUERY = """
query NrqlSingleAccount($accountId: Int!, $nrql: Nrql!) {
  actor {
    account(id: $accountId) {
      nrql(query: $nrql) {
        results
      }
    }
  }
}
"""

# Entity search: find entities by project id (account tag + APM domain + name)
# https://docs.newrelic.com/docs/apis/nerdgraph/examples/nerdgraph-entities-api-tutorial
ENTITY_SEARCH_QUERY = """
query EntitySearch($searchQuery: String!) {
  actor {
    entitySearch(query: $searchQuery) {
      query
      results {
        entities {
          accountId
          guid
          name
          tags {
            key
            values
          }
        }
      }
    }
  }
}
"""


def _get_config() -> dict[str, Any]:
    """Load configuration from environment."""
    api_key = os.environ.get("NEW_RELIC_API_KEY", "").strip()
    region = (os.environ.get("NEW_RELIC_REGION") or "us").strip().lower()
    account_id_str = os.environ.get("NEW_RELIC_ACCOUNT_ID", "").strip()

    if region == "eu":
        base_url = GRAPHQL_URL_EU
    else:
        base_url = GRAPHQL_URL_US

    default_account_id: int | None = None
    if account_id_str:
        try:
            default_account_id = int(account_id_str)
        except ValueError:
            default_account_id = None

    return {
        "api_key": api_key,
        "base_url": base_url,
        "default_account_id": default_account_id,
    }


def _ensure_api_key(api_key: str) -> None:
    """Raise if API key is missing (do not expose the key)."""
    if not api_key:
        raise ValueError(
            "NEW_RELIC_API_KEY is not set. Set it in the environment or .env before running the server."
        )


def _execute_nerdgraph(
    base_url: str,
    api_key: str,
    query: str,
    variables: dict[str, Any],
    timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT,
) -> dict[str, Any]:
    """
    Send a GraphQL request to NerdGraph. Returns the JSON response body.
    Raises with a safe message on HTTP or GraphQL errors (no API key in messages).
    """
    _ensure_api_key(api_key)
    payload = {"query": query, "variables": variables}
    headers = {
        "Content-Type": "application/json",
        "API-Key": api_key,
    }
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(base_url, json=payload, headers=headers)
    body = response.json()

    if response.status_code != 200:
        msg = body.get("message", body.get("error", response.text)) if isinstance(body, dict) else response.text
        raise ValueError(f"NerdGraph request failed (HTTP {response.status_code}): {msg}")

    if "errors" in body and body["errors"]:
        messages = [e.get("message", str(e)) for e in body["errors"]]
        raise ValueError("NerdGraph returned errors: " + "; ".join(messages))

    return body


def _extract_single_account_results(data: dict[str, Any]) -> list[Any]:
    """Extract results from single-account NRQL response."""
    try:
        return data["data"]["actor"]["account"]["nrql"]["results"] or []
    except (KeyError, TypeError):
        return []


def _extract_entity_search_entities(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract entities from entitySearch response (results.entities array)."""
    try:
        results = data["data"]["actor"]["entitySearch"]["results"]
        return (results.get("entities") or []) if isinstance(results, dict) else []
    except (KeyError, TypeError):
        return []


# -----------------------------------------------------------------------------
# MCP server and tools
# -----------------------------------------------------------------------------

mcp = FastMCP(
    "New Relic NRQL",
    instructions="Execute NRQL queries against New Relic via NerdGraph.",
)


@mcp.tool()
def execute_nrql(
    query: str,
    account_id: int | None = None,
    timeout_seconds: int = 30,
) -> str:
    """
    Execute an NRQL query against a New Relic account via NerdGraph.

    Requires NEW_RELIC_API_KEY to be set. The query must be valid NRQL
    (e.g. SELECT count(*) FROM Transaction SINCE 1 HOUR AGO).
    If account_id is not provided, NEW_RELIC_ACCOUNT_ID is used when set.
    """
    config = _get_config()
    _ensure_api_key(config["api_key"])
    raw_aid = account_id if account_id is not None else config["default_account_id"]
    if raw_aid is None:
        raise ValueError(
            "account_id is required. Pass it to this tool or set NEW_RELIC_ACCOUNT_ID in the environment."
        )
    try:
        aid = int(raw_aid)
    except (TypeError, ValueError):
        raise ValueError("account_id must be an integer (e.g. 3502244).") from None
    timeout_seconds = max(1, min(70, timeout_seconds))
    body = _execute_nerdgraph(
        config["base_url"],
        config["api_key"],
        NRQL_SINGLE_ACCOUNT_QUERY,
        {"accountId": aid, "nrql": query.strip()},
        timeout_seconds=timeout_seconds,
    )
    results = _extract_single_account_results(body)
    return json.dumps(results, indent=2)


@mcp.tool()
def get_account_id_by_project_id(project_id: str) -> str:
    """
    Retrieve New Relic account ID (and entity details) by project ID.

    Uses NerdGraph entity search to find APM entities whose name and tags.account
    match the given project_id. Returns accountId, guid, name, and tags for each
    matching entity. Useful to resolve account ID when you only know the project name.

    See: https://docs.newrelic.com/docs/apis/nerdgraph/examples/nerdgraph-entities-api-tutorial
    """
    config = _get_config()
    _ensure_api_key(config["api_key"])
    project_id = (project_id or "").strip()
    if not project_id:
        raise ValueError("project_id is required and must be non-empty.")
    # Escape single quotes in project_id to avoid breaking the search query
    safe_id = project_id.replace("'", "\\'")
    search_query = (
        f"tags.account LIKE '%{safe_id}%' AND domain = 'APM' AND name = '{safe_id}'"
    )
    body = _execute_nerdgraph(
        config["base_url"],
        config["api_key"],
        ENTITY_SEARCH_QUERY,
        {"searchQuery": search_query},
        timeout_seconds=30,
    )
    entities = _extract_entity_search_entities(body)
    if not entities:
        return json.dumps(
            {
                "found": False,
                "message": f"No entities found for project_id: {project_id}",
                "entities": [],
            },
            indent=2,
        )
    return json.dumps(
        {
            "found": True,
            "count": len(entities),
            "entities": [
                {
                    "accountId": e.get("accountId"),
                    "guid": e.get("guid"),
                    "name": e.get("name"),
                    "tags": e.get("tags"),
                }
                for e in entities
            ],
        },
        indent=2,
    )


def main() -> None:
    """Run the MCP server. Default: stdio. Set MCP_TRANSPORT=http for streamable HTTP."""
    config = _get_config()
    _ensure_api_key(config["api_key"])
    transport = (os.environ.get("MCP_TRANSPORT") or "stdio").strip().lower()
    if transport == "http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
    sys.exit(0)
