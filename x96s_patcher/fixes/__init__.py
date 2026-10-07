"""Fix registry: (name, description, targets, needs, function).

A fix is func(ctx, entries) -> (replacements, changed, summary).
Fixes run sequentially; each sees the previous fixes' replacements.

entries keys are CANONICAL file names ("dtbo.img",
"vendor.new.dat.br", ...), transport-agnostic: the pipeline maps
each package type's slots onto them (an OTA zip carries dtbo.img
as-is, a burn package carries it as dtbo.PARTITION).

targets lists the package types the fix may run on: "ota"
(recovery OTA zip), "aip" (Amlogic burn package). needs lists the
canonical files the fix reads; if any is absent from the package,
the fix is skipped with an explicit N/A note (no silent-KeyError).

Import order below IS run order. To add a fix: write the module
(declare targets + needs, decorate with @register), import it here.
"""

from collections.abc import Callable
from typing import Any

# Context passed through the fixes (carries work_dir).
Ctx = dict[str, Any]
# Zip entries by name (raw bytes).
Entries = dict[str, bytes]
# A fix result: (replacement entries, changed, summary).
FixResult = tuple[dict[str, bytes], bool, str]
# A fix function.
FixFunc = Callable[[Ctx, Entries], FixResult]


def register(name: str, desc: str, targets: tuple[str, ...],
             needs: tuple[str, ...] = ()) -> Callable[[FixFunc], FixFunc]:
    """Decorator: add a fix to the registry (see module docstring)."""
    def deco(func: FixFunc) -> FixFunc:
        _entries.append((name, desc, targets, needs, func))
        return func
    return deco


_entries: list[tuple[str, str, tuple[str, ...], tuple[str, ...], FixFunc]] = []

from . import dtbo  # noqa: E402
from . import vendor_tabs  # noqa: E402
from . import vendor_wifi_rc  # noqa: E402
from . import vendor_wifi_ko  # noqa: E402
from . import vendor_wifi_dispatch  # noqa: E402
from . import vendor_bt  # noqa: E402
from . import bootloader  # noqa: E402

FIXES: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], FixFunc], ...] \
    = tuple(_entries)
