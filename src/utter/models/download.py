"""Model downloader: streams the .tar.bz2, reports progress, extracts atomically."""

from __future__ import annotations

import logging
import shutil
import tarfile
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Callable

from utter import __version__
from utter.models.registry import ModelSpec, resolve_files

log = logging.getLogger(__name__)

ProgressFn = Callable[[int, int], None]  # (bytes_done, bytes_total or -1)


class DownloadCancelled(Exception):
    pass


def _safe_members(tar: tarfile.TarFile, dest: Path):
    """Refuse path traversal / absolute paths inside the archive."""
    dest_resolved = dest.resolve()
    for m in tar.getmembers():
        target = (dest / m.name).resolve()
        if dest_resolved not in target.parents and target != dest_resolved:
            raise tarfile.TarError(f"unsafe path in archive: {m.name}")
        if m.issym() or m.islnk():
            continue
        yield m


def download_model(
    spec: ModelSpec,
    progress: ProgressFn | None = None,
    cancel: threading.Event | None = None,
    chunk_size: int = 1 << 18,
) -> Path:
    """Download + extract `spec` into its install dir. Returns the install dir."""
    dest = spec.install_dir
    if resolve_files(spec, dest) is not None:
        return dest

    tmp_root = Path(tempfile.mkdtemp(prefix=f"utter-{spec.id}-", dir=dest.parent))
    archive = tmp_root / "model.tar.bz2"
    try:
        req = urllib.request.Request(spec.url, headers={"User-Agent": f"Utter/{__version__}"})
        with urllib.request.urlopen(req, timeout=60) as resp, archive.open("wb") as fh:
            total = int(resp.headers.get("Content-Length") or -1)
            done = 0
            while True:
                if cancel is not None and cancel.is_set():
                    raise DownloadCancelled()
                block = resp.read(chunk_size)
                if not block:
                    break
                fh.write(block)
                done += len(block)
                if progress:
                    progress(done, total)

        extract_dir = tmp_root / "x"
        extract_dir.mkdir()
        with tarfile.open(archive, "r:bz2") as tar:
            tar.extractall(extract_dir, members=_safe_members(tar, extract_dir))
        archive.unlink(missing_ok=True)

        # Archives contain exactly one top-level folder; flatten it into the install dir.
        entries = [p for p in extract_dir.iterdir()]
        src = entries[0] if len(entries) == 1 and entries[0].is_dir() else extract_dir
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        shutil.move(str(src), str(dest))

        if resolve_files(spec, dest) is None:
            raise RuntimeError(
                f"Archive for {spec.id} did not contain the expected files. "
                "The upstream package layout may have changed - please open an issue."
            )
        log.info("installed %s -> %s", spec.id, dest)
        return dest
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def delete_model(spec: ModelSpec) -> None:
    shutil.rmtree(spec.install_dir, ignore_errors=True)


def dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) / (1024 * 1024)
