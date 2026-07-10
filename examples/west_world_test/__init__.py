"""Compatibility package for the WestWorld example.

The project files live in examples/WestWorld, while older imports and run
commands still use examples.west_world_test. Extending __path__ keeps those
imports working without duplicating modules.
"""
from __future__ import annotations

from pathlib import Path

_WESTWORLD_PATH = Path(__file__).resolve().parents[1] / "WestWorld"
__path__ = [str(_WESTWORLD_PATH)]
