from __future__ import annotations

import dataclasses as _dc
import sys
from abc import ABC
from dataclasses import dataclass
from enum import StrEnum


class Op(StrEnum):
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    SLASH = "SLASH"
    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"
    LESS_THAN = "LESS_THAN"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL"
    AND = "AND"
    OR = "OR"
    XOR = "XOR"
    NOT = "NOT"
    INCREMENT = "INCREMENT"
    DECREMENT = "DECREMENT"


@dataclass
class ASTNode(ABC): ...  # noqa: B024


@dataclass
class Program(ASTNode):
    body: list[Statement]


@dataclass
class ConstDecl(ASTNode):
    name: str
    type_name: str
    value: Expr


@dataclass
class VarDecl(ASTNode):
    name: str
    type_name: str
    value: Expr


@dataclass
class ArrayDecl(ASTNode):
    name: str
    type_name: str
    size: int


@dataclass
class FunDecl(ASTNode):
    name: str
    params: list[tuple[str, str]]
    body: Block
    return_type: str | None = None


@dataclass
class InterruptDecl(ASTNode):
    vector: int
    name: str
    body: Block


@dataclass
class IfStmt(ASTNode):
    condition: Expr | None
    then_block: Block
    else_branch: IfStmt | Block | None


@dataclass
class WhileStmt(ASTNode):
    condition: Expr
    body: Block


@dataclass
class Block(ASTNode):
    body: list[Statement]


@dataclass
class AssignStmt(ASTNode):
    name: str
    value: Expr


@dataclass
class ExprStmt(ASTNode):
    expr: Expr


@dataclass
class ReturnStmt(ASTNode):
    value: Expr | None


@dataclass
class IndexAssignStmt(ASTNode):
    name: str
    index: Expr
    value: Expr


@dataclass
class BinaryOp(ASTNode):
    op: Op
    left: Expr
    right: Expr


@dataclass
class UnaryOp(ASTNode):
    op: Op
    operand: Expr


@dataclass
class PostfixOp(ASTNode):
    op: Op
    operand: Expr


@dataclass
class Call(ASTNode):
    name: str
    args: list[Expr]


@dataclass
class IndexExpr(ASTNode):
    name: str
    index: Expr


@dataclass
class Ident(ASTNode):
    name: str


@dataclass
class Number(ASTNode):
    value: int


@dataclass
class String(ASTNode):
    value: str


@dataclass
class Bool(ASTNode):
    value: bool


type Statement = (
    ConstDecl
    | VarDecl
    | ArrayDecl
    | FunDecl
    | InterruptDecl
    | IfStmt
    | WhileStmt
    | AssignStmt
    | IndexAssignStmt
    | ExprStmt
    | ReturnStmt
)
type Expr = BinaryOp | UnaryOp | PostfixOp | Call | IndexExpr | Ident | Number | String | Bool


def print_ast(node: ASTNode, *, file: sys.IO[str] = sys.stdout) -> None:
    lines: list[str] = []
    _ast_collect(node, "", "", lines)
    print("\n".join(lines), file=file)


def _ast_collect(node: ASTNode, prefix: str, child_prefix: str, lines: list[str]) -> None:
    if not _dc.is_dataclass(node) or isinstance(node, type):
        lines.append(prefix + repr(node))
        return

    scalars: list[tuple[str, ASTNode]] = []
    children: list[tuple[str, ASTNode]] = []
    for f in _dc.fields(node):
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
