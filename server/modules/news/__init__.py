"""News topics / digests — Pi-side collect + AI summarize.

Provider order: Mistral → Claude → ChatGPT → Gemini.
Keys stay on the Pi only.
"""

from server.modules.news.router import router
from server.modules.news.scheduler import start_scheduler, stop_scheduler
from server.modules.news.service import get_topic_digests, startup_news

__all__ = [
    "router",
    "get_topic_digests",
    "startup_news",
    "start_scheduler",
    "stop_scheduler",
]
