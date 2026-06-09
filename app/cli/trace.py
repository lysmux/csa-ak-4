import click

from app.isa.flag import Flag
from app.simulation.control_unit import ControlUnit


def format_flags(flags: Flag, *, styled: bool = False) -> str:
    items = [
        ("N", Flag.N),
        ("Z", Flag.Z),
        ("V", Flag.V),
        ("C", Flag.C),
    ]

    if not styled:
        return " ".join(ch if bit in flags else "·" for ch, bit in items)

    return " ".join(
        click.style(ch, fg="yellow", bold=True) if bit in flags else click.style("·", dim=True) for ch, bit in items
    )


def trace_var(name: str, value: str, *, color: str = "white", styled: bool = False) -> str:
    if not styled:
        return f"{name:>5}: {value}"

    name = click.style(f"{name:>5}", bold=True, fg="cyan")
    value = click.style(value, fg=color)

    return f"{name}: {value}"


def trace_line(cu: ControlUnit, *, styled: bool = False) -> str:
    snap = cu.snapshot
    instr = snap.instruction

    parts = [
        trace_var("tick", f"{snap.tick:6d}", color="green", styled=styled),
        trace_var("state", f"{snap.state.name:<10}", color="magenta", styled=styled),
        trace_var("pc", f"0x{snap.pc:04X}", color="yellow", styled=styled),
        trace_var(
            "ir",
            f"{instr.opcode.name:<8} 0x{instr.operand:08X}",
            color="white",
            styled=styled,
        ),
        trace_var("flags", format_flags(snap.flags), styled=styled),
        trace_var("tos", f"0x{snap.tos:08X}", color="green", styled=styled),
        trace_var("nos", f"0x{snap.nos:08X}", color="green", styled=styled),
        trace_var("rtos", f"0x{snap.r_tos:08X}", color="green", styled=styled),
    ]

    return " │ ".join(parts)
