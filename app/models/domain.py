from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
@dataclass(slots=True)
class Outcome: name:str; price:float; point:float|None=None
@dataclass(slots=True)
class Market: key:str; bookmaker:str; outcomes:list[Outcome]=field(default_factory=list); last_update:str|None=None; synthetic:bool=False
@dataclass(slots=True)
class Event: event_id:str; sport_key:str; sport_title:str; commence_time:datetime; home_team:str; away_team:str; markets:list[Market]=field(default_factory=list); raw:dict[str,Any]=field(default_factory=dict)
@dataclass(slots=True)
class Analysis:
    event_id:str; sport_key:str; sport_title:str; match_name:str; commence_time:datetime; market_key:str; market_label:str; pick:str; odds:float; line:float|None; implied_probability:float; model_probability:float; value_edge:float; confidence:int; anomaly_score:int; risk_level:str; reasons:list[str]; warnings:list[str]; bookmaker:str; data_quality:str; synthetic:bool=False; ai_validator_score:int=100; ai_validator_verdict:str='APPROVE'; stake_amount:float=0.0; stake_percent:float=0.0
