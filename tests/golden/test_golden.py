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

from tests.golden.helpers import DEFAULT_MAX_TRACE, GOLDEN_DIR, run_and_snapshot

_yaml_files = sorted(GOLDEN_DIR.glob("*.yaml"))


@pytest.mark.golden
@pytest.mark.parametrize("yaml_path", _yaml_files, ids=lambda p: p.stem)
def test_golden(yaml_path: Path, request: pytest.FixtureRequest) -> None:
    name = yaml_path.stem
    stored_text = yaml_path.read_text(encoding="utf-8")
    stored = yaml.safe_load(stored_text)
    max_trace = stored.get("max_trace", DEFAULT_MAX_TRACE)

    _, snap_yaml = run_and_snapshot(name, yaml_path, max_trace)

    if request.config.getoption("--update-golden"):
        yaml_path.write_text(snap_yaml, encoding="utf-8")
        return

    assert snap_yaml == stored_text, f"[{name}] golden snapshot mismatch — run with --update-golden to regenerate"
