from __future__ import annotations

from docs_reader import cuda
from docs_reader.config import Settings


def test_gpu_base_url_shape():
    assert cuda.GPU_BASE_URL.startswith("http://")
    assert cuda.GPU_BASE_URL.endswith("/v1")


def test_server_up_false_on_dead_port():
    assert cuda.server_up("127.0.0.1:1", timeout=0.5) is False


def test_default_model_is_gemma():
    assert Settings().os_text_model == "gemma3:4b"


def test_cuda_env_toggle(monkeypatch):
    monkeypatch.setenv("DOCS_READER_CUDA", "1")
    assert Settings().cuda is True
    monkeypatch.setenv("DOCS_READER_CUDA", "0")
    assert Settings().cuda is False
