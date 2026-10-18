"""把 kaikki.org 的维基词典数据导入本地 SQLite 数据库。

用法：
    python import_data.py data/raw-wiktextract-data.jsonl.gz
    python import_data.py 文件1.jsonl 文件2.jsonl ...   （也可以用按语言拆分的旧文件）

只保留英语、法语、荷兰语的词条；大文件是一行一行流式读取的，内存占用很小。
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sqlite3
import sys
import time

from etymology import KEEP_TEMPLATES, norm

try:  # orjson 能快 2–3 倍，没有也能用
    import orjson

    loads = orjson.loads
except ImportError:  # pragma: no cover
    loads = json.loads

WANT_LANGS = {"en", "fr", "nl"}
TRANSLATION_LANGS = {"fr", "nl", "cmn", "zh"}
SKIP_POS = {"name", "character", "symbol", "punct", "romanization", "prefix", "suffix", "infix", "affix"}
# 预筛选：只有包含 "lang_code": "en|fr|nl" 的行才需要完整解析（解析后再检查顶层字段）
PREFILTER = re.compile(rb'"lang_code":\s*"(?:en|fr|nl)"')

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY,
  lang TEXT NOT NULL,
  word TEXT NOT NULL,
  word_norm TEXT NOT NULL,
  pos TEXT,
  glosses TEXT,
  etym_text TEXT,
  etym TEXT,
  n_trans INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS translations (
  en_id INTEGER NOT NULL,
  lang TEXT NOT NULL,
  word TEXT NOT NULL,
  word_norm TEXT NOT NULL,
  sense TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""
INDEXES = """
CREATE INDEX IF NOT EXISTS ix_entries_word ON entries(lang, word_norm);
CREATE INDEX IF NOT EXISTS ix_tr_word ON translations(lang, word_norm);
CREATE INDEX IF NOT EXISTS ix_tr_en ON translations(en_id);
"""


def open_any(path: str):
    return gzip.open(path, "rb") if path.endswith(".gz") else open(path, "rb")


def glosses_of(obj: dict) -> list[str]:
    out = []
    for s in obj.get("senses") or []:
        g = s.get("glosses") or s.get("raw_glosses") or []
        if g:
            out.append(g[-1] if len(g) > 1 else g[0])
        if len(out) >= 6:
            break
    return out


def run(paths: list[str], db_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)

    counts = {k: 0 for k in WANT_LANGS}
    lines = 0
    t0 = time.time()
    batch_e, batch_t = [], []
    next_id = 1

    def flush():
        con.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?)", batch_e)
        con.executemany("INSERT INTO translations VALUES (?,?,?,?,?)", batch_t)
        con.commit()
        batch_e.clear()
        batch_t.clear()

    for path in paths:
        total = os.path.getsize(path)
        with open_any(path) as f:
            raw = f.fileobj if hasattr(f, "fileobj") else f  # 用来估算进度
            for line in f:
                lines += 1
                if lines % 200_000 == 0:
                    pos = raw.tell() if hasattr(raw, "tell") else 0
                    pct = 100 * pos / total if total else 0
                    print(f"\r  已读 {lines:,} 行  {pct:5.1f}%  英 {counts['en']:,} 法 {counts['fr']:,} 荷 {counts['nl']:,}"
                          f"  用时 {int(time.time() - t0)} 秒", end="", flush=True)
                if not PREFILTER.search(line):
                    continue
                try:
                    obj = loads(line)
                except ValueError:
                    continue
                lang = obj.get("lang_code")
                word = obj.get("word")
                if lang not in WANT_LANGS or not word or obj.get("pos") in SKIP_POS:
                    continue
                gl = glosses_of(obj)
                if not gl:
                    continue
                etym = [t for t in (obj.get("etymology_templates") or []) if t.get("name") in KEEP_TEMPLATES]
                trs = []
                if lang == "en":
                    for t in obj.get("translations") or []:
                        code = t.get("code") or t.get("lang_code")
                        w = t.get("word")
                        if code in TRANSLATION_LANGS and w:
                            trs.append((next_id, "cmn" if code == "zh" else code, w, norm(w), t.get("sense") or ""))
                batch_e.append((next_id, lang, word, norm(word), obj.get("pos"),
                                json.dumps(gl, ensure_ascii=False),
                                (obj.get("etymology_text") or "")[:4000],
                                json.dumps(etym, ensure_ascii=False),
                                sum(1 for x in trs if x[1] in ("fr", "nl"))))
                batch_t.extend(trs)
                counts[lang] += 1
                next_id += 1
                if len(batch_e) >= 5000:
                    flush()
    flush()
    print(f"\n建立索引……")
    con.executescript(INDEXES)
    con.execute("INSERT OR REPLACE INTO meta VALUES ('imported_at', ?)", (time.strftime("%Y-%m-%d"),))
    con.execute("INSERT OR REPLACE INTO meta VALUES ('source', ?)", (", ".join(os.path.basename(p) for p in paths),))
    con.commit()
    con.execute("VACUUM")
    con.close()
    print(f"完成：英语 {counts['en']:,} 条，法语 {counts['fr']:,} 条，荷兰语 {counts['nl']:,} 条。"
          f"数据库：{db_path}（用时 {int(time.time() - t0)} 秒）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="导入 kaikki.org 维基词典数据")
    ap.add_argument("files", nargs="+", help="kaikki 的 .jsonl 或 .jsonl.gz 文件")
    ap.add_argument("--db", default=os.path.join("data", "words.db"), help="数据库保存位置")
    a = ap.parse_args()
    for p in a.files:
        if not os.path.exists(p):
            sys.exit(f"找不到文件：{p}")
    run(a.files, a.db)
