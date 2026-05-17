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
    format: Literal["string", "raw"] = "string"
    address: int


class InputDeviceConfig(BaseModel):
    address: int
    vector: int = Field(ge=0, le=7)
    schedule: list[tuple[int, int | str]] = Field(default_factory=list)

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, schedule: list[tuple[int, int | str]]) -> list[tuple[int, int]]:
        normalized: list[tuple[int, int]] = []
        for tick, value in schedule:
            if tick < 1:
                msg = f"interrupt tick must be >= 1, got {tick}"
                raise ValueError(msg)
            if isinstance(value, str):
                if len(value) != 1:
                    msg = f"schedule value must be a single character, got {value!r}"
                    raise ValueError(msg)
                normalized.append((tick, ord(value)))
            else:
                normalized.append((tick, value))
        ticks = [t for t, _ in normalized]
        duplicates = {t for t in ticks if ticks.count(t) > 1}
        if duplicates:
            msg = f"duplicate tick numbers in schedule: {sorted(duplicates)}"
            raise ValueError(msg)
        return normalized


class IOConfig(BaseModel):
    output: OutputDeviceConfig
    inputs: dict[str, InputDeviceConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_no_address_collision(self) -> "IOConfig":
        used: dict[int, str] = {self.output.address: "output"}
        for name, cfg in self.inputs.items():
            if cfg.address in used:
                msg = (
                    f"input {name!r} address {cfg.address:#x} collides with "
                    f"{used[cfg.address]!r}"
                )
                raise ValueError(msg)
            used[cfg.address] = f"input {name!r}"
        return self


class Config(BaseModel):
    limit: int = Field(default=1000, gt=0)
    memory_size: MemorySize = Field(default_factory=MemorySize)
    stack_size: StackSize = Field(default_factory=StackSize)
    io: IOConfig

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
