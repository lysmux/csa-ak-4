from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Never


class TokenType(StrEnum):
    EOF = "EOF"

    # Literals
    STRING = "STRING"
    NUMBER = "NUMBER"

    # Multi-char operators
    INCREMENT = "++"
    DECREMENT = "--"
    EQUAL = "=="
    NOT_EQUAL = "!="
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN_OR_EQUAL = ">="
    AND = "&&"
    OR = "||"
    XOR = "^"

    # Single char operators
    ASSIGN = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    NOT = "!"
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"

    # Delimiters
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    LBRACKET = "["
    RBRACKET = "]"
    COLON = ":"
    SEMICOLON = ";"
    COMMA = ","

    # Generic
    IDENT = "IDENT"

    # Keywords
    CONST = "const"
    VAR = "var"
    IF = "if"
    ELSE = "else"
    WHILE = "while"
    FUN = "fun"
    TRUE = "true"
    FALSE = "false"
    RETURN = "return"
    INTERRUPT = "interrupt"
    TYPE = "type"


type TokenTypeMap = dict[str, TokenType]

WHITESPACE = {" ", "\t", "\n", "\r"}

KEYWORDS: TokenTypeMap = {
    "var": TokenType.VAR,
    "const": TokenType.CONST,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "fun": TokenType.FUN,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "return": TokenType.RETURN,
    "interrupt": TokenType.INTERRUPT,
    "int": TokenType.TYPE,
    "bool": TokenType.TYPE,
    "string": TokenType.TYPE,
}

DELIMITERS: TokenTypeMap = {
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    ":": TokenType.COLON,
    ";": TokenType.SEMICOLON,
    ",": TokenType.COMMA,
}

OPERATORS: TokenTypeMap = {
    "++": TokenType.INCREMENT,
    "--": TokenType.DECREMENT,
    "==": TokenType.EQUAL,
    "!=": TokenType.NOT_EQUAL,
    "<=": TokenType.LESS_THAN_OR_EQUAL,
    ">=": TokenType.GREATER_THAN_OR_EQUAL,
    "&&": TokenType.AND,
    "||": TokenType.OR,
    "=": TokenType.ASSIGN,
    "<": TokenType.LESS_THAN,
    ">": TokenType.GREATER_THAN,
    "!": TokenType.NOT,
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "^": TokenType.XOR,
}


@dataclass(slots=True)
class Token:
    type: TokenType
    value: str
    line: int
    column: int


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(f"{message} at line {line}, column {column}")

        self.line = line
        self.column = column


class Lexer:
    def __init__(self, source: str) -> None:
        self.source = source

        self.pos = 0
        self.line = 1
        self.column = 1

    @property
    def current_char(self) -> str | None:
        return self.peek()

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []

        while True:
            token = self.next_token()
            tokens.append(token)

            if token.type is TokenType.EOF:
                break

        return tokens

    def next_token(self) -> Token:
        self.skip_ignored()

        char = self.current_char
        if char is None:
            return Token(type=TokenType.EOF, value="", line=self.line, column=self.column)

        if char.isdigit():
            return self.scan_number()

        if char.isalpha() or char == "_":
            return self.scan_identifier()

        if char == '"':
            return self.scan_string()

        if token := self.scan_operator():
            return token

        if token := self.scan_delimiter():
            return token

        self.error(f"Unexpected character {char!r}")

    def scan_number(self) -> Token:
        line, col = self.line, self.column

        if self.peek() == "0" and self.peek(1) in ("x", "X"):
            self.advance()
            self.advance()

            hex_num = self.scan_while(lambda c: c in "abcdefABCDEF")
            value = str(int(hex_num, 16))
        else:
            value = self.scan_while(lambda c: c.isdigit())

        return Token(type=TokenType.NUMBER, value=value, line=line, column=col)

    def scan_identifier(self) -> Token:
        line, col = self.line, self.column

        value = self.scan_while(lambda c: c.isalpha() or c == "_")
        return Token(type=KEYWORDS.get(value, TokenType.IDENT), value=value, line=line, column=col)

    ESCAPES: dict[str, str] = {
        "n": "\n",
        "t": "\t",
        "r": "\r",
        "0": "\0",
        "\\": "\\",
        '"': '"',
        "'": "'",
    }

    def scan_string(self) -> Token:
        line, col = self.line, self.column

        self.advance()

        chars: list[str] = []
        while (ch := self.current_char) is not None and ch != '"':
            if ch == "\\":
                esc_line, esc_col = self.line, self.column
                self.advance()
                esc = self.current_char
                if esc is None:
                    self.error_at("Unterminated escape in string", line, col)
                mapped = self.ESCAPES.get(esc)
                if mapped is None:
                    self.error_at(f"Unknown escape sequence '\\{esc}'", esc_line, esc_col)
                chars.append(mapped)
                self.advance()
                continue

            chars.append(ch)
            self.advance()

        if self.current_char is None:
            self.error_at("Unterminated string", line, col)

        self.advance()

        return Token(
            TokenType.STRING,
            "".join(chars),
            line,
            col,
        )

    def scan_operator(self) -> Token | None:
        line, col = self.line, self.column

        two = self.peek(0, 2)
        if two is not None and two in OPERATORS:
            self.advance()
            self.advance()

            return Token(type=OPERATORS[two], value=two, line=line, column=col)

        one = self.peek()
        if one is not None and one in OPERATORS:
            self.advance()

            return Token(type=OPERATORS[one], value=one, line=line, column=col)

        return None

    def scan_delimiter(self) -> Token | None:
        line, col = self.line, self.column

        char = self.current_char
        if char is not None and self.current_char in DELIMITERS:
            self.advance()

            return Token(type=DELIMITERS[char], value=char, line=line, column=col)

        return None

    def scan_while(self, predicate: Callable[[str], bool]) -> str:
        chars = ""
        while (char := self.current_char) is not None and predicate(char):
            chars += char
            self.advance()

        return chars

    def skip_ignored(self) -> None:
        while True:
            if self.current_char in WHITESPACE:
                self.advance()
                continue

            if self.current_char == "/" and self.peek(1) == "/":
                self.skip_comment()
                continue

            break

    def skip_comment(self) -> None:
        while self.current_char not in {None, "\n"}:
            self.advance()

    def peek(self, offset: int = 0, size: int = 1) -> str | None:
        start = self.pos + offset
        end = start + size

        if start >= len(self.source):
            return None

        return self.source[start:end]

    def advance(self) -> None:
        if self.current_char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

        self.pos += 1

    def error(self, message: str) -> Never:
        raise LexerError(message, self.line, self.column)

    def error_at(self, message: str, line: int, column: int) -> Never:
        raise LexerError(message, line, column)
