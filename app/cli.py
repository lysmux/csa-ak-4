import pickle
import time
from pathlib import Path

import click

from app.config import Config
from app.isa.flags import Flags
from app.isa.instruction import Instruction
from app.simulation.control_unit import ControlUnit
from app.simulation.data_path import DataPath
from app.simulation.io import CharInput, CharOutput, Device, IntOutput
from app.simulation.memory import Memory
from app.simulation.stack import Stack
from app.translator.analyzer import Analyzer
from app.translator.codegen import CodeGen, InputDevice, OutputDevice
from app.translator.lexer import Lexer
from app.translator.parser import Parser


def _format_flags(flags: Flags) -> str:
    return "".join(
        ch if bit in flags else "-" for ch, bit in (("N", Flags.N), ("Z", Flags.Z), ("V", Flags.V), ("C", Flags.C))
    )


def _trace_line(cu: ControlUnit) -> str:
    s = cu.snapshot
    instr = s.instruction
    return (
        f"tick={s.tick:6d}  "
        f"st={s.state.name:<9} "
        f"pc=0x{s.pc:04x}  "
        f"ir={instr.opcode.name:<8} 0x{instr.operand:08x}  "
        f"flags={_format_flags(s.flags)}  "
        f"tos=0x{s.tos & 0xFFFFFFFF:08x}  "
        f"nos=0x{s.nos & 0xFFFFFFFF:08x}  "
        f"rtos=0x{s.r_tos & 0xFFFFFFFF:08x}"
    )


@click.group()
def cli() -> None:
    pass


def _output_devices_for_codegen(config: Config) -> dict[str, OutputDevice]:
    return {name: OutputDevice(address=cfg.address, kind=cfg.kind) for name, cfg in config.io.outputs.items()}


def _input_devices_for_codegen(config: Config) -> dict[str, InputDevice]:
    return {name: InputDevice(address=cfg.address, vector=cfg.vector) for name, cfg in config.io.inputs.items()}


def _build_io_map(config: Config) -> tuple[dict[int, Device], dict[int, Device]]:
    """Returns (io_map, address->device map of *output* devices for printing buffers)."""
    io_map: dict[int, Device] = {}
    outputs_by_addr: dict[int, Device] = {}
    addr_kind: dict[int, str] = {}

    for name, cfg in config.io.outputs.items():
        existing_kind = addr_kind.get(cfg.address)
        if existing_kind is not None and existing_kind != cfg.kind:
            msg = (
                f"output address {cfg.address:#x} used with conflicting kinds "
                f"({existing_kind!r} and {cfg.kind!r}); label {name!r}"
            )
            raise ValueError(msg)
        addr_kind[cfg.address] = cfg.kind

        if cfg.address in outputs_by_addr:
            io_map[cfg.address] = outputs_by_addr[cfg.address]
            continue

        dev: Device = CharOutput() if cfg.kind == "char" else IntOutput()
        outputs_by_addr[cfg.address] = dev
        io_map[cfg.address] = dev

    inputs_by_addr: dict[int, CharInput] = {}
    vectors_seen: dict[int, int] = {}  # vector → address
    for name, cfg in config.io.inputs.items():
        prev_addr = vectors_seen.get(cfg.vector)
        if prev_addr is not None and prev_addr != cfg.address:
            msg = (
                f"vector {cfg.vector} is assigned to multiple input devices "
                f"(addresses {prev_addr:#x} and {cfg.address:#x}); "
                f"label {name!r}"
            )
            raise ValueError(msg)
        vectors_seen[cfg.vector] = cfg.address

        existing = inputs_by_addr.get(cfg.address)
        if existing is not None:
            io_map[cfg.address] = existing
            continue

        dev = CharInput(schedule=cfg.schedule, vector=cfg.vector)
        inputs_by_addr[cfg.address] = dev
        io_map[cfg.address] = dev

    return io_map, outputs_by_addr


@cli.command()
@click.argument(
    "source",
    type=click.Path(
        exists=True,
        resolve_path=True,
        dir_okay=False,
        readable=True,
        path_type=Path,
    ),
)
@click.argument(
    "target",
    type=click.Path(
        resolve_path=True,
        dir_okay=False,
        writable=True,
        path_type=Path,
    ),
)
@click.option(
    "-c",
    "--config",
    "config_path",
    type=click.Path(
        exists=True,
        resolve_path=True,
        dir_okay=False,
        readable=True,
        path_type=Path,
    ),
)
def compile(source: Path, target: Path, config_path: Path | None) -> None:
    config = Config.from_yaml(config_path) if config_path else Config()
    output_devices = _output_devices_for_codegen(config)
    input_devices = _input_devices_for_codegen(config)

    tokens = Lexer(source.read_text(encoding="utf-8")).tokenize()
    ast = Parser(tokens).parse()
    Analyzer(
        output_devices=set(output_devices),
        input_devices=set(input_devices),
    ).analyze(ast)
    program = CodeGen(
        output_devices=output_devices,
        input_devices=input_devices,
    ).generate(ast)

    with target.open("wb") as f:
        pickle.dump(program.instructions, f)
        pickle.dump(program.data, f)
        pickle.dump(program.interrupt_handlers, f)

    with target.with_suffix(".dbg").open("w", encoding="utf-8") as f:
        f.write("Instructions:\n")
        for addr, instr in enumerate(program.instructions):
            decoded = Instruction.from_binary(instr)
            f.write(f"{addr:#04x} - {instr:#08x} - {decoded.opcode.name} {decoded.operand:#08x}\n")

        f.write("\nData:\n")
        for addr, cell in enumerate(program.data):
            f.write(f"{addr:#04x} - {cell & 0xFFFFFFFF:#08x} - .word {cell:#x}\n")

        f.write("\nInterrupt handlers:\n")
        for vector, addr in program.interrupt_handlers.items():
            f.write(f"  vector {vector} -> {addr:#06x}\n")

    click.echo(f"Compiled {source} to {target.name}")


@cli.command()
@click.argument(
    "file",
    type=click.Path(
        exists=True,
        resolve_path=True,
        dir_okay=False,
        readable=True,
        path_type=Path,
    ),
)
@click.option(
    "-c",
    "--config",
    "config_path",
    type=click.Path(
        exists=True,
        resolve_path=True,
        dir_okay=False,
        readable=True,
        path_type=Path,
    ),
)
@click.option(
    "--trace",
    is_flag=True,
    default=False,
    help="Print CPU state on every tick (PC, IR, FLAGS, TOS/NOS, RTOS).",
)
def run(file: Path, config_path: Path | None, trace: bool) -> None:
    with file.open("rb") as f:
        instructions = pickle.load(f)
        data = pickle.load(f)
        interrupt_handlers: dict[int, int] = pickle.load(f)

    config = Config.from_yaml(config_path) if config_path else Config()

    instr_memory = Memory(config.memory_size.instruction)
    instr_memory.fill(instructions)

    data_memory = Memory(config.memory_size.data)
    data_memory.fill(data)

    return_stack = Stack(config.stack_size.ret)
    data_stack = Stack(config.stack_size.data)

    io_map, outputs_by_addr = _build_io_map(config)

    data_path = DataPath(
        memory=data_memory,
        stack=data_stack,
        io_map=io_map,
    )

    cu = ControlUnit(
        data_path=data_path,
        instr_memory=instr_memory,
        return_stack=return_stack,
        vector_table=dict(interrupt_handlers),
    )

    on_tick = None
    if trace:

        def on_tick(unit: ControlUnit) -> None:
            click.echo(_trace_line(unit))

    wall_start = time.perf_counter()
    cu.run(limit=config.limit, on_tick=on_tick)
    wall_ms = (time.perf_counter() - wall_start) * 1000.0

    seen: set[int] = set()
    for name, cfg in config.io.outputs.items():
        if cfg.address in seen:
            continue
        seen.add(cfg.address)
        dev = outputs_by_addr.get(cfg.address)
        if dev is not None and hasattr(dev, "string"):
            click.echo(f"{name}: {dev.string}")

    click.echo(f"ticks: {cu.snapshot.tick}")
    click.echo(f"time:  {wall_ms:.3f} ms")


if __name__ == "__main__":
    cli()
