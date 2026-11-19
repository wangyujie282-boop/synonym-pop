"""Check the distributable game without third-party Python dependencies."""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from build import ROOT, build


def json_after(text, marker):
    return json.JSONDecoder().raw_decode(text, text.index(marker) + len(marker))


def verify():
    page_path = ROOT / "web/index.html"
    before = page_path.read_bytes()
    build()
    assert before == page_path.read_bytes(), "web/index.html is outdated; rebuild and commit it"
    text = before.decode("utf-8")
    listening, end = json_after(text, "const DATAS={L:")
    reading, _ = json.JSONDecoder().raw_decode(text, end + 3)
    audio, _ = json_after(text, "const AUDIO_MAP=")
    qa, _ = json_after(text, "const CONTENT_QA=")
    totals = {}
    for mode, data in [("L", listening), ("R", reading)]:
        totals[mode] = sum(not qa[mode].get(f"{book}|{i}") for book, rows in data.items() for i, _ in enumerate(rows))
        assert all(len(row) >= 5 and row[2].strip() and row[3].strip() for rows in data.values() for row in rows)
    assert totals == {"L": 981, "R": 2675}, f"Unexpected active item counts: {totals}"
    assert sum(len(qa[m]) for m in ("L", "R")) == 179, "Review holds changed"
    web = (ROOT / "web").resolve()
    for paths in audio.values():
        assert paths, "Empty audio mapping"
        for name in paths:
            path = (web / name).resolve()
            assert web in path.parents and path.is_file(), f"Missing or unsafe audio path: {name}"
            assert path.stat().st_size > 100, f"Empty audio file: {name}"
    for book, rows in listening.items():
        for index, row in enumerate(rows):
            if not qa["L"].get(f"{book}|{index}"):
                for wording in row[2:4]:
                    assert audio.get(wording), f"No recording: {book}, item {index}"
    for name in re.findall(r'(?:src|href)="(assets/[^"<>]+)"', text):
        assert (web / name).is_file(), f"Missing asset: {name}"
    font_dir = web / "assets/fonts"
    for item in json.loads((font_dir / "SOURCES.json").read_text(encoding="utf-8")):
        assert hashlib.sha256((font_dir / item["file"]).read_bytes()).hexdigest() == item["sha256"], f"Font changed: {item['file']}"
    assert "DAILY_REVIEW_LIMIT" not in text and "function dailyReviewPool" not in text
    assert not any(token in text for token in ("__DATA__", "__RDATA__", "__AUDIO__", "__QA__"))
    assert "fonts.googleapis.com" not in text
    # Only inspect publishable sources and assets, never local Git credentials or metadata.
    banned = ["niao" + "xiaofang", "鸟" + "小方", "/Users/", "/Volumes/", "BEGIN PRIVATE KEY", "github_pat_", "ghp_"]
    for folder in (ROOT / "source", ROOT / "web"):
        for path in folder.rglob("*"):
            if not path.is_file():
                continue
            assert not path.is_symlink(), f"Unexpected symlink: {path.name}"
            assert not any(word in path.name for word in banned), "Excluded asset filename"
            if path.suffix in {".html", ".json", ".svg", ".css"}:
                content = path.read_text(encoding="utf-8")
                assert not any(word in content for word in banned), f"Excluded content: {path.relative_to(ROOT)}"
    audio_count = len(list((web / "audio").glob("*.mp3")))
    assert audio_count == 1815, f"Unexpected audio file count: {audio_count}"
    node = shutil.which("node")
    if node:
        script = re.search(r"<script>(.*)</script>", text, re.S).group(1)
        with tempfile.TemporaryDirectory() as folder:
            filename = Path(folder) / "game.js"
            filename.write_text(script, encoding="utf-8")
            subprocess.run([node, "--check", str(filename)], check=True)
    print(json.dumps({"activeItems": totals, "heldItems": 179, "audioFiles": audio_count, "javascriptSyntax": "passed" if node else "not checked (Node unavailable)", "result": "passed"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    verify()
