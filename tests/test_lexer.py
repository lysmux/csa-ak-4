import pytest
from app.translator.lexer import Lexer, LexerError, Token, TokenType


def tokenize(source: str) -> list[Token]:
    return [t for t in Lexer(source).tokenize() if t.type != TokenType.EOF]


def types(source: str) -> list[TokenType]:
    return [t.type for t in tokenize(source)]


def test_integer():
    tokens = tokenize("42")
    assert tokens == [Token(TokenType.NUMBER, "42", 1, 1)]


def test_string():
    tokens = tokenize('"hello"')
    assert tokens == [Token(TokenType.STRING, "hello", 1, 1)]


def test_empty_string():
    tokens = tokenize('""')
    assert tokens == [Token(TokenType.STRING, "", 1, 1)]


def test_identifier():
    tokens = tokenize("abc")
    assert tokens == [Token(TokenType.IDENT, "abc", 1, 1)]


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("const", TokenType.CONST),
        ("var", TokenType.VAR),
        ("if", TokenType.IF),
        ("else", TokenType.ELSE),
        ("while", TokenType.WHILE),
        ("fun", TokenType.FUN),
        ("true", TokenType.TRUE),
        ("false", TokenType.FALSE),
    ],
)
def test_keywords(src: str, expected: TokenType):
    assert types(src) == [expected]


def test_keyword_prefix_is_ident():
    assert types("iffy") == [TokenType.IDENT]
    assert types("constant") == [TokenType.IDENT]


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("++", TokenType.INCREMENT),
        ("--", TokenType.DECREMENT),
        ("==", TokenType.EQUAL),
        ("!=", TokenType.NOT_EQUAL),
        ("<=", TokenType.LESS_THAN_OR_EQUAL),
        (">=", TokenType.GREATER_THAN_OR_EQUAL),
        ("&&", TokenType.AND),
        ("||", TokenType.OR),
        ("^", TokenType.XOR),
        ("=", TokenType.ASSIGN),
        ("<", TokenType.LESS_THAN),
        (">", TokenType.GREATER_THAN),
        ("!", TokenType.NOT),
        ("+", TokenType.PLUS),
        ("-", TokenType.MINUS),
        ("*", TokenType.STAR),
        ("/", TokenType.SLASH),
    ],
)
def test_operators(src: str, expected: TokenType):
    assert types(src) == [expected]


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        ("(", TokenType.LPAREN),
        (")", TokenType.RPAREN),
        ("{", TokenType.LBRACE),
        ("}", TokenType.RBRACE),
        ("[", TokenType.LBRACKET),
        ("]", TokenType.RBRACKET),
        (":", TokenType.COLON),
        (";", TokenType.SEMICOLON),
        (",", TokenType.COMMA),
    ],
)
def test_delimiters(src: str, expected: TokenType):
    assert types(src) == [expected]


def test_whitespace_skipped():
    assert types("  \t\n  ") == []


def test_comment_skipped():
    assert types("// this is a comment") == []


def test_column_tracking():
    tokens = tokenize("a + b")
    assert [(t.type, t.column) for t in tokens] == [
        (TokenType.IDENT, 1),
        (TokenType.PLUS, 3),
        (TokenType.IDENT, 5),
    ]


def test_line_tracking():
    tokens = tokenize("a\nb\nc")
    assert [t.line for t in tokens] == [1, 2, 3]


def test_line_and_column_after_newline():
    tokens = tokenize("a\n  b")
    b = tokens[1]
    assert b.line == 2
    assert b.column == 3


def test_const_declaration():
    assert types("const a: int = 1;") == [
        TokenType.CONST,
        TokenType.IDENT,
        TokenType.COLON,
        TokenType.TYPE,
        TokenType.ASSIGN,
        TokenType.NUMBER,
        TokenType.SEMICOLON,
    ]


def test_var_declaration():
    assert types("var b: int = 2;") == [
        TokenType.VAR,
        TokenType.IDENT,
        TokenType.COLON,
        TokenType.TYPE,
        TokenType.ASSIGN,
        TokenType.NUMBER,
        TokenType.SEMICOLON,
    ]


def test_if_else():
    assert types("if (a > b) {} else {}") == [
        TokenType.IF,
        TokenType.LPAREN,
        TokenType.IDENT,
        TokenType.GREATER_THAN,
        TokenType.IDENT,
        TokenType.RPAREN,
        TokenType.LBRACE,
        TokenType.RBRACE,
        TokenType.ELSE,
        TokenType.LBRACE,
        TokenType.RBRACE,
    ]


def test_while():
    assert types("while (!(a+b)) {}") == [
        TokenType.WHILE,
        TokenType.LPAREN,
        TokenType.NOT,
        TokenType.LPAREN,
        TokenType.IDENT,
        TokenType.PLUS,
        TokenType.IDENT,
        TokenType.RPAREN,
        TokenType.RPAREN,
        TokenType.LBRACE,
        TokenType.RBRACE,
    ]


def test_fun_declaration():
    assert types("fun main(int a, bool b) {}") == [
        TokenType.FUN,
        TokenType.IDENT,
        TokenType.LPAREN,
        TokenType.TYPE,
        TokenType.IDENT,
        TokenType.COMMA,
        TokenType.TYPE,
        TokenType.IDENT,
        TokenType.RPAREN,
        TokenType.LBRACE,
        TokenType.RBRACE,
    ]


def test_increment_postfix():
    assert types("a++") == [TokenType.IDENT, TokenType.INCREMENT]


def test_decrement_prefix():
    assert types("--b") == [TokenType.DECREMENT, TokenType.IDENT]


def test_increment_not_two_plus():
    assert types("++") == [TokenType.INCREMENT]
    assert types("+ +") == [TokenType.PLUS, TokenType.PLUS]


def test_unknown_character_raises():
    with pytest.raises(LexerError):
        tokenize("@")
