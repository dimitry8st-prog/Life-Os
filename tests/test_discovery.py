import datetime as dt
from types import SimpleNamespace

from src import discovery


NOW = dt.datetime(2026, 7, 22, tzinfo=dt.timezone.utc)


def test_discover_filters_scores_and_deduplicates(monkeypatch):
    entries = [
        {"title": "New agentic coding benchmark", "summary": "prompt engineering and AI agents", "link": "https://example.org/a?utm=x", "published_parsed": NOW.timetuple()},
        {"title": "Unrelated cooking", "summary": "recipe", "link": "https://example.org/b", "published_parsed": NOW.timetuple()},
    ]
    monkeypatch.setattr(discovery.feedparser, "parse", lambda *a, **k: SimpleNamespace(entries=entries))
    cfg = {"lookback_days": 7, "max_per_run": 5, "topics": {"vibe-coding": ["agentic coding", "ai agents"]}, "sources": [{"name": "Test", "url": "https://feed", "topics": ["vibe-coding"]}]}
    result = discovery.discover(cfg, set(), now=NOW)
    assert len(result) == 1
    assert result[0].url == "https://example.org/a"
    assert result[0].score >= 20


def test_seen_state_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    discovery.save_seen(path, {"https://example.org/a?x=1"})
    assert discovery.load_seen(path) == {"https://example.org/a"}
