import pytest

from engine import BitNetEngine


@pytest.fixture(autouse=True)
def _tmp_tokens_file(tmp_path, monkeypatch):
    """Keeps tokens.json and settings.json out of the repo, and a saved setting from leaking into the next test."""
    monkeypatch.setenv("BITNET_TOKENS_FILE", str(tmp_path / "tokens.json"))


class FakeLoaded:
    """Stands in for a loaded model: answers `reply` and records every call."""

    def __init__(self, source, reply="hello"):
        self.source, self.reply, self.calls = source, reply, []

    def generate(self, messages, temperature, max_tokens, max_time):
        self.calls.append({"messages": messages, "temperature": temperature, "max_tokens": max_tokens})
        return {"content": self.reply, "prompt_tokens": 3, "completion_tokens": 5, "finish": "stop"}


def make_engine(**options):
    """An engine whose loader builds FakeLoaded models; `engine.loads` lists the sources it was asked for."""
    loads = []

    def loader(source):
        loads.append(source)
        return FakeLoaded(source)

    options.setdefault("loader", loader)
    options.setdefault("set_threads", lambda count: None)
    engine = BitNetEngine("m", **options)
    engine.loads = loads
    return engine
