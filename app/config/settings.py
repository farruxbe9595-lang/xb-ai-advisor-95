from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str = Field("", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field("", alias="TELEGRAM_CHAT_ID")

    # API keys
    odds_api_key: str = Field("", alias="ODDS_API_KEY")
    api_sports_key: str = Field("", alias="API_SPORTS_KEY")

    # OpenAI
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
    ai_enabled: bool = Field(True, alias="AI_ENABLED")

    # Storage
    db_path: str = Field("/app/storage/signals.db", alias="DB_PATH")

    # Timezone
    timezone_offset_hours: int = Field(5, alias="TIMEZONE_OFFSET_HOURS")

    # Loop intervals
    scan_interval_seconds: int = Field(1800, alias="SCAN_INTERVAL_SECONDS")
    result_interval_seconds: int = Field(900, alias="RESULT_INTERVAL_SECONDS")
    live_scan_interval_seconds: int = Field(180, alias="LIVE_SCAN_INTERVAL_SECONDS")

    # Odds API
    odds_regions: str = Field("eu", alias="ODDS_REGIONS")
    odds_markets: str = Field("h2h,spreads", alias="ODDS_MARKETS")

    # Enabled sports. Keep only sports that your Odds API plan supports.
    sport_keys: str = Field(
        "basketball_nba,basketball_wnba",
        alias="SPORT_KEYS",
    )

    # Enabled markets for internal filtering.
    # Recommended for stable test: h2h,spreads
    # Add totals only after result tracking is verified.
    enabled_markets: str = Field("h2h,spreads", alias="ENABLED_MARKETS")

    # API-Sports hosts
    api_sports_basketball_host: str = Field(
        "v1.basketball.api-sports.io",
        alias="API_SPORTS_BASKETBALL_HOST",
    )
    api_sports_tennis_host: str = Field(
        "v1.tennis.api-sports.io",
        alias="API_SPORTS_TENNIS_HOST",
    )
    api_sports_football_host: str = Field(
        "v3.football.api-sports.io",
        alias="API_SPORTS_FOOTBALL_HOST",
    )

    # Event window
    min_hours_before_match: float = Field(-0.5, alias="MIN_HOURS_BEFORE_MATCH")
    max_hours_before_match: int = Field(24, alias="MAX_HOURS_BEFORE_MATCH")
    max_events_per_scan: int = Field(80, alias="MAX_EVENTS_PER_SCAN")

    # Signal filters
    min_confidence: int = Field(75, alias="MIN_CONFIDENCE")
    min_ai_validator_score: int = Field(65, alias="MIN_AI_VALIDATOR_SCORE")
    min_value_edge: float = Field(1.0, alias="MIN_VALUE_EDGE")
    max_anomaly_score: int = Field(40, alias="MAX_ANOMALY_SCORE")

    # Odds range
    min_odds: float = Field(1.30, alias="MIN_ODDS")
    max_odds: float = Field(3.50, alias="MAX_ODDS")

    # Signal limits
    max_signals_per_scan: int = Field(3, alias="MAX_SIGNALS_PER_SCAN")
    max_signals_per_day: int = Field(10, alias="MAX_SIGNALS_PER_DAY")
    one_signal_per_event: bool = Field(True, alias="ONE_SIGNAL_PER_EVENT")

    # Bankroll / risk engine
    bankroll: float = Field(1000.0, alias="BANKROLL")
    # Backward compatible: old setting can still exist in Railway.
    stake_percent: float = Field(1.0, alias="STAKE_PERCENT")
    base_stake_percent: float = Field(1.0, alias="BASE_STAKE_PERCENT")
    max_stake_percent: float = Field(2.0, alias="MAX_STAKE_PERCENT")
    min_stake_percent: float = Field(0.20, alias="MIN_STAKE_PERCENT")
    max_consecutive_losses: int = Field(3, alias="MAX_CONSECUTIVE_LOSSES")
    daily_loss_limit_percent: float = Field(10.0, alias="DAILY_LOSS_LIMIT_PERCENT")

    # Optional engines
    enable_live_engine: bool = Field(False, alias="ENABLE_LIVE_ENGINE")
    enable_synthetic_half_totals: bool = Field(False, alias="ENABLE_SYNTHETIC_HALF_TOTALS")

    # Reports
    daily_report_hour_uz: int = Field(23, alias="DAILY_REPORT_HOUR_UZ")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
