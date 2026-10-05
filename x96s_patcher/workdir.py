"""Temporary working directory, always inside the launch directory."""

import os
import shutil
import tempfile

TMP_PREFIX = ".fix_x96s-"


class WorkDir:
    """Temporary directory inside the launch dir, removed on close."""

    def __init__(self) -> None:
        self.path: str = tempfile.mkdtemp(prefix=TMP_PREFIX, dir=os.getcwd())
        self._closed: bool = False

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            shutil.rmtree(self.path, ignore_errors=True)

    def __enter__(self) -> "WorkDir":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
