import json
from datetime import datetime, timezone, timedelta

import aiosqlite

from app.config.settings import settings


def _utc_now():
    return datetime.now(timezone.utc)


def _uz_now():
    return _utc_now() + timedelta(hours=settings.timezone_offset_hours)


def _parse_iso_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


class Repository:
    def __init__(self, db_path):
        self.db_path = db_path

    async def save_odds_snapshot(self, event):
        now = _utc_now().isoformat()
        rows = []

        for m in event.markets:
            for o in m.outcomes:
                rows.append((
                    event.event_id,
                    event.sport_key,
                    m.key,
                    m.bookmaker,
                    o.name,
                    o.point,
                    o.price,
                    now,
                ))

        if rows:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executemany(
                    '''
                    INSERT INTO odds_snapshots(
                        event_id, sport_key, market_key, bookmaker,
                        outcome_name, line, odds, created_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                    ''',
                    rows,
                )
                await db.commit()

    async def get_previous_odds(self, event_id, market_key, outcome_name, line):
        async with aiosqlite.connect(self.db_path) as db:
            if line is None:
                cur = await db.execute(
                    '''
                    SELECT odds FROM odds_snapshots
                    WHERE event_id=? AND market_key=? AND outcome_name=? AND line IS NULL
                    ORDER BY id DESC LIMIT 1
                    ''',
                    (event_id, market_key, outcome_name),
                )
            else:
                cur = await db.execute(
                    '''
                    SELECT odds FROM odds_snapshots
                    WHERE event_id=? AND market_key=? AND outcome_name=?
                    AND ABS(line - ?) < 0.001
                    ORDER BY id DESC LIMIT 1
                    ''',
                    (event_id, market_key, outcome_name, line),
                )

            row = await cur.fetchone()
            return float(row[0]) if row else None

    async def save_event_link(self, odds_event_id, sport_key, api_sports_event_id):
        if not api_sports_event_id:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                '''
                INSERT INTO event_links(
                    odds_event_id, sport_key, api_sports_event_id, created_at
                ) VALUES(?,?,?,?)
                ON CONFLICT(odds_event_id)
                DO UPDATE SET api_sports_event_id=excluded.api_sports_event_id
                ''',
                (
                    odds_event_id,
                    sport_key,
                    str(api_sports_event_id),
                    _utc_now().isoformat(),
                ),
            )
            await db.commit()

    async def get_event_link(self, odds_event_id):
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                '''
                SELECT api_sports_event_id
                FROM event_links
                WHERE odds_event_id=?
                LIMIT 1
                ''',
                (odds_event_id,),
            )
            row = await cur.fetchone()
            return row[0] if row and row[0] else None

    async def signal_exists(self, a):
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                '''
                SELECT id FROM signals
                WHERE event_id=? AND market_key=? AND pick=?
                AND (
                    (line IS NULL AND ? IS NULL)
                    OR
                    (line IS NOT NULL AND ? IS NOT NULL AND ABS(line - ?) < 0.001)
                )
                LIMIT 1
                ''',
                (
                    a.event_id,
                    a.market_key,
                    a.pick,
                    a.line,
                    a.line,
                    a.line or 0,
                ),
            )
            return await cur.fetchone() is not None

    async def save_signal(self, a):
        if await self.signal_exists(a):
            return False

        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                '''
                INSERT INTO signals(
                    signal_code,
                    event_id, sport_key, sport_title, match_name, commence_time,
                    market_key, market_label, pick, odds, line,
                    implied_probability, model_probability, value_edge,
                    confidence, anomaly_score, risk_level, bookmaker,
                    reasons, warnings, data_quality, synthetic,
                    ai_validator_score, ai_validator_verdict,
                    stake_amount, stake_percent, status, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''',
                (
                    None,
                    a.event_id,
                    a.sport_key,
                    a.sport_title,
                    a.match_name,
                    a.commence_time.isoformat(),
                    a.market_key,
                    a.market_label,
                    a.pick,
                    a.odds,
                    a.line,
                    a.implied_probability,
                    a.model_probability,
                    a.value_edge,
                    a.confidence,
                    a.anomaly_score,
                    a.risk_level,
                    a.bookmaker,
                    json.dumps(a.reasons, ensure_ascii=False),
                    json.dumps(a.warnings, ensure_ascii=False),
                    a.data_quality,
                    1 if a.synthetic else 0,
                    a.ai_validator_score,
                    a.ai_validator_verdict,
                    a.stake_amount,
                    a.stake_percent,
                    'pending',
                    _utc_now().isoformat(),
                ),
            )

            signal_id = cur.lastrowid
            prefix = (
                a.sport_key.upper()
                .replace('BASKETBALL_', '')
                .replace('TENNIS_', '')
                .replace('SOCCER_', '')
            )
            date_code = _uz_now().strftime('%Y%m%d')
            signal_code = f'{prefix}-{date_code}-{signal_id:04d}'

            await db.execute(
                'UPDATE signals SET signal_code=? WHERE id=?',
                (signal_code, signal_id),
            )
            await db.commit()

            a.signal_code = signal_code
            return True

    async def pending_signals(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                '''
                SELECT * FROM signals
                WHERE status='pending'
                ORDER BY id ASC
                LIMIT 100
                '''
            )
            return [dict(r) for r in await cur.fetchall()]

    async def mark_signal(self, signal_id, status, result_text):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                '''
                UPDATE signals
                SET status=?, result_text=?
                WHERE id=?
                ''',
                (status, result_text, signal_id),
            )
            await db.commit()

    async def stats_summary(self):
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                '''
                SELECT status, COUNT(*)
                FROM signals
                GROUP BY status
                '''
            )
            return {r[0]: r[1] for r in await cur.fetchall()}

    async def performance_by_market(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                '''
                SELECT
                    sport_key,
                    market_key,
                    COUNT(*) total,
                    SUM(CASE WHEN status='won' THEN 1 ELSE 0 END) won,
                    SUM(CASE WHEN status='lost' THEN 1 ELSE 0 END) lost,
                    AVG(confidence) avg_confidence,
                    AVG(value_edge) avg_edge
                FROM signals
                WHERE status IN ('won','lost')
                GROUP BY sport_key, market_key
                ORDER BY total DESC
                '''
            )
            return [dict(r) for r in await cur.fetchall()]

    async def daily_pl(self):
        today_uz = _uz_now().date()
        cutoff_utc = _utc_now() - timedelta(hours=36)

        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                '''
                SELECT status, stake_amount, odds, created_at
                FROM signals
                WHERE created_at >= ?
                ''',
                (cutoff_utc.isoformat(),),
            )
            rows = await cur.fetchall()

        pl = 0.0
        for status, stake, odds, created_at in rows:
            created_dt = _parse_iso_dt(created_at)
            if created_dt is None:
                continue
            created_uz_date = (created_dt + timedelta(hours=settings.timezone_offset_hours)).date()
            if created_uz_date != today_uz:
                continue

            stake = float(stake or 0)
            odds = float(odds or 0)

            if status == 'won':
                pl += stake * (odds - 1)
            elif status == 'lost':
                pl -= stake

        return round(pl, 2)

    async def consecutive_losses(self):
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                '''
                SELECT status FROM signals
                WHERE status IN ('won','lost')
                ORDER BY id DESC
                LIMIT 20
                '''
            )
            rows = await cur.fetchall()

        n = 0
        for (status,) in rows:
            if status == 'lost':
                n += 1
            else:
                break

        return n

    async def daily_report_sent(self, report_date):
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                '''
                SELECT id FROM daily_reports
                WHERE report_date=?
                LIMIT 1
                ''',
                (report_date,),
            )
            return await cur.fetchone() is not None

    async def mark_daily_report_sent(self, report_date):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                '''
                INSERT OR IGNORE INTO daily_reports(report_date, sent_at)
                VALUES(?,?)
                ''',
                (report_date, _utc_now().isoformat()),
            )
            await db.commit()
