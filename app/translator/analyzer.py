from __future__ import annotations

from dataclasses import dataclass
from typing import Never

from app.translator.builtins import BUILTINS, LABELS, Args, Param
from app.translator.nodes import (
    ArrayDecl,
    AssignStmt,
    ASTNode,
    BinaryOp,
    Block,
    Bool,
    Call,
    ConstDecl,
    Expr,
    ExprStmt,
    FunDecl,
    Ident,
    IfStmt,
    IndexAssignStmt,
    IndexExpr,
    InterruptDecl,
    Number,
    Op,
    PostfixOp,
    Program,
    ReturnStmt,
    String,
    UnaryOp,
    VarDecl,
    WhileStmt,
)
from app.translator.types import NUMERIC, Type

ARITH_OPS = {Op.PLUS, Op.MINUS, Op.STAR, Op.SLASH}
CMP_OPS = {Op.EQUAL, Op.NOT_EQUAL, Op.LESS_THAN, Op.GREATER_THAN, Op.LESS_THAN_OR_EQUAL, Op.GREATER_THAN_OR_EQUAL}
LOGIC_OPS = {Op.AND, Op.OR, Op.XOR}
INCR_OPS = {Op.INCREMENT, Op.DECREMENT}


@dataclass
class Symbol:
    name: str
    type_name: Type
    mutable: bool

    params: list[tuple[Type, str]] | None = None
    return_type: Type | None = None


class Scope:
    def __init__(self, parent: Scope | None = None) -> None:
        self._syms: dict[str, Symbol] = {}
        self.parent = parent

    def define(self, sym: Symbol) -> Symbol | None:
        existing = self._syms.get(sym.name)
        if existing is not None:
            return existing
        self._syms[sym.name] = sym
        return None

    def resolve(self, name: str) -> Symbol | None:
        sym = self._syms.get(name)
        if sym is not None:
            return sym
        return self.parent.resolve(name) if self.parent else None


class SemanticError(Exception):
    pass


class Analyzer:
    def __init__(
        self,
        output_devices: set[str] | None = None,
        input_devices: set[str] | None = None,
    ) -> None:
        self._scope = Scope()
        self._return_type: Type | None = None
        self._in_interrupt_handler = False

        for label in output_devices or set():
            self._scope.define(Symbol(label, Type.OUTPUT_DEVICE, mutable=False))
        for label in input_devices or set():
            self._scope.define(Symbol(label, Type.INPUT_DEVICE, mutable=False))

    def analyze(self, program: Program) -> None:
        self._visit(program)

    def _push(self) -> None:
        self._scope = Scope(self._scope)

    def _pop(self) -> None:
        parent = self._scope.parent
        if parent is None:
            self.error("cannot pop the global scope")
        self._scope = parent

    def _define(self, sym: Symbol) -> None:
        existing = self._scope.define(sym)
        if existing is not None:
            self.error(f"'{sym.name}' already declared in this scope")

    def _resolve(self, name: str) -> Symbol | None:
        sym = self._scope.resolve(name)
        if sym is None:
            self.error(f"undefined name '{name}'")
        return sym

    def error(self, message: str) -> Never:
        raise SemanticError(message)

    def _visit(self, node: ASTNode) -> Type | None:
        match node:
            case Program(body=body):
                for stmt in body:
                    self._visit(stmt)

            case ConstDecl(name=name, type_name=t, value=value):
                t_type = Type(t)
                vtype = self._visit(value)
                self._check_compat(t_type, vtype, f"const '{name}'")
                self._define(Symbol(name, t_type, mutable=False))

            case VarDecl(name=name, type_name=t, value=value):
                t_type = Type(t)
                vtype = self._visit(value)
                self._check_compat(t_type, vtype, f"var '{name}'")
                self._define(Symbol(name, t_type, mutable=True))

            case ArrayDecl(name=name, type_name=_, size=_):
                self._define(Symbol(name, Type.ARRAY, mutable=True))

            case IndexAssignStmt(name=name, index=index, value=value):
                sym = self._resolve(name)
                if sym is not None and sym.type_name != Type.ARRAY:
                    self.error(f"'{name}' is not an array")
                self._visit(index)
                self._visit(value)

            case FunDecl(name=name, params=params, body=body, return_type=rt):
                rt_type = Type(rt) if rt else None
                params_typed = [(Type(tn), pn) for tn, pn in params]
                self._define(Symbol(name, Type.FUN, mutable=False, params=params_typed, return_type=rt_type))
                self._push()
                for type_name, param_name in params:
                    self._define(Symbol(param_name, Type(type_name), mutable=True))
                prev = self._return_type
                self._return_type = rt_type
                self._visit(body)
                self._return_type = prev
                self._pop()

            case InterruptDecl(vector=_, name=name, body=body):
                self._define(Symbol(name, Type.INTERRUPT, mutable=False))
                self._push()
                prev_in_handler = self._in_interrupt_handler
                self._in_interrupt_handler = True
                self._visit(body)
                self._in_interrupt_handler = prev_in_handler
                self._pop()

            case AssignStmt(name=name, value=value):
                sym = self._resolve(name)
                if sym is not None and not sym.mutable:
                    self.error(f"cannot assign to const '{name}'")
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
                        self._visit(else_branch)

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
                    self.error("cannot return from an interrupt handler")
                vtype = self._visit(value) if value is not None else None
                if self._return_type is None:
                    if vtype is not None:
                        self.error("cannot return a value from a void function")
                else:
                    if value is not None:
                        self._check_compat(self._return_type, vtype, "return value")

            case BinaryOp(op=op, left=left, right=right):
                ltype = self._visit(left)
                rtype = self._visit(right)
                return self._infer_binary(op, ltype, rtype)

            case UnaryOp(op=op, operand=operand):
                if op in INCR_OPS:
                    if not isinstance(operand, Ident):
                        self.error(f"'{op}' requires an identifier as operand")
                    sym = self._resolve(operand.name)
                    if sym is not None:
                        if not sym.mutable:
                            self.error(f"cannot apply '{op}' to const '{operand.name}'")
                        if sym.type_name not in NUMERIC:
                            self.error(f"'{op}' requires a numeric variable, got '{sym.type_name}'")
                    return sym.type_name if sym else None
                otype = self._visit(operand)
                if op == Op.NOT:
                    if otype is not None and otype != Type.BOOL:
                        self.error(f"'!' requires bool, got '{otype}'")
                    return Type.BOOL
                return otype

            case PostfixOp(op=op, operand=operand):
                if not isinstance(operand, Ident):
                    self.error(f"'{op}' requires an identifier as operand")
                sym = self._resolve(operand.name)
                if sym is not None:
                    if not sym.mutable:
                        self.error(f"cannot apply '{op}' to const '{operand.name}'")
                    if sym.type_name not in NUMERIC:
                        self.error(f"'{op}' requires a numeric variable, got '{sym.type_name}'")
                return sym.type_name if sym else None

            case Call(name=name, args=args):
                builtin = BUILTINS.get(name)
                if builtin is None:
                    return self._check_user_call(name, args)
                if name == "read":
                    self._check_read(builtin.overload, args)
                else:
                    self._check_overload(name, builtin.overload, args)
                return builtin.return_type

            case IndexExpr(name=name, index=index):
                sym = self._resolve(name)
                if sym is not None and sym.type_name != Type.ARRAY:
                    self.error(f"'{name}' is not an array")
                self._visit(index)
                return Type.INT

            case Ident(name=name):
                sym = self._resolve(name)
                if sym is not None:
                    match sym.type_name:
                        case Type.OUTPUT_DEVICE:
                            self.error(f"output device label '{name}' can only appear as first arg of print")
                        case Type.INPUT_DEVICE:
                            self.error(f"input device label '{name}' can only appear as arg of read")
                        case Type.ARRAY:
                            self.error(f"array '{name}' must be indexed with []")
                        case _:
                            return sym.type_name
                return None

            case Number():
                return Type.INT

            case String():
                return Type.STRING

            case Bool():
                return Type.BOOL

        return None

    def _check_overload(self, name: str, overload: list[Args], args: list[Expr]) -> None:
        chosen = self._select_overload(overload, args)
        if chosen is None:
            self.error(f"'{name}' got {len(args)} argument(s); no matching overload")
        for i, arg in enumerate(args):
            param = chosen.params[min(i, len(chosen.params) - 1)] if chosen.variadic else chosen.params[i]
            if param in LABELS:
                continue
            allowed = param if isinstance(param, frozenset) else {param}
            arg_type = self._visit(arg)
            if arg_type is not None and arg_type not in allowed:
                self.error(f"argument {i + 1}: invalid type '{arg_type}', expected one of {sorted(allowed)}")

    def _select_overload(self, overload: list[Args], args: list[Expr]) -> Args | None:
        for form in sorted(overload, key=lambda f: bool(f.params) and f.params[0] in LABELS, reverse=True):
            if self._overload_matches(form, args):
                return form
        return None

    def _overload_matches(self, form: Args, args: list[Expr]) -> bool:
        if form.variadic:
            if len(args) < len(form.params) - 1:
                return False
        elif len(args) != len(form.params):
            return False
        return all(
            self._is_device_label(arg, param) for param, arg in zip(form.params, args, strict=False) if param in LABELS
        )

    def _is_device_label(self, arg: Expr, device: Param) -> bool:
        if not isinstance(arg, Ident):
            return False
        sym = self._scope.resolve(arg.name)
        return sym is not None and sym.type_name == device

    def _check_read(self, overload: list[Args], args: list[Expr]) -> None:
        label = next(p for form in overload for p in form.params if p in LABELS)
        if not args:
            if not self._in_interrupt_handler:
                self.error("read() without a label can only be used in an interrupt handler")
        elif len(args) == 1 and self._is_device_label(args[0], label):
            return
        elif len(args) == 1 and isinstance(args[0], Ident):
            self.error(f"'{args[0].name}' is not an input device label")
        else:
            self.error("read expects 0 or 1 device-label arg")

    def _check_user_call(self, name: str, args: list[Expr]) -> Type | None:
        sym = self._resolve(name)
        if sym is not None:
            if sym.type_name == Type.INTERRUPT:
                self.error(f"interrupt handler '{name}' cannot be called directly")
            elif sym.type_name != Type.FUN:
                self.error(f"'{name}' is not a function")
            elif sym.params is not None and len(args) != len(sym.params):
                self.error(f"'{name}' expects {len(sym.params)} arg(s), got {len(args)}")
        for arg in args:
            self._visit(arg)
        return sym.return_type if sym else None

    def _check_compat(self, declared: Type, actual: Type | None, label: str) -> None:
        if actual is None or declared == actual:
            return
        if declared == Type.LONG and actual == Type.INT:
            return
        self.error(f"type mismatch for {label}: expected '{declared}', got '{actual}'")

    def _infer_binary(self, op: str, ltype: Type | None, rtype: Type | None) -> Type | None:
        if op in ARITH_OPS:
            for t, side in ((ltype, "left"), (rtype, "right")):
                if t is not None and t not in NUMERIC:
                    self.error(f"'{op}' requires numeric operands, got '{t}' on {side}")
            if Type.LONG in (ltype, rtype):
                return Type.LONG
            return ltype or rtype

        if op in CMP_OPS:
            if ltype is not None and rtype is not None and ltype != rtype:
                if not (ltype in NUMERIC and rtype in NUMERIC):
                    self.error(f"'{op}' cannot compare '{ltype}' with '{rtype}'")
            return Type.BOOL

        if op in LOGIC_OPS:
            for t, side in ((ltype, "left"), (rtype, "right")):
                if t is not None and t != Type.BOOL:
                    self.error(f"'{op}' requires bool operands, got '{t}' on {side}")
            return Type.BOOL

        return None
