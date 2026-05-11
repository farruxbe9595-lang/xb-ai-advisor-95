import os
import httpx
from datetime import datetime, timezone


class ApiSportsClient:
    def __init__(
        self,
        api_key,
        basketball_host,
        tennis_host,
        football_host
    ):
        self.api_key = api_key
        self.basketball_host = basketball_host
        self.tennis_host = tennis_host
        self.football_host = football_host
        
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

    async def enrich_basketball(self, home_team, away_team, commence_time):
        try:
            date_str = commence_time.date().isoformat()

            data = await self._get(
                self.basketball_host,
                "/games",
                {"date": date_str}
            )

            for g in data.get("response", []):
                h = g.get("teams", {}).get("home", {}).get("name", "")
                a = g.get("teams", {}).get("away", {}).get("name", "")

                if self._match_names(home_team, h) and self._match_names(away_team, a):
                    return {
                        "data_quality": "api_sports_basketball",
                        "api_sports_event_id": g.get("id"),
                        "league": g.get("league", {}).get("name"),
                        "country": g.get("country", {}).get("name"),
                        "home_team": h,
                        "away_team": a,
                        "status": g.get("status", {}).get("long"),
                    }

            return {"data_quality": "odds_only", "warning": "API-Sports basketball mapping topilmadi"}

        except Exception as e:
            return {"data_quality": "odds_only", "warning": f"Basketball enrich error: {repr(e)}"}

    async def enrich_tennis(self, home_team, away_team, commence_time):
        try:
            date_str = commence_time.date().isoformat()

            data = await self._get(
                self.tennis_host,
                "/fixtures",
                {"date": date_str}
            )

            for g in data.get("response", []):
                players = g.get("players", {})
                p1 = players.get("first", {}).get("name", "")
                p2 = players.get("second", {}).get("name", "")

                if (
                    self._match_names(home_team, p1) and self._match_names(away_team, p2)
                ) or (
                    self._match_names(home_team, p2) and self._match_names(away_team, p1)
                ):
                    return {
                        "data_quality": "api_sports_tennis",
                        "api_sports_event_id": g.get("id"),
                        "league": g.get("league", {}).get("name"),
                        "home_team": p1,
                        "away_team": p2,
                        "status": g.get("status", {}).get("long"),
                    }

            return {"data_quality": "odds_only", "warning": "API-Sports tennis mapping topilmadi"}

        except Exception as e:
            return {"data_quality": "odds_only", "warning": f"Tennis enrich error: {repr(e)}"}

    async def enrich_soccer(self, home_team, away_team, commence_time):
        try:
            date_str = commence_time.date().isoformat()

            data = await self._get(
                self.football_host,
                "/fixtures",
                {"date": date_str}
            )

            for g in data.get("response", []):
                teams = g.get("teams", {})
                h = teams.get("home", {}).get("name", "")
                a = teams.get("away", {}).get("name", "")

                if self._match_names(home_team, h) and self._match_names(away_team, a):
                    fixture = g.get("fixture", {})
                    league = g.get("league", {})

                    return {
                        "data_quality": "api_sports_football",
                        "api_sports_event_id": fixture.get("id"),
                        "league": league.get("name"),
                        "country": league.get("country"),
                        "season": league.get("season"),
                        "round": league.get("round"),
                        "home_team": h,
                        "away_team": a,
                        "status": fixture.get("status", {}).get("long"),
                        "venue": fixture.get("venue", {}).get("name"),
                    }

            return {"data_quality": "odds_only", "warning": "API-Sports football mapping topilmadi"}

        except Exception as e:
            return {"data_quality": "odds_only", "warning": f"Football enrich error: {repr(e)}"}

    async def basketball_result(self, api_id):
        try:
            data = await self._get(
                self.basketball_host,
                "/games",
                {"id": api_id}
            )
            return data
        except Exception as e:
            return {"error": repr(e)}

    async def tennis_result(self, api_id):
        try:
            data = await self._get(
                self.tennis_host,
                "/fixtures",
                {"id": api_id}
            )
            return data
        except Exception as e:
            return {"error": repr(e)}

    async def soccer_result(self, api_id):
        try:
            data = await self._get(
                self.football_host,
                "/fixtures",
                {"id": api_id}
            )
            return data
        except Exception as e:
            return {"error": repr(e)}

    def _match_names(self, a, b):
        if not a or not b:
            return False

        a = self._clean_name(a)
        b = self._clean_name(b)

        if a == b:
            return True

        if a in b or b in a:
            return True

        a_parts = set(a.split())
        b_parts = set(b.split())

        if not a_parts or not b_parts:
            return False

        common = a_parts.intersection(b_parts)

        return len(common) >= 2

    def _clean_name(self, name):
        return (
            str(name)
            .lower()
            .replace("fc", "")
            .replace("cf", "")
            .replace("afc", "")
            .replace("bc", "")
            .replace(".", "")
            .replace("-", " ")
            .replace("_", " ")
            .strip()
        )
