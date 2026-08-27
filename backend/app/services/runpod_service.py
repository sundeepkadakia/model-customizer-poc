import os
import httpx

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")

RUNPOD_BASE_URL = "https://api.runpod.io/v2"


def get_headers():
    if not RUNPOD_API_KEY:
        raise RuntimeError("RUNPOD_API_KEY is not configured")

    return {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }


async def list_pods():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{RUNPOD_BASE_URL}/pods",
            headers=get_headers(),
        )

        response.raise_for_status()
        return response.json()