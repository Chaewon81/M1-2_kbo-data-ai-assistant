from __future__ import annotations

from datetime import date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DataRecord(BaseModel):
    id: str = ""
    date: date
    season: int = Field(ge=1900, le=2100)
    team: str = Field(min_length=1, max_length=30)
    opponent: str = Field(min_length=1, max_length=30)
    home_away: Literal["home", "away"]
    runs_for: int | None = Field(default=None, ge=0)
    runs_against: int | None = Field(default=None, ge=0)
    result: Literal["W", "L", "D"] | None = None
    run_diff: int | None = None
    value: int | None = None
    status: Literal["completed", "scheduled", "cancelled", "postponed"] = "completed"
    stadium: str = ""
    game_id: str = Field(min_length=1, max_length=80)
    memo: str = Field(default="", max_length=500)
    source_url: str = ""
    is_manual: bool = False

    @model_validator(mode="after")
    def validate_completed_values(self) -> "DataRecord":
        if self.status == "completed" and any(value is None for value in (self.runs_for, self.runs_against, self.result, self.run_diff, self.value)):
            raise ValueError("completed 경기에는 점수, 결과, 득실차가 필요합니다.")
        return self


class DataCreate(DataRecord):
    pass


class DataUpdate(BaseModel):
    memo: str | None = Field(default=None, max_length=500)
    status: Literal["completed", "scheduled", "cancelled", "postponed"] | None = None
    runs_for: int | None = Field(default=None, ge=0)
    runs_against: int | None = Field(default=None, ge=0)
    is_manual: bool | None = None


class DataListResponse(BaseModel):
    count: int
    items: list[DataRecord]


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=10000)
    created_at: datetime | None = None


class ConversationCreate(BaseModel):
    title: str = Field(default="새 대화", min_length=1, max_length=120)
    messages: list[ConversationMessage] = Field(default_factory=list, max_length=100)
    summary: dict | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationRecord(ConversationSummary):
    messages: list[ConversationMessage]
    summary: dict | None = None


class ConversationListResponse(BaseModel):
    count: int
    items: list[ConversationSummary]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    season: int | None = Field(default=None, ge=1900, le=2100)
    team: str | None = Field(default=None, min_length=1, max_length=30)
    last_n: int | None = Field(default=None, ge=1, le=100)


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    summary: dict
    model: str


class PredictionRequest(BaseModel):
    team_a: str = Field(min_length=1, max_length=30)
    team_b: str = Field(min_length=1, max_length=30)
    season: int | None = Field(default=None, ge=1900, le=2100)
    last_n: int = Field(default=10, ge=1, le=100)
    pitcher_a: str | None = Field(default=None, max_length=80)
    pitcher_a_id: str | None = Field(default=None, max_length=50)
    pitcher_b: str | None = Field(default=None, max_length=80)
    pitcher_b_id: str | None = Field(default=None, max_length=50)


class PredictionResponse(BaseModel):
    team_a: str
    team_b: str
    team_a_probability: float
    team_b_probability: float
    method: str
    season: int | None
    last_n: int
    pitchers: dict[str, str | None]
    limitations: list[str]
    pitcher_stats_applied: bool = False
    pitcher_stats_as_of: dict[str, str | None] = Field(default_factory=dict)
    pitcher_data_count: dict[str, int] = Field(default_factory=dict)


class PitcherStat(BaseModel):
    season: int = Field(ge=1900, le=2100)
    team_code: str = Field(min_length=1, max_length=20)
    team: str = Field(min_length=1, max_length=30)
    player_id: str = Field(min_length=1, max_length=50)
    player: str = Field(min_length=1, max_length=80)
    games_appeared: int = Field(ge=0)
    innings: float = Field(ge=0)
    earned_runs: int = Field(ge=0)
    era: float = Field(ge=0)
    whip: float = Field(ge=0)
    strikeouts: int = Field(ge=0)
    source_url: str = ""
    as_of: str = ""
    updated_at: str = ""


class PitcherListResponse(BaseModel):
    count: int
    items: list[PitcherStat]
    invalid_count: int = 0
    duplicate_count: int = 0
