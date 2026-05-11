from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class MemorySize(BaseModel):
    instruction: int = 1000
    data: int = 1000


class StackSize(BaseModel):
    ret: int = 1000
    data: int = 1000


class OutputDeviceConfig(BaseModel):
    kind: Literal["char", "int"] = "char"
    address: int


class InputDeviceConfig(BaseModel):
    address: int
    vector: int
    schedule: list[tuple[int, str]] = Field(default_factory=list)


class IOConfig(BaseModel):
    outputs: dict[str, OutputDeviceConfig] = Field(default_factory=dict)
    inputs: dict[str, InputDeviceConfig] = Field(default_factory=dict)


class Config(BaseModel):
    limit: int = 1000
    memory_size: MemorySize = Field(default_factory=MemorySize)
    stack_size: StackSize = Field(default_factory=StackSize)
    io: IOConfig = Field(default_factory=IOConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        raw = yaml.safe_load(path.read_text())
        return cls.model_validate(raw)
