import os
import httpx
from datetime import datetime, timezone


class ApiSportsClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.basketball_host = os.getenv("API_SPORTS_BASKETBALL_HOST", "v1.basketball.api-sports.io")
        self.tennis_host = os.getenv("API_SPORTS_TENNIS_HOST", "v1.tennis.api-sports.io")
        self.football_host = os.getenv("API_SPORTS_FOOTBALL_HOST", "v3.football.api-sports.io")

    def headers(self, host: str):
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": host,
        }

    async def _get(self, host: str, path: str, params: dict):
        url = f"https://{host}{path}"

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=self.headers(host), params=params)
            r.raise_for_status()
            return r.json()

    async def enrich
