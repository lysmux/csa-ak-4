import pytest

from app.isa.instruction import Instruction
from app.isa.opcode import Opcode
from app.translator.codegen import CodeGen, CodeGenError, CompiledProgram
from app.translator.lexer import Lexer
from app.translator.parser import Parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compile(src: str) -> CompiledProgram:
    tokens = Lexer().tokenize(src)
    ast = Parser(tokens).parse()
    return CodeGen().generate(ast)


def instrs(src: str) -> list[Instruction]:
    return [Instruction.from_binary(w) for w in compile(src).instructions]


def opcodes(src: str) -> list[Opcode]:
    return [i.opcode for i in instrs(src)]


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------

def test_halt_always_last():
    for src in ["", "var x: int = 1;", "fun f() {}", "while (true) { var x: int = 1; }"]:
        assert instrs(src)[-1].opcode == Opcode.HALT


def test_empty_program():
    assert opcodes("") == [Opcode.HALT]


# ---------------------------------------------------------------------------
# Literals — статическая инициализация в data[]
# ---------------------------------------------------------------------------

def test_number_static_init():
    # Значение известно → прямо в data, без PUSH/STORE
    result = compile("const x: int = 42;")
    assert result.data == [42]
    assert opcodes("const x: int = 42;") == [Opcode.HALT]


def test_bool_true_static_init():
    result = compile("const x: bool = true;")
    assert result.data == [1]


def test_bool_false_static_init():
    result = compile("const x: bool = false;")
    assert result.data == [0]


def test_string_push_zero():
    # Строки не вычисляются статически → PUSH 0; STORE
    i = instrs('const x: int = "hello";')
    assert i[0] == Instruction(Opcode.PUSH, 0)


# ---------------------------------------------------------------------------
# Variable allocation and addressing
# ---------------------------------------------------------------------------

def test_first_var_addr_zero():
    # var с литералом → static init, data[0] = 1
    result = compile("var x: int = 1;")
    assert result.data == [1]
    assert opcodes("var x: int = 1;") == [Opcode.HALT]


def test_second_var_addr_one():
    result = compile("var a: int = 1; var b: int = 2;")
    assert result.data == [1, 2]


def test_data_section_size():
    result = compile("var a: int = 1; var b: int = 2; var c: int = 3;")
    assert len(result.data) == 3


def test_data_section_static_init():
    result = compile("var x: int = 99;")
    assert result.data == [99]


def test_ident_load():
    # var x = 5 → data[0]=5 без кода; var y = x → LOAD x; STORE y
    i = instrs("var x: int = 5; var y: int = x;")
    assert i[0] == Instruction(Opcode.LOAD, 0)   # x — var, не const
    assert i[1] == Instruction(Opcode.STORE, 1)


def test_shadowing_allocates_new_addr():
    result = compile("var x: int = 1; if (true) { var x: int = 2; }")
    assert len(result.data) == 2


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def test_assign_stores_to_correct_addr():
    # var x = 0 → static init; x = 7 → PUSH 7; STORE 0
    i = instrs("var x: int = 0; x = 7;")
    assert i[0] == Instruction(Opcode.PUSH, 7)
    assert i[1] == Instruction(Opcode.STORE, 0)


# ---------------------------------------------------------------------------
# ExprStmt — always drops result
# ---------------------------------------------------------------------------

def test_expr_stmt_drops():
    i = instrs("var x: int = 1; x + 2;")
    # last before HALT is DROP
    assert i[-2].opcode == Opcode.DROP


# ---------------------------------------------------------------------------
# Arithmetic binary operators
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op,expected_opcode", [
    ("+", Opcode.ADD),
    ("-", Opcode.SUB),
    ("*", Opcode.MUL),
    ("/", Opcode.DIV),
])
def test_arithmetic_ops(op, expected_opcode):
    src = f"var a: int = 2; var b: int = 3; var c: int = a {op} b;"
    assert expected_opcode in opcodes(src)


@pytest.mark.parametrize("op,expected_opcode", [
    ("&&", Opcode.AND),
    ("||", Opcode.OR),
    ("^",  Opcode.XOR),
])
def test_logical_ops(op, expected_opcode):
    # var операнды — не вычисляются статически → опкод в инструкциях
    src = f"var a: bool = true; var b: bool = false; var c: bool = a {op} b;"
    assert expected_opcode in opcodes(src)


def test_arithmetic_operand_order():
    # a - b: gen(a); gen(b); SUB → NOS-TOS = a-b
    i = instrs("var a: int = 5; var b: int = 3; var c: int = a - b;")
    sub_idx = next(j for j, x in enumerate(i) if x.opcode == Opcode.SUB)
    # The two LOADs must come before SUB
    assert i[sub_idx - 2].opcode == Opcode.LOAD   # a
    assert i[sub_idx - 1].opcode == Opcode.LOAD   # b


# ---------------------------------------------------------------------------
# Comparison operators
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op,jump", [
    ("==", Opcode.JZ),
    ("!=", Opcode.JNZ),
    ("<",  Opcode.JL),
    (">",  Opcode.JG),
    ("<=", Opcode.JLE),
    (">=", Opcode.JGE),
])
def test_comparison_uses_cmp_and_jump(op, jump):
    src = f"var a: int = 1; var b: int = 2; var c: bool = a {op} b;"
    ops = opcodes(src)
    assert Opcode.CMP in ops
    assert jump in ops


def test_comparison_result_is_0_or_1():
    # After gen(l > r): sequence ends with PUSH 0 (false) or PUSH 1 (true)
    i = instrs("var a: int = 5; var b: int = 3; var c: bool = a > b;")
    pushes = [x.operand for x in i if x.opcode == Opcode.PUSH]
    # Should have PUSH 0 (false branch) and PUSH 1 (true branch)
    assert 0 in pushes
    assert 1 in pushes


# ---------------------------------------------------------------------------
# Logical NOT
# ---------------------------------------------------------------------------

def test_not_uses_jz():
    # var операнд — NOT не вычисляется статически → JZ в инструкциях
    assert Opcode.JZ in opcodes("var x: bool = true; var y: bool = !x;")


def test_not_result_inverts():
    # !x (x — var) → JZ → PUSH 1 если x == 0
    i = instrs("var x: bool = true; var y: bool = !x;")
    jz = next(x for x in i if x.opcode == Opcode.JZ)
    assert i[jz.operand].opcode == Opcode.PUSH
    assert i[jz.operand].operand == 1


# ---------------------------------------------------------------------------
# Prefix and postfix increment/decrement
# ---------------------------------------------------------------------------

def test_prefix_inc_sequence():
    i = instrs("var x: int = 0; ++x;")
    ops = [x.opcode for x in i]
    # Must appear: LOAD, INC, DUP, STORE (prefix: new value on stack)
    idx = ops.index(Opcode.INC)
    assert ops[idx - 1] == Opcode.LOAD
    assert ops[idx + 1] == Opcode.DUP
    assert ops[idx + 2] == Opcode.STORE


def test_postfix_inc_sequence():
    i = instrs("var x: int = 0; x++;")
    ops = [x.opcode for x in i]
    # Must appear: LOAD, DUP, INC, STORE (postfix: old value on stack)
    idx = ops.index(Opcode.INC)
    assert ops[idx - 2] == Opcode.LOAD
    assert ops[idx - 1] == Opcode.DUP
    assert ops[idx + 1] == Opcode.STORE


def test_prefix_dec_sequence():
    i = instrs("var x: int = 0; --x;")
    ops = [x.opcode for x in i]
    idx = ops.index(Opcode.DEC)
    assert ops[idx - 1] == Opcode.LOAD
    assert ops[idx + 1] == Opcode.DUP


def test_postfix_dec_sequence():
    i = instrs("var x: int = 0; x--;")
    ops = [x.opcode for x in i]
    idx = ops.index(Opcode.DEC)
    assert ops[idx - 2] == Opcode.LOAD
    assert ops[idx - 1] == Opcode.DUP


# ---------------------------------------------------------------------------
# if / else
# ---------------------------------------------------------------------------

def test_if_contains_jz_and_jmp():
    ops = opcodes("var x: int = 0; if (true) { x = 1; }")
    assert Opcode.JZ in ops
    assert Opcode.JMP in ops


def test_if_jz_jumps_past_then():
    # With else: JZ jumps to lbl_else = instruction right after the then→end JMP
    i = instrs("var x: int = 0; if (true) { x = 1; } else { x = 2; }")
    jmp_idx = next(j for j, x in enumerate(i) if x.opcode == Opcode.JMP)
    jz = next(x for x in i if x.opcode == Opcode.JZ)
    assert jz.operand == jmp_idx + 1   # else block starts right after JMP


def test_if_else_both_branches():
    i = instrs("var x: int = 0; if (true) { x = 1; } else { x = 2; }")
    # There should be exactly one JZ (condition test) and one JMP (then→end)
    jz_count  = sum(1 for x in i if x.opcode == Opcode.JZ)
    jmp_count = sum(1 for x in i if x.opcode == Opcode.JMP)
    assert jz_count == 1
    assert jmp_count == 1


def test_if_no_else_no_else_code():
    i_without = instrs("var x: int = 0; if (true) { x = 1; }")
    i_with    = instrs("var x: int = 0; if (true) { x = 1; } else { x = 2; }")
    # With else has more instructions
    assert len(i_with) > len(i_without)


def test_if_empty_condition_no_condition_code():
    # if () {} — cond is None, no flag-test code emitted
    i = instrs("if () {}")
    # Only JMP (skip else) and HALT — no CMP/JZ from condition
    assert Opcode.JZ not in [x.opcode for x in i]


def test_else_if_chain():
    ops = opcodes("var a: bool = true; var b: bool = false; if (a) { } else if (b) { }")
    # Two conditions → two JZ instructions
    assert ops.count(Opcode.JZ) == 2


# ---------------------------------------------------------------------------
# while loop
# ---------------------------------------------------------------------------

def test_while_contains_jz_and_jmp():
    ops = opcodes("var x: int = 0; while (false) {}")
    assert Opcode.JZ in ops
    assert Opcode.JMP in ops


def test_while_jmp_is_backward():
    # The loop-back JMP must point to an address BEFORE itself
    i = instrs("var x: int = 5; while (x > 0) { x = x - 1; }")
    jmps = [(idx, x) for idx, x in enumerate(i) if x.opcode == Opcode.JMP]
    # At least one JMP jumps backward (loop back)
    assert any(x.operand < idx for idx, x in jmps)


def test_while_jz_exits_loop():
    # JZ (exit) must point past the loop-back JMP
    i = instrs("var x: int = 0; while (false) { x = 1; }")
    jz = next(x for x in i if x.opcode == Opcode.JZ)
    last_jmp = max(idx for idx, x in enumerate(i) if x.opcode == Opcode.JMP)
    assert jz.operand > last_jmp


# ---------------------------------------------------------------------------
# Function declarations
# ---------------------------------------------------------------------------

def test_fun_starts_with_jmp():
    # First instruction must be JMP (skip over body)
    i = instrs("fun f() {}")
    assert i[0].opcode == Opcode.JMP


def test_fun_body_ends_with_ret():
    i = instrs("fun f() {}")
    assert any(x.opcode == Opcode.RET for x in i)


def test_fun_jmp_skips_to_after_ret():
    i = instrs("fun f() {}")
    jmp = i[0]                                   # JMP lbl_skip
    ret_idx = next(j for j, x in enumerate(i) if x.opcode == Opcode.RET)
    assert jmp.operand == ret_idx + 1            # skip label is right after RET


def test_fun_params_stored_in_prologue():
    i = instrs("fun f(int a, int b) {} f(1, 2);")
    # Function prologue: two STORE instructions (one per param)
    ret_idx = next(j for j, x in enumerate(i) if x.opcode == Opcode.RET)
    jmp_idx = 0  # first instruction
    body_range = i[jmp_idx + 1 : ret_idx]
    stores = [x for x in body_range if x.opcode == Opcode.STORE]
    assert len(stores) == 2


def test_fun_params_get_data_addrs():
    i = instrs("fun f(int a) {} f(1);")
    # param 'a' must be stored at some data addr
    prologue_store = next(x for x in i if x.opcode == Opcode.STORE)
    assert prologue_store.operand >= 0


# ---------------------------------------------------------------------------
# Function calls
# ---------------------------------------------------------------------------

def test_call_uses_call_opcode():
    assert Opcode.CALL in opcodes("fun f() {} f();")


def test_call_target_is_function_entry():
    i = instrs("fun f() {} f();")
    call = next(x for x in i if x.opcode == Opcode.CALL)
    # CALL target must point to instruction after JMP (= function entry)
    jmp = i[0]   # JMP lbl_skip
    # function entry is instruction 1 (right after the JMP)
    assert call.operand == 1


def test_call_followed_by_push_zero():
    # Call always leaves a dummy 0 on stack
    i = instrs("fun f() {} f();")
    call_idx = next(j for j, x in enumerate(i) if x.opcode == Opcode.CALL)
    assert i[call_idx + 1] == Instruction(Opcode.PUSH, 0)


def test_call_args_pushed_in_order():
    i = instrs("fun f(int a, int b) {} f(10, 20);")
    call_idx = next(j for j, x in enumerate(i) if x.opcode == Opcode.CALL)
    # Two PUSH before CALL: 10 then 20
    arg_pushes = [x for x in i[:call_idx] if x.opcode == Opcode.PUSH]
    assert arg_pushes[-2].operand == 10
    assert arg_pushes[-1].operand == 20


# ---------------------------------------------------------------------------
# Built-in calls
# ---------------------------------------------------------------------------

def test_builtin_print_no_call():
    assert Opcode.CALL not in opcodes('print("x");')


def test_builtin_println_drops_arg():
    i = instrs('println("hello");')
    # arg is pushed (PUSH 0 for string) then DROPped
    ops = [x.opcode for x in i]
    push_idx = ops.index(Opcode.PUSH)
    assert ops[push_idx + 1] == Opcode.DROP


def test_builtin_leaves_push_zero():
    # builtin → PUSH 0 (dummy return) → ExprStmt DROP
    i = instrs('print("x");')
    # should have DROP as second-to-last before HALT
    assert i[-2].opcode == Opcode.DROP


# ---------------------------------------------------------------------------
# Backpatching correctness
# ---------------------------------------------------------------------------

def test_all_jump_targets_in_range():
    src = """
    var x: int = 5;
    if (x > 3) { x = 1; } else { x = 2; }
    while (x > 0) { x = x - 1; }
    """
    i = instrs(src)
    n = len(i)
    jump_ops = {Opcode.JMP, Opcode.JZ, Opcode.JNZ, Opcode.JG, Opcode.JL,
                Opcode.JGE, Opcode.JLE, Opcode.CALL}
    for instr in i:
        if instr.opcode in jump_ops:
            assert 0 <= instr.operand < n, (
                f"jump target {instr.operand} out of range [0, {n})"
            )


# ---------------------------------------------------------------------------
# Full example compiles without error
# ---------------------------------------------------------------------------

def test_full_example_compiles():
    src = open("examples/example.cube").read()
    result = compile(src)
    assert len(result.instructions) > 0
    assert Instruction.from_binary(result.instructions[-1]).opcode == Opcode.HALT


def test_full_example_instruction_count():
    src = open("examples/example.cube").read()
    result = compile(src)
    assert len(result.instructions) == 83


def test_full_example_data_count():
    src = open("examples/example.cube").read()
    result = compile(src)
    assert len(result.data) == 5


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

def test_undefined_var_raises():
    from app.translator.nodes import Program, ExprStmt, Ident
    prog = Program([ExprStmt(Ident("unknown"))])
    with pytest.raises(CodeGenError, match="undefined variable"):
        CodeGen().generate(prog)


def test_undefined_function_raises():
    from app.translator.nodes import Program, ExprStmt, Call
    prog = Program([ExprStmt(Call("no_such_fun", []))])
    with pytest.raises(CodeGenError, match="undefined function"):
        CodeGen().generate(prog)
