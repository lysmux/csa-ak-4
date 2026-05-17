from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from app.config import Config, IOConfig
from app.isa.state import State
from app.simulation.control_unit import ControlUnit
from app.simulation.data_path import DataPath
from app.simulation.io import Device, Input, Output
from app.simulation.memory import Memory
from app.simulation.stack import Stack
from app.translator.codegen import CompiledProgram


class StopReason(StrEnum):
    HALT = "halt"
    TICK_LIMIT = "tick limit reached"


@dataclass
class SimulationResult:
    stop_reason: StopReason
    ticks: int
    wall_ms: float
    outputs: dict[str, str]


@dataclass(frozen=True)
class IODevices:
    outputs: dict[str, Output]
    io_map: dict[int, Device]


def _build_io_devices(config: IOConfig) -> IODevices:
    outputs: dict[str, Output] = {}
    io_map: dict[int, Device] = {}

    for name, cfg in config.outputs.items():
        output = Output(format=cfg.format)
        outputs[name] = output
        io_map[cfg.address] = output

    for cfg in config.inputs.values():
        io_map[cfg.address] = Input(schedule=cfg.schedule, vector=cfg.vector)

    return IODevices(outputs=outputs, io_map=io_map)


def run_control_unit(
    cu: ControlUnit,
    limit: int | None = None,
    on_tick: Callable[[ControlUnit], None] | None = None,
) -> StopReason:
    while cu.current_state is not State.HALT:
        if limit is not None and cu.current_tick >= limit:
            return StopReason.TICK_LIMIT
        cu.tick()
        if on_tick is not None:
            on_tick(cu)
    return StopReason.HALT


def simulate(
    program: CompiledProgram,
    config: Config,
    on_tick: Callable[[ControlUnit], None] | None = None,
) -> SimulationResult:
    instr_memory = Memory(config.memory_size.instruction)
    instr_memory.fill(program.instructions)

    data_memory = Memory(config.memory_size.data)
    data_memory.fill(program.data)

    io_devices = _build_io_devices(config.io)

    data_path = DataPath(
        memory=data_memory,
        stack=Stack(config.stack_size.data),
        io_map=io_devices.io_map,
    )

    cu = ControlUnit(
        data_path=data_path,
        instr_memory=instr_memory,
        return_stack=Stack(config.stack_size.ret),
        vector_table=program.interrupt_handlers,
    )

    wall_start = time.perf_counter()
    stop_reason = run_control_unit(cu, limit=config.limit, on_tick=on_tick)
    wall_ms = (time.perf_counter() - wall_start) * 1000.0

    output_strings = {name: output.as_string() for name, output in io_devices.outputs.items()}

    return SimulationResult(
        ticks=cu.snapshot.tick,
        stop_reason=stop_reason,
        wall_ms=wall_ms,
        outputs=output_strings,
    )
