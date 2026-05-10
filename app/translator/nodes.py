from __future__ import annotations

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


Statement = ConstDecl | VarDecl | FunDecl | IfStmt | WhileStmt | AssignStmt | ExprStmt | ReturnStmt
Expr = BinaryOp | UnaryOp | PostfixOp | Call | Ident | Number | String | Bool
