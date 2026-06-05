from pathlib import Path

import pytest
from app.config import (
    Config,
    InputDeviceConfig,
    IOConfig,
    OutputDeviceConfig,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# InputDeviceConfig.schedule normalization / validation
# ---------------------------------------------------------------------------


def test_schedule_char_is_converted_to_ordinal():
    dev = InputDeviceConfig(address=0x10, vector=1, schedule=[(1, "A")])
    assert dev.schedule == [(1, ord("A"))]


def test_schedule_tick_must_be_positive():
    with pytest.raises(ValidationError, match="tick must be >= 1"):
        InputDeviceConfig(address=0x10, vector=1, schedule=[(0, 1)])


def test_schedule_multichar_string_rejected():
    with pytest.raises(ValidationError, match="single character"):
        InputDeviceConfig(address=0x10, vector=1, schedule=[(1, "AB")])


def test_schedule_duplicate_ticks_rejected():
    with pytest.raises(ValidationError, match="duplicate tick"):
        InputDeviceConfig(address=0x10, vector=1, schedule=[(1, 1), (1, 2)])


def test_input_vector_out_of_range_rejected():
    with pytest.raises(ValidationError):
        InputDeviceConfig(address=0x10, vector=8)


# ---------------------------------------------------------------------------
# IOConfig collision / default-output validation
# ---------------------------------------------------------------------------


def test_default_output_name():
    io = IOConfig(
        outputs={
            "a": OutputDeviceConfig(address=0x100),
            "b": OutputDeviceConfig(address=0x101, default=True),
        }
    )
    assert io.default_output_name == "b"


def test_no_default_output_name_is_none():
    io = IOConfig(outputs={"a": OutputDeviceConfig(address=0x100)})
    assert io.default_output_name is None


def test_multiple_default_outputs_rejected():
    with pytest.raises(ValidationError, match="only one output device can be default"):
        IOConfig(
            outputs={
                "a": OutputDeviceConfig(address=0x100, default=True),
                "b": OutputDeviceConfig(address=0x101, default=True),
            }
        )


def test_output_address_collision_rejected():
    with pytest.raises(ValidationError, match="collides"):
        IOConfig(
            outputs={
                "a": OutputDeviceConfig(address=0x100),
                "b": OutputDeviceConfig(address=0x100),
            }
        )


def test_output_input_address_collision_rejected():
    with pytest.raises(ValidationError, match="collides"):
        IOConfig(
            outputs={"a": OutputDeviceConfig(address=0x100)},
            inputs={"k": InputDeviceConfig(address=0x100, vector=1)},
        )


# ---------------------------------------------------------------------------
# Config-level validation
# ---------------------------------------------------------------------------


def test_schedule_tick_exceeding_limit_rejected():
    with pytest.raises(ValidationError, match="exceeds simulation limit"):
        Config(
            limit=10,
            io=IOConfig(inputs={"k": InputDeviceConfig(address=0x100, vector=1, schedule=[(20, 1)])}),
        )


def test_config_defaults():
    config = Config()
    assert config.limit == 1000
    assert config.memory_size.instruction == 1000
    assert config.stack_size.data == 1000


def test_from_yaml(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "limit: 500\nio:\n  outputs:\n    out:\n      address: 0x222\n      default: true\n",
        encoding="utf-8",
    )
    config = Config.from_yaml(path)
    assert config.limit == 500
    assert config.io.default_output_name == "out"
