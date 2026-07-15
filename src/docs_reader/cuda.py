"""GPU (CUDA) Ollama helper.

The system Ollama is often a snap package whose sandbox forces CPU. This module
runs a GPU-enabled Ollama on a separate port (:11500) WITHOUT sudo by launching the
snap's bundled binary + CUDA libraries OUTSIDE the sandbox, reusing the models the
snap already downloaded. ``--cuda`` on the CLI calls :func:`ensure_gpu_server`.

Paths are overridable via env for non-snap installs:
    DOCS_READER_OLLAMA_BIN, DOCS_READER_OLLAMA_LIB, OLLAMA_MODELS
"""

from __future__ import annotations

import os
import subprocess
import time
import urllib.request
from pathlib import Path

GPU_HOST = os.environ.get("DOCS_READER_CUDA_HOST", "127.0.0.1:11500")
GPU_BASE_URL = f"http://{GPU_HOST}/v1"

_SNAP = Path("/snap/ollama/current")
_DEFAULT_BIN = os.environ.get("DOCS_READER_OLLAMA_BIN", str(_SNAP / "bin" / "ollama"))
_DEFAULT_LIB = os.environ.get("DOCS_READER_OLLAMA_LIB", str(_SNAP / "lib" / "ollama"))
_DEFAULT_MODELS = os.environ.get("OLLAMA_MODELS", "/var/snap/ollama/common/models")
_LOG = "/tmp/docsreader_ollama_gpu.log"


def server_up(host: str = GPU_HOST, timeout: float = 2.0) -> bool:
    try:
        urllib.request.urlopen(f"http://{host}/api/version", timeout=timeout)
        return True
    except Exception:
        return False


def uses_gpu(host: str = GPU_HOST) -> bool:
    """Best-effort check that a loaded model is on the GPU (reads the log)."""
    try:
        log = Path(_LOG).read_text(errors="replace")
        return "library=CUDA" in log
    except Exception:
        return False


def ensure_gpu_server(timeout: int = 90) -> str:
    """Ensure a GPU Ollama is listening; start it if needed. Returns the base URL."""
    if server_up():
        return GPU_BASE_URL

    binary = Path(_DEFAULT_BIN)
    if not binary.exists():
        raise RuntimeError(
            f"GPU Ollama is not running on {GPU_HOST} and no Ollama binary was found at "
            f"{binary}. Set DOCS_READER_OLLAMA_BIN / DOCS_READER_OLLAMA_LIB, or start a GPU "
            f"Ollama manually (see tools/ollama_gpu.sh)."
        )

    libdir = Path(_DEFAULT_LIB)
    env = dict(os.environ)
    env["OLLAMA_HOST"] = GPU_HOST
    env.setdefault("OLLAMA_MODELS", _DEFAULT_MODELS)
    ld = [str(libdir), str(libdir / "cuda_v12"), str(libdir / "cuda_v13")]
    env["LD_LIBRARY_PATH"] = ":".join(p for p in ld if Path(p).exists()) + ":" + env.get("LD_LIBRARY_PATH", "")

    with open(_LOG, "a") as log:
        subprocess.Popen(
            [str(binary), "serve"], env=env, stdout=log, stderr=log, start_new_session=True
        )

    deadline = time.time() + timeout
    while time.time() < deadline:
        if server_up():
            return GPU_BASE_URL
        time.sleep(1)
    raise RuntimeError(f"GPU Ollama did not become ready on {GPU_HOST} within {timeout}s (see {_LOG})")
