"""yt-dlp argv construction for download.py.

Regression guard: ``--sub-langs all`` makes yt-dlp fetch YouTube's hundreds of
auto-translated caption tracks, which can take minutes and stalls before the
video download even starts. The default must stay bounded to Chinese and
English, with caller-provided language priorities validated before subprocess
execution.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "watch" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import download  # noqa: E402

URL = "https://www.youtube.com/watch?v=rlOpbu3Enkw"


def _capture_argv(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Stub subprocess.run inside download.py and record every argv."""
    calls: list[list[str]] = []

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        return _Result()

    monkeypatch.setattr(download.subprocess, "run", fake_run)
    monkeypatch.setattr(download.shutil, "which", lambda _: "/usr/bin/yt-dlp")
    return calls


def _sub_langs(argv: list[str]) -> str:
    idx = argv.index("--sub-langs")
    return argv[idx + 1]


def _assert_bounded_default(langs: str) -> None:
    tokens = langs.split(",")
    assert "all" not in tokens, f"sub-langs must not request all languages, got {langs!r}"
    assert tokens == ["zh.*", "en.*"]


def test_fetch_captions_requests_bounded_chinese_then_english(monkeypatch, tmp_path):
    calls = _capture_argv(monkeypatch)
    download.fetch_captions(URL, tmp_path / "download")
    _assert_bounded_default(_sub_langs(calls[0]))


def test_download_url_requests_bounded_chinese_then_english(monkeypatch, tmp_path):
    calls = _capture_argv(monkeypatch)
    # _pick_video returns None with no real file, which raises SystemExit after
    # the yt-dlp argv is already built — that's all we need to inspect.
    with pytest.raises(SystemExit):
        download.download_url(URL, tmp_path / "download")
    _assert_bounded_default(_sub_langs(calls[0]))


def test_custom_caption_priority_reaches_ytdlp(monkeypatch, tmp_path):
    calls = _capture_argv(monkeypatch)
    download.fetch_captions(URL, tmp_path / "download", sub_langs="ja.*,en.*")
    assert _sub_langs(calls[0]) == "ja.*,en.*"


def test_rejects_sub_langs_that_look_like_options():
    with pytest.raises(SystemExit, match="--sub-langs"):
        download.normalize_sub_langs("--config-location")


def test_pick_subtitle_uses_requested_priority(tmp_path):
    (tmp_path / "video.en.vtt").touch()
    (tmp_path / "video.zh-Hans.vtt").touch()
    assert download._pick_subtitle(tmp_path, "zh.*,en.*").name == "video.zh-Hans.vtt"
    assert download._pick_subtitle(tmp_path, "en.*,zh.*").name == "video.en.vtt"
