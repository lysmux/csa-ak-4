import pytest
from app.translator.lexer import Lexer
from app.translator.nodes import (
    AssignStmt,
    BinaryOp,
    Block,
    Bool,
    Call,
    ConstDecl,
    FunDecl,
    Ident,
    IfStmt,
    Number,
    PostfixOp,
    Program,
    String,
    UnaryOp,
    VarDecl,
    WhileStmt,
)
from app.translator.parser import ParseError, Parser


def parse(source: str) -> Program:
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def stmt(source: str):
    return parse(source).body[0]


def expr(source: str):
    return stmt(source + ";").expr


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------

def test_const_decl():
    assert stmt("const x: int = 42;") == ConstDecl(
        name="x", type_name="int", value=Number(42)
    )


def test_var_decl():
    assert stmt("var y: byte = 0;") == VarDecl(
        name="y", type_name="byte", value=Number(0)
    )


def test_const_decl_string_value():
    assert stmt('const msg: string = "hi";') == ConstDecl(
        name="msg", type_name="string", value=String('hi')
    )


def test_var_decl_bool_value():
    assert stmt("var flag: bool = true;") == VarDecl(
        name="flag", type_name="bool", value=Bool(True)
    )


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------

def test_assign_stmt():
    assert stmt("x = 1;") == AssignStmt(name="x", value=Number(1))


def test_assign_expr():
    assert stmt("x = a + b;") == AssignStmt(
        name="x",
        value=BinaryOp("PLUS", Ident("a"), Ident("b")),
    )


# ---------------------------------------------------------------------------
# Expressions — literals & atoms
# ---------------------------------------------------------------------------

def test_number():
    assert expr("42") == Number(42)


def test_string():
    assert expr('"hello"') == String('hello')


def test_true():
    assert expr("true") == Bool(True)


def test_false():
    assert expr("false") == Bool(False)


def test_ident():
    assert expr("x") == Ident("x")


def test_grouped():
    assert expr("(1)") == Number(1)


# ---------------------------------------------------------------------------
# Expressions — binary operators & precedence
# ---------------------------------------------------------------------------

def test_addition():
    assert expr("a + b") == BinaryOp("PLUS", Ident("a"), Ident("b"))


def test_precedence_mul_over_add():
    # a + b * c  →  a + (b * c)
    assert expr("a + b * c") == BinaryOp(
        "PLUS",
        Ident("a"),
        BinaryOp("STAR", Ident("b"), Ident("c")),
    )


def test_precedence_add_over_cmp():
    # a + b > c  →  (a + b) > c
    assert expr("a + b > c") == BinaryOp(
        "GREATER_THAN",
        BinaryOp("PLUS", Ident("a"), Ident("b")),
        Ident("c"),
    )


def test_precedence_cmp_over_eq():
    # a < b == c < d  →  (a < b) == (c < d)
    assert expr("a < b == c < d") == BinaryOp(
        "EQUAL",
        BinaryOp("LESS_THAN", Ident("a"), Ident("b")),
        BinaryOp("LESS_THAN", Ident("c"), Ident("d")),
    )


def test_precedence_eq_over_and():
    # a == b && c != d  →  (a == b) && (c != d)
    assert expr("a == b && c != d") == BinaryOp(
        "AND",
        BinaryOp("EQUAL", Ident("a"), Ident("b")),
        BinaryOp("NOT_EQUAL", Ident("c"), Ident("d")),
    )


def test_precedence_and_over_or():
    # a || b && c  →  a || (b && c)
    assert expr("a || b && c") == BinaryOp(
        "OR",
        Ident("a"),
        BinaryOp("AND", Ident("b"), Ident("c")),
    )


def test_left_associativity():
    # a - b - c  →  (a - b) - c
    assert expr("a - b - c") == BinaryOp(
        "MINUS",
        BinaryOp("MINUS", Ident("a"), Ident("b")),
        Ident("c"),
    )


def test_parens_override_precedence():
    # (a + b) * c
    assert expr("(a + b) * c") == BinaryOp(
        "STAR",
        BinaryOp("PLUS", Ident("a"), Ident("b")),
        Ident("c"),
    )


@pytest.mark.parametrize("op,name", [
    ("==", "EQUAL"), ("!=", "NOT_EQUAL"),
    ("<",  "LESS_THAN"), (">",  "GREATER_THAN"),
    ("<=", "LESS_THAN_OR_EQUAL"), (">=", "GREATER_THAN_OR_EQUAL"),
    ("&&", "AND"), ("||", "OR"), ("^", "XOR"),
    ("+",  "PLUS"), ("-",  "MINUS"),
    ("*",  "STAR"), ("/",  "SLASH"),
])
def test_binary_operators(op, name):
    assert expr(f"a {op} b") == BinaryOp(name, Ident("a"), Ident("b"))


# ---------------------------------------------------------------------------
# Expressions — unary / postfix
# ---------------------------------------------------------------------------

def test_prefix_not():
    assert expr("!a") == UnaryOp("NOT", Ident("a"))


def test_prefix_increment():
    assert expr("++x") == UnaryOp("INCREMENT", Ident("x"))


def test_prefix_decrement():
    assert expr("--x") == UnaryOp("DECREMENT", Ident("x"))


def test_postfix_increment():
    assert expr("x++") == PostfixOp("INCREMENT", Ident("x"))


def test_postfix_decrement():
    assert expr("x--") == PostfixOp("DECREMENT", Ident("x"))


def test_postfix_binds_tighter_than_mul():
    # x++ * y  →  (x++) * y
    assert expr("x++ * y") == BinaryOp(
        "STAR", PostfixOp("INCREMENT", Ident("x")), Ident("y")
    )


def test_not_binds_tighter_than_and():
    # !a && b  →  (!a) && b
    assert expr("!a && b") == BinaryOp("AND", UnaryOp("NOT", Ident("a")), Ident("b"))


# ---------------------------------------------------------------------------
# Expressions — function calls
# ---------------------------------------------------------------------------

def test_call_no_args():
    assert expr("f()") == Call("f", [])


def test_call_one_arg():
    assert expr('print("hi")') == Call("print", [String('hi')])


def test_call_multiple_args():
    assert expr("f(1, 2, 3)") == Call("f", [Number(1), Number(2), Number(3)])


def test_call_expr_arg():
    assert expr("f(a + b)") == Call("f", [BinaryOp("PLUS", Ident("a"), Ident("b"))])


# ---------------------------------------------------------------------------
# Control flow
# ---------------------------------------------------------------------------

def test_while():
    assert stmt("while (x) {}") == WhileStmt(
        condition=Ident("x"), body=Block([])
    )


def test_while_complex_condition():
    assert stmt("while (!(a+b)) {}") == WhileStmt(
        condition=UnaryOp("NOT", BinaryOp("PLUS", Ident("a"), Ident("b"))),
        body=Block([]),
    )


def test_if_no_else():
    node = stmt("if (a) {}")
    assert isinstance(node, IfStmt)
    assert node.condition == Ident("a")
    assert node.then_block == Block([])
    assert node.else_branch is None


def test_if_else():
    node = stmt("if (a) {} else {}")
    assert isinstance(node, IfStmt)
    assert node.else_branch == Block([])


def test_if_else_if():
    node = stmt("if (a) {} else if (b) {}")
    assert isinstance(node, IfStmt)
    assert isinstance(node.else_branch, IfStmt)
    assert node.else_branch.condition == Ident("b")


def test_if_empty_condition():
    node = stmt("if () {}")
    assert isinstance(node, IfStmt)
    assert node.condition is None


def test_if_body():
    node = stmt("if (x) { y = 1; }")
    assert node.then_block == Block([AssignStmt("y", Number(1))])


# ---------------------------------------------------------------------------
# Function declarations
# ---------------------------------------------------------------------------

def test_fun_no_params():
    assert stmt("fun main() {}") == FunDecl(
        name="main", params=[], body=Block([])
    )


def test_fun_one_param():
    assert stmt("fun f(int x) {}") == FunDecl(
        name="f", params=[("int", "x")], body=Block([])
    )


def test_fun_multiple_params():
    assert stmt("fun f(int a, bool b, string c) {}") == FunDecl(
        name="f",
        params=[("int", "a"), ("bool", "b"), ("string", "c")],
        body=Block([]),
    )


def test_fun_with_body():
    node = stmt("fun f() { x = 1; }")
    assert node.body == Block([AssignStmt("x", Number(1))])


# ---------------------------------------------------------------------------
# Program-level
# ---------------------------------------------------------------------------

def test_multiple_statements():
    program = parse("const a: int = 1;\nvar b: int = 2;")
    assert len(program.body) == 2
    assert isinstance(program.body[0], ConstDecl)
    assert isinstance(program.body[1], VarDecl)


def test_empty_program():
    assert parse("") == Program([])


def test_full_example():
    src = open("examples/example.cube").read()
    program = parse(src)
    assert len(program.body) == 13


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

def test_missing_semicolon_in_const():
    with pytest.raises(ParseError):
        parse("const x: int = 1")


def test_unexpected_token():
    with pytest.raises(ParseError):
        parse("const = 1;")


def test_unclosed_block():
    with pytest.raises(ParseError):
        parse("while (x) {")
