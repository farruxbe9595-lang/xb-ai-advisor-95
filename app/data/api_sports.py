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
            response = await client.get(
                url,
                headers=self.headers(host),
                params=params,
            )

            if response.status_code >= 400:
                raise RuntimeError(
                    f"API-Sports HTTP {response.status_code}: {response.text[:300]}"
                )

            return response.json()

    def _clean_name(self, name: str):
        cleaned = (
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
        return " ".join(cleaned.split())

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
                {"date": commence_time.date().isoformat()},
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
                "warning": "API-Sports basketball mapping topilmadi",
            }

        except Exception as e:
            return {
                "data_quality": "odds_only",
                "warning": f"Basketball enrich error: {repr(e)}",
            }

    async def enrich_tennis(self, home_team, away_team, commence_time):
        try:
            data = await self._get(
                self.tennis_host,
                "/fixtures",
                {"date": commence_time.date().isoformat()},
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
                "warning": "API-Sports tennis mapping topilmadi",
            }

        except Exception as e:
            return {
                "data_quality": "odds_only",
                "warning": f"Tennis enrich error: {repr(e)}",
            }

    async def enrich_soccer(self, home_team, away_team, commence_time):
        try:
            data = await self._get(
                self.football_host,
                "/fixtures",
                {"date": commence_time.date().isoformat()},
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
                "warning": "API-Sports football mapping topilmadi",
            }

        except Exception as e:
            return {
                "data_quality": "odds_only",
                "warning": f"Football enrich error: {repr(e)}",
            }

    async def basketball_result(self, api_id):
        try:
            raw = await self._get(self.basketball_host, "/games", {"id": api_id})
            return self._normalize_basketball(raw)
        except Exception as e:
            return {"error": repr(e)}

    async def tennis_result(self, api_id):
        try:
            raw = await self._get(self.tennis_host, "/fixtures", {"id": api_id})
            return self._normalize_tennis(raw)
        except Exception as e:
            return {"error": repr(e)}

    async def soccer_result(self, api_id):
        try:
            raw = await self._get(self.football_host, "/fixtures", {"id": api_id})
            return self._normalize_soccer(raw)
        except Exception as e:
            return {"error": repr(e)}

    def _first_response(self, raw):
        response = raw.get("response") if isinstance(raw, dict) else None
        if isinstance(response, list) and response:
            return response[0]
        if isinstance(response, dict):
            return response
        return None

    def _num(self, value):
        try:
            if value is None or value == "":
                return None
            return int(float(value))
        except Exception:
            return None

    def _score_from_obj(self, obj):
        if obj is None:
            return None
        if isinstance(obj, (int, float, str)):
            return self._num(obj)
        if isinstance(obj, dict):
            for key in ("total", "points", "score", "current", "final"):
                n = self._num(obj.get(key))
                if n is not None:
                    return n
        return None

    def _basketball_half_score(self, team_scores):
        if not isinstance(team_scores, dict):
            return None

        q1 = self._num(team_scores.get("quarter_1") or team_scores.get("q1"))
        q2 = self._num(team_scores.get("quarter_2") or team_scores.get("q2"))

        if q1 is not None and q2 is not None:
            return q1 + q2

        p1 = self._num(team_scores.get("period_1"))
        p2 = self._num(team_scores.get("period_2"))
        if p1 is not None and p2 is not None:
            return p1 + p2

        return None

    def _is_finished(self, status):
        short = str(status.get("short", "") if isinstance(status, dict) else "").upper()
        long = str(status.get("long", status) if status else "").lower()

        finish_shorts = {"FT", "AOT", "AP", "FIN", "FINISHED", "ENDED"}
        finish_words = ("finished", "after over time", "full time", "ended", "completed")

        return short in finish_shorts or any(w in long for w in finish_words)

    def _normalize_basketball(self, raw):
        game = self._first_response(raw)
        if not game:
            return {"finished": False, "status": "not_found"}

        status_obj = game.get("status", {})
        finished = self._is_finished(status_obj)

        teams = game.get("teams", {})
        home = teams.get("home", {}).get("name", "")
        away = teams.get("away", {}).get("name", "")

        scores = game.get("scores", {})
        home_scores = scores.get("home", {})
        away_scores = scores.get("away", {})

        hs = self._score_from_obj(home_scores)
        aw = self._score_from_obj(away_scores)

        if hs is None:
            hs = self._num(scores.get("home"))
        if aw is None:
            aw = self._num(scores.get("away"))

        winner = None
        if finished and hs is not None and aw is not None and hs != aw:
            winner = home if hs > aw else away

        return {
            "finished": finished,
            "status": status_obj.get("long") if isinstance(status_obj, dict) else str(status_obj),
            "home_team": home,
            "away_team": away,
            "home_score": hs,
            "away_score": aw,
            "first_half_home": self._basketball_half_score(home_scores),
            "first_half_away": self._basketball_half_score(away_scores),
            "winner": winner,
        }

    def _normalize_tennis(self, raw):
        game = self._first_response(raw)
        if not game:
            return {"finished": False, "status": "not_found"}

        status_obj = game.get("status", {})
        finished = self._is_finished(status_obj)

        players = game.get("players", {})
        p1_obj = players.get("first", {})
        p2_obj = players.get("second", {})
        p1 = p1_obj.get("name", "")
        p2 = p2_obj.get("name", "")

        winner = None

        if p1_obj.get("winner") is True:
            winner = p1
        elif p2_obj.get("winner") is True:
            winner = p2
        elif isinstance(game.get("winner"), dict):
            winner = game["winner"].get("name")

        scores = game.get("scores", {})
        hs = self._score_from_obj(scores.get("home") or scores.get("first"))
        aw = self._score_from_obj(scores.get("away") or scores.get("second"))

        return {
            "finished": finished,
            "status": status_obj.get("long") if isinstance(status_obj, dict) else str(status_obj),
            "home_team": p1,
            "away_team": p2,
            "home_score": hs,
            "away_score": aw,
            "winner": winner,
        }

    def _normalize_soccer(self, raw):
        game = self._first_response(raw)
        if not game:
            return {"finished": False, "status": "not_found"}

        fixture = game.get("fixture", {})
        status_obj = fixture.get("status", {})
        finished = self._is_finished(status_obj)

        teams = game.get("teams", {})
        home = teams.get("home", {}).get("name", "")
        away = teams.get("away", {}).get("name", "")

        goals = game.get("goals", {})
        hs = self._num(goals.get("home"))
        aw = self._num(goals.get("away"))

        winner = None
        if finished and hs is not None and aw is not None and hs != aw:
            winner = home if hs > aw else away

        return {
            "finished": finished,
            "status": status_obj.get("long") if isinstance(status_obj, dict) else str(status_obj),
            "home_team": home,
            "away_team": away,
            "home_score": hs,
            "away_score": aw,
            "winner": winner,
        }
