"""Run with: python -m server"""

import uvicorn

from server.auth import require_api_key
from server.config import get_settings


def main() -> None:
    require_api_key()
    settings = get_settings()
    uvicorn.run(
        "server.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
