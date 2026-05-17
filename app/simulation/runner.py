from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.config import Config, IOConfig
from app.simulation.control_unit import ControlUnit
from app.simulation.data_path import DataPath
from app.simulation.io import Device, Input, Output
from app.simulation.memory import Memory
from app.simulation.stack import Stack
from app.translator.codegen import CompiledProgram


@dataclass
class SimulationResult:
    ticks: int
    wall_ms: float
    output: str


@dataclass(frozen=True)
class IODevices:
    output: Output
    io_map: dict[int, Device]


def _build_input_devices(config: IOConfig) -> dict[int, Input]:
    return {
        cfg.address: Input(schedule=cfg.schedule, vector=cfg.vector)
        for cfg in config.inputs.values()
    }


def _build_io_devices(config: IOConfig) -> IODevices:
    output = Output(format=config.output.format)
    io_map: dict[int, Device] = {
        config.output.address: output,
        **_build_input_devices(config),
    }
    return IODevices(output=output, io_map=io_map)


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
    cu.run(limit=config.limit, on_tick=on_tick)
    wall_ms = (time.perf_counter() - wall_start) * 1000.0

    return SimulationResult(
        ticks=cu.snapshot.tick,
        wall_ms=wall_ms,
        output=io_devices.output.as_string(),
    )
