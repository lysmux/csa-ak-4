from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class MemorySize(BaseModel):
    instruction: int = Field(default=1000, gt=0)
    data: int = Field(default=1000, gt=0)


class StackSize(BaseModel):
    ret: int = Field(default=1000, gt=0)
    data: int = Field(default=1000, gt=0)


class OutputDeviceConfig(BaseModel):
    kind: Literal["char", "int"] = "char"
    address: int


class InputDeviceConfig(BaseModel):
    address: int
    vector: int = Field(ge=0, le=7)
    schedule: list[tuple[int, str]] = Field(default_factory=list)

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, schedule: list[tuple[int, str]]) -> list[tuple[int, str]]:
        for tick, _ in schedule:
            if tick < 1:
                msg = f"interrupt tick must be >= 1, got {tick}"
                raise ValueError(msg)
        ticks = [t for t, _ in schedule]
        duplicates = {t for t in ticks if ticks.count(t) > 1}
        if duplicates:
            msg = f"duplicate tick numbers in schedule: {sorted(duplicates)}"
            raise ValueError(msg)
        return schedule


class IOConfig(BaseModel):
    outputs: dict[str, OutputDeviceConfig] = Field(default_factory=dict)
    inputs: dict[str, InputDeviceConfig] = Field(default_factory=dict)


class Config(BaseModel):
    limit: int = Field(default=1000, gt=0)
    memory_size: MemorySize = Field(default_factory=MemorySize)
    stack_size: StackSize = Field(default_factory=StackSize)
    io: IOConfig = Field(default_factory=IOConfig)

    @model_validator(mode="after")
    def validate_schedule_within_limit(self) -> "Config":
        for name, cfg in self.io.inputs.items():
            for tick, _ in cfg.schedule:
                if tick > self.limit:
                    msg = f"input {name!r}: tick {tick} exceeds simulation limit {self.limit}"
                    raise ValueError(msg)
        return self

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        raw = yaml.safe_load(path.read_text())
        return cls.model_validate(raw)
