"""Prepare every file before replacement and restore this transaction on failure."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile


def replace_files(updates: dict[Path, bytes]) -> None:
    originals = {path: path.read_bytes() for path in updates}
    staged = {}
    written = []
    try:
        for path, content in updates.items():
            descriptor, name = tempfile.mkstemp(prefix='.rill-update-', dir=path.parent)
            staged[path] = Path(name)
            os.fchmod(descriptor, path.stat().st_mode & 0o777)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        # Refuse to overwrite a concurrent edit detected during preparation.
        if any(path.read_bytes() != old for path, old in originals.items()):
            raise RuntimeError('concurrent edit while preparing package update')
        for path, temporary in staged.items():
            os.replace(temporary, path)
            written.append(path)
    except Exception:
        for path in reversed(written):
            if path.read_bytes() != updates[path]:
                raise RuntimeError(f'concurrent edit prevents rollback: {path}')
            descriptor, name = tempfile.mkstemp(prefix='.rill-rollback-', dir=path.parent)
            try:
                os.fchmod(descriptor, path.stat().st_mode & 0o777)
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(originals[path])
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, path)
            finally:
                Path(name).unlink(missing_ok=True)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
