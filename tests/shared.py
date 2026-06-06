from app.isa.consts import WORD_BYTES
from app.isa.instruction import Instruction
from app.simulation.control_unit import ControlUnit, CUSnapshot
from app.simulation.data_path import DataPath
from app.simulation.memory import DataMemory, InstrMemory
from app.simulation.runner import run_control_unit
from app.simulation.stack import Stack


def read_word(memory: bytearray, index: int) -> int:
    """Decode the little-endian 32-bit word at the given word index of a byte image."""
    start = index * WORD_BYTES
    return int.from_bytes(memory[start : start + WORD_BYTES], "little")


def run_simulation(
    instructions: list[Instruction],
    initial_memory: dict[int, int],
) -> CUSnapshot:
    instr_memory = InstrMemory(512)
    instr_memory.fill([instr.to_binary() for instr in instructions])

    data_memory = DataMemory(256)
    for addr, value in initial_memory.items():
        data_memory.write(addr, value)

    data_path = DataPath(
        memory=data_memory,
        stack=Stack(50),
        io_map={},
    )

    cu = ControlUnit(
        data_path=data_path,
        instr_memory=instr_memory,
        return_stack=Stack(50),
    )

    run_control_unit(cu)

    return cu.snapshot
