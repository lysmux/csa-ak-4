from __future__ import annotations

from dataclasses import dataclass
from typing import Never

from app.translator.nodes import (
    ArrayDecl,
    AssignStmt,
    BinaryOp,
    Block,
    Bool,
    Call,
    ConstDecl,
    ExprStmt,
    FunDecl,
    Ident,
    IfStmt,
    IndexAssignStmt,
    IndexExpr,
    InterruptDecl,
    Number,
    PostfixOp,
    Program,
    ReturnStmt,
    String,
    UnaryOp,
    VarDecl,
    WhileStmt,
)

_NUMERIC = frozenset({"byte", "int"})
_ARITH_OPS = frozenset({"PLUS", "MINUS", "STAR", "SLASH"})
_CMP_OPS = frozenset({"EQUAL", "NOT_EQUAL", "LESS_THAN", "GREATER_THAN", "LESS_THAN_OR_EQUAL", "GREATER_THAN_OR_EQUAL"})
_LOGIC_OPS = frozenset({"AND", "OR", "XOR"})
_INCR_OPS = frozenset({"INCREMENT", "DECREMENT"})

# Встроенные функции — допустимы без объявления, arity=None означает любое число аргументов
_BUILTINS: dict[str, int | None] = {
    "print": None,
    "println": None,
    "getchar": None,
    "addc": 2,
    "enable_interrupts": 0,
    "disable_interrupts": 0,
}


# ---------------------------------------------------------------------------
# Symbol table
# ---------------------------------------------------------------------------


@dataclass
class Symbol:
    name: str
    type_name: str  # 'byte', 'int', 'bool', 'string', 'fun'
    mutable: bool
    params: list[tuple[str, str]] | None = None  # только для функций
    return_type: str | None = None  # только для функций


class Scope:
    def __init__(self, parent: Scope | None = None) -> None:
        self._syms: dict[str, Symbol] = {}
        self.parent = parent

    def define(self, sym: Symbol) -> Symbol | None:
        """Возвращает существующий символ, если имя уже занято в данной области."""
        existing = self._syms.get(sym.name)
        if existing is not None:
            return existing
        self._syms[sym.name] = sym
        return None

    def resolve(self, name: str) -> Symbol | None:
        """Ищет символ вверх по цепочке областей видимости."""
        sym = self._syms.get(name)
        if sym is not None:
            return sym
        return self.parent.resolve(name) if self.parent else None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SemanticError(Exception): ...


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class Analyzer:
    def __init__(
        self,
        output_devices: set[str] | None = None,
        input_devices: set[str] | None = None,
    ) -> None:
        self._errors: list[SemanticError] = []
        self._scope = Scope()
        self._return_type: str | None = None
        self._in_interrupt_handler = False
        for label in output_devices or set():
            self._scope.define(Symbol(label, "output_device", mutable=False))
        for label in input_devices or set():
            self._scope.define(Symbol(label, "input_device", mutable=False))

    def analyze(self, program: Program) -> list[SemanticError]:
        self._visit(program)
        return self._errors

    # --- scope helpers ---

    def _push(self) -> None:
        self._scope = Scope(self._scope)

    def _pop(self) -> None:
        self._scope = self._scope.parent

    def _define(self, sym: Symbol) -> None:
        existing = self._scope.define(sym)
        if existing is not None:
            self._err(f"'{sym.name}' already declared in this scope")

    def _resolve(self, name: str) -> Symbol | None:
        sym = self._scope.resolve(name)
        if sym is None:
            self._err(f"undefined name '{name}'")
        return sym

    def _err(self, message: str) -> Never:
        raise SemanticError(message)

    # --- visitor (returns inferred type or None if unknown) ---

    def _visit(self, node: object) -> str | None:  # noqa: PLR0911, PLR0912
        match node:
            case Program(body=body):
                for stmt in body:
                    self._visit(stmt)

            case ConstDecl(name=name, type_name=t, value=value):
                vtype = self._visit(value)
                self._check_compat(t, vtype, f"const '{name}'")
                self._define(Symbol(name, t, mutable=False))

            case VarDecl(name=name, type_name=t, value=value):
                vtype = self._visit(value)
                self._check_compat(t, vtype, f"var '{name}'")
                self._define(Symbol(name, t, mutable=True))

            case ArrayDecl(name=name, type_name=t, size=_):
                self._define(Symbol(name, "array", mutable=True))

            case IndexAssignStmt(name=name, index=index, value=value):
                sym = self._resolve(name)
                if sym is not None and sym.type_name != "array":
                    self._err(f"'{name}' is not an array")
                self._visit(index)
                self._visit(value)

            case FunDecl(name=name, params=params, body=body, return_type=rt):
                self._define(Symbol(name, "fun", mutable=False, params=params, return_type=rt))
                self._push()
                for type_name, param_name in params:
                    self._define(Symbol(param_name, type_name, mutable=True))
                prev = self._return_type
                self._return_type = rt
                self._visit(body)
                self._return_type = prev
                self._pop()

            case InterruptDecl(vector=_, name=name, body=body):
                self._define(Symbol(name, "interrupt", mutable=False))
                self._push()
                prev = self._in_interrupt_handler
                self._in_interrupt_handler = True
                self._visit(body)
                self._in_interrupt_handler = prev
                self._pop()

            case AssignStmt(name=name, value=value):
                sym = self._resolve(name)
                if sym is not None and not sym.mutable:
                    self._err(f"cannot assign to const '{name}'")
                vtype = self._visit(value)
                if sym is not None:
                    self._check_compat(sym.type_name, vtype, f"'{name}'")

            case IfStmt(condition=cond, then_block=then_block, else_branch=else_branch):
                if cond is not None:
                    self._visit(cond)
                self._push()
                self._visit(then_block)
                self._pop()
                if else_branch is not None:
                    if isinstance(else_branch, Block):
                        self._push()
                        self._visit(else_branch)
                        self._pop()
                    else:
                        self._visit(else_branch)  # IfStmt управляет своими скоупами сам

            case WhileStmt(condition=cond, body=body):
                self._visit(cond)
                self._push()
                self._visit(body)
                self._pop()

            case Block(body=stmts):
                for stmt in stmts:
                    self._visit(stmt)

            case ExprStmt(expr=e):
                self._visit(e)

            case ReturnStmt(value=value):
                if self._in_interrupt_handler:
                    self._err("cannot return from an interrupt handler")
                vtype = self._visit(value) if value is not None else None
                if self._return_type is None:
                    if vtype is not None:
                        self._err("cannot return a value from a void function")
                else:
                    if value is not None:
                        self._check_compat(self._return_type, vtype, "return value")

            # --- выражения ---

            case BinaryOp(op=op, left=left, right=right):
                ltype = self._visit(left)
                rtype = self._visit(right)
                return self._infer_binary(op, ltype, rtype)

            case UnaryOp(op=op, operand=operand):
                if op in _INCR_OPS:
                    if not isinstance(operand, Ident):
                        self._err(f"'{op}' requires an identifier as operand")
                        return None
                    sym = self._resolve(operand.name)
                    if sym is not None:
                        if not sym.mutable:
                            self._err(f"cannot apply '{op}' to const '{operand.name}'")
                        if sym.type_name not in _NUMERIC:
                            self._err(f"'{op}' requires a numeric variable, got '{sym.type_name}'")
                    return sym.type_name if sym else None
                otype = self._visit(operand)
                if op == "NOT":
                    if otype is not None and otype != "bool":
                        self._err(f"'!' requires bool, got '{otype}'")
                    return "bool"
                return otype

            case PostfixOp(op=op, operand=operand):
                if not isinstance(operand, Ident):
                    self._err(f"'{op}' requires an identifier as operand")
                    return None
                sym = self._resolve(operand.name)
                if sym is not None:
                    if not sym.mutable:
                        self._err(f"cannot apply '{op}' to const '{operand.name}'")
                    if sym.type_name not in _NUMERIC:
                        self._err(f"'{op}' requires a numeric variable, got '{sym.type_name}'")
                return sym.type_name if sym else None

            case Call(name=name, args=args):
                fun_sym: Symbol | None = None
                visit_args = args
                if name in _BUILTINS:
                    if name in {"print", "println"} and args and isinstance(args[0], Ident):
                        first_sym = self._scope.resolve(args[0].name)
                        if first_sym is not None and first_sym.type_name == "output_device":
                            visit_args = args[1:]
                    elif name == "getchar":
                        if len(args) == 0:
                            if not self._in_interrupt_handler:
                                self._err("getchar() without a label can only be used in an interrupt handler")
                            visit_args = []
                        elif len(args) == 1 and isinstance(args[0], Ident):
                            first_sym = self._scope.resolve(args[0].name)
                            if first_sym is None or first_sym.type_name != "input_device":
                                self._err(f"'{args[0].name}' is not an input device label")
                            visit_args = []
                        else:
                            self._err("getchar expects 0 or 1 device-label arg")
                            visit_args = []
                    expected = _BUILTINS[name]
                    if expected is not None and len(args) != expected:
                        self._err(f"'{name}' expects {expected} arg(s), got {len(args)}")
                else:
                    fun_sym = self._resolve(name)
                    if fun_sym is not None:
                        if fun_sym.type_name == "interrupt":
                            self._err(f"interrupt handler '{name}' cannot be called directly")
                        elif fun_sym.type_name != "fun":
                            self._err(f"'{name}' is not a function")
                        elif fun_sym.params is not None and len(args) != len(fun_sym.params):
                            self._err(f"'{name}' expects {len(fun_sym.params)} arg(s), got {len(args)}")
                for arg in visit_args:
                    self._visit(arg)
                return fun_sym.return_type if fun_sym else None

            case IndexExpr(name=name, index=index):
                sym = self._resolve(name)
                if sym is not None and sym.type_name != "array":
                    self._err(f"'{name}' is not an array")
                self._visit(index)
                return "int"

            case Ident(name=name):
                sym = self._resolve(name)
                if sym is not None and sym.type_name == "output_device":
                    self._err(f"output device label '{name}' can only appear as first arg of print/println")
                if sym is not None and sym.type_name == "input_device":
                    self._err(f"input device label '{name}' can only appear as arg of getchar")
                if sym is not None and sym.type_name == "array":
                    self._err(f"array '{name}' must be indexed with []")
                return sym.type_name if sym else None

            case Number():
                return "int"

            case String():
                return "string"

            case Bool():
                return "bool"

        return None

    # --- type helpers ---

    def _check_compat(self, declared: str, actual: str | None, label: str) -> None:
        if actual is None or declared == actual:
            return
        # byte ↔ int считается совместимым (числовое расширение)
        if declared in _NUMERIC and actual in _NUMERIC:
            return
        self._err(f"type mismatch for {label}: expected '{declared}', got '{actual}'")

    def _infer_binary(self, op: str, ltype: str | None, rtype: str | None) -> str | None:
        if op in _ARITH_OPS:
            for t, side in ((ltype, "left"), (rtype, "right")):
                if t is not None and t not in _NUMERIC:
                    self._err(f"'{op}' requires numeric operands, got '{t}' on {side}")
            if ltype in _NUMERIC or rtype in _NUMERIC:
                return "int"
            return ltype or rtype

        if op in _CMP_OPS:
            if ltype is not None and rtype is not None and ltype != rtype:
                if not (ltype in _NUMERIC and rtype in _NUMERIC):
                    self._err(f"'{op}' cannot compare '{ltype}' with '{rtype}'")
            return "bool"

        if op in _LOGIC_OPS:
            for t, side in ((ltype, "left"), (rtype, "right")):
                if t is not None and t != "bool":
                    self._err(f"'{op}' requires bool operands, got '{t}' on {side}")
            return "bool"

        return None
