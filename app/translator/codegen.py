from __future__ import annotations

from dataclasses import dataclass

from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.translator.nodes import (
    AssignStmt, BinaryOp, Block, Bool, Call, ConstDecl,
    ExprStmt, FunDecl, Ident, IfStmt, Number, PostfixOp,
    Program, ReturnStmt, String, UnaryOp, VarDecl, WhileStmt,
)

_BUILTINS = frozenset({"print", "println"})

MMIO_OUT_ADDR = 0x222

# Comparison op name → conditional jump opcode for the TRUE branch
_CMP_JUMP: dict[str, Opcode] = {
    "EQUAL":                 Opcode.JZ,
    "NOT_EQUAL":             Opcode.JNZ,
    "LESS_THAN":             Opcode.JL,
    "GREATER_THAN":          Opcode.JG,
    "LESS_THAN_OR_EQUAL":    Opcode.JLE,
    "GREATER_THAN_OR_EQUAL": Opcode.JGE,
}

_ARITH_OP: dict[str, Opcode] = {
    "PLUS":  Opcode.ADD,
    "MINUS": Opcode.SUB,
    "STAR":  Opcode.MUL,
    "SLASH": Opcode.DIV,
    "AND":   Opcode.AND,
    "OR":    Opcode.OR,
    "XOR":   Opcode.XOR,
}


@dataclass
class CompiledProgram:
    instructions: list[int]
    data: list[int]


class CodeGenError(Exception):
    pass


class CodeGen:
    def __init__(self) -> None:
        self._instrs: list[Instruction] = []
        self._scopes: list[dict[str, int]] = [{}]
        self._data: list[int] = []
        self._data_size: int = 0
        self._const_values: dict[int, int] = {}
        self._fun_labels: dict[str, str] = {}
        self._fun_returns: dict[str, bool] = {}
        self._labels: dict[str, int] = {}
        self._patches: list[tuple[int, str]] = []
        self._label_count: int = 0

    # --- public API --------------------------------------------------------

    def generate(self, program: Program) -> CompiledProgram:
        entry_idx = len(self._instrs)
        self._emit(Opcode.CALL, 0)   # patched to main's address
        self._emit(Opcode.HALT)
        self._gen(program)
        main_label = self._fun_labels.get("main")
        if main_label is None:
            raise CodeGenError("missing entry point: function 'main' is required")
        self._patches.append((entry_idx, main_label))
        self._backpatch()
        return CompiledProgram(
            instructions=[i.to_binary() for i in self._instrs],
            data=self._data,
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
            addr = self._labels[label]
            instr = self._instrs[idx]
            self._instrs[idx] = Instruction(instr.opcode, addr)

    # --- scope / variable helpers ------------------------------------------

    def _push_scope(self) -> None:
        self._scopes.append({})

    def _pop_scope(self) -> None:
        self._scopes.pop()

    def _alloc_var(self, name: str) -> int:
        addr = self._data_size
        self._scopes[-1][name] = addr
        self._data_size += 1
        self._data.append(0)
        return addr

    def _alloc_string(self, s: str) -> int:
        addr = self._data_size
        for ch in s:
            self._data.append(ord(ch))
            self._data_size += 1
        self._data.append(0)
        self._data_size += 1
        return addr

    def _emit_cstr_loop(self, addr: int) -> None:
        lbl_loop = self._fresh_label()
        lbl_exit = self._fresh_label()
        self._emit(Opcode.PUSH, addr)
        self._mark_label(lbl_loop)
        self._emit(Opcode.DUP)
        self._emit(Opcode.LOADI)
        self._emit_jump(Opcode.JZ, lbl_exit)
        self._emit(Opcode.STORE, MMIO_OUT_ADDR)
        self._emit(Opcode.INC)
        self._emit_jump(Opcode.JMP, lbl_loop)
        self._mark_label(lbl_exit)
        self._emit(Opcode.DROP)
        self._emit(Opcode.DROP)

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
                    case "PLUS":                  return lv + rv
                    case "MINUS":                 return lv - rv
                    case "STAR":                  return lv * rv
                    case "SLASH":                 return lv // rv if rv != 0 else None
                    case "AND":                   return lv & rv
                    case "OR":                    return lv | rv
                    case "XOR":                   return lv ^ rv
                    case "EQUAL":                 return int(lv == rv)
                    case "NOT_EQUAL":             return int(lv != rv)
                    case "LESS_THAN":             return int(lv < rv)
                    case "GREATER_THAN":          return int(lv > rv)
                    case "LESS_THAN_OR_EQUAL":    return int(lv <= rv)
                    case "GREATER_THAN_OR_EQUAL": return int(lv >= rv)
                    case _:                       return None
            case UnaryOp(op="NOT", operand=e):
                v = self._static_eval(e)
                return None if v is None else int(v == 0)
            case _:
                return None

    def _var_addr(self, name: str) -> int:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        raise CodeGenError(f"undefined variable: {name!r}")

    # --- flag-test helper (condition → flags, stack cleared) ---------------

    def _emit_flag_test(self) -> None:
        """After gen(cond): TOS = value. Sets FLAGS = value, clears stack."""
        self._emit(Opcode.PUSH, 0)   # 0:value
        self._emit(Opcode.CMP)        # FLAGS = value - 0; stack: 0:value
        self._emit(Opcode.DROP)       # stack: value
        self._emit(Opcode.DROP)       # stack: empty

    # --- main visitor ------------------------------------------------------

    def _gen(self, node: object) -> None:  # noqa: PLR0912, PLR0915
        match node:

            # ----------------------------------------------------------------
            # Program
            # ----------------------------------------------------------------
            case Program(body=body):
                for stmt in body:
                    self._gen(stmt)

            # ----------------------------------------------------------------
            # Declarations
            # ----------------------------------------------------------------
            case ConstDecl(name=name, value=value):
                addr = self._alloc_var(name)
                sv = self._static_eval(value)
                if sv is not None:
                    self._data[addr] = sv
                    self._const_values[addr] = sv
                else:
                    self._gen(value)
                    self._emit(Opcode.STORE, addr)

            case VarDecl(name=name, value=value):
                addr = self._alloc_var(name)
                sv = self._static_eval(value)
                if sv is not None:
                    self._data[addr] = sv
                else:
                    self._gen(value)
                    self._emit(Opcode.STORE, addr)

            # ----------------------------------------------------------------
            # Statements
            # ----------------------------------------------------------------
            case AssignStmt(name=name, value=value):
                self._gen(value)
                self._emit(Opcode.STORE, self._var_addr(name))

            case ExprStmt(expr=e):
                self._gen(e)
                self._emit(Opcode.DROP)

            case Block(body=stmts):
                for stmt in stmts:
                    self._gen(stmt)

            case IfStmt(condition=cond, then_block=then_block, else_branch=else_branch):
                lbl_else = self._fresh_label()
                lbl_end  = self._fresh_label()
                if cond is not None:
                    self._gen(cond)
                    self._emit_flag_test()
                    self._emit_jump(Opcode.JZ, lbl_else)
                self._gen(then_block)
                self._emit_jump(Opcode.JMP, lbl_end)
                self._mark_label(lbl_else)
                if else_branch is not None:
                    self._gen(else_branch)
                self._mark_label(lbl_end)

            case WhileStmt(condition=cond, body=body):
                lbl_loop = self._fresh_label()
                lbl_end  = self._fresh_label()
                self._mark_label(lbl_loop)
                self._gen(cond)
                self._emit_flag_test()
                self._emit_jump(Opcode.JZ, lbl_end)
                self._gen(body)
                self._emit_jump(Opcode.JMP, lbl_loop)
                self._mark_label(lbl_end)

            case FunDecl(name=name, params=params, body=body, return_type=rt):
                lbl_fun  = self._fresh_label()
                lbl_skip = self._fresh_label()
                self._fun_labels[name] = lbl_fun
                self._fun_returns[name] = rt is not None
                self._emit_jump(Opcode.JMP, lbl_skip)
                self._mark_label(lbl_fun)
                self._push_scope()
                # Caller pushed args left-to-right; TOS = last arg.
                # Pop into param memory in reverse order.
                for _type, param_name in reversed(params):
                    addr = self._alloc_var(param_name)
                    self._emit(Opcode.STORE, addr)
                self._gen(body)
                if rt is not None:
                    self._emit(Opcode.PUSH, 0)   # fallback return value
                self._emit(Opcode.RET)
                self._pop_scope()
                self._mark_label(lbl_skip)

            # ----------------------------------------------------------------
            # Expressions — atoms
            # ----------------------------------------------------------------
            case Number(value=v):
                self._emit(Opcode.PUSH, v)

            case Bool(value=v):
                self._emit(Opcode.PUSH, 1 if v else 0)

            case String():
                self._emit(Opcode.PUSH, 0)   # strings not supported

            case Ident(name=name):
                addr = self._var_addr(name)
                cv = self._const_values.get(addr)
                if cv is not None:
                    self._emit(Opcode.PUSH, cv)
                else:
                    self._emit(Opcode.LOAD, addr)

            # ----------------------------------------------------------------
            # Expressions — binary
            # ----------------------------------------------------------------
            case BinaryOp(op=op, left=left, right=right) if op in _ARITH_OP:
                self._gen(left)
                self._gen(right)
                self._emit(_ARITH_OP[op])

            case BinaryOp(op=op, left=left, right=right) if op in _CMP_JUMP:
                # gen(l); gen(r): NOS=l, TOS=r  →  CMP computes l−r
                lbl_true = self._fresh_label()
                lbl_end  = self._fresh_label()
                self._gen(left)
                self._gen(right)
                self._emit(Opcode.CMP)          # FLAGS = l−r; stack: r:l
                self._emit(Opcode.DROP)         # stack: l
                self._emit(Opcode.DROP)         # stack: empty
                self._emit_jump(_CMP_JUMP[op], lbl_true)
                self._emit(Opcode.PUSH, 0)
                self._emit_jump(Opcode.JMP, lbl_end)
                self._mark_label(lbl_true)
                self._emit(Opcode.PUSH, 1)
                self._mark_label(lbl_end)

            # ----------------------------------------------------------------
            # Expressions — unary
            # ----------------------------------------------------------------
            case UnaryOp(op="NOT", operand=operand):
                lbl_true = self._fresh_label()
                lbl_end  = self._fresh_label()
                self._gen(operand)
                self._emit_flag_test()          # FLAGS = operand; stack empty
                self._emit_jump(Opcode.JZ, lbl_true)   # if operand==0: true
                self._emit(Opcode.PUSH, 0)
                self._emit_jump(Opcode.JMP, lbl_end)
                self._mark_label(lbl_true)
                self._emit(Opcode.PUSH, 1)
                self._mark_label(lbl_end)

            case UnaryOp(op="INCREMENT", operand=Ident(name=name)):
                addr = self._var_addr(name)
                self._emit(Opcode.LOAD, addr)
                self._emit(Opcode.INC)
                self._emit(Opcode.DUP)
                self._emit(Opcode.STORE, addr)

            case UnaryOp(op="DECREMENT", operand=Ident(name=name)):
                addr = self._var_addr(name)
                self._emit(Opcode.LOAD, addr)
                self._emit(Opcode.DEC)
                self._emit(Opcode.DUP)
                self._emit(Opcode.STORE, addr)

            case PostfixOp(op="INCREMENT", operand=Ident(name=name)):
                addr = self._var_addr(name)
                self._emit(Opcode.LOAD, addr)
                self._emit(Opcode.DUP)
                self._emit(Opcode.INC)
                self._emit(Opcode.STORE, addr)

            case PostfixOp(op="DECREMENT", operand=Ident(name=name)):
                addr = self._var_addr(name)
                self._emit(Opcode.LOAD, addr)
                self._emit(Opcode.DUP)
                self._emit(Opcode.DEC)
                self._emit(Opcode.STORE, addr)

            # ----------------------------------------------------------------
            # Expressions — calls
            # ----------------------------------------------------------------
            case ReturnStmt(value=value):
                if value is not None:
                    self._gen(value)
                self._emit(Opcode.RET)

            case Call(name=name, args=args) if name in _BUILTINS:
                for arg in args:
                    if isinstance(arg, String):
                        addr = self._alloc_string(arg.value)
                        self._emit_cstr_loop(addr)
                    else:
                        self._gen(arg)
                        self._emit(Opcode.STORE, MMIO_OUT_ADDR)
                if name == "println":
                    self._emit(Opcode.PUSH, ord('\n'))
                    self._emit(Opcode.STORE, MMIO_OUT_ADDR)
                self._emit(Opcode.PUSH, 0)   # dummy return value

            case Call(name=name, args=args):
                lbl = self._fun_labels.get(name)
                if lbl is None:
                    raise CodeGenError(f"undefined function: {name!r}")
                for arg in args:
                    self._gen(arg)
                self._emit_jump(Opcode.CALL, lbl)
                if not self._fun_returns.get(name, False):
                    self._emit(Opcode.PUSH, 0)   # dummy for void functions

            case _:
                raise CodeGenError(f"unhandled node: {node!r}")
