# Транслятор языка Cube

Транслятор преобразует исходный текст на языке Cube в двоичное представление, пригодное для исполнения стековым процессором. Конвейер состоит из четырёх этапов:

```
Исходный код  ──►  Лексер  ──►  Парсер  ──►  Анализатор  ──►  Кодогенератор
                 [Tokens]     [AST]     [AST (проверен)]   [CompiledProgram]
```

---

## Содержание

1. [Лексический анализ](#1-лексический-анализ-lexer)
2. [Синтаксический анализ](#2-синтаксический-анализ-parser)
3. [Семантический анализ](#3-семантический-анализ-analyzer)
4. [Кодогенерация](#4-кодогенерация-codegen)
5. [Грамматика языка](#5-грамматика-языка)
6. [Типы и совместимость](#6-типы-и-совместимость)
7. [Соглашение о вызовах](#7-соглашение-о-вызовах)
8. [MMIO-устройства](#8-mmio-устройства)
9. [Прерывания](#9-прерывания)
10. [Ошибки](#10-ошибки)

---

## 1. Лексический анализ (Lexer)

**Файл:** `app/translator/lexer.py`

### 1.1 Потоки токенов

Лексер сканирует источник посимвольно и возвращает `list[Token]`. Каждый `Token` содержит тип (`TokenType`), строковое значение, строку и столбец.

Пробелы (`[ \t\n\r]`) и однострочные комментарии (`//`) пропускаются.

### 1.2 Типы токенов

| Категория | Токены |
|-----------|--------|
| Конец файла | `EOF` |
| Литерал | `NUMBER`, `STRING` |
| Идентификатор | `IDENT` |
| Ключевые слова | `CONST`, `VAR`, `FUN`, `INTERRUPT`, `IF`, `ELSE`, `WHILE`, `RETURN`, `TRUE`, `FALSE` |
| Типы | `TYPE` (покрывает `int`, `byte`, `bool`, `string`) |
| Операторы | см. ниже |
| Разделители | `LPAREN`, `RPAREN`, `LBRACE`, `RBRACE`, `LBRACKET`, `RBRACKET`, `COLON`, `SEMICOLON`, `COMMA` |

### 1.3 Ключевые слова

```
const  var  fun  interrupt  if  else  while  return  true  false
int    byte bool  string
```

`int`, `byte`, `bool`, `string` токенизируются как `TYPE`, остальные — отдельными токенами.

### 1.4 Операторы

Двухсимвольные проверяются **перед** односимвольными:

| Токен | Символ | Значение |
|-------|--------|---------|
| `INCREMENT` | `++` | Префиксный/постфиксный инкремент |
| `DECREMENT` | `--` | Префиксный/постфиксный декремент |
| `EQUAL` | `==` | Равенство |
| `NOT_EQUAL` | `!=` | Неравенство |
| `LESS_THAN_OR_EQUAL` | `<=` | ≤ (знаковое) |
| `GREATER_THAN_OR_EQUAL` | `>=` | ≥ (знаковое) |
| `AND` | `&&` | Логическое И |
| `OR` | `\|\|` | Логическое ИЛИ |
| `XOR` | `^` | Побитовое XOR |
| `ASSIGN` | `=` | Присваивание |
| `LESS_THAN` | `<` | < (знаковое) |
| `GREATER_THAN` | `>` | > (знаковое) |
| `NOT` | `!` | Логическое НЕ |
| `PLUS` | `+` | Сложение |
| `MINUS` | `-` | Вычитание |
| `STAR` | `*` | Умножение |
| `SLASH` | `/` | Деление (целочисленное) |

### 1.5 Числовые литералы

- **Десятичные:** `0`, `42`, `1000`
- **Шестнадцатеричные:** `0x00`, `0xFF`, `0xFFFFFFFF`

Hex-литерал конвертируется в десятичную строку ещё на этапе лексинга (хранится как `int`).

### 1.6 Строковые литералы и escape-последовательности

Строки ограничены `"..."`. Поддерживаемые escape:

| Escape | Символ | Код |
|--------|--------|-----|
| `\n` | Перевод строки | 10 |
| `\t` | Табуляция | 9 |
| `\r` | Возврат каретки | 13 |
| `\0` | Нуль-байт | 0 |
| `\\` | Обратный слеш | 92 |
| `\"` | Двойная кавычка | 34 |
| `\'` | Одинарная кавычка | 39 |

Неизвестный escape (`\x`, `\q`, …) вызывает `LexerError`.

---

## 2. Синтаксический анализ (Parser)

**Файл:** `app/translator/parser.py`

### 2.1 Точка входа

```python
Parser(tokens: list[Token]).parse() -> Program
```

### 2.2 Диспетчеризация операторов

`parse_statement()` смотрит на первый токен:

| Первый токен | Метод | Результат |
|--------------|-------|-----------|
| `const` | `parse_const_decl()` | `ConstDecl` |
| `var` | `parse_var_decl()` | `VarDecl` или `ArrayDecl` |
| `fun` | `parse_fun_decl()` | `FunDecl` |
| `interrupt` | `parse_interrupt_decl()` | `InterruptDecl` |
| `return` | `parse_return_stmt()` | `ReturnStmt` |
| `if` | `parse_if_stmt()` | `IfStmt` |
| `while` | `parse_while_stmt()` | `WhileStmt` |
| `IDENT` + `=` | `parse_assign_stmt()` | `AssignStmt` |
| `IDENT` + `[` | `parse_index_assign_stmt()` | `IndexAssignStmt` |
| иное | `parse_expr_stmt()` | `ExprStmt` |

### 2.3 Синтаксис объявлений

```
const IDENT : TYPE = EXPR ;

var IDENT : TYPE = EXPR ;
var IDENT : TYPE [ NUMBER ] ;          // массив

fun IDENT ( PARAM_LIST ) [ : TYPE ] BLOCK

interrupt NUMBER IDENT ( ) BLOCK       // без параметров

PARAM_LIST ::= TYPE IDENT ( , TYPE IDENT )*
```

Пример:

```cube
const MAX: int = 100;
var counter: int = 0;
var buf: int[8];

fun add(int a, int b): int { return a + b; }

interrupt 0 on_input() { print(char_output, getchar()); }
```

### 2.4 Синтаксис операторов

```
BLOCK          ::= { STMT* }
return_stmt    ::= return [ EXPR ] ;
if_stmt        ::= if ( [ EXPR ] ) BLOCK [ else ( if_stmt | BLOCK ) ]
while_stmt     ::= while ( EXPR ) BLOCK
assign_stmt    ::= IDENT = EXPR ;
index_assign   ::= IDENT [ EXPR ] = EXPR ;
expr_stmt      ::= EXPR ;                   // точка с запятой опциональна
```

Условие `if` может быть пустым: `if () {}` — тело выполняется безусловно.

### 2.5 Разбор выражений (алгоритм Пратта)

Выражения разбираются методом `parse_expr(min_bp)` с таблицей приоритетов:

| Приоритет (bp) | Оператор | Ассоциативность |
|----------------|----------|-----------------|
| 1 | `\|\|` | левая |
| 2 | `&&` | левая |
| 3 | `^` | левая |
| 4 | `==` `!=` | левая |
| 5 | `<` `>` `<=` `>=` | левая |
| 6 | `+` `-` | левая |
| 7 | `*` `/` | левая |
| 8 | префикс `!` `++` `--` | правая |
| 9 | постфикс `++` `--` | левая |

Атомарные выражения:

| Форма | Результат |
|-------|-----------|
| `NUMBER` | `Number(int)` |
| `STRING` | `String(str)` — строка уже без escape |
| `true` / `false` | `Bool(bool)` |
| `IDENT` | `Ident(name)` |
| `IDENT ( ARGS )` | `Call(name, args)` |
| `IDENT [ EXPR ]` | `IndexExpr(name, index)` |
| `( EXPR )` | вложенное выражение |
| `! EXPR` | `UnaryOp("NOT", e)` |
| `++ IDENT` | `UnaryOp("INCREMENT", Ident)` |
| `-- IDENT` | `UnaryOp("DECREMENT", Ident)` |

### 2.6 Узлы AST

#### Операторы (Statement)

| Узел | Поля |
|------|------|
| `Program` | `body: list[Statement]` |
| `ConstDecl` | `name, type_name, value: Expr` |
| `VarDecl` | `name, type_name, value: Expr` |
| `ArrayDecl` | `name, type_name, size: int` |
| `FunDecl` | `name, params: list[(str,str)], body: Block, return_type: str\|None` |
| `InterruptDecl` | `vector: int, name, body: Block` |
| `IfStmt` | `condition: Expr\|None, then_block: Block, else_branch: IfStmt\|Block\|None` |
| `WhileStmt` | `condition: Expr, body: Block` |
| `Block` | `body: list[Statement]` |
| `AssignStmt` | `name: str, value: Expr` |
| `IndexAssignStmt` | `name, index: Expr, value: Expr` |
| `ExprStmt` | `expr: Expr` |
| `ReturnStmt` | `value: Expr\|None` |

#### Выражения (Expr)

| Узел | Поля |
|------|------|
| `BinaryOp` | `op: str, left: Expr, right: Expr` |
| `UnaryOp` | `op: str, operand: Expr` |
| `PostfixOp` | `op: str, operand: Expr` |
| `Call` | `name: str, args: list[Expr]` |
| `IndexExpr` | `name: str, index: Expr` |
| `Ident` | `name: str` |
| `Number` | `value: int` |
| `String` | `value: str` |
| `Bool` | `value: bool` |

`op` в `BinaryOp`/`UnaryOp`/`PostfixOp` — это имя токена (`"PLUS"`, `"NOT"`, `"INCREMENT"`, …).

---

## 3. Семантический анализ (Analyzer)

**Файл:** `app/translator/analyzer.py`

### 3.1 Таблица символов

```python
class Symbol:
    name: str
    type_name: str     # "int" | "byte" | "bool" | "string" | "fun"
                       # | "array" | "interrupt"
                       # | "output_device" | "input_device"
    mutable: bool
    params: list | None      # для fun: [(type_name, param_name), ...]
    return_type: str | None  # для fun
```

`Scope` — цепочка областей видимости. `define()` возвращает уже существующий символ при конфликте, `resolve()` ищет вверх по цепочке.

### 3.2 Области видимости

| Область | Создаётся при |
|---------|---------------|
| Глобальная | Запуск анализатора |
| Функция | `FunDecl` |
| Блок тела функции | `FunDecl` body |
| Обработчик прерывания | `InterruptDecl` |
| `if` / `while` тело | `IfStmt`, `WhileStmt` |

Внутренние области могут переопределять имена из внешних.

Встроенные функции (`print`, `println`, `getchar`, `addc`, `enable_interrupts`, `disable_interrupts`) и метки устройств (переданные в `Analyzer(output_devices=..., input_devices=...)`) регистрируются в глобальной области на этапе инициализации.

### 3.3 Встроенные функции

| Функция | Арность | Описание |
|---------|---------|---------|
| `print` | любая | Вывод аргументов на MMIO-устройство |
| `println` | любая | Как `print`, для char-устройств добавляет `\n` |
| `getchar` | 0 или 1 | Чтение символа с MMIO-устройства |
| `addc` | 2 | Сложение с учётом carry-флага |
| `enable_interrupts` | 0 | Выставить IE |
| `disable_interrupts` | 0 | Сбросить IE |

### 3.4 Правила для `print` / `println`

Первый аргумент — голый идентификатор с типом `output_device` → метка устройства; остальные аргументы — содержимое вывода.  
Без метки устройства — все аргументы считаются содержимым, пишутся на устройство `"default"`.

```cube
print(char_output, "Hello\n");   // явная метка
println("World");                // устройство default
```

### 3.5 Правила для `getchar`

| Форма | Разрешена | Контекст |
|-------|-----------|----------|
| `getchar()` | только внутри `interrupt N ...` | читает с устройства, привязанного к вектору N |
| `getchar(label)` | везде | явная метка; метка должна иметь тип `input_device` |

### 3.6 Проверка типов

**Совместимость:** `byte` ↔ `int`; все остальные типы проверяются на точное совпадение.

**Бинарные операторы:**

| Группа | Операторы | Требование к операндам | Результат |
|--------|-----------|------------------------|-----------|
| Арифметика | `+ - * /` | числовые | `int` |
| Сравнение | `== != < > <= >=` | совместимые | `bool` |
| Логика | `&& \|\| ^` | `bool` | `bool` |

**Унарные операторы:**

| Оператор | Требование к операнду | Результат |
|----------|-----------------------|-----------|
| `!` | `bool` | `bool` |
| `++ --` (префикс/постфикс) | `Ident`, изменяемая числовая переменная | тип операнда |

### 3.7 Особые ограничения

- `return` внутри `interrupt N ...` — `SemanticError`.
- Прямой вызов обработчика прерывания (`on_input()`) — `SemanticError`.
- Обращение к массиву без индекса (`arr` вместо `arr[i]`) — `SemanticError`.
- Использование `output_device`-метки не как первый аргумент `print`/`println` — `SemanticError`.
- Использование `input_device`-метки вне аргумента `getchar` — `SemanticError`.

### 3.8 Вывод AST

`print_ast(node, *, file=sys.stdout)` выводит дерево в читаемом виде:

```
Program
└─ body:
   └─ [0] FunDecl  name='main'  params=[]  return_type=None
      └─ body: Block
         └─ body:
            └─ [0] ExprStmt
               └─ expr: Call  name='print'
                  └─ args:
                     ├─ [0] Ident  name='char_output'
                     └─ [1] String  value='Hello, World!\n'
```

---

## 4. Кодогенерация (CodeGen)

**Файл:** `app/translator/codegen.py`

### 4.1 Инициализация

```python
CodeGen(
    output_devices: dict[str, OutputDevice] | None = None,
    input_devices:  dict[str, InputDevice]  | None = None,
)

@dataclass(frozen=True)
class OutputDevice:
    address: int   # MMIO-адрес
    kind: str      # "char" | "int"

@dataclass(frozen=True)
class InputDevice:
    address: int
    vector: int
```

### 4.2 Точка входа

```python
CodeGen(...).generate(program: Program) -> CompiledProgram
```

```python
@dataclass
class CompiledProgram:
    instructions: list[int]          # двоичные инструкции
    data: list[int]                  # сегмент данных
    interrupt_handlers: dict[int,int] # вектор → адрес инструкции
```

### 4.3 Компоновка бинарника

```
Addr 0:  CALL  main_addr    ← точка входа
Addr 1:  HALT
Addr 2+: тела всех FunDecl / InterruptDecl (в порядке объявления)
```

Каждое тело функции предваряется `JMP skip`, перепрыгивающим само тело (чтобы тело не выполнялось при последовательном исполнении):

```
JMP skip_label
fun_label:
  [пролог: STORE параметров]
  [тело]
  RET  (или RTI для interrupt)
skip_label:
```

### 4.4 Сегмент данных

Переменные и массивы размещаются последовательно при компиляции (compile-time allocation). Строковые литералы хранятся как cstr (последовательность байт, завершённая нулём).

| Тип | Размер |
|-----|--------|
| `var x: int` | 1 слово |
| `var arr: int[N]` | N слов |
| `"Hello\n"` | 7 слов (`H`, `e`, `l`, `l`, `o`, `\n`, `0`) |

### 4.5 Генерация по узлам AST

#### Константы и переменные

**ConstDecl / VarDecl со статически вычислимым значением:**

```
data[addr] = value   (установить при загрузке)
PUSH value
STORE addr
```

Статическая оценка (`_static_eval`) применяется к `Number`, `Bool`, константам-идентификаторам и арифметическим/логическим выражениям над ними. Если значение вычислимо, оно сохраняется в `_const_values[addr]` — последующие обращения к константе генерируют `PUSH value` вместо `LOAD addr`.

**VarDecl с нестатическим значением:**

```
gen(value)    ← произвольный код вычисления
STORE addr
```

**ArrayDecl:** выделяет N нулей в сегменте данных, кода не эмитирует.

#### Операторы

| Оператор | Код |
|----------|-----|
| `AssignStmt` | `gen(value); STORE addr` |
| `ExprStmt` | `gen(expr); DROP` |
| `ReturnStmt` | `gen(value)?; RET` |
| `Block` | посещение каждого оператора |

**IfStmt:**

```
gen(cond)
PUSH 0; CMP; DROP; DROP   ← _emit_flag_test: FLAGS = cond, стек пуст
JZ else_label
gen(then)
JMP end_label
else_label:
gen(else)?
end_label:
```

**WhileStmt:**

```
loop_label:
gen(cond)
PUSH 0; CMP; DROP; DROP
JZ end_label
gen(body)
JMP loop_label
end_label:
```

**FunDecl:**

```
JMP skip
fun_label:
  [для каждого параметра (в обратном порядке): STORE param_addr]
  gen(body)
  [если есть тип возврата: PUSH 0]   ← fallback-возврат
  RET
skip_label:
```

**InterruptDecl:**

```
JMP skip
handler_label:
  gen(body)
  RTI
skip_label:
```

#### Выражения — атомы

| Выражение | Код |
|-----------|-----|
| `Number(v)` | `PUSH v` |
| `Bool(true)` | `PUSH 1` |
| `Bool(false)` | `PUSH 0` |
| `Ident(x)` (const) | `PUSH const_value` |
| `Ident(x)` (var) | `LOAD addr_x` |
| `IndexExpr(arr, idx)` | `PUSH base; gen(idx); ADD; LOADI` |
| `String(s)` вне print | `PUSH 0` (строки вне вывода не поддерживаются) |

#### Выражения — операции

**Арифметика / битовые:**

```
gen(left)
gen(right)
EMIT opcode          ← ADD | SUB | MUL | DIV | AND | OR | XOR
```

Таблица соответствия:

| Токен | Опкод |
|-------|-------|
| `PLUS` | `ADD` |
| `MINUS` | `SUB` |
| `STAR` | `MUL` |
| `SLASH` | `DIV` |
| `AND` | `AND` |
| `OR` | `OR` |
| `XOR` | `XOR` |

**Сравнение:**

```
gen(left)
gen(right)
CMP; DROP; DROP
J<cond> true_label
PUSH 0
JMP end_label
true_label:
PUSH 1
end_label:
```

| Оператор | Переход на true |
|----------|----------------|
| `==` | `JZ` |
| `!=` | `JNZ` |
| `<` | `JL` |
| `>` | `JG` |
| `<=` | `JLE` |
| `>=` | `JGE` |

**Логическое НЕ (`!`):**

```
gen(operand)
PUSH 0; CMP; DROP; DROP    ← _emit_flag_test
JZ true_label
PUSH 0
JMP end_label
true_label:
PUSH 1
end_label:
```

**Инкремент/декремент:**

| Форма | Код | Результат на стеке |
|-------|-----|--------------------|
| `++x` (префикс) | `LOAD addr; INC; DUP; STORE addr` | новое значение |
| `--x` (префикс) | `LOAD addr; DEC; DUP; STORE addr` | новое значение |
| `x++` (постфикс) | `LOAD addr; DUP; INC; STORE addr` | старое значение |
| `x--` (постфикс) | `LOAD addr; DUP; DEC; STORE addr` | старое значение |

**Присваивание по индексу (`arr[idx] = val`):**

```
gen(val)            ← стек: [val]
PUSH base_addr
gen(idx)
ADD                 ← стек: [val, base+idx]
STOREI              ← M[base+idx] = val
```

#### Встроенные вызовы

**`print(label?, ...args)`** и **`println(label?, ...args)`:**

1. Определить устройство: первый аргумент `Ident` с меткой устройства → берётся его адрес и `kind`; иначе — устройство `"default"`.
2. Для каждого аргумента из полезной нагрузки:
   - `String`: `_emit_cstr_loop(str_addr, mmio_addr)` — цикл вывода cstr
   - прочее: `gen(arg); STORE mmio_addr`
3. Если `println` **и** `kind == "char"`: `PUSH 10; STORE mmio_addr`
4. `PUSH 0` — фиктивный возврат (ExprStmt сделает DROP)

**`_emit_cstr_loop(str_addr, mmio_addr)`:**

```
PUSH str_addr
loop:
  DUP
  LOADI               ← загрузить байт по текущему указателю
  JZ exit             ← нулевой байт = конец строки
  STORE mmio_addr     ← записать байт в MMIO
  INC                 ← перейти к следующему байту
  JMP loop
exit:
  DROP                ← снять нулевой байт
  DROP                ← снять указатель
```

**`getchar(label?)`:**

- С явной меткой: `LOAD device.address`
- Без метки (внутри обработчика прерывания): устройство находится по `_inputs_by_vector[_current_interrupt_vector]` → `LOAD device.address`

**`addc(a, b)`:**

```
gen(a)
gen(b)
ADDC          ← TOS ← NOS + TOS + C (carry-флаг от предыдущей ADD)
```

Важно: аргументы должны загружаться через `LOAD` (переменные), а не `PUSH` (литералы). `PUSH` сбрасывает C-флаг до выполнения `ADDC`.

**`enable_interrupts()` / `disable_interrupts()`:**

```
EI  (или DI)
PUSH 0          ← фиктивный возврат
```

**Пользовательские функции:**

```
gen(arg1)
gen(arg2)
...
gen(argN)
CALL fun_label
[если void: PUSH 0]    ← фиктивный возврат
```

### 4.6 Вспомогательные методы

| Метод | Описание |
|-------|---------|
| `_alloc_var(name)` | Выделяет 1 слово в сегменте данных, записывает в текущий скоуп |
| `_alloc_array(name, size)` | Выделяет N нулевых слов |
| `_alloc_string(s)` | Выделяет cstr, возвращает базовый адрес |
| `_emit_flag_test()` | Устанавливает FLAGS по TOS, чистит стек: `PUSH 0; CMP; DROP; DROP` |
| `_emit_cstr_loop(str_addr, mmio)` | Цикл вывода строки в MMIO |
| `_static_eval(node)` | Попытка compile-time вычисления; `None` если не удалось |
| `_var_addr(name)` | Ищет адрес переменной по цепочке скоупов |
| `_fresh_label()` | Генерирует уникальную метку `__L<N>` |
| `_emit_jump(op, label)` | Эмитирует прыжок, добавляет в очередь патчей |
| `_backpatch()` | Проставляет реальные адреса во все отложенные прыжки |

---

## 5. Грамматика языка

```
program      ::= top_decl*

top_decl     ::= const_decl
               | var_decl
               | fun_decl
               | interrupt_decl

const_decl   ::= "const" IDENT ":" type_name "=" expr ";"
var_decl     ::= "var" IDENT ":" type_name "=" expr ";"
               | "var" IDENT ":" type_name "[" NUMBER "]" ";"
fun_decl     ::= "fun" IDENT "(" param_list ")" [ ":" type_name ] block
interrupt_decl ::= "interrupt" NUMBER IDENT "(" ")" block

param_list   ::= ε | type_name IDENT ( "," type_name IDENT )*
type_name    ::= "int" | "byte" | "bool" | "string" | IDENT

statement    ::= const_decl | var_decl | fun_decl | interrupt_decl
               | return_stmt | if_stmt | while_stmt
               | assign_stmt | index_assign_stmt | expr_stmt | block

return_stmt  ::= "return" expr? ";"?
if_stmt      ::= "if" "(" expr? ")" block ( "else" ( if_stmt | block ) )?
while_stmt   ::= "while" "(" expr ")" block
assign_stmt  ::= IDENT "=" expr ";"
index_assign ::= IDENT "[" expr "]" "=" expr ";"
expr_stmt    ::= expr ";"?
block        ::= "{" statement* "}"

expr         ::= expr infix_op expr
               | prefix_op expr
               | expr postfix_op
               | atom

infix_op     ::= "||" | "&&" | "^"
               | "==" | "!="
               | "<" | ">" | "<=" | ">="
               | "+" | "-" | "*" | "/"

prefix_op    ::= "!" | "++" | "--"
postfix_op   ::= "++" | "--"

atom         ::= NUMBER | STRING | "true" | "false"
               | IDENT
               | IDENT "(" arg_list ")"
               | IDENT "[" expr "]"
               | "(" expr ")"

arg_list     ::= ε | expr ( "," expr )*
```

---

## 6. Типы и совместимость

| Тип | Хранение в рантайме | Диапазон |
|-----|---------------------|---------|
| `int` | 32-битное знаковое | −2³¹ … 2³¹−1 |
| `byte` | 32-битное слово, семантика 8-бит | 0 … 255 |
| `bool` | 32-битное слово | `0` (false) / `1` (true) |
| `string` | cstr в сегменте данных | только в `print`/`println` |
| `int[N]` | N последовательных слов | — |

**Совместимость:** `byte` и `int` взаимозаменяемы. Прочие типы должны совпадать точно.

---

## 7. Соглашение о вызовах

### Передача аргументов

1. Вызывающий вычисляет аргументы **слева направо** и кладёт их на стек данных.
2. TOS = последний аргумент.
3. В прологе функция снимает параметры **в обратном порядке** (`STORE` каждого параметра начиная с последнего).

```
Вызов f(a, b, c):
  gen(a)  → стек: [a]
  gen(b)  → стек: [a, b]
  gen(c)  → стек: [a, b, c]   ← TOS = c
  CALL f

Пролог f(int x, int y, int z):
  STORE addr_z   ← pop c → z
  STORE addr_y   ← pop b → y
  STORE addr_x   ← pop a → x
```

### Возврат значения

- Функция с типом возврата кладёт результат на стек данных перед `RET`.
- Fallback: если `return` не достигнут — `PUSH 0; RET` (генерируется кодогенератором).
- Функция без возврата: вызывающий получает фиктивный `PUSH 0` после `CALL`.

### Стек возвратов

`CALL` сохраняет адрес следующей инструкции в стек возвратов; `RET` восстанавливает его.

---

## 8. MMIO-устройства

### Конфигурация

Устройства передаются в `CodeGen` и `Analyzer`:

```python
output_devices = {
    "default":     OutputDevice(address=0x222, kind="char"),
    "char_output": OutputDevice(address=0x222, kind="char"),
    "int_output":  OutputDevice(address=0x224, kind="int"),
}
input_devices = {
    "keyboard":    InputDevice(address=0x223, vector=0),
}
```

### Виды выходных устройств

| `kind` | Класс симулятора | `.string` |
|--------|------------------|-----------|
| `char` | `CharOutput` | Буфер байт → строка через `chr()` |
| `int` | `IntOutput` | Буфер целых → через `" ".join(str(v) ...)` |

### Разрешение меток в коде

```cube
print(char_output, "Hello\n");   // явная метка → MMIO 0x222
println("done");                  // метка "default" → MMIO 0x222
print(int_output, 42);           // метка "int_output" → MMIO 0x224
```

### `println` и символ новой строки

`println` добавляет `PUSH 10; STORE mmio_addr` только если `kind == "char"`. Для `int`-устройств `\n` не добавляется — форматирование остаётся за самим устройством.

---

## 9. Прерывания

### Объявление обработчика

```cube
interrupt 0 on_input() {
    print(char_output, getchar());
}
```

- Число `0` — номер вектора прерывания.
- Имя функции произвольное.
- Параметры запрещены.
- `return` внутри запрещён.

### Генерируемый код

```
JMP skip
handler_label:          ← адрес обработчика записывается в interrupt_handlers[0]
  gen(body)
  RTI                   ← Pop PC, Pop FLAGS, IE ← 1
skip_label:
```

### Вход в прерывание (аппаратный)

При установленном `PS.IE` и сигнале IRQ от устройства:

```
M_R[RSP--] ← FLAGS
M_R[RSP--] ← PC
PS.IE ← 0
PS.IRQ ← 0
PC ← vector_table[N]
```

### Чтение ввода внутри обработчика

```cube
interrupt 0 on_char() {
    var c: int = getchar();          // читает с устройства вектора 0
    print(char_output, c);
}
```

`getchar()` без метки → транслятор разрешает устройство по текущему `_current_interrupt_vector` через `_inputs_by_vector[vector].address` → эмитирует `LOAD address`.

---

## 10. Ошибки

### `LexerError(message, line, column)`

Возникает при:
- Неожиданный символ
- Незакрытая строка
- Неизвестная escape-последовательность (`\x`)
- Оборванный escape в конце строки

### `ParseError(message)`

Возникает при:
- Несовпадение ожидаемого токена
- Неожиданный конец ввода
- Недопустимое выражение

### `SemanticError(message)`

Возникает при:
- Неопределённое имя
- Повторное объявление в той же области
- Несовместимые типы
- `return` в обработчике прерывания
- Прямой вызов обработчика прерывания
- Массив без индекса
- Метка устройства в недопустимой позиции
- `getchar()` вне обработчика прерывания
- Неверная арность встроенных функций

### `CodeGenError(message)`

Возникает при:
- Нет функции `main`
- Неопределённая функция во время кодогенерации
- Нет устройства `"default"` при использовании `print` без метки
- `getchar()` внутри обработчика без подходящего устройства
- Конфликт векторов в `_inputs_by_vector`

---

## Примеры

### Hello, World!

```cube
fun main() {
    print(char_output, "Hello, World!\n");
}
```

### Эхо ввода (прерывание)

```cube
interrupt 0 on_char() {
    print(char_output, getchar());
}

fun main() {
    enable_interrupts();
    while (true) {}
}
```

### 64-битное сложение

```cube
fun main() {
    var a_hi: int = 0;
    var a_lo: int = 0xFFFFFFFF;   // A = 2^32 - 1
    var b_hi: int = 0;
    var b_lo: int = 1;            // B = 1

    var sum_lo: int = a_lo + b_lo;        // ADD: C = 1
    var sum_hi: int = addc(a_hi, b_hi);   // ADDC использует C

    print(int_output, sum_hi);   // 1
    print(int_output, sum_lo);   // 0
}
```

### Пузырьковая сортировка через прерывания (фрагмент)

```cube
var nums:  int[5];
var count: int  = 0;

interrupt 0 on_num() {
    var c: int = getchar();
    if (c != 0) {
        nums[count] = c;
        count++;
    }
}

fun main() {
    enable_interrupts();
    while (count < 5) {}
    disable_interrupts();
    // ... сортировка ...
}
```
