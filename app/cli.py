import pickle
from pathlib import Path
from pprint import pprint

import click

from app.config import Config
from app.isa.instruction import Instruction
from app.simulation.control_unit import ControlUnit
from app.simulation.data_path import DataPath
from app.simulation.io import CharInput, CharOutput, Device
from app.simulation.memory import Memory
from app.simulation.stack import Stack
from app.translator.analyzer import Analyzer
from app.translator.codegen import CodeGen
from app.translator.lexer import Lexer
from app.translator.parser import Parser


@click.group()
def cli():
    pass

@cli.command()
@click.argument('source', type=click.Path(
    exists=True,
    resolve_path=True,
    dir_okay=False,
    readable=True,
    path_type=Path
))
@click.argument('target', type=click.Path(
    resolve_path=True,
    dir_okay=False,
    writable=True,
    path_type=Path
))
@click.option(
    "-c", "--config", "config_path",
    type=click.Path(
        exists=True,
        resolve_path=True,
        dir_okay=False,
        readable=True,
        path_type=Path
    )
)
def compile(source: Path, target: Path, config_path: Path | None):
    config = Config.from_yaml(config_path) if config_path else Config()
    out_addr = config.io.char_output.address
    in_addr = config.io.char_input.address if config.io.char_input is not None else None

    tokens = Lexer(source.read_text(encoding="utf-8")).tokenize()
    ast = Parser(tokens).parse()
    Analyzer().analyze(ast)
    program = CodeGen(mmio_out_addr=out_addr, mmio_in_addr=in_addr).generate(ast)

    with target.open("wb") as f:
        pickle.dump(program.instructions, f)
        pickle.dump(program.data, f)
        pickle.dump(program.interrupt_handlers, f)

    with target.with_suffix(".dbg").open("w", encoding="utf-8") as f:
        f.write("Instructions:\n")
        for addr, instr in enumerate(program.instructions):
            f.write(f'{addr:#04x} - {instr:#08x} - {Instruction.from_binary(instr).opcode.name} {Instruction.from_binary(instr).operand:#08x}\n')

        f.write("\nData:\n")
        for addr, cell in enumerate(program.data):
            f.write(f'{addr:#04x} - {cell & 0xFFFFFFFF:#08x} - .word {cell:#x}\n')

        f.write("\nInterrupt handlers:\n")
        for vector, addr in program.interrupt_handlers.items():
            f.write(f'  vector {vector} -> {addr:#06x}\n')

    click.echo(f"Compiled {source} to {target.name}")


@cli.command()
@click.argument('file', type=click.Path(
    exists=True,
    resolve_path=True,
    dir_okay=False,
    readable=True,
    path_type=Path
))
@click.option(
    "-c", "--config", "config_path",
    type=click.Path(
        exists=True,
        resolve_path=True,
        dir_okay=False,
        readable=True,
        path_type=Path
    )
)
def run(file: Path, config_path: Path | None):
    with file.open("rb") as f:
        instructions = pickle.load(f)
        data = pickle.load(f)
        interrupt_handlers: dict[int, int] = pickle.load(f)

    if config_path is not None:
        config = Config.from_yaml(config_path)
    else:
        config = Config()

    instr_memory = Memory(config.memory_size.instruction)
    instr_memory.fill(instructions)

    data_memory = Memory(config.memory_size.data)
    data_memory.fill(data)

    return_stack = Stack(config.stack_size.ret)
    data_stack = Stack(config.stack_size.data)

    io_map: dict[int, Device] = {}
    char_device = CharOutput()
    io_map[config.io.char_output.address] = char_device

    if config.io.char_input is not None:
        char_input = CharInput(
            schedule=config.io.char_input.schedule,
            vector=config.io.char_input.vector,
        )
        io_map[config.io.char_input.address] = char_input

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

    cu.run(limit=config.limit)

    pprint(cu.snapshot.data_memory[:10])
    pprint(cu.snapshot.data_stack[:10])
    print(char_device.string)

if __name__ == "__main__":
    cli()
