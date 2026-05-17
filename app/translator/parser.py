from app.translator.lexer import Token, TokenType
from app.translator.nodes import (
    ArrayDecl,
    AssignStmt,
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
    Statement,
    String,
    UnaryOp,
    VarDecl,
    WhileStmt,
)

INFIX_BP: dict[TokenType, int] = {
    TokenType.OR: 1,
    TokenType.AND: 2,
    TokenType.XOR: 3,
    TokenType.EQUAL: 4,
    TokenType.NOT_EQUAL: 4,
    TokenType.LESS_THAN: 5,
    TokenType.GREATER_THAN: 5,
    TokenType.LESS_THAN_OR_EQUAL: 5,
    TokenType.GREATER_THAN_OR_EQUAL: 5,
    TokenType.PLUS: 6,
    TokenType.MINUS: 6,
    TokenType.STAR: 7,
    TokenType.SLASH: 7,
}

POSTFIX_BP: dict[TokenType, int] = {
    TokenType.INCREMENT: 9,
    TokenType.DECREMENT: 9,
}

PREFIX_BP = 8
PREFIX_OPS = {TokenType.NOT, TokenType.INCREMENT, TokenType.DECREMENT}


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens

        self.pos = 0

    def parse(self) -> Program:
        body: list[Statement] = []
        while not self.at_end():
            body.append(self.parse_statement())
        return Program(body)

    def peek(self, offset: int = 0) -> Token | None:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else None

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def at_end(self) -> bool:
        tok = self.peek()
        return tok is None or tok.type == TokenType.EOF

    def eat(self, expected: TokenType) -> Token:
        tok = self.peek()
        if tok is None:
            msg = f"Expected {expected.name}, got EOF"
            raise ParseError(msg)
        if tok.type != expected:
            msg = f"Expected {expected.name!r}, got {tok.type.name!r} at line {tok.line}, column {tok.column}"
            raise ParseError(msg)

        return self.advance()

    def parse_statement(self) -> Statement:
        tok = self.peek()
        if tok is None:
            msg = "Unexpected EOF"
            raise ParseError(msg)

        match tok.type:
            case TokenType.CONST:
                return self.parse_const_decl()
            case TokenType.VAR:
                return self.parse_var_decl()
            case TokenType.FUN:
                return self.parse_fun_decl()
            case TokenType.INTERRUPT:
                return self.parse_interrupt_decl()
            case TokenType.RETURN:
                return self.parse_return_stmt()
            case TokenType.IF:
                return self.parse_if_stmt()
            case TokenType.WHILE:
                return self.parse_while_stmt()
            case TokenType.IDENT if self.peek(1) and self.peek(1).type == TokenType.ASSIGN:
                return self.parse_assign_stmt()
            case TokenType.IDENT if self.peek(1) and self.peek(1).type == TokenType.LBRACKET:
                return self.parse_index_assign_stmt()
            case _:
                return self.parse_expr_stmt()

    def parse_const_decl(self) -> ConstDecl:
        self.eat(TokenType.CONST)
        name = self.eat(TokenType.IDENT).value
        self.eat(TokenType.COLON)
        type_name = self.eat(TokenType.TYPE).value
        self.eat(TokenType.ASSIGN)
        value = self.parse_expr()
        self.eat(TokenType.SEMICOLON)
        return ConstDecl(name=name, type_name=type_name, value=value)

    def parse_var_decl(self) -> VarDecl | ArrayDecl:
        self.eat(TokenType.VAR)
        name = self.eat(TokenType.IDENT).value
        self.eat(TokenType.COLON)
        type_name = self.eat(TokenType.TYPE).value

        if self.peek().type is TokenType.LBRACKET:
            self.advance()
            size = int(self.eat(TokenType.NUMBER).value)
            self.eat(TokenType.RBRACKET)
            self.eat(TokenType.SEMICOLON)
            return ArrayDecl(name=name, type_name=type_name, size=size)

        self.eat(TokenType.ASSIGN)
        value = self.parse_expr()
        self.eat(TokenType.SEMICOLON)
        return VarDecl(name=name, type_name=type_name, value=value)

    def parse_assign_stmt(self) -> AssignStmt:
        name = self.eat(TokenType.IDENT).value
        self.eat(TokenType.ASSIGN)
        value = self.parse_expr()
        self.eat(TokenType.SEMICOLON)
        return AssignStmt(name=name, value=value)

    def parse_index_assign_stmt(self) -> IndexAssignStmt:
        name = self.eat(TokenType.IDENT).value
        self.eat(TokenType.LBRACKET)
        index = self.parse_expr()
        self.eat(TokenType.RBRACKET)
        self.eat(TokenType.ASSIGN)
        value = self.parse_expr()
        self.eat(TokenType.SEMICOLON)
        return IndexAssignStmt(name=name, index=index, value=value)

    def parse_fun_decl(self) -> FunDecl:
        self.eat(TokenType.FUN)
        name = self.eat(TokenType.IDENT).value
        self.eat(TokenType.LPAREN)
        params = self.parse_param_list()
        self.eat(TokenType.RPAREN)

        return_type: str | None = None
        if self.peek().type is TokenType.COLON:
            self.advance()
            return_type = self.eat(TokenType.TYPE).value
        body = self.parse_block()
        return FunDecl(name=name, params=params, body=body, return_type=return_type)

    def parse_param_list(self) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = []
        if self.peek() and self.peek().type == TokenType.RPAREN:
            return params

        while True:
            type_name = self.eat(TokenType.TYPE).value
            param_name = self.eat(TokenType.IDENT).value
            params.append((type_name, param_name))

            if self.peek().type is not TokenType.COMMA:
                break

            self.advance()

        return params

    def parse_interrupt_decl(self) -> InterruptDecl:
        self.eat(TokenType.INTERRUPT)
        vector = int(self.eat(TokenType.NUMBER).value)
        name = self.eat(TokenType.IDENT).value
        self.eat(TokenType.LPAREN)
        self.eat(TokenType.RPAREN)
        body = self.parse_block()
        return InterruptDecl(vector=vector, name=name, body=body)

    def parse_return_stmt(self) -> ReturnStmt:
        self.eat(TokenType.RETURN)
        if self.peek() and self.peek().type != TokenType.SEMICOLON:
            value = self.parse_expr()
            self.eat(TokenType.SEMICOLON)
            return ReturnStmt(value=value)
        self.eat(TokenType.SEMICOLON)
        return ReturnStmt(value=None)

    def parse_if_stmt(self) -> IfStmt:
        self.eat(TokenType.IF)
        self.eat(TokenType.LPAREN)

        condition = self.parse_expr()

        self.eat(TokenType.RPAREN)
        then_block = self.parse_block()

        else_branch: IfStmt | Block | None = None
        if self.peek().type is TokenType.ELSE:
            self.advance()
            if self.peek() and self.peek().type == TokenType.IF:
                else_branch = self.parse_if_stmt()
            else:
                else_branch = self.parse_block()
        return IfStmt(condition=condition, then_block=then_block, else_branch=else_branch)

    def parse_while_stmt(self) -> WhileStmt:
        self.eat(TokenType.WHILE)
        self.eat(TokenType.LPAREN)
        condition = self.parse_expr()
        self.eat(TokenType.RPAREN)
        body = self.parse_block()
        return WhileStmt(condition=condition, body=body)

    def parse_expr_stmt(self) -> ExprStmt:
        expr = self.parse_expr()
        self.eat(TokenType.SEMICOLON)
        return ExprStmt(expr=expr)

    def parse_block(self) -> Block:
        self.eat(TokenType.LBRACE)
        body: list[Statement] = []
        while not self.at_end() and self.peek().type != TokenType.RBRACE:
            body.append(self.parse_statement())
        self.eat(TokenType.RBRACE)
        return Block(body=body)

    def parse_expr(self, min_bp: int = 0) -> Expr:
        tok = self.peek()
        if tok is None:
            msg = "Unexpected end of input in expression"
            raise ParseError(msg)

        if tok.type in PREFIX_OPS:
            op = self.advance()
            if op.type in (TokenType.INCREMENT, TokenType.DECREMENT):
                operand = Ident(self.eat(TokenType.IDENT).value)
            else:
                operand = self.parse_expr(PREFIX_BP)
            left = UnaryOp(op=Op[op.type.name], operand=operand)
        elif tok.type == TokenType.NUMBER:
            left = Number(int(self.advance().value))
        elif tok.type == TokenType.STRING:
            left = String(self.advance().value)
        elif tok.type == TokenType.TRUE:
            left = Bool(True)
            self.advance()
        elif tok.type == TokenType.FALSE:
            left = Bool(False)
            self.advance()
        elif tok.type == TokenType.IDENT:
            name = self.advance().value
            if self.peek() and self.peek().type == TokenType.LPAREN:
                self.advance()
                args = self.parse_arg_list()
                self.eat(TokenType.RPAREN)
                left = Call(name=name, args=args)
            elif self.peek() and self.peek().type == TokenType.LBRACKET:
                self.advance()
                index = self.parse_expr()
                self.eat(TokenType.RBRACKET)
                left = IndexExpr(name=name, index=index)
            else:
                left = Ident(name)
        elif tok.type == TokenType.LPAREN:
            self.advance()
            left = self.parse_expr()
            self.eat(TokenType.RPAREN)
        else:
            msg = f"Unexpected token {tok.type.name!r} {tok.value!r} at line {tok.line}, column {tok.column}"
            raise ParseError(msg)

        while True:
            op_tok = self.peek()
            if op_tok is None:
                break

            post_bp = POSTFIX_BP.get(op_tok.type)
            if post_bp is not None and post_bp > min_bp:
                self.advance()
                left = PostfixOp(op=Op[op_tok.type.name], operand=left)
                continue

            infix_bp = INFIX_BP.get(op_tok.type)
            if infix_bp is None or infix_bp <= min_bp:
                break

            self.advance()
            right = self.parse_expr(infix_bp)
            left = BinaryOp(op=Op[op_tok.type.name], left=left, right=right)

        return left

    def parse_arg_list(self) -> list[Expr]:
        args: list[Expr] = []
        if self.peek() and self.peek().type == TokenType.RPAREN:
            return args

        while True:
            args.append(self.parse_expr())
            if self.peek().type is not TokenType.COMMA:
                break

            self.advance()

        return args
