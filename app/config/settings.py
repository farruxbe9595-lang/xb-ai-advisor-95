from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str = Field('', alias='TELEGRAM_BOT_TOKEN')
    telegram_chat_id: str = Field('', alias='TELEGRAM_CHAT_ID')

    odds_api_key: str = Field('', alias='ODDS_API_KEY')
    api_sports_key: str = Field('', alias='API_SPORTS_KEY')

    openai_api_key: str = Field('', alias='OPENAI_API_KEY')
    openai_model: str = Field('gpt-4o-mini', alias='OPENAI_MODEL')

    db_path: str = Field('storage/signals.db', alias='DB_PATH')

    scan_interval_seconds: int = Field(1800, alias='SCAN_INTERVAL_SECONDS')
    live_scan_interval_seconds: int = Field(180, alias='LIVE_SCAN_INTERVAL_SECONDS')
    result_interval_seconds: int = Field(900, alias='RESULT_INTERVAL_SECONDS')
    daily_report_hour: int = Field(9, alias='DAILY_REPORT_HOUR')

    odds_regions: str = Field('eu', alias='ODDS_REGIONS')
    odds_markets: str = Field('h2h,totals,spreads', alias='ODDS_MARKETS')

    sport_keys: str = Field(
        'basketball_nba,basketball_euroleague,tennis_atp,tennis_wta,soccer_epl,soccer_spain_la_liga,soccer_germany_bundesliga',
        alias='SPORT_KEYS'
    )

    api_sports_basketball_host: str = Field(
        'v1.basketball.api-sports.io',
        alias='API_SPORTS_BASKETBALL_HOST'
    )

    api_sports_tennis_host: str = Field(
        'v1.tennis.api-sports.io',
        alias='API_SPORTS_TENNIS_HOST'
    )

    api_sports_football_host: str = Field(
        'v3.football.api-sports.io',
        alias='API_SPORTS_FOOTBALL_HOST'
    )

    min_confidence: int = Field(75, alias='MIN_CONFIDENCE')
    min_value_edge: float = Field(5.0, alias='MIN_VALUE_EDGE')
    max_anomaly_score: int = Field(35, alias='MAX_ANOMALY_SCORE')

    min_odds: float = Field(1.55, alias='MIN_ODDS')
    max_odds: float = Field(3.20, alias='MAX_ODDS')

    stake_percent: float = Field(1.0, alias='STAKE_PERCENT')

    ai_enabled: bool = Field(True, alias='AI_ENABLED')

    class Config:
        env_file = '.env'
        case_sensitive = False


settings = Settings()
