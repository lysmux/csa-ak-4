from __future__ import annotations

import dataclasses as _dc
import sys as _sys
from dataclasses import dataclass


@dataclass
class Program:
    body: list[Statement]


@dataclass
class ConstDecl:
    name: str
    type_name: str
    value: Expr


@dataclass
class VarDecl:
    name: str
    type_name: str
    value: Expr


@dataclass
class FunDecl:
    name: str
    params: list[tuple[str, str]]
    body: Block
    return_type: str | None = None


@dataclass
class InterruptDecl:
    vector: int
    name: str
    body: Block


@dataclass
class IfStmt:
    condition: Expr | None
    then_block: Block
    else_branch: IfStmt | Block | None


@dataclass
class WhileStmt:
    condition: Expr
    body: Block


@dataclass
class Block:
    body: list[Statement]


@dataclass
class AssignStmt:
    name: str
    value: Expr


@dataclass
class ExprStmt:
    expr: Expr


@dataclass
class ReturnStmt:
    value: Expr | None


@dataclass
class BinaryOp:
    op: str
    left: Expr
    right: Expr


@dataclass
class UnaryOp:
    op: str
    operand: Expr


@dataclass
class PostfixOp:
    op: str
    operand: Expr


@dataclass
class Call:
    name: str
    args: list[Expr]


@dataclass
class Ident:
    name: str


@dataclass
class Number:
    value: int


@dataclass
class String:
    value: str


@dataclass
class Bool:
    value: bool


Statement = ConstDecl | VarDecl | FunDecl | InterruptDecl | IfStmt | WhileStmt | AssignStmt | ExprStmt | ReturnStmt
Expr = BinaryOp | UnaryOp | PostfixOp | Call | Ident | Number | String | Bool


def print_ast(node: object, *, file: "_sys.IO[str]" = _sys.stdout) -> None:
    lines: list[str] = []
    _ast_collect(node, "", "", lines)
    print("\n".join(lines), file=file)


def _ast_collect(node: object, prefix: str, child_prefix: str, lines: list[str]) -> None:
    if not _dc.is_dataclass(node) or isinstance(node, type):
        lines.append(prefix + repr(node))
        return

    scalars: list[tuple[str, object]] = []
    children: list[tuple[str, object]] = []
    for f in _dc.fields(node):  # type: ignore[arg-type]
        v = getattr(node, f.name)
        if (isinstance(v, list) and v) or (_dc.is_dataclass(v) and not isinstance(v, type)):
            children.append((f.name, v))
        else:
            scalars.append((f.name, v))

    scalar_str = "  ".join(f"{k}={v!r}" for k, v in scalars)
    header = type(node).__name__ + ("  " + scalar_str if scalar_str else "")
    lines.append(prefix + header)

    for i, (fname, child) in enumerate(children):
        last = i == len(children) - 1
        conn = "└─ " if last else "├─ "
        next_cp = child_prefix + ("   " if last else "│  ")

        if isinstance(child, list):
            lines.append(child_prefix + conn + fname + ":")
            for j, item in enumerate(child):
                item_last = j == len(child) - 1
                item_conn = "└─ " if item_last else "├─ "
                item_cp = next_cp + ("   " if item_last else "│  ")
                _ast_collect(item, next_cp + item_conn + f"[{j}] ", item_cp, lines)
        else:
            _ast_collect(child, child_prefix + conn + fname + ": ", next_cp, lines)
