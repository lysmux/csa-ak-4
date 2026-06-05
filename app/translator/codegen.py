from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.config import InputDeviceConfig, OutputDeviceConfig
from app.isa.consts import INSTR_BYTES, WORD_BYTES
from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
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
    Op,
    PostfixOp,
    Program,
    ReturnStmt,
    String,
    UnaryOp,
    VarDecl,
    WhileStmt,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.translator.nodes import Expr

_BUILTINS = frozenset({"print", "read", "enable_interrupts", "disable_interrupts"})

# Comparison op → conditional jump opcode for the TRUE branch
_CMP_JUMP: dict[Op, Opcode] = {
    Op.EQUAL: Opcode.JZ,
    Op.NOT_EQUAL: Opcode.JNZ,
    Op.LESS_THAN: Opcode.JL,
    Op.GREATER_THAN: Opcode.JG,
    Op.LESS_THAN_OR_EQUAL: Opcode.JLE,
    Op.GREATER_THAN_OR_EQUAL: Opcode.JGE,
}

_ARITH_OP: dict[Op, Opcode] = {
    Op.PLUS: Opcode.ADD,
    Op.MINUS: Opcode.SUB,
    Op.STAR: Opcode.MUL,
    Op.SLASH: Opcode.DIV,
    Op.AND: Opcode.AND,
    Op.OR: Opcode.OR,
    Op.XOR: Opcode.XOR,
}

# Arithmetic op → 64-bit double-word opcode (long operands).
_DARITH_OP: dict[Op, Opcode] = {
    Op.PLUS: Opcode.DADD,
    Op.MINUS: Opcode.DSUB,
    Op.STAR: Opcode.DMUL,
    Op.SLASH: Opcode.DDIV,
}

INT = "int"
LONG = "long"
BOOL = "bool"


@dataclass
class CompiledProgram:
    instructions: list[int]
    data: list[int]
    interrupt_handlers: dict[int, int]


class CodeGenError(Exception):
    pass


class CodeGen:
    def __init__(
        self,
        output_devices: dict[str, OutputDeviceConfig],
        input_devices: dict[str, InputDeviceConfig] | None = None,
    ) -> None:
        self._output_devices = output_devices
        self._default_output_name = next((name for name, cfg in output_devices.items() if cfg.default), None)
        self._input_devices = input_devices or {}
        self._inputs_by_vector: dict[int, InputDeviceConfig] = {}
        for dev in self._input_devices.values():
            existing = self._inputs_by_vector.get(dev.vector)
            if existing is None:
                self._inputs_by_vector[dev.vector] = dev
            elif existing.address != dev.address:
                msg = (
                    f"vector {dev.vector} is assigned to multiple input devices "
                    f"with different addresses ({existing.address:#x} and {dev.address:#x})"
                )
                raise CodeGenError(msg)
        self._current_interrupt_vector: int | None = None
        self._instrs: list[Instruction] = []
        self._scopes: list[dict[str, tuple[int, str]]] = [{}]
        self._data: list[int] = []
        self._data_size: int = 0
        self._const_values: dict[int, int] = {}
        self._fun_labels: dict[str, str] = {}
        self._fun_returns: dict[str, bool] = {}
        self._fun_return_types: dict[str, str | None] = {}
        self._current_return_type: str | None = None
        self._interrupt_handlers: dict[int, str] = {}
        self._interrupt_names: set[str] = set()
        self._labels: dict[str, int] = {}
        self._patches: list[tuple[int, str]] = []
        self._label_count: int = 0

    # --- public API --------------------------------------------------------

    def generate(
        self,
        program: Program,
        require_entry_point: bool = True,
    ) -> CompiledProgram:
        if require_entry_point:
            entry_idx = len(self._instrs)
            self._emit(Opcode.CALL, 0)  # patched to main's address
            self._emit(Opcode.HALT)
        self._gen(program)
        if require_entry_point:
            main_label = self._fun_labels.get("main")
            if main_label is None:
                msg = "missing entry point: function 'main' is required"
                raise CodeGenError(msg)
            self._patches.append((entry_idx, main_label))
        else:
            self._emit(Opcode.HALT)
        self._backpatch()
        handlers_resolved = {v: self._labels[lbl] * INSTR_BYTES for v, lbl in self._interrupt_handlers.items()}
        return CompiledProgram(
            instructions=[i.to_binary() for i in self._instrs],
            data=self._data,
            interrupt_handlers=handlers_resolved,
        )

    # --- emit helpers ------------------------------------------------------

    def _emit(self, op: Opcode, operand: int = 0) -> None:
        self._instrs.append(Instruction(op, operand))

    def _fresh_label(self) -> str:
        self._label_count += 1
        return f"__L{self._label_count}"

    def _mark_label(self, label: str) -> None:
        self._labels[label] = len(self._instrs)

    def _emit_jump(self, op: Opcode, label: str) -> None:
        self._patches.append((len(self._instrs), label))
        self._instrs.append(Instruction(op, 0))

    def _backpatch(self) -> None:
        for idx, label in self._patches:
            addr = self._labels[label] * INSTR_BYTES
            instr = self._instrs[idx]
            self._instrs[idx] = Instruction(instr.opcode, addr)

    # --- scope / variable helpers ------------------------------------------

    def _push_scope(self) -> None:
        self._scopes.append({})

    def _pop_scope(self) -> None:
        self._scopes.pop()

    @staticmethod
    def _width(type_name: str) -> int:
        return 2 if type_name == LONG else 1

    def _alloc_array(self, name: str, size: int) -> int:
        addr = self._data_size * WORD_BYTES
        self._scopes[-1][name] = (addr, "array")
        self._data_size += size
        self._data.extend([0] * size)
        return addr

    def _alloc_var(self, name: str, type_name: str = INT) -> int:
        addr = self._data_size * WORD_BYTES
        width = self._width(type_name)
        self._scopes[-1][name] = (addr, type_name)
        self._data_size += width
        self._data.extend([0] * width)
        return addr

    def _alloc_string(self, s: str) -> int:
        addr = self._data_size * WORD_BYTES
        for ch in s:
            self._data.append(ord(ch))
            self._data_size += 1
        self._data.append(0)
        self._data_size += 1
        return addr

    def _set_data_word(self, byte_addr: int, value: int) -> None:
        self._data[byte_addr // WORD_BYTES] = value & 0xFFFFFFFF

    def _emit_cstr_loop(self, str_addr: int, mmio_addr: int) -> None:
        lbl_loop = self._fresh_label()
        lbl_exit = self._fresh_label()
        self._emit(Opcode.PUSH, str_addr)
        self._mark_label(lbl_loop)
        self._emit(Opcode.DUP)
        self._emit(Opcode.LOADI)
        self._emit_jump(Opcode.JZ, lbl_exit)
        self._emit(Opcode.STORE, mmio_addr)
        self._emit(Opcode.PUSH, WORD_BYTES)
        self._emit(Opcode.ADD)
        self._emit_jump(Opcode.JMP, lbl_loop)
        self._mark_label(lbl_exit)
        self._emit(Opcode.DROP)
        self._emit(Opcode.DROP)

    def _resolve_output_device(self, args: Sequence[Expr]) -> tuple[OutputDeviceConfig, Sequence[Expr]]:
        if args and isinstance(args[0], Ident) and args[0].name in self._output_devices:
            return self._output_devices[args[0].name], args[1:]

        if self._default_output_name is None:
            msg = "no default output device configured; pass an output label as the first print argument"
            raise CodeGenError(msg)
        return self._output_devices[self._default_output_name], args

    # --- compile-time evaluation -------------------------------------------

    def _static_eval(self, node: object) -> int | None:
        match node:
            case Number(value=v):
                return v
            case Bool(value=v):
                return 1 if v else 0
            case Ident(name=name):
                try:
                    return self._const_values.get(self._var_addr(name))
                except CodeGenError:
                    return None
            case BinaryOp(op=op, left=l, right=r):
                lv = self._static_eval(l)
                rv = self._static_eval(r)
                if lv is None or rv is None:
                    return None
                match op:
                    case Op.PLUS:
                        return lv + rv
                    case Op.MINUS:
                        return lv - rv
                    case Op.STAR:
                        return lv * rv
                    case Op.SLASH:
                        return lv // rv if rv != 0 else None
                    case Op.AND:
                        return lv & rv
                    case Op.OR:
                        return lv | rv
                    case Op.XOR:
                        return lv ^ rv
                    case Op.EQUAL:
                        return int(lv == rv)
                    case Op.NOT_EQUAL:
                        return int(lv != rv)
                    case Op.LESS_THAN:
                        return int(lv < rv)
                    case Op.GREATER_THAN:
                        return int(lv > rv)
                    case Op.LESS_THAN_OR_EQUAL:
                        return int(lv <= rv)
                    case Op.GREATER_THAN_OR_EQUAL:
                        return int(lv >= rv)
                    case _:
                        return None
            case UnaryOp(op=Op.NOT, operand=e):
                inner = self._static_eval(e)
                return None if inner is None else int(inner == 0)
            case _:
                return None

    def _var_addr(self, name: str) -> int:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name][0]
        msg = f"undefined variable: {name!r}"
        raise CodeGenError(msg)

    def _var_type(self, name: str) -> str:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name][1]
        msg = f"undefined variable: {name!r}"
        raise CodeGenError(msg)

    # --- flag-test helper (condition → flags, stack cleared) ---------------

    def _emit_flag_test(self) -> None:
        """After gen(cond): TOS = value. Sets FLAGS = value, clears stack."""
        self._emit(Opcode.PUSH, 0)  # 0:value
        self._emit(Opcode.CMP)  # FLAGS = value - 0; stack: 0:value
        self._emit(Opcode.DROP)  # stack: value
        self._emit(Opcode.DROP)  # stack: empty

    # --- type inference / coercion ----------------------------------------

    def _expr_type(self, node: object) -> str:
        match node:
            case Number(value=v):
                return LONG if not (-(1 << 31) <= v <= (1 << 32) - 1) else INT
            case Bool():
                return BOOL
            case Ident(name=name):
                return self._var_type(name)
            case IndexExpr():
                return INT
            case UnaryOp(op=Op.NOT):
                return BOOL
            case UnaryOp(operand=Ident(name=name)) | PostfixOp(operand=Ident(name=name)):
                return self._var_type(name)
            case BinaryOp(op=op, left=left, right=right):
                if op in _ARITH_OP and op not in (Op.AND, Op.OR, Op.XOR):
                    return LONG if LONG in (self._expr_type(left), self._expr_type(right)) else INT
                return BOOL
            case Call(name=name):
                return self._fun_return_types.get(name) or INT
            case _:
                return INT

    def _emit_long_literal(self, value: int) -> None:
        v = value & 0xFFFFFFFFFFFFFFFF
        self._emit(Opcode.PUSH, v & 0xFFFFFFFF)  # lo -> NOS
        self._emit(Opcode.PUSH, (v >> 32) & 0xFFFFFFFF)  # hi -> TOS

    def _gen_as(self, node: object, target: str) -> None:
        """Emit `node` coerced to `target`, leaving width(target) cells on the stack."""
        if target == LONG:
            sv = self._static_eval(node)
            if sv is not None:
                self._emit_long_literal(sv)
                return
            if self._gen_value(node) != LONG:
                self._emit(Opcode.I2L)  # sign-extend int -> long
            return
        if self._gen_value(node) == LONG:
            msg = "cannot use a long value where a 32-bit value is required"
            raise CodeGenError(msg)

    def _gen_truth(self, cond: object) -> None:
        """Emit `cond`, reduce it to a single truth cell, and set FLAGS from it."""
        if self._gen_value(cond) == LONG:
            self._emit(Opcode.OR)  # lo | hi == 0  iff the whole long is zero
        self._emit_flag_test()

    def _emit_store(self, addr: int, type_name: str) -> None:
        if type_name == LONG:
            self._emit(Opcode.STORE, addr + WORD_BYTES)  # hi (TOS)
            self._emit(Opcode.STORE, addr)  # lo (NOS)
        else:
            self._emit(Opcode.STORE, addr)

    # --- statements --------------------------------------------------------

    def _gen(self, node: object) -> None:
        match node:
            case Program(body=body) | Block(body=body):
                for stmt in body:
                    self._gen(stmt)

            case ConstDecl(name=name, type_name=tn, value=value):
                self._gen_decl(name, tn, value, is_const=True)

            case VarDecl(name=name, type_name=tn, value=value):
                self._gen_decl(name, tn, value, is_const=False)

            case ArrayDecl(name=name, size=size):
                self._alloc_array(name, size)

            case AssignStmt(name=name, value=value):
                type_name = self._var_type(name)
                self._gen_as(value, type_name)
                self._emit_store(self._var_addr(name), type_name)

            case ExprStmt(expr=e):
                t = self._gen_value(e)
                for _ in range(self._width(t)):
                    self._emit(Opcode.DROP)

            case IfStmt(condition=cond, then_block=then_block, else_branch=else_branch):
                lbl_else = self._fresh_label()
                lbl_end = self._fresh_label()
                if cond is not None:
                    self._gen_truth(cond)
                    self._emit_jump(Opcode.JZ, lbl_else)
                self._gen(then_block)
                self._emit_jump(Opcode.JMP, lbl_end)
                self._mark_label(lbl_else)
                if else_branch is not None:
                    self._gen(else_branch)
                self._mark_label(lbl_end)

            case WhileStmt(condition=cond, body=body):
                lbl_loop = self._fresh_label()
                lbl_end = self._fresh_label()
                self._mark_label(lbl_loop)
                self._gen_truth(cond)
                self._emit_jump(Opcode.JZ, lbl_end)
                self._gen(body)
                self._emit_jump(Opcode.JMP, lbl_loop)
                self._mark_label(lbl_end)

            case FunDecl(name=name, params=params, body=body, return_type=rt):
                if rt == LONG or any(tn == LONG for tn, _ in params):
                    msg = "long function parameters/return values are not yet supported"
                    raise CodeGenError(msg)
                lbl_fun = self._fresh_label()
                lbl_skip = self._fresh_label()
                self._fun_labels[name] = lbl_fun
                self._fun_returns[name] = rt is not None
                self._fun_return_types[name] = rt
                self._emit_jump(Opcode.JMP, lbl_skip)
                self._mark_label(lbl_fun)
                self._push_scope()
                # Caller pushed args left-to-right; TOS = last arg. Pop in reverse.
                for type_name, param_name in reversed(params):
                    addr = self._alloc_var(param_name, type_name)
                    self._emit(Opcode.STORE, addr)
                prev_rt = self._current_return_type
                self._current_return_type = rt
                self._gen(body)
                self._current_return_type = prev_rt
                if rt is not None:
                    self._emit(Opcode.PUSH, 0)  # fallback return value
                self._emit(Opcode.RET)
                self._pop_scope()
                self._mark_label(lbl_skip)

            case InterruptDecl(vector=vector, name=name, body=body):
                lbl_fun = self._fresh_label()
                lbl_skip = self._fresh_label()
                self._interrupt_handlers[vector] = lbl_fun
                self._interrupt_names.add(name)
                self._emit_jump(Opcode.JMP, lbl_skip)
                self._mark_label(lbl_fun)
                self._push_scope()
                prev_vector = self._current_interrupt_vector
                self._current_interrupt_vector = vector
                self._gen(body)
                self._current_interrupt_vector = prev_vector
                self._emit(Opcode.RTI)
                self._pop_scope()
                self._mark_label(lbl_skip)

            case IndexAssignStmt(name=name, index=index, value=value):
                self._gen_as(value, INT)  # arrays hold 32-bit values
                base = self._var_addr(name)
                self._emit(Opcode.PUSH, base)
                self._gen_as(index, INT)
                self._emit(Opcode.PUSH, WORD_BYTES)
                self._emit(Opcode.MUL)
                self._emit(Opcode.ADD)
                self._emit(Opcode.STOREI)

            case ReturnStmt(value=value):
                if value is not None:
                    self._gen_as(value, self._current_return_type or INT)
                self._emit(Opcode.RET)

            case _:
                msg = f"unhandled statement: {node!r}"
                raise CodeGenError(msg)

    def _gen_decl(self, name: str, type_name: str, value: object, *, is_const: bool) -> None:
        addr = self._alloc_var(name, type_name)
        sv = self._static_eval(value)
        if type_name == LONG:
            if sv is not None:
                vv = sv & 0xFFFFFFFFFFFFFFFF
                self._set_data_word(addr, vv & 0xFFFFFFFF)
                self._set_data_word(addr + WORD_BYTES, (vv >> 32) & 0xFFFFFFFF)
                self._emit_long_literal(sv)
            else:
                self._gen_as(value, LONG)
            self._emit_store(addr, LONG)
            return

        if sv is not None:
            self._set_data_word(addr, sv & 0xFFFFFFFF)
            if is_const:
                self._const_values[addr] = sv
                return
            self._emit(Opcode.PUSH, sv & 0xFFFFFFFF)
            self._emit(Opcode.STORE, addr)
            return

        self._gen_as(value, type_name)
        self._emit(Opcode.STORE, addr)

    def _gen_incdec(self, name: str, op: Opcode, *, prefix: bool) -> None:
        if self._var_type(name) == LONG:
            msg = "'++'/'--' on long is not yet supported"
            raise CodeGenError(msg)
        addr = self._var_addr(name)
        self._emit(Opcode.LOAD, addr)
        if prefix:
            self._emit(op)
            self._emit(Opcode.DUP)
        else:
            self._emit(Opcode.DUP)
            self._emit(op)
        self._emit(Opcode.STORE, addr)

    # --- expressions (leave width(type) cells, return the type) ------------

    def _gen_value(self, node: object) -> str:  # noqa: PLR0911, PLR0912
        match node:
            case Number(value=v):
                t = self._expr_type(node)
                if t == LONG:
                    self._emit_long_literal(v)
                else:
                    self._emit(Opcode.PUSH, v & 0xFFFFFFFF)
                return t

            case Bool(value=v):
                self._emit(Opcode.PUSH, 1 if v else 0)
                return BOOL

            case String():
                self._emit(Opcode.PUSH, 0)  # strings not supported as values
                return INT

            case Ident(name=name):
                type_name = self._var_type(name)
                addr = self._var_addr(name)
                if type_name == LONG:
                    self._emit(Opcode.LOAD, addr)  # lo
                    self._emit(Opcode.LOAD, addr + WORD_BYTES)  # hi
                    return LONG
                cv = self._const_values.get(addr)
                if cv is not None:
                    self._emit(Opcode.PUSH, cv & 0xFFFFFFFF)
                else:
                    self._emit(Opcode.LOAD, addr)
                return type_name

            case IndexExpr(name=name, index=index):
                base = self._var_addr(name)
                self._emit(Opcode.PUSH, base)
                self._gen_as(index, INT)
                self._emit(Opcode.PUSH, WORD_BYTES)
                self._emit(Opcode.MUL)
                self._emit(Opcode.ADD)
                self._emit(Opcode.LOADI)
                return INT

            case BinaryOp(op=op, left=left, right=right) if op in _ARITH_OP:
                rt = self._expr_type(node)
                if rt == LONG:
                    self._gen_as(left, LONG)
                    self._gen_as(right, LONG)
                    self._emit(_DARITH_OP[op])
                else:
                    self._gen_as(left, INT)
                    self._gen_as(right, INT)
                    self._emit(_ARITH_OP[op])
                return rt

            case BinaryOp(op=op, left=left, right=right) if op in _CMP_JUMP:
                ct = LONG if LONG in (self._expr_type(left), self._expr_type(right)) else INT
                lbl_true = self._fresh_label()
                lbl_end = self._fresh_label()
                self._gen_as(left, ct)
                self._gen_as(right, ct)
                if ct == LONG:
                    # DSUB consumes both long operands -> 2-cell result; FLAGS = 64-bit l-r
                    self._emit(Opcode.DSUB)
                    self._emit(Opcode.DROP)
                    self._emit(Opcode.DROP)
                else:
                    self._emit(Opcode.CMP)  # FLAGS = l-r; stack unchanged
                    self._emit(Opcode.DROP)
                    self._emit(Opcode.DROP)
                self._emit_jump(_CMP_JUMP[op], lbl_true)
                self._emit(Opcode.PUSH, 0)
                self._emit_jump(Opcode.JMP, lbl_end)
                self._mark_label(lbl_true)
                self._emit(Opcode.PUSH, 1)
                self._mark_label(lbl_end)
                return BOOL

            case UnaryOp(op=Op.NOT, operand=operand):
                lbl_true = self._fresh_label()
                lbl_end = self._fresh_label()
                self._gen_truth(operand)
                self._emit_jump(Opcode.JZ, lbl_true)  # operand == 0 -> true
                self._emit(Opcode.PUSH, 0)
                self._emit_jump(Opcode.JMP, lbl_end)
                self._mark_label(lbl_true)
                self._emit(Opcode.PUSH, 1)
                self._mark_label(lbl_end)
                return BOOL

            case UnaryOp(op=Op.INCREMENT, operand=Ident(name=name)):
                self._gen_incdec(name, Opcode.INC, prefix=True)
                return self._var_type(name)
            case UnaryOp(op=Op.DECREMENT, operand=Ident(name=name)):
                self._gen_incdec(name, Opcode.DEC, prefix=True)
                return self._var_type(name)
            case PostfixOp(op=Op.INCREMENT, operand=Ident(name=name)):
                self._gen_incdec(name, Opcode.INC, prefix=False)
                return self._var_type(name)
            case PostfixOp(op=Op.DECREMENT, operand=Ident(name=name)):
                self._gen_incdec(name, Opcode.DEC, prefix=False)
                return self._var_type(name)

            case Call() as call:
                return self._gen_call(call)

            case _:
                msg = f"unhandled expression: {node!r}"
                raise CodeGenError(msg)

    def _gen_call(self, call: Call) -> str:
        match call:
            case Call(name="read", args=args):
                if args and isinstance(args[0], Ident) and args[0].name in self._input_devices:
                    if len(args) != 1:
                        msg = "read expects 0 or 1 device-label arg"
                        raise CodeGenError(msg)
                    dev = self._input_devices[args[0].name]
                    self._emit(Opcode.LOAD, dev.address)
                elif not args:
                    if self._current_interrupt_vector is None:
                        msg = "read() without a label can only be used inside an interrupt handler"
                        raise CodeGenError(msg)
                    vec_dev = self._inputs_by_vector.get(self._current_interrupt_vector)
                    if vec_dev is None:
                        msg = f"no input device configured for interrupt vector {self._current_interrupt_vector}"
                        raise CodeGenError(msg)
                    self._emit(Opcode.LOAD, vec_dev.address)
                else:
                    msg = "read expects 0 or 1 device-label arg"
                    raise CodeGenError(msg)
                return INT

            case Call(name="enable_interrupts"):
                self._emit(Opcode.EI)
                self._emit(Opcode.PUSH, 0)
                return INT

            case Call(name="disable_interrupts"):
                self._emit(Opcode.DI)
                self._emit(Opcode.PUSH, 0)
                return INT

            case Call(name="print", args=args):
                device, payload = self._resolve_output_device(args)
                for arg in payload:
                    if isinstance(arg, String):
                        addr = self._alloc_string(arg.value)
                        self._emit_cstr_loop(addr, device.address)
                    elif self._expr_type(arg) == LONG:
                        self._gen_as(arg, LONG)
                        self._emit(Opcode.STORE, device.address)
                        self._emit(Opcode.STORE, device.address)
                    else:
                        self._gen_as(arg, INT)
                        self._emit(Opcode.STORE, device.address)
                self._emit(Opcode.PUSH, 0)
                return INT

            case Call(name=name, args=args):
                if name in self._interrupt_names:
                    msg = f"interrupt handler '{name}' cannot be called directly"
                    raise CodeGenError(msg)
                lbl = self._fun_labels.get(name)
                if lbl is None:
                    msg = f"undefined function: {name!r}"
                    raise CodeGenError(msg)
                for arg in args:
                    self._gen_as(arg, INT)
                self._emit_jump(Opcode.CALL, lbl)
                if not self._fun_returns.get(name, False):
                    self._emit(Opcode.PUSH, 0)  # dummy for void functions
                    return INT
                return self._fun_return_types.get(name) or INT

            case _:
                msg = f"unhandled call: {call!r}"
                raise CodeGenError(msg)
