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

    # Single-char operators
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
    WHITESPACE = {" ", "\t", "\n", "\r"}

    KEYWORDS: dict[str, TokenType] = {
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
        "byte": TokenType.TYPE,
        "bool": TokenType.TYPE,
        "string": TokenType.TYPE,
    }

    DELIMITERS: dict[str, TokenType] = {
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

    OPERATORS: dict[str, TokenType] = {
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

        while (token := self.next_token()).type is not TokenType.EOF:
            tokens.append(token)

        tokens.append(self.make_token(TokenType.EOF, ""))

        return tokens

    def next_token(self) -> Token:
        self.skip_ignored()

        char = self.current_char
        if char is None:
            return self.make_token(TokenType.EOF, "")

        if char.isdigit():
            return self.scan_number()

        if char.isalpha() or char == "_":
            return self.scan_identifier()

        if char == '"':
            return self.scan_string()

        if token := self.scan_operator():
            return token

        if token_type := self.DELIMITERS.get(char):
            return self.scan_single_char(token_type)

        self.error(f"Unexpected character {char!r}")


    def scan_number(self) -> Token:
        return self.scan_while(
            TokenType.NUMBER,
            lambda c: c.isdigit(),
        )

    def scan_identifier(self) -> Token:
        token = self.scan_while(
            TokenType.IDENT,
            lambda c: c.isalnum() or c == "_",
        )

        token.type = self.KEYWORDS.get(token.value, TokenType.IDENT)
        return token

    def scan_string(self) -> Token:
        line, col = self.line, self.column

        self.advance()  # opening quote

        chars: list[str] = []

        while (ch := self.current_char) is not None and ch != '"':
            chars.append(ch)
            self.advance()

        if self.current_char is None:
            self.error_at("Unterminated string", line, col)

        self.advance()  # closing quote

        return Token(
            TokenType.STRING,
            "".join(chars),
            line,
            col,
        )

    def scan_operator(self) -> Token | None:
        two = self.peek(0, 2)

        if two is not None and two in self.OPERATORS:
            return self.consume(two, self.OPERATORS[two])

        one = self.peek()

        if one is not None and one in self.OPERATORS:
            return self.consume(one, self.OPERATORS[one])

        return None

    def scan_single_char(self, token_type: TokenType) -> Token:
        char = self.current_char

        if char is None:
            self.error("Unexpected EOF")

        return self.consume(char, token_type)

    def scan_while(
        self,
        token_type: TokenType,
        predicate: Callable[[str], bool],
    ) -> Token:
        line, col = self.line, self.column
        chars: list[str] = []

        while (
            (char := self.current_char) is not None
            and predicate(char)
        ):
            chars.append(char)
            self.advance()

        return Token(
            token_type,
            "".join(chars),
            line,
            col,
        )

    def consume(
        self,
        lexeme: str,
        token_type: TokenType,
    ) -> Token:
        line, col = self.line, self.column

        for _ in lexeme:
            self.advance()

        return Token(token_type, lexeme, line, col)

    def skip_ignored(self) -> None:
        while True:
            if self.current_char in self.WHITESPACE:
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

    def make_token(
        self,
        token_type: TokenType,
        value: str,
    ) -> Token:
        return Token(
            token_type,
            value,
            self.line,
            self.column,
        )

    def error(self, message: str) -> Never:
        raise LexerError(message, self.line, self.column)

    def error_at(self, message: str, line: int, column: int) -> Never:
        raise LexerError(message, line, column)
