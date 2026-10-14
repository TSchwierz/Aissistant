"""News topics / digests / job trigger API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from server.modules.news import service
from server.modules.news.providers import PROVIDER_ORDER, configured_providers
from server.modules.news.schemas import (
    DigestOut,
    RunResultOut,
    TopicCreate,
    TopicOut,
    TopicUpdate,
)

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/status")
def news_status() -> dict:
    return {
        "providers_order": list(PROVIDER_ORDER),
        "providers_configured": configured_providers(),
        "topics": len(service.list_topics()),
    }


@router.post("/topics", response_model=TopicOut, status_code=201)
def create_topic(body: TopicCreate) -> TopicOut:
    try:
        return service.create_topic(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/topics", response_model=list[TopicOut])
def list_topics() -> list[TopicOut]:
    return service.list_topics()


@router.get("/topics/{topic_id}", response_model=TopicOut)
def get_topic(topic_id: str) -> TopicOut:
    topic = service.get_topic(topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.put("/topics/{topic_id}", response_model=TopicOut)
def update_topic(topic_id: str, body: TopicUpdate) -> TopicOut:
    try:
        topic = service.update_topic(topic_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: str) -> dict:
    if not service.delete_topic(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"deleted": True, "id": topic_id}


@router.post("/topics/{topic_id}/run", response_model=RunResultOut)
def run_topic(
    topic_id: str,
    for_date: str | None = Query(
        default=None, description="YYYY-MM-DD override for digest for_date"
    ),
) -> RunResultOut:
    try:
        return service.run_topic(topic_id, for_date=for_date)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/digests", response_model=list[DigestOut])
def list_digests(
    topic_id: str | None = None,
    date: str | None = Query(default=None, description="YYYY-MM-DD"),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[DigestOut]:
    return service.list_digests(topic_id=topic_id, for_date=date, limit=limit)


@router.get("/digests/latest", response_model=list[DigestOut])
def latest_digests(
    date: str | None = Query(
        default=None, description="YYYY-MM-DD (default: today in PA_TIMEZONE)"
    ),
) -> list[DigestOut]:
    return service.latest_digests(for_date=date)
