from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.translator.ast_repr import render
from app.translator.types import Type


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
class ASTNode:
    inferred_type: Type | None = field(default=None, compare=False, kw_only=True, metadata={"ast_skip": True})

    def __str__(self) -> str:
        return render(self)


@dataclass
class Program(ASTNode):
    body: list[Statement]


@dataclass
class ConstDecl(ASTNode):
    name: str
    type_name: Type
    value: Expr


@dataclass
class VarDecl(ASTNode):
    name: str
    type_name: Type
    value: Expr


@dataclass
class ArrayDecl(ASTNode):
    name: str
    type_name: Type
    size: int


@dataclass
class FunDecl(ASTNode):
    name: str
    params: list[tuple[Type, str]]
    body: Block
    return_type: Type = Type.VOID


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
