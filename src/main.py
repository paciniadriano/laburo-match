"""Process entrypoint: `python -m src.main` starts the MCP server over Streamable HTTP."""

from src.config.settings import get_settings
from src.server import create_mcp_server, http_options


def main() -> None:
    settings = get_settings()
    server = create_mcp_server(settings)
    server.run(
        transport="http",
        host=settings.server_host,
        port=settings.server_port,
        **http_options(settings),
    )


if __name__ == "__main__":
    main()
