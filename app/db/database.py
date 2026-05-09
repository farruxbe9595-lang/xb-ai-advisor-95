import aiosqlite
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS odds_snapshots(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT,
    sport_key TEXT,
    market_key TEXT,
    bookmaker TEXT,
    outcome_name TEXT,
    line REAL,
    odds REAL,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_odds_lookup
ON odds_snapshots(event_id, market_key, outcome_name, line, id);

CREATE TABLE IF NOT EXISTS event_links(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    odds_event_id TEXT UNIQUE,
    sport_key TEXT,
    api_sports_event_id TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS signals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_code TEXT,
    event_id TEXT,
    sport_key TEXT,
    sport_title TEXT,
    match_name TEXT,
    commence_time TEXT,
    market_key TEXT,
    market_label TEXT,
    pick TEXT,
    odds REAL,
    line REAL,
    implied_probability REAL,
    model_probability REAL,
    value_edge REAL,
    confidence INTEGER,
    anomaly_score INTEGER,
    risk_level TEXT,
    bookmaker TEXT,
    reasons TEXT,
    warnings TEXT,
    data_quality TEXT,
    synthetic INTEGER DEFAULT 0,
    ai_validator_score INTEGER DEFAULT 100,
    ai_validator_verdict TEXT DEFAULT 'APPROVE',
    stake_amount REAL DEFAULT 0,
    stake_percent REAL DEFAULT 0,
    status TEXT DEFAULT 'pending',
    result_text TEXT,
    created_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_signal_unique
ON signals(event_id, market_key, pick, line);

CREATE TABLE IF NOT EXISTS daily_reports(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT UNIQUE,
    sent_at TEXT
);
'''

async def init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)

        # Eski database bo‘lsa, signal_code ustunini qo‘shadi
        cur = await db.execute("PRAGMA table_info(signals)")
        columns = [row[1] for row in await cur.fetchall()]
        if "signal_code" not in columns:
            await db.execute("ALTER TABLE signals ADD COLUMN signal_code TEXT")

        await db.commit()
