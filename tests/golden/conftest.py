"""Shared helpers for golden tests."""
from __future__ import annotations

import io
from pathlib import Path

import yaml
from app.config import Config
from app.isa.instruction import Instruction
from app.simulation.control_unit import ControlUnit
from app.simulation.data_path import DataPath
from app.simulation.io import CharInput, CharOutput, IntOutput
from app.simulation.memory import Memory
from app.simulation.stack import Stack
from app.translator.analyzer import Analyzer
from app.translator.codegen import CodeGen, CompiledProgram, InputDevice, OutputDevice
from app.translator.lexer import Lexer
from app.translator.nodes import print_ast
from app.translator.parser import Parser

GOLDEN_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# PyYAML: literal block scalar representer  (produces  |  or  |-  style)
# ---------------------------------------------------------------------------

class _Lit(str):
    """Marker class: dump this string as a YAML literal block scalar."""


def _lit(s: str) -> _Lit:
    return _Lit(s)


yaml.add_representer(
    _Lit,
    lambda dumper, data: dumper.represent_scalar(
        "tag:yaml.org,2002:str", data, style="|"
    ),
)


# ---------------------------------------------------------------------------
# pytest option
# ---------------------------------------------------------------------------

def pytest_addoption(parser: object) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Regenerate *.yaml golden files instead of comparing",
    )


# ---------------------------------------------------------------------------
# Compilation / simulation helpers
# ---------------------------------------------------------------------------

def compile_source(
    src: str,
    output_devices: dict[str, OutputDevice],
    input_devices: dict[str, InputDevice] | None = None,
) -> tuple[object, CompiledProgram]:
    tokens = Lexer(src).tokenize()
    ast = Parser(tokens).parse()
    Analyzer(
        output_devices=set(output_devices),
        input_devices=set(input_devices or {}),
    ).analyze(ast)
    program = CodeGen(
        output_devices=output_devices,
        input_devices=input_devices or {},
    ).generate(ast)
    return ast, program


def get_ast_dump(ast: object) -> str:
    buf = io.StringIO()
    print_ast(ast, file=buf)
    return buf.getvalue()


def build_dbg(program: CompiledProgram) -> str:
    lines = ["Instructions:"]
    for addr, word in enumerate(program.instructions):
        instr = Instruction.from_binary(word)
        lines.append(
            f"  0x{addr:04x} - {word:#010x} - {instr.opcode.name} {instr.operand:#010x}"
        )
    lines.append("\nData:")
    for addr, cell in enumerate(program.data):
        lines.append(f"  0x{addr:04x} - {cell & 0xFFFFFFFF:#010x} - .word {cell:#010x}")
    lines.append("\nInterrupt handlers:")
    for vec, a in program.interrupt_handlers.items():
        lines.append(f"  vector {vec} -> {a:#06x}")
    return "\n".join(lines)


def run_golden(
    program: CompiledProgram,
    config: Config,
    max_trace: int = 60,
) -> tuple[ControlUnit, dict[str, CharOutput], dict[str, IntOutput], list[str]]:
    instr_mem = Memory(config.memory_size.instruction)
    instr_mem.fill(program.instructions)
    data_mem = Memory(config.memory_size.data)
    data_mem.fill(program.data)
    rs = Stack(config.stack_size.ret)
    ds = Stack(config.stack_size.data)

    io_map: dict[int, object] = {}
    char_devs: dict[str, CharOutput] = {}
    int_devs: dict[str, IntOutput] = {}
    seen_addrs: set[int] = set()

    for name, cfg in config.io.outputs.items():
        if cfg.address not in seen_addrs:
            dev: CharOutput | IntOutput = (
                CharOutput() if cfg.kind == "char" else IntOutput()
            )
            io_map[cfg.address] = dev
            seen_addrs.add(cfg.address)
        dev = io_map[cfg.address]
        (char_devs if cfg.kind == "char" else int_devs)[name] = dev  # type: ignore[index]

    for name, cfg in config.io.inputs.items():
        if cfg.address not in io_map:
            io_map[cfg.address] = CharInput(
                schedule=list(cfg.schedule), vector=cfg.vector
            )

    from app.cli import _trace_line

    trace: list[str] = []

    def on_tick(cu: ControlUnit) -> None:
        if len(trace) < max_trace:
            trace.append(_trace_line(cu))

    dp = DataPath(memory=data_mem, stack=ds, io_map=io_map)
    cu = ControlUnit(
        data_path=dp,
        instr_memory=instr_mem,
        return_stack=rs,
        vector_table=dict(program.interrupt_handlers),
    )
    cu.run(limit=config.limit, on_tick=on_tick)
    return cu, char_devs, int_devs, trace


# ---------------------------------------------------------------------------
# Snapshot assembly
# ---------------------------------------------------------------------------

def build_snapshot(
    name: str,
    source: str,
    config_dict: dict,
    max_trace: int,
    ast_dump: str,
    dbg: str,
    trace_lines: list[str],
    total_ticks: int,
    char_out: str,
    int_out: list[int],
) -> dict:
    return {
        "name": name,
        "source": _lit(source),
        "config": config_dict,
        "max_trace": max_trace,
        "expected_output": {
            "char_output": _lit(char_out) if "\n" in char_out or len(char_out) > 40 else char_out,
            "int_output": int_out,
        },
        "ast": _lit(ast_dump),
        "machine_code": _lit(dbg),
        "trace": {
            "total_ticks": total_ticks,
            "lines": _lit("\n".join(trace_lines)),
        },
    }


def dump_snapshot(snap: dict) -> str:
    return yaml.dump(
        snap,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=120,
    )


def run_and_snapshot(name: str, yaml_path: Path, max_trace: int) -> tuple[dict, str]:
    """Load source + config from yaml_path, compile, run, return (snap_dict, snap_yaml)."""
    stored = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    source = stored["source"]
    config_dict = stored["config"]
    config = Config.model_validate(config_dict)

    out_devs = {
        n: OutputDevice(address=cfg.address, kind=cfg.kind)
        for n, cfg in config.io.outputs.items()
    }
    in_devs = {
        n: InputDevice(address=cfg.address, vector=cfg.vector)
        for n, cfg in config.io.inputs.items()
    }

    ast, prog = compile_source(source, out_devs, in_devs)
    cu, char_devs, int_devs, trace = run_golden(prog, config, max_trace=max_trace)

    char_out = "".join(d.string for d in char_devs.values())
    int_out: list[int] = []
    for d in int_devs.values():
        int_out.extend(d.buffer)

    snap = build_snapshot(
        name=name,
        source=source,
        config_dict=config_dict,
        max_trace=max_trace,
        ast_dump=get_ast_dump(ast),
        dbg=build_dbg(prog),
        trace_lines=trace,
        total_ticks=cu.snapshot.tick,
        char_out=char_out,
        int_out=int_out,
    )
    return snap, dump_snapshot(snap)
