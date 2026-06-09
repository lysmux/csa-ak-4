import dataclasses

from app.translator.types import Type


def render(node: object) -> str:
    lines: list[str] = []
    _collect(node, "", "", lines)
    return "\n".join(lines)


def _fmt(value: object) -> str:
    if isinstance(value, Type):
        return repr(value.value)
    if isinstance(value, tuple):
        return "(" + ", ".join(_fmt(item) for item in value) + ")"
    return repr(value)


def _collect(node: object, prefix: str, child_prefix: str, lines: list[str]) -> None:
    if not dataclasses.is_dataclass(node) or isinstance(node, type):
        lines.append(prefix + _fmt(node))
        return

    scalars: list[tuple[str, object]] = []
    children: list[tuple[str, object]] = []
    for f in dataclasses.fields(node):
        if f.metadata.get("ast_skip"):
            continue
        v = getattr(node, f.name)
        if (isinstance(v, list) and v) or (dataclasses.is_dataclass(v) and not isinstance(v, type)):
            children.append((f.name, v))
        else:
            scalars.append((f.name, v))

    scalar_str = "  ".join(f"{k}={_fmt(v)}" for k, v in scalars)
    header = type(node).__name__ + ("  " + scalar_str if scalar_str else "")
    lines.append(prefix + header)

    for i, (fname, child) in enumerate(children):
        last = i == len(children) - 1
        conn = "└─ " if last else "├─ "
        next_cp = child_prefix + ("   " if last else "│  ")

        if isinstance(child, list):
            lines.append(child_prefix + conn + fname + ":")
            for j, item in enumerate(child):
                item_last = j == len(child) - 1
                item_conn = "└─ " if item_last else "├─ "
                item_cp = next_cp + ("   " if item_last else "│  ")
                _collect(item, next_cp + item_conn + f"[{j}] ", item_cp, lines)
        else:
            _collect(child, child_prefix + conn + fname + ": ", next_cp, lines)
