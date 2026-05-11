import pytest
from app.translator.lexer import Lexer, LexerError, TokenType


def _scan(src: str) -> str:
    tokens = Lexer(src).tokenize()
    string_tokens = [t for t in tokens if t.type is TokenType.STRING]
    assert len(string_tokens) == 1
    return string_tokens[0].value


@pytest.mark.parametrize("src,expected", [
    (r'"\n"',       "\n"),
    (r'"\t"',       "\t"),
    (r'"\r"',       "\r"),
    (r'"\0"',       "\0"),
    (r'"\\"',       "\\"),
    (r'"\""',       '"'),
    (r'"\'"',       "'"),
    (r'"a\nb"',     "a\nb"),
    (r'"\n\t\r"',   "\n\t\r"),
    (r'"hello\n"',  "hello\n"),
    (r'"path\\to"', "path\\to"),
])
def test_escape_sequences(src: str, expected: str):
    assert _scan(src) == expected


def test_string_without_escapes():
    assert _scan('"plain"') == "plain"


def test_unknown_escape_raises():
    with pytest.raises(LexerError, match=r"Unknown escape sequence '\\x'"):
        Lexer(r'"\x"').tokenize()


def test_dangling_backslash_raises():
    with pytest.raises(LexerError):
        Lexer('"hello\\').tokenize()
