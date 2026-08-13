from __future__ import annotations

import os

import uvicorn


def _port_from_environment() -> int:
    raw = os.getenv("CROW_PLATFORM_PORT", "8080")
    try:
        port = int(raw)
    except ValueError as error:
        raise ValueError("CROW_PLATFORM_PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("CROW_PLATFORM_PORT must be between 1 and 65535")
    return port


def main() -> None:
    host = os.getenv("CROW_PLATFORM_BIND_ADDRESS", "127.0.0.1")
    uvicorn.run("crow_workbench.shell:app", host=host, port=_port_from_environment(), reload=False)


if __name__ == "__main__":
    main()
