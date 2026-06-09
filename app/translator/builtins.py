from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.translator.types import PRINTABLE, Type

if TYPE_CHECKING:
    from app.translator.analyzer import Analyzer
    from app.translator.codegen import CodeGen
    from app.translator.nodes import Expr

type Emit = Callable[[CodeGen, Sequence[Expr]], str]
type Check = Callable[[Analyzer, Sequence[Expr]], None]


type Param = Type | frozenset[Type]

LABELS = frozenset({Type.OUTPUT_DEVICE, Type.INPUT_DEVICE})


@dataclass(frozen=True)
class Args:
    params: tuple[Param, ...] = ()
    variadic: bool = False


@dataclass(frozen=True)
class Builtin:
    overload: list[Args]
    return_type: Type | None
    emit: Emit
    check: Check | None = None


def _read_requires_interrupt_context(analyzer: Analyzer, args: Sequence[Expr]) -> None:
    if not args and not analyzer.in_interrupt_handler:
        analyzer.error("read() without a label can only be used in an interrupt handler")


BUILTINS: dict[str, Builtin] = {
    "print": Builtin(
        overload=[
            Args((PRINTABLE,), variadic=True),  # print(value, ...)
            Args((Type.OUTPUT_DEVICE, PRINTABLE), variadic=True),  # print(out_label, value, ...)
        ],
        return_type=None,
        emit=lambda cg, args: cg.gen_print(args),
    ),
    "read": Builtin(
        overload=[
            Args(),  # read()
            Args((Type.INPUT_DEVICE,)),  # read(in_label)
        ],
        return_type=Type.INT,
        emit=lambda cg, args: cg.gen_read(args),
        check=_read_requires_interrupt_context,
    ),
    "enable_interrupts": Builtin(overload=[Args()], return_type=None, emit=lambda cg, _: cg.gen_enable_interrupts()),
    "disable_interrupts": Builtin(overload=[Args()], return_type=None, emit=lambda cg, _: cg.gen_disable_interrupts()),
}
