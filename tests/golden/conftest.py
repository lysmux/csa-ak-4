"""Pytest hooks for golden tests."""

from __future__ import annotations


def pytest_addoption(parser: object) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Regenerate *.yaml golden files instead of comparing",
    )
