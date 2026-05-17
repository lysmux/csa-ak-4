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
    default: bool = False


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
    outputs: dict[str, OutputDeviceConfig] = Field(default_factory=dict)
    inputs: dict[str, InputDeviceConfig] = Field(default_factory=dict)

    @property
    def default_output_name(self) -> str | None:
        return next((name for name, cfg in self.outputs.items() if cfg.default), None)

    @model_validator(mode="after")
    def validate_no_address_collision(self) -> "IOConfig":
        default_output_names = [name for name, cfg in self.outputs.items() if cfg.default]
        if len(default_output_names) > 1:
            msg = f"only one output device can be default, got {default_output_names}"
            raise ValueError(msg)

        used: dict[int, str] = {}
        for name, cfg in self.outputs.items():
            if cfg.address in used:
                msg = f"output {name!r} address {cfg.address:#x} collides with {used[cfg.address]!r}"
                raise ValueError(msg)
            used[cfg.address] = f"output {name!r}"

        for name, cfg in self.inputs.items():
            if cfg.address in used:
                msg = f"input {name!r} address {cfg.address:#x} collides with {used[cfg.address]!r}"
                raise ValueError(msg)
            used[cfg.address] = f"input {name!r}"
        return self


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
