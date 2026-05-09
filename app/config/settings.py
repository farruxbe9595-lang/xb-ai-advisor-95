from pydantic import Field
from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    bot_token: str = Field('', alias='BOT_TOKEN'); group_id: str = Field('', alias='GROUP_ID')
    odds_api_key: str = Field('', alias='ODDS_API_KEY'); api_sports_key: str = Field('', alias='API_SPORTS_KEY')
    openai_api_key: str = Field('', alias='OPENAI_API_KEY'); openai_model: str = Field('gpt-4o-mini', alias='OPENAI_MODEL')
    db_path: str = Field('storage/signals.db', alias='DB_PATH')
    scan_interval_seconds: int = Field(600, alias='SCAN_INTERVAL_SECONDS'); live_scan_interval_seconds: int = Field(180, alias='LIVE_SCAN_INTERVAL_SECONDS'); result_interval_seconds: int = Field(900, alias='RESULT_INTERVAL_SECONDS'); daily_report_hour: int = Field(9, alias='DAILY_REPORT_HOUR')
    odds_regions: str = Field('eu', alias='ODDS_REGIONS'); odds_markets: str = Field('h2h,totals,spreads', alias='ODDS_MARKETS'); sport_keys: str = Field('basketball_nba,basketball_euroleague,tennis_atp,tennis_wta', alias='SPORT_KEYS')
    api_sports_basketball_host: str = Field('v1.basketball.api-sports.io', alias='API_SPORTS_BASKETBALL_HOST'); api_sports_tennis_host: str = Field('v1.tennis.api-sports.io', alias='API_SPORTS_TENNIS_HOST')
    min_confidence: int = Field(78, alias='MIN_CONFIDENCE'); min_value_edge: float = Field(3.5, alias='MIN_VALUE_EDGE'); max_anomaly_score: int = Field(68, alias='MAX_ANOMALY_SCORE'); min_odds: float = Field(1.25, alias='MIN_ODDS'); max_odds: float = Field(2.30, alias='MAX_ODDS'); max_hours_before_match: int = Field(48, alias='MAX_HOURS_BEFORE_MATCH'); max_signals_per_event: int = Field(2, alias='MAX_SIGNALS_PER_EVENT'); min_ai_validator_score: int = Field(70, alias='MIN_AI_VALIDATOR_SCORE')
    bankroll: float = Field(500, alias='BANKROLL'); base_stake_percent: float = Field(1.0, alias='BASE_STAKE_PERCENT'); max_stake_percent: float = Field(2.0, alias='MAX_STAKE_PERCENT'); daily_loss_limit_percent: float = Field(5.0, alias='DAILY_LOSS_LIMIT_PERCENT'); max_consecutive_losses: int = Field(3, alias='MAX_CONSECUTIVE_LOSSES')
    enable_winner_market: bool = Field(True, alias='ENABLE_WINNER_MARKET'); enable_totals_market: bool = Field(True, alias='ENABLE_TOTALS_MARKET'); enable_spreads_market: bool = Field(True, alias='ENABLE_SPREADS_MARKET'); enable_synthetic_half_totals: bool = Field(True, alias='ENABLE_SYNTHETIC_HALF_TOTALS'); enable_live_engine: bool = Field(True, alias='ENABLE_LIVE_ENGINE'); enable_ai_validator: bool = Field(True, alias='ENABLE_AI_VALIDATOR')
    advisory_only: bool = Field(True, alias='ADVISORY_ONLY')
    class Config: env_file='.env'; populate_by_name=True
settings=Settings()
