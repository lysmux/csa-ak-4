from collections.abc import Callable

from app.isa.instruction import Instruction
from app.simulation.control_unit import ControlUnit, CUSnapshot
from app.simulation.data_path import DataPath
from app.simulation.memory import Memory
from app.simulation.runner import run_control_unit
from app.simulation.stack import Stack


def run_simulation(
    instructions: list[Instruction],
    initial_memory: dict[int, int],
) -> CUSnapshot:
    instr_memory = Memory(50)
    instr_memory.fill([instr.to_binary() for instr in instructions])

    return_stack = Stack(50)

    data_memory = Memory(50)
    for addr, value in initial_memory.items():
        data_memory._memory[addr] = value

    data_stack = Stack(50)
    data_path = DataPath(
        memory=data_memory,
        stack=data_stack,
        io_map={},
    )

    cu = ControlUnit(
        data_path=data_path,
        instr_memory=instr_memory,
        return_stack=return_stack,
    )

    run_control_unit(cu)

    return cu.snapshot


type SimulationTest = Callable[[list[Instruction], dict[int, int]], CUSnapshot]
