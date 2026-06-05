from __future__ import annotations

from pathlib import Path

import click

from app import binary
from app.cli.errors import error_wrap
from app.cli.helpers import Output, ReadableFile, WritableFile, load_config
from app.config import Config
from app.isa.consts import INSTR_BYTES, WORD_BYTES
from app.isa.instruction import Instruction
from app.translator.analyzer import Analyzer
from app.translator.codegen import CodeGen, CompiledProgram
from app.translator.lexer import Lexer
from app.translator.parser import Parser


def compile_source(source: Path, config: Config) -> CompiledProgram:
    tokens = Lexer(source.read_text(encoding="utf-8")).tokenize()
    ast = Parser(tokens).parse()
    Analyzer(
        output_devices=set(config.io.outputs),
        input_devices=set(config.io.inputs),
    ).analyze(ast)
    return CodeGen(
        output_devices=config.io.outputs,
        input_devices=config.io.inputs,
    ).generate(ast)


def _ascii_hint(value: int) -> str:
    ch = value & 0xFF
    return f"  ; '{chr(ch)}'" if 0x20 <= ch <= 0x7E else ""


def write_debug(program: CompiledProgram, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("; Instructions\n")
        for index, instr in enumerate(program.instructions):
            decoded = Instruction.from_binary(instr)
            addr = index * INSTR_BYTES
            f.write(f"  0x{addr:04X}  0x{instr:010X}  {decoded.opcode.name:<10}  0x{decoded.operand:08X}\n")

        f.write("\n; Data\n")
        for index, cell in enumerate(program.data):
            word = cell & 0xFFFFFFFF
            addr = index * WORD_BYTES
            f.write(f"  0x{addr:04X}  0x{word:08X}{_ascii_hint(word)}\n")

        f.write("\n; Interrupt Handlers\n")
        if program.interrupt_handlers:
            for vector, addr in program.interrupt_handlers.items():
                f.write(f"  vector {vector}  ->  0x{addr:04X}\n")
        else:
            f.write("  (none)\n")


@click.command()
@click.argument("source", type=ReadableFile)
@click.argument("target", type=WritableFile)
@click.option("-c", "--config", "config_path", type=ReadableFile)
@click.option("--debug", "debug_path", type=WritableFile)
@error_wrap
def compile(
    source: Path,
    target: Path,
    config_path: Path | None,
    debug_path: Path | None,
) -> None:
    config = load_config(config_path)
    program = compile_source(source, config)

    with target.open("wb") as f:
        binary.write(f, program)

    debug_path = debug_path or target.with_suffix(".dbg")
    write_debug(program, debug_path)

    out = Output()
    out.section("Compiled")
    out.line(f"{click.style(str(source), fg='cyan')} -> {click.style(target.name, bold=True)}")
    out.section("Debug")
    out.line(click.style(debug_path.name, fg="yellow"))
