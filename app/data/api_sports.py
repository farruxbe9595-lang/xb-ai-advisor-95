import httpx


class ApiSportsClient:
    def __init__(
        self,
        api_key: str,
        basketball_host: str,
        tennis_host: str,
        football_host: str
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
        if not self.api_key:
            raise RuntimeError("API_SPORTS_KEY is empty")

        url = f"https://{host}{path}"

        async with httpx.AsyncClient(timeout=35) as client:
            response = await client.get(
                url,
                headers=self.headers(host),
                params=params
            )

            if response.status_code >= 400:
                raise RuntimeError(
                    f"API-Sports HTTP {response.status_code}: {response.text[:300]}"
                )

            return response.json()

    def _clean_name(self, name: str):
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

    def _match_names(self, a: str, b: str):
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
        common = a_parts.intersection(b_parts)

        return len(common) >= 2

    async def enrich_basketball(self, home_team, away_team, commence_time):
        try:
            data = await self._get(
                self.basketball_host,
                "/games",
                {"date": commence_time.date().isoformat()}
            )

            for game in data.get("response", []):
                h = game.get("teams", {}).get("home", {}).get("name", "")
                a = game.get("teams", {}).get("away", {}).get("name", "")

                if self._match_names(home_team, h) and self._match_names(away_team, a):
                    return {
                        "data_quality": "api_sports_basketball",
                        "api_sports_event_id": game.get("id"),
                        "league": game.get("league", {}).get("name"),
                        "country": game.get("country", {}).get("name"),
                        "home_team": h,
                        "away_team": a,
                        "status": game.get("status", {}).get("long"),
                    }

            return {
                "data_quality": "odds_only",
                "warning": "API-Sports basketball mapping topilmadi"
            }

        except Exception as e:
            return {
                "data_quality": "odds_only",
                "warning": f"Basketball enrich error: {repr(e)}"
            }

    async def enrich_tennis(self, home_team, away_team, commence_time):
        try:
            data = await self._get(
                self.tennis_host,
                "/fixtures",
                {"date": commence_time.date().isoformat()}
            )

            for game in data.get("response", []):
                players = game.get("players", {})
                p1 = players.get("first", {}).get("name", "")
                p2 = players.get("second", {}).get("name", "")

                ok1 = self._match_names(home_team, p1) and self._match_names(away_team, p2)
                ok2 = self._match_names(home_team, p2) and self._match_names(away_team, p1)

                if ok1 or ok2:
                    return {
                        "data_quality": "api_sports_tennis",
                        "api_sports_event_id": game.get("id"),
                        "league": game.get("league", {}).get("name"),
                        "home_team": p1,
                        "away_team": p2,
                        "status": game.get("status", {}).get("long"),
                    }

            return {
                "data_quality": "odds_only",
                "warning": "API-Sports tennis mapping topilmadi"
            }

        except Exception as e:
            return {
                "data_quality": "odds_only",
                "warning": f"Tennis enrich error: {repr(e)}"
            }

    async def enrich_soccer(self, home_team, away_team, commence_time):
        try:
            data = await self._get(
                self.football_host,
                "/fixtures",
                {"date": commence_time.date().isoformat()}
            )

            for game in data.get("response", []):
                teams = game.get("teams", {})
                h = teams.get("home", {}).get("name", "")
                a = teams.get("away", {}).get("name", "")

                if self._match_names(home_team, h) and self._match_names(away_team, a):
                    fixture = game.get("fixture", {})
                    league = game.get("league", {})

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

            return {
                "data_quality": "odds_only",
                "warning": "API-Sports football mapping topilmadi"
            }

        except Exception as e:
            return {
                "data_quality": "odds_only",
                "warning": f"Football enrich error: {repr(e)}"
            }

    async def basketball_result(self, api_id):
        try:
            return await self._get(self.basketball_host, "/games", {"id": api_id})
        except Exception as e:
            return {"error": repr(e)}

    async def tennis_result(self, api_id):
        try:
            return await self._get(self.tennis_host, "/fixtures", {"id": api_id})
        except Exception as e:
            return {"error": repr(e)}

    async def soccer_result(self, api_id):
        try:
            return await self._get(self.football_host, "/fixtures", {"id": api_id})
        except Exception as e:
            return {"error": repr(e)}
