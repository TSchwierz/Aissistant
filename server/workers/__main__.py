"""Run one background worker: ``python -m server.workers climate|scale|news``."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"climate", "scale", "news"}:
        raise SystemExit("usage: python -m server.workers climate|scale|news")
    name = args[0]
    if name == "climate":
        from server.modules.climate.collector import run_collector

        run_collector()
        return
    if name == "scale":
        from server.modules.health.scale_scan import run_forever

        run_forever()
        return
    from server.modules.news.scheduler import run_forever as run_news

    run_news()


if __name__ == "__main__":
    main()
