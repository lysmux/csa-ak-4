"""Golden tests: параметризованы по *.yaml-файлам в tests/golden/.

Запуск:
  pytest tests/golden                        # проверка
  pytest tests/golden --update-golden        # регенерация снапшотов

Структура yaml:
  name, source, config, max_trace, expected_output, ast, machine_code, trace
"""
from pathlib import Path

import pytest
import yaml
from tests.golden.conftest import (
    GOLDEN_DIR,
    run_and_snapshot,
)

MAX_TRACE: dict[str, int] = {
    "hello":             200,
    "cat":               60,
    "hello_user_name":   80,
    "sort":              100,
    "double_precision":  200,
}

_yaml_files = sorted(GOLDEN_DIR.glob("*.yaml"))


@pytest.mark.golden
@pytest.mark.parametrize("yaml_path", _yaml_files, ids=lambda p: p.stem)
def test_golden(yaml_path: Path, request: pytest.FixtureRequest) -> None:
    name = yaml_path.stem
    max_trace = MAX_TRACE.get(name, 60)

    snap, snap_yaml = run_and_snapshot(name, yaml_path, max_trace)

    update = request.config.getoption("--update-golden")

    if update:
        yaml_path.write_text(snap_yaml, encoding="utf-8")
        return

    stored_text = yaml_path.read_text(encoding="utf-8")
    stored = yaml.safe_load(stored_text)

    assert snap["expected_output"] == stored["expected_output"], (
        f"[{name}] Output mismatch:\n"
        f"  computed: {snap['expected_output']}\n"
        f"  stored:   {stored['expected_output']}"
    )
    assert snap_yaml == stored_text, (
        f"[{name}] Full snapshot mismatch — run with --update-golden to regenerate"
    )
