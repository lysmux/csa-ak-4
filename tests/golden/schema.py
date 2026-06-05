from app.config import Config
from app.utils import YamlBaseModel
from pydantic import BaseModel


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
    max_trace: int = 60
    config: Config

    snapshot: GoldenSnapshot | None = None
