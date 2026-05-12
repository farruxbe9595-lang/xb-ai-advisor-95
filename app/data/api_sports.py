import httpx


class ApiSportsClient:
    def __init__(
        self,
        api_key: str,
        basketball_host: str,
        tennis_host: str,
        football_host: str,
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
            response = await client.get(url, headers=self.headers(host), params=params)

            if response.status_code >= 400:
                raise RuntimeError(f"API-Sports HTTP {response.status_code}: {response.text[:300]}")

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
            data = await self._get(self.basketball_host, "/games", {"date": commence_time.date().isoformat()})

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

            return {"data_quality": "odds_only", "warning": "API-Sports basketball mapping topilmadi"}

        except Exception as e:
            return {"data_quality": "odds_only", "warning": f"Basketball enrich error: {repr(e)}"}

    async def enrich_tennis(self, home_team, away_team, commence_time):
        try:
            data = await self._get(self.tennis_host, "/fixtures", {"date": commence_time.date().isoformat()})

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

            return {"data_quality": "odds_only", "warning": "API-Sports tennis mapping topilmadi"}

        except Exception as e:
            return {"data_quality": "odds_only", "warning": f"Tennis enrich error: {repr(e)}"}

    async def enrich_soccer(self, home_team, away_team, commence_time):
        try:
            data = await self._get(self.football_host, "/fixtures", {"date": commence_time.date().isoformat()})

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

            return {"data_quality": "odds_only", "warning": "API-Sports football mapping topilmadi"}

        except Exception as e:
            return {"data_quality": "odds_only", "warning": f"Football enrich error: {repr(e)}"}

    async def basketball_result(self, api_id):
        try:
            data = await self._get(self.basketball_host, "/games", {"id": api_id})
            return self._normalize_basketball_result(data)
        except Exception as e:
            return {"error": repr(e)}

    async def tennis_result(self, api_id):
        try:
            data = await self._get(self.tennis_host, "/fixtures", {"id": api_id})
            return self._normalize_tennis_result(data)
        except Exception as e:
            return {"error": repr(e)}

    async def soccer_result(self, api_id):
        try:
            data = await self._get(self.football_host, "/fixtures", {"id": api_id})
            return self._normalize_soccer_result(data)
        except Exception as e:
            return {"error": repr(e)}

    def _normalize_basketball_result(self, data):
        response = data.get("response") or []
        if not response:
            return {"finished": False, "status": "not_found"}

        game = response[0]
        status_obj = game.get("status") or {}
        status_long = str(status_obj.get("long") or status_obj.get("short") or "").lower()
        status_short = str(status_obj.get("short") or "").lower()
        finished = any(x in status_long for x in ["finished", "after over", "ended"]) or status_short in {"ft", "aot", "ap"}

        teams = game.get("teams") or {}
        scores = game.get("scores") or {}
        home_team = (teams.get("home") or {}).get("name")
        away_team = (teams.get("away") or {}).get("name")
        home_score = self._extract_score(scores.get("home"))
        away_score = self._extract_score(scores.get("away"))

        winner = None
        if finished and home_score is not None and away_score is not None:
            if home_score > away_score:
                winner = home_team
            elif away_score > home_score:
                winner = away_team

        first_half_home, first_half_away = self._extract_basketball_half(scores)

        return {
            "finished": finished,
            "status": status_obj.get("long") or status_obj.get("short"),
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "first_half_home": first_half_home,
            "first_half_away": first_half_away,
            "winner": winner,
        }

    def _normalize_soccer_result(self, data):
        response = data.get("response") or []
        if not response:
            return {"finished": False, "status": "not_found"}

        game = response[0]
        fixture = game.get("fixture") or {}
        status_obj = fixture.get("status") or {}
        status_short = str(status_obj.get("short") or "").upper()
        finished = status_short in {"FT", "AET", "PEN"}

        teams = game.get("teams") or {}
        goals = game.get("goals") or {}
        home_team = (teams.get("home") or {}).get("name")
        away_team = (teams.get("away") or {}).get("name")
        home_score = goals.get("home")
        away_score = goals.get("away")

        winner = None
        if finished and home_score is not None and away_score is not None:
            if home_score > away_score:
                winner = home_team
            elif away_score > home_score:
                winner = away_team
            else:
                winner = "Draw"

        return {
            "finished": finished,
            "status": status_obj.get("long") or status_short,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "winner": winner,
        }

    def _normalize_tennis_result(self, data):
        response = data.get("response") or []
        if not response:
            return {"finished": False, "status": "not_found"}

        game = response[0]
        status_obj = game.get("status") or {}
        status_long = str(status_obj.get("long") or status_obj.get("short") or "").lower()
        finished = any(x in status_long for x in ["finished", "ended", "retired", "walkover"])

        players = game.get("players") or {}
        p1 = (players.get("first") or {}).get("name")
        p2 = (players.get("second") or {}).get("name")
        winner = None

        winner_obj = game.get("winner") or {}
        if isinstance(winner_obj, dict):
            winner = winner_obj.get("name")

        return {
            "finished": finished,
            "status": status_obj.get("long") or status_obj.get("short"),
            "home_team": p1,
            "away_team": p2,
            "home_score": None,
            "away_score": None,
            "winner": winner,
        }

    def _extract_score(self, side_score):
        if side_score is None:
            return None
        if isinstance(side_score, (int, float)):
            return int(side_score)
        if isinstance(side_score, dict):
            for key in ["total", "points", "score", "final"]:
                val = side_score.get(key)
                if val is not None:
                    try:
                        return int(val)
                    except Exception:
                        pass
        return None

    def _extract_basketball_half(self, scores):
        try:
            home = scores.get("home") or {}
            away = scores.get("away") or {}
            h1 = home.get("quarter_1") or home.get("q1") or 0
            h2 = home.get("quarter_2") or home.get("q2") or 0
            a1 = away.get("quarter_1") or away.get("q1") or 0
            a2 = away.get("quarter_2") or away.get("q2") or 0
            if h1 is None or h2 is None or a1 is None or a2 is None:
                return None, None
            return int(h1) + int(h2), int(a1) + int(a2)
        except Exception:
            return None, None
