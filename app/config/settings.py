from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    telegram_bot_token: str = Field(
        "",
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "BOT_TOKEN"),
    )
    telegram_chat_id: str = Field(
        "",
        validation_alias=AliasChoices("TELEGRAM_CHAT_ID", "GROUP_ID", "CHAT_ID"),
    )
    bot_enabled: bool = Field(True, validation_alias=AliasChoices("BOT_ENABLED", "TELEGRAM_ENABLED"))

    odds_api_key: str = Field("", alias="ODDS_API_KEY")
    api_sports_key: str = Field("", alias="API_SPORTS_KEY")

    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")

    db_path: str = Field("/app/storage/signals.db", alias="DB_PATH")

    scan_interval_seconds: int = Field(1800, alias="SCAN_INTERVAL_SECONDS")
    result_interval_seconds: int = Field(900, alias="RESULT_INTERVAL_SECONDS")
    live_scan_interval_seconds: int = Field(180, alias="LIVE_SCAN_INTERVAL_SECONDS")
    daily_report_hour: int = Field(9, alias="DAILY_REPORT_HOUR")

    odds_regions: str = Field("eu", alias="ODDS_REGIONS")
    odds_markets: str = Field("h2h,spreads", alias="ODDS_MARKETS")
    enabled_markets: str = Field("h2h,spreads", alias="ENABLED_MARKETS")
    sport_keys: str = Field(
        "basketball_nba,basketball_wnba,soccer_epl,soccer_spain_la_liga,soccer_germany_bundesliga",
        alias="SPORT_KEYS",
    )

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

    timezone_offset_hours: int = Field(5, alias="TIMEZONE_OFFSET_HOURS")
    max_hours_before_match: int = Field(24, alias="MAX_HOURS_BEFORE_MATCH")

    min_confidence: int = Field(75, alias="MIN_CONFIDENCE")
    min_ai_validator_score: int = Field(65, alias="MIN_AI_VALIDATOR_SCORE")
    min_value_edge: float = Field(
        1.0,
        validation_alias=AliasChoices("MIN_VALUE_EDGE", "MIN_VALUE_EDG"),
    )
    max_anomaly_score: int = Field(40, alias="MAX_ANOMALY_SCORE")
    min_odds: float = Field(1.30, alias="MIN_ODDS")
    max_odds: float = Field(3.50, alias="MAX_ODDS")

    bankroll: float = Field(1000.0, alias="BANKROLL")
    stake_percent: float = Field(1.0, alias="STAKE_PERCENT")
    base_stake_percent: float = Field(1.0, alias="BASE_STAKE_PERCENT")
    max_stake_percent: float = Field(2.0, alias="MAX_STAKE_PERCENT")
    max_consecutive_losses: int = Field(3, alias="MAX_CONSECUTIVE_LOSSES")
    daily_loss_limit_percent: float = Field(10.0, alias="DAILY_LOSS_LIMIT_PERCENT")

    max_signals_per_scan: int = Field(3, alias="MAX_SIGNALS_PER_SCAN")
    max_signals_per_day: int = Field(10, alias="MAX_SIGNALS_PER_DAY")
    max_signals_per_event: int = Field(1, alias="MAX_SIGNALS_PER_EVENT")

    ai_enabled: bool = Field(True, alias="AI_ENABLED")
    enable_ai_validator: bool = Field(True, alias="ENABLE_AI_VALIDATOR")
    enable_live_engine: bool = Field(False, alias="ENABLE_LIVE_ENGINE")
    enable_synthetic_half_totals: bool = Field(False, alias="ENABLE_SYNTHETIC_HALF_TOTALS")

    express_mode: bool = Field(False, alias="EXPRESS_MODE")
    express_min_legs: int = Field(2, alias="EXPRESS_MIN_LEGS")
    express_max_legs: int = Field(2, alias="EXPRESS_MAX_LEGS")
    express_min_confidence: int = Field(82, alias="EXPRESS_MIN_CONFIDENCE")
    express_min_ai_score: int = Field(75, alias="EXPRESS_MIN_AI_SCORE")
    express_min_value_edge: float = Field(1.5, alias="EXPRESS_MIN_VALUE_EDGE")
    express_max_anomaly_score: int = Field(25, alias="EXPRESS_MAX_ANOMALY_SCORE")
    express_min_odds: float = Field(1.35, alias="EXPRESS_MIN_ODDS")
    express_max_odds: float = Field(1.90, alias="EXPRESS_MAX_ODDS")
    express_min_total_odds: float = Field(2.10, alias="EXPRESS_MIN_TOTAL_ODDS")
    express_max_total_odds: float = Field(3.80, alias="EXPRESS_MAX_TOTAL_ODDS")
    express_max_per_scan: int = Field(1, alias="EXPRESS_MAX_PER_SCAN")
    express_stake_percent: float = Field(0.5, alias="EXPRESS_STAKE_PERCENT")
    express_allow_same_sport: bool = Field(True, alias="EXPRESS_ALLOW_SAME_SPORT")

    @property
    def bot_token(self) -> str:
        return self.telegram_bot_token

    @property
    def chat_id(self) -> str:
        return self.telegram_chat_id

    @property
    def group_id(self) -> str:
        return self.telegram_chat_id


settings = Settings()
