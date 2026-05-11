import pytest
from app.translator.analyzer import Analyzer, SemanticError
from app.translator.lexer import Lexer
from app.translator.parser import Parser


def analyze(source: str) -> list[SemanticError]:
    tokens = Lexer().tokenize(source)
    ast = Parser(tokens).parse()
    return Analyzer().analyze(ast)


def errors(source: str) -> list[str]:
    return [e.message for e in analyze(source)]


def ok(source: str) -> None:
    errs = errors(source)
    assert errs == [], f"unexpected errors: {errs}"


def has_error(source: str, fragment: str) -> None:
    errs = errors(source)
    assert any(fragment in e for e in errs), (
        f"expected error containing {fragment!r}, got: {errs}"
    )


def error_count(source: str) -> int:
    return len(errors(source))


# ---------------------------------------------------------------------------
# Declarations — valid
# ---------------------------------------------------------------------------

def test_const_decl_ok():
    ok("const x: int = 1;")


def test_var_decl_ok():
    ok("var x: int = 0;")


def test_var_bool():
    ok("var flag: bool = true;")


def test_var_string():
    ok('var msg: string = "hi";')


def test_byte_int_compat_decl():
    ok("const a: byte = 1; var b: int = a;")


# ---------------------------------------------------------------------------
# Declarations — errors
# ---------------------------------------------------------------------------

def test_duplicate_const():
    has_error("const x: int = 1; const x: int = 2;", "already declared")


def test_duplicate_var():
    has_error("var x: int = 1; var x: int = 2;", "already declared")


def test_type_mismatch_decl():
    has_error('const x: int = "hello";', "type mismatch")


def test_type_mismatch_bool_to_int():
    has_error("const x: int = true;", "type mismatch")


def test_type_mismatch_string_to_bool():
    has_error('var x: bool = "yes";', "type mismatch")


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def test_assign_ok():
    ok("var x: int = 0; x = 1;")


def test_assign_undefined():
    has_error("x = 1;", "undefined name 'x'")


def test_assign_to_const():
    has_error("const x: int = 1; x = 2;", "cannot assign to const 'x'")


def test_assign_type_mismatch():
    has_error('var x: int = 0; x = "str";', "type mismatch")


def test_assign_numeric_compat():
    ok("const a: byte = 1; var b: int = 0; b = a;")


# ---------------------------------------------------------------------------
# Scope — shadowing and nesting
# ---------------------------------------------------------------------------

def test_duplicate_in_same_scope():
    has_error("var x: int = 1; var x: bool = true;", "already declared")


def test_shadowing_in_nested_scope():
    ok("var x: int = 0; if (true) { var x: bool = true; }")


def test_inner_variable_not_visible_outside():
    has_error("if (true) { var x: int = 1; } var y: int = x;", "undefined name 'x'")


def test_outer_variable_visible_inside():
    ok("var x: int = 0; if (true) { x = 1; }")


# ---------------------------------------------------------------------------
# Undefined names
# ---------------------------------------------------------------------------

def test_use_before_decl():
    has_error("var x: int = y;", "undefined name 'y'")


def test_undefined_in_expr():
    has_error("var x: int = a + 1;", "undefined name 'a'")


def test_undefined_ident_in_assign():
    has_error("var x: int = 0; x = unknown;", "undefined name 'unknown'")


# ---------------------------------------------------------------------------
# Binary operators — type checks
# ---------------------------------------------------------------------------

def test_arithmetic_ok():
    ok("const a: int = 1; const b: int = 2; var c: int = a + b;")


def test_arithmetic_byte_int():
    ok("const a: byte = 1; const b: int = 2; var c: int = a + b;")


def test_arithmetic_on_bool():
    has_error("const a: bool = true; var b: int = a + 1;", "requires numeric operands")


def test_arithmetic_on_string():
    has_error('const a: string = "x"; var b: int = a + 1;', "requires numeric operands")


def test_comparison_ok():
    ok("const a: int = 1; const b: int = 2; var c: bool = a < b;")


def test_comparison_mixed_numeric():
    ok("const a: byte = 1; const b: int = 2; var c: bool = a < b;")


def test_comparison_type_mismatch():
    has_error('const a: int = 1; const b: string = "x"; var c: bool = a == b;', "cannot compare")


def test_logical_ok():
    ok("const a: bool = true; const b: bool = false; var c: bool = a && b;")


def test_logical_on_int():
    has_error("const a: int = 1; const b: bool = true; var c: bool = a && b;", "requires bool operands")


# ---------------------------------------------------------------------------
# Unary / postfix operators
# ---------------------------------------------------------------------------

def test_not_ok():
    ok("const a: bool = true; var b: bool = !a;")


def test_not_on_int():
    has_error("const a: int = 1; var b: bool = !a;", "'!' requires bool")


def test_prefix_incr_ok():
    ok("var x: int = 0; ++x;")


def test_postfix_incr_ok():
    ok("var x: int = 0; x++;")


def test_prefix_incr_on_const():
    has_error("const x: int = 0; ++x;", "cannot apply 'INCREMENT' to const")


def test_postfix_decr_on_const():
    has_error("const x: int = 0; x--;", "cannot apply 'DECREMENT' to const")


def test_incr_on_bool():
    has_error("var x: bool = true; ++x;", "requires a numeric variable")


def test_incr_on_string():
    has_error('var x: string = "hi"; x++;', "requires a numeric variable")


# ---------------------------------------------------------------------------
# Function declarations
# ---------------------------------------------------------------------------

def test_fun_no_params_ok():
    ok("fun f() {}")


def test_fun_params_ok():
    ok("fun f(int a, bool b) {}")


def test_fun_duplicate():
    has_error("fun f() {} fun f() {}", "already declared")


def test_fun_params_in_scope():
    ok("fun f(int x) { var y: int = x; }")


def test_fun_params_not_leaked():
    has_error("fun f(int x) {} var y: int = x;", "undefined name 'x'")


def test_fun_params_mutable():
    ok("fun f(int x) { x = 2; }")


# ---------------------------------------------------------------------------
# Function calls
# ---------------------------------------------------------------------------

def test_call_ok():
    ok("fun f(int a) {} f(1);")


def test_call_wrong_arity():
    has_error("fun f(int a) {} f(1, 2);", "expects 1 arg(s), got 2")


def test_call_undefined():
    has_error("g();", "undefined name 'g'")


def test_call_non_function():
    has_error("const x: int = 1; x();", "is not a function")


def test_builtin_print():
    ok('print("hello");')


def test_builtin_println():
    ok('println("world");')


# ---------------------------------------------------------------------------
# Control flow
# ---------------------------------------------------------------------------

def test_if_ok():
    ok("var x: int = 0; if (true) { x = 1; }")


def test_while_ok():
    ok("var x: int = 0; while (true) { x = 1; }")


def test_while_undefined_condition():
    has_error("while (z) {}", "undefined name 'z'")


def test_if_else_separate_scopes():
    ok("if (true) { var x: int = 1; } else { var x: bool = true; }")


def test_if_else_if_ok():
    ok("var a: bool = true; var b: bool = false; if (a) {} else if (b) {}")


# ---------------------------------------------------------------------------
# Multiple errors collected — analyzer does not stop at first error
# ---------------------------------------------------------------------------

def test_multiple_undefined():
    assert error_count("x = 1; y = 2;") == 2


def test_multiple_type_errors():
    assert error_count('const a: int = "x"; const b: bool = 1;') == 2


def test_errors_in_nested_scopes_collected():
    src = "if (true) { x = 1; } y = 2;"
    assert error_count(src) == 2


# ---------------------------------------------------------------------------
# Scope — while body
# ---------------------------------------------------------------------------

def test_while_body_scope():
    has_error("while (true) { var x: int = 0; } var y: int = x;", "undefined name 'x'")


def test_while_body_sees_outer():
    ok("var x: int = 0; while (true) { x = 1; }")


def test_while_body_mutable_check():
    has_error("const x: int = 0; while (true) { x = 1; }", "cannot assign to const")


# ---------------------------------------------------------------------------
# Scope — else/else-if isolation
# ---------------------------------------------------------------------------

def test_else_scope_isolated():
    has_error("if (true) {} else { var x: int = 1; } var y: int = x;", "undefined name 'x'")


def test_else_if_chain_ok():
    ok("""
    var a: bool = true;
    var b: bool = false;
    var c: bool = true;
    if (a) { var x: int = 1; } else if (b) { var x: int = 2; } else { var x: int = 3; }
    """)


def test_deeply_nested_scope():
    ok("var x: int = 0; while (true) { if (true) { x = 1; } }")


# ---------------------------------------------------------------------------
# Binary operators — parametrized
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op", ["+", "-", "*", "/"])
def test_arithmetic_all_ops_ok(op):
    ok(f"const a: int = 1; const b: int = 2; var c: int = a {op} b;")


@pytest.mark.parametrize("op", ["+", "-", "*", "/"])
def test_arithmetic_all_ops_on_bool_err(op):
    has_error(f"const a: bool = true; var b: int = a {op} 1;", "requires numeric operands")


@pytest.mark.parametrize("op", ["==", "!=", "<", ">", "<=", ">="])
def test_cmp_all_ops_ok(op):
    ok(f"const a: int = 1; const b: int = 2; var c: bool = a {op} b;")


@pytest.mark.parametrize("op", ["&&", "||", "^"])
def test_logic_all_ops_ok(op):
    ok(f"const a: bool = true; const b: bool = false; var c: bool = a {op} b;")


@pytest.mark.parametrize("op", ["&&", "||", "^"])
def test_logic_all_ops_on_int_err(op):
    has_error(f"const a: int = 1; const b: bool = true; var c: bool = a {op} b;", "requires bool operands")


# ---------------------------------------------------------------------------
# Type inference chains
# ---------------------------------------------------------------------------

def test_arithmetic_result_used_in_comparison():
    ok("const a: int = 1; const b: int = 2; var c: bool = a + b > 0;")


def test_comparison_result_used_in_logical():
    ok("const a: int = 1; const b: int = 2; var c: bool = a < b && b > 0;")


def test_nested_arithmetic():
    ok("const a: int = 1; const b: int = 2; const c: int = 3; var d: int = a + b * c;")


def test_int_declaration_from_comparison():
    has_error("const a: int = 1; const b: int = 2; const c: int = a < b;", "type mismatch")


def test_bool_declaration_from_arithmetic():
    has_error("const a: int = 1; const b: int = 2; const c: bool = a + b;", "type mismatch")


# ---------------------------------------------------------------------------
# Increment/decrement — all combinations
# ---------------------------------------------------------------------------

def test_prefix_decr_ok():
    ok("var x: int = 0; --x;")


def test_postfix_incr_on_undefined():
    has_error("x++;", "undefined name 'x'")


def test_prefix_incr_on_undefined():
    has_error("++x;", "undefined name 'x'")


def test_prefix_decr_on_const():
    has_error("const x: int = 0; --x;", "cannot apply 'DECREMENT' to const")


def test_postfix_incr_on_bool():
    has_error("var x: bool = true; x++;", "requires a numeric variable")


def test_decrement_byte():
    ok("var x: byte = 1; --x;")


# ---------------------------------------------------------------------------
# Function declarations — advanced
# ---------------------------------------------------------------------------

def test_fun_body_valid_stmts():
    ok("fun f(int a, int b) { var c: int = a + b; c = a; }")


def test_fun_recursive_call_ok():
    ok("fun f(int n) { f(n); }")


def test_fun_forward_reference_fails():
    # функция вызвана до объявления — анализатор обходит в порядке объявления
    has_error("f(); fun f() {}", "undefined name 'f'")


def test_fun_reuses_name_as_var():
    has_error("fun x() {} const x: int = 1;", "already declared")


def test_fun_call_zero_args_no_params():
    ok("fun f() {} f();")


def test_fun_call_too_few_args():
    has_error("fun f(int a, int b) {} f(1);", "expects 2 arg(s), got 1")


def test_fun_call_zero_args_when_expected():
    has_error("fun f(int a) {} f();", "expects 1 arg(s), got 0")


def test_fun_call_nested():
    ok("fun f(int a) {} fun g(int b) { f(b); }")


def test_fun_body_undefined():
    has_error("fun f() { x = 1; }", "undefined name 'x'")


# ---------------------------------------------------------------------------
# Call expressions
# ---------------------------------------------------------------------------

def test_call_result_in_expr():
    ok("fun f(int a) {} var x: int = 0; x = x + 0;")


def test_call_as_arg():
    ok("fun id(int a) {} id(id(1));")


# ---------------------------------------------------------------------------
# Literal type inference
# ---------------------------------------------------------------------------

def test_number_infers_int():
    ok("const x: int = 42;")


def test_bool_true_infers_bool():
    ok("const x: bool = true;")


def test_bool_false_infers_bool():
    ok("const x: bool = false;")


def test_string_infers_string():
    ok('const x: string = "hello";')


def test_number_not_byte():
    # byte ↔ int совместимы — числовое расширение
    ok("const x: byte = 42;")


# ---------------------------------------------------------------------------
# Full example
# ---------------------------------------------------------------------------

def test_example_errors():
    src = open("examples/example.cube").read()
    errs = errors(src)
    # const a++ и a-- невалидны, !(a+b) применяет ! к int
    messages = "\n".join(errs)
    assert "cannot apply 'INCREMENT' to const 'a'" in messages
    assert "cannot apply 'DECREMENT' to const 'a'" in messages
    assert "'!' requires bool" in messages
