from datetime import datetime
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.domain import Event, Market, Outcome


class OddsApiClient:
    BASE = "https://api.the-odds-api.com/v4/sports"

    def __init__(self, api_key: str, regions: str, markets: str):
        self.api_key = api_key
        self.regions = regions
        self.markets = markets

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _get_json(self, url: str, params: dict):
        timeout = aiohttp.ClientTimeout(total=45)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as resp:
                text = await resp.text()

                if resp.status >= 400:
                    raise RuntimeError(f"Odds API HTTP {resp.status}: {text[:300]}")

                return await resp.json()

    async def fetch_events_for_sport(self, sport_key: str):
        if not self.api_key:
            raise RuntimeError("ODDS_API_KEY is empty")

        payload = await self._get_json(
            f"{self.BASE}/{sport_key}/odds",
            {
                "apiKey": self.api_key,
                "regions": self.regions,
                "markets": self.markets,
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            },
        )

        events = []

        if not isinstance(payload, list):
            return events

        for item in payload:
            markets = []

            for bm in item.get("bookmakers", []):
                bookmaker = bm.get("title") or bm.get("key") or "bookmaker"

                for mk in bm.get("markets", []):
                    outcomes = []

                    for o in mk.get("outcomes", []):
                        if o.get("price") is None:
                            continue

                        outcomes.append(
                            Outcome(
                                name=str(o.get("name", "")),
                                price=float(o["price"]),
                                point=float(o["point"]) if o.get("point") is not None else None,
                            )
                        )

                    if outcomes:
                        markets.append(
                            Market(
                                key=str(mk.get("key", "")),
                                bookmaker=bookmaker,
                                outcomes=outcomes,
                                last_update=mk.get("last_update"),
                            )
                        )

            if item.get("id") and item.get("commence_time"):
                events.append(
                    Event(
                        event_id=str(item["id"]),
                        sport_key=str(item.get("sport_key", sport_key)),
                        sport_title=str(item.get("sport_title", sport_key)),
                        commence_time=datetime.fromisoformat(
                            item["commence_time"].replace("Z", "+00:00")
                        ),
                        home_team=str(item.get("home_team", "")),
                        away_team=str(item.get("away_team", "")),
                        markets=markets,
                        raw=item,
                    )
                )

        return events
