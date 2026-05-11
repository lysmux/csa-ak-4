from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class MemorySize(BaseModel):
    instruction: int = 1000
    data: int = 1000


class StackSize(BaseModel):
    ret: int = 1000
    data: int = 1000


class CharOutputConfig(BaseModel):
    address: int = 0x222


class CharInputConfig(BaseModel):
    address: int = 0x223
    vector: int = 0
    schedule: list[tuple[int, str]] = Field(default_factory=list)


class IOConfig(BaseModel):
    char_output: CharOutputConfig = Field(default_factory=CharOutputConfig)
    char_input: CharInputConfig | None = None


class Config(BaseModel):
    limit: int = 1000
    memory_size: MemorySize = Field(default_factory=MemorySize)
    stack_size: StackSize = Field(default_factory=StackSize)
    io: IOConfig = Field(default_factory=IOConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        raw = yaml.safe_load(path.read_text())
        return cls.model_validate(raw)
