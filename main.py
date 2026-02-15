"""New Relic MCP server entry point. Run with: uv run main.py or uv run newrelic-mcp."""
from server import main as run_server


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
