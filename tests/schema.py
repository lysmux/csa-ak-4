from app.config import Config
from app.utils import YamlBaseModel
from pydantic import BaseModel, Field


class GoldenTrace(BaseModel):
    total_ticks: int
    lines: str


class GoldenSnapshot(YamlBaseModel):
    output: dict[str, str]
    ast: str
    machine_code: str
    trace: GoldenTrace


class GoldenInput(YamlBaseModel):
    name: str
    source: str
    trace_window: int = Field(default=100, gt=0)
    config: Config

    snapshot: GoldenSnapshot | None = None
