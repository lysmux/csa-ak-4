from pathlib import Path

import pytest

from tests.golden.helpers import run_and_snapshot
from tests.golden.schema import GoldenInput

GOLDEN_DIR = Path(__file__).parent / "yaml"
_yaml_files = sorted(GOLDEN_DIR.glob("*.yaml"))


@pytest.mark.parametrize("yaml_path", _yaml_files, ids=lambda p: p.stem)
def test_golden(yaml_path: Path, request: pytest.FixtureRequest) -> None:
    golden_input = GoldenInput.from_yaml(yaml_path)

    snapshot = run_and_snapshot(golden_input)

    if request.config.getoption("--update-golden"):
        golden_input.snapshot = snapshot
        yaml_path.write_text(golden_input.dump_yaml(), encoding="utf-8")
        return

    if golden_input.snapshot is None:
        pytest.fail("Snapshot is missing. Generate it first using `--update-golden`")

    assert snapshot == golden_input.snapshot, f"[{golden_input.name}] golden snapshot mismatch"
