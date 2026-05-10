from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class MemorySize(BaseModel):
    instruction: int = 1000
    data: int = 1000


class StackSize(BaseModel):
    ret: int = 1000
    data: int = 1000

class Config(BaseModel):
    limit: int = 1000
    memory_size: MemorySize = Field(default_factory=MemorySize)
    stack_size: StackSize = Field(default_factory=StackSize)

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        raw = yaml.safe_load(path.read_text())
        return cls.model_validate(raw)
