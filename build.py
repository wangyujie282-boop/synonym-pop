"""Build the static game using only Python's standard library."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"


def load(name):
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build():
    findings = {(f["mode"], f["row"]): f for f in load("content-review.json")["findings"]}
    qa = {"L": {}, "R": {}}
    datasets = {"L": {}, "R": {}}
    for mode, filename in [("L", "rows.json"), ("R", "rrows.json")]:
        for index, source_row in enumerate(load(filename)):
            if mode == "L":
                book, src, number, q, t, zh = source_row
                row = [src, int(number), q, t, zh]
            else:
                book, test, passage, number, q, t, zh, sentence = source_row
                row = [f"T{test}-P{passage}", number, q, t, zh] + ([sentence] if sentence else [])
            finding = findings.get((mode, index), {})
            count = len([x for x in row[3].split("=") if x.strip()])
            for key, value in finding.get("correction", {}).items():
                row[{"q": 2, "t": 3, "zh": 4}[key]] = value
            if len([x for x in row[3].split("=") if x.strip()]) != count:
                raise ValueError(f"Correction changes saved indices: {mode} row {index}")
            if mode == "R":
                for column in (2, 3):
                    row[column] = re.sub(r"\s*\((?:n|v|adj|adv|prep|conj|pron)\.\s*\)", "", row[column]).strip()
            target = datasets[mode].setdefault(book, [])
            for wording in ([x.strip() for x in row[3].split("=") if x.strip()] or [row[3]]):
                if finding.get("status") == "hold":
                    qa[mode][f"{book}|{len(target)}"] = True
                target.append(row[:3] + [wording] + row[4:])
    audio = load("audio-map.json")
    for old, new in [("did not realized before", "did not realize before"), ("no placed left", "no place left")]:
        if old in audio:
            audio[new] = audio[old]
    qa["version"] = hashlib.sha256(encode([datasets["L"], datasets["R"], qa]).encode()).hexdigest()[:12]
    page = (SOURCE / "template.html").read_text(encoding="utf-8")
    for token, value in [("__DATA__", datasets["L"]), ("__RDATA__", datasets["R"]), ("__AUDIO__", audio), ("__QA__", qa)]:
        page = page.replace(token, encode(value))
    # Keep the same generated document structure and stable item IDs as the original release.
    page = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><link rel="icon" href="data:,"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0">' + page + '</body></html>'
    (ROOT / "web").mkdir(exist_ok=True)
    (ROOT / "web/index.html").write_text(page, encoding="utf-8")
    print("Built web/index.html")


if __name__ == "__main__":
    build()
