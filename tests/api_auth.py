"""Small helpers for API-key unittest clients."""

TEST_API_KEY = "unit-test-api-key"


def bearer(key: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {key or TEST_API_KEY}"}
