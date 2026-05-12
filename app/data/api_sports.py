import re

import httpx


FINISHED_STATUS = {
    'ft', 'aot', 'ap', 'final', 'finished', 'match finished', 'game finished',
    'after overtime', 'after penalties', 'ended', 'closed'
}


class ApiSportsClient:
    def __init__(self, api_key, basketball_host, tennis_host, football_host):
        self.api_key = api_key
        self.basketball_host = basketball_host
        self.tennis_host = tennis_host
        self.football_host = football_host

    def headers(self, host: str):
        return {
            'x-rapidapi-key': self.api_key,
            'x-rapidapi-host': host,
        }

    async def _get(self, host: str, path: str, params: dict):
        if not self.api_key:
            return {'response': [], 'warning': 'API_SPORTS_KEY is empty'}

        url = f'https://{host}{path}'
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=self.headers(host), params=params)
            r.raise_for_status()
            return r.json()

    async def enrich_basketball(self, home_team, away_team, commence_time):
        try:
            data = await self._get(self.basketball_host, '/games', {'date': commence_time.date().isoformat()})

            for g in data.get('response', []):
                h = g.get('teams', {}).get('home', {}).get('name', '')
                a = g.get('teams', {}).get('away', {}).get('name', '')

                if self._match_names(home_team, h) and self._match_names(away_team, a):
                    return {
                        'data_quality': 'api_sports_basketball',
                        'api_sports_event_id': g.get('id'),
                        'league': g.get('league', {}).get('name'),
                        'country': g.get('country', {}).get('name'),
                        'home_team': h,
                        'away_team': a,
                        'status': g.get('status', {}).get('long') or g.get('status', {}).get('short'),
                    }

            return {'data_quality': 'odds_only', 'warning': 'API-Sports basketball mapping topilmadi'}

        except Exception as e:
            return {'data_quality': 'odds_only', 'warning': f'Basketball enrich error: {repr(e)}'}

    async def enrich_tennis(self, home_team, away_team, commence_time):
        try:
            data = await self._get(self.tennis_host, '/fixtures', {'date': commence_time.date().isoformat()})

            for g in data.get('response', []):
                players = g.get('players', {})
                p1 = players.get('first', {}).get('name', '')
                p2 = players.get('second', {}).get('name', '')

                if (
                    self._match_names(home_team, p1) and self._match_names(away_team, p2)
                ) or (
                    self._match_names(home_team, p2) and self._match_names(away_team, p1)
                ):
                    return {
                        'data_quality': 'api_sports_tennis',
                        'api_sports_event_id': g.get('id'),
                        'league': g.get('league', {}).get('name'),
                        'home_team': p1,
                        'away_team': p2,
                        'status': g.get('status', {}).get('long') or g.get('status', {}).get('short'),
                    }

            return {'data_quality': 'odds_only', 'warning': 'API-Sports tennis mapping topilmadi'}

        except Exception as e:
            return {'data_quality': 'odds_only', 'warning': f'Tennis enrich error: {repr(e)}'}

    async def enrich_soccer(self, home_team, away_team, commence_time):
        try:
            data = await self._get(self.football_host, '/fixtures', {'date': commence_time.date().isoformat()})

            for g in data.get('response', []):
                teams = g.get('teams', {})
                h = teams.get('home', {}).get('name', '')
                a = teams.get('away', {}).get('name', '')

                if self._match_names(home_team, h) and self._match_names(away_team, a):
                    fixture = g.get('fixture', {})
                    league = g.get('league', {})

                    return {
                        'data_quality': 'api_sports_football',
                        'api_sports_event_id': fixture.get('id'),
                        'league': league.get('name'),
                        'country': league.get('country'),
                        'season': league.get('season'),
                        'round': league.get('round'),
                        'home_team': h,
                        'away_team': a,
                        'status': fixture.get('status', {}).get('long') or fixture.get('status', {}).get('short'),
                        'venue': fixture.get('venue', {}).get('name'),
                    }

            return {'data_quality': 'odds_only', 'warning': 'API-Sports football mapping topilmadi'}

        except Exception as e:
            return {'data_quality': 'odds_only', 'warning': f'Football enrich error: {repr(e)}'}

    async def basketball_result(self, api_id):
        try:
            raw = await self._get(self.basketball_host, '/games', {'id': api_id})
            return self.normalize_basketball_result(raw)
        except Exception as e:
            return {'error': repr(e), 'finished': False}

    async def tennis_result(self, api_id):
        try:
            raw = await self._get(self.tennis_host, '/fixtures', {'id': api_id})
            return self.normalize_tennis_result(raw)
        except Exception as e:
            return {'error': repr(e), 'finished': False}

    async def soccer_result(self, api_id):
        try:
            raw = await self._get(self.football_host, '/fixtures', {'id': api_id})
            return self.normalize_soccer_result(raw)
        except Exception as e:
            return {'error': repr(e), 'finished': False}

    def normalize_basketball_result(self, raw):
        g = self._first_response(raw)
        if not g:
            return {'finished': False, 'status': 'not_found'}

        status = g.get('status', {})
        status_text = status.get('short') or status.get('long') or ''
        scores = g.get('scores', {})
        home_scores = scores.get('home', {}) or {}
        away_scores = scores.get('away', {}) or {}

        hs = self._num(home_scores.get('total') or home_scores.get('points'))
        aw = self._num(away_scores.get('total') or away_scores.get('points'))

        q1h = self._num(home_scores.get('quarter_1'))
        q2h = self._num(home_scores.get('quarter_2'))
        q1a = self._num(away_scores.get('quarter_1'))
        q2a = self._num(away_scores.get('quarter_2'))

        first_half_home = q1h + q2h if q1h is not None and q2h is not None else None
        first_half_away = q1a + q2a if q1a is not None and q2a is not None else None

        home_team = g.get('teams', {}).get('home', {}).get('name', '')
        away_team = g.get('teams', {}).get('away', {}).get('name', '')
        winner = None
        if hs is not None and aw is not None:
            if hs > aw:
                winner = home_team
            elif aw > hs:
                winner = away_team

        return {
            'sport': 'basketball',
            'finished': self._is_finished(status_text),
            'status': status_text,
            'home_team': home_team,
            'away_team': away_team,
            'home_score': hs,
            'away_score': aw,
            'first_half_home': first_half_home,
            'first_half_away': first_half_away,
            'winner': winner,
            'raw': raw,
        }

    def normalize_tennis_result(self, raw):
        g = self._first_response(raw)
        if not g:
            return {'finished': False, 'status': 'not_found'}

        status = g.get('status', {})
        status_text = status.get('short') or status.get('long') or ''
        players = g.get('players', {})
        first = players.get('first', {}) or {}
        second = players.get('second', {}) or {}
        p1 = first.get('name', '')
        p2 = second.get('name', '')

        winner = None
        if first.get('winner') is True:
            winner = p1
        elif second.get('winner') is True:
            winner = p2

        p1_sets, p2_sets = self._tennis_sets_score(g.get('scores'))
        if winner is None and p1_sets is not None and p2_sets is not None and p1_sets != p2_sets:
            winner = p1 if p1_sets > p2_sets else p2

        return {
            'sport': 'tennis',
            'finished': self._is_finished(status_text),
            'status': status_text,
            'home_team': p1,
            'away_team': p2,
            'home_score': p1_sets,
            'away_score': p2_sets,
            'winner': winner,
            'raw': raw,
        }

    def normalize_soccer_result(self, raw):
        g = self._first_response(raw)
        if not g:
            return {'finished': False, 'status': 'not_found'}

        fixture = g.get('fixture', {})
        status = fixture.get('status', {})
        status_text = status.get('short') or status.get('long') or ''
        teams = g.get('teams', {})
        goals = g.get('goals', {})
        home_team = teams.get('home', {}).get('name', '')
        away_team = teams.get('away', {}).get('name', '')
        hs = self._num(goals.get('home'))
        aw = self._num(goals.get('away'))

        winner = None
        if hs is not None and aw is not None:
            if hs > aw:
                winner = home_team
            elif aw > hs:
                winner = away_team
            else:
                winner = 'Draw'

        return {
            'sport': 'soccer',
            'finished': self._is_finished(status_text),
            'status': status_text,
            'home_team': home_team,
            'away_team': away_team,
            'home_score': hs,
            'away_score': aw,
            'winner': winner,
            'raw': raw,
        }

    def _first_response(self, raw):
        if not raw or not isinstance(raw, dict):
            return None
        response = raw.get('response')
        if isinstance(response, list) and response:
            return response[0]
        if isinstance(response, dict):
            return response
        return None

    def _is_finished(self, status):
        s = str(status or '').strip().lower()
        return s in FINISHED_STATUS or 'finish' in s or s == 'ft'

    def _num(self, value):
        if value is None or value == '':
            return None
        try:
            return int(value)
        except Exception:
            try:
                return float(value)
            except Exception:
                return None

    def _tennis_sets_score(self, scores):
        if not scores:
            return None, None

        p1_sets = 0
        p2_sets = 0

        if isinstance(scores, list):
            for s in scores:
                first_score = self._num(s.get('first'))
                second_score = self._num(s.get('second'))
                if first_score is None or second_score is None or first_score == second_score:
                    continue
                if first_score > second_score:
                    p1_sets += 1
                else:
                    p2_sets += 1
            return p1_sets, p2_sets

        if isinstance(scores, dict):
            first_total = self._num(scores.get('first') or scores.get('home'))
            second_total = self._num(scores.get('second') or scores.get('away'))
            return first_total, second_total

        return None, None

    def _match_names(self, a, b):
        if not a or not b:
            return False

        a_clean = self._clean_name(a)
        b_clean = self._clean_name(b)

        if a_clean == b_clean:
            return True

        if a_clean in b_clean or b_clean in a_clean:
            return True

        a_parts = set(a_clean.split())
        b_parts = set(b_clean.split())

        if not a_parts or not b_parts:
            return False

        return len(a_parts.intersection(b_parts)) >= 2

    def _clean_name(self, name):
        text = str(name).lower()
        text = re.sub(r'\b(fc|cf|afc|bc|club|team)\b', ' ', text)
        text = text.replace('.', ' ').replace('-', ' ').replace('_', ' ')
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
