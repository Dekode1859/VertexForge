"""Repository-owned runtime smoke check for VertexForge.

This script validates the Python version and verifies that the core
application modules can be imported in the active environment.
"""

from __future__ import annotations

import importlib
import platform
import sys
from pathlib import Path


MIN_PYTHON = (3, 11)
MAX_PYTHON_EXCLUSIVE = (3, 13)


def ensure_python_supported() -> None:
    version = sys.version_info[:3]
    if version < MIN_PYTHON or version >= MAX_PYTHON_EXCLUSIVE:
        raise RuntimeError(
            "Unsupported Python version "
            f"{platform.python_version()}. VertexForge requires Python >=3.11,<3.13."
        )


def ensure_imports() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))

    modules = [
        "schema",
        "tools",
        "compiler",
        "api",
    ]

    for module_name in modules:
        importlib.import_module(module_name)
        print(f"[OK] Imported {module_name}")


def main() -> int:
    ensure_python_supported()
    print(f"[OK] Python {platform.python_version()}")
    ensure_imports()
    print("[OK] Runtime smoke check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
