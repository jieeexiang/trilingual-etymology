"""查词：从数据库里找出英、法、荷三个对应词，并组装词源链和关系分析。"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from urllib.parse import quote

from etymology import analyse, build_chain, norm, related_words

LANG_NAMES = {"en": "English", "fr": "French", "nl": "Dutch"}
SIDE_LANGS = ("en", "fr", "nl")


class Dictionary:
    def __init__(self, db_path: str):
        self.con = sqlite3.connect(db_path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row

    # ---------- 基础查询 ----------
    def entries(self, lang: str, word: str) -> list[dict]:
        rows = self.con.execute("SELECT * FROM entries WHERE lang=? AND word_norm=?", (lang, norm(word))).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["glosses"] = json.loads(d["glosses"] or "[]")
            d["etym"] = json.loads(d["etym"] or "[]")
            out.append(d)
        # 大小写完全一致的优先（Brood 与 brood）
        out.sort(key=lambda d: d["word"] != word)
        return out

    def meta(self) -> dict:
        try:
            return {k: v for k, v in self.con.execute("SELECT key, value FROM meta")}
        except sqlite3.Error:
            return {}

    # ---------- 选词 ----------
    @staticmethod
    def _best_entry(rows: list[dict], prefer_pos: str | None = None) -> dict | None:
        if not rows:
            return None
        return max(rows, key=lambda d: (
            d["word"] == rows[0]["word"],
            d["pos"] == prefer_pos,
            d["n_trans"],
            bool(d["etym"]),
            d["pos"] == "noun",
            -d["id"],
        ))

    @staticmethod
    def _mentions(glosses: list[str], word: str) -> int:
        """释义里是否出现某个英语词：首条释义命中 2 分，其他释义命中 1 分。"""
        pat = re.compile(r"(?<![\w-])" + re.escape(word.lower()) + r"(?![\w-])")
        for i, g in enumerate(glosses):
            if pat.search(g.lower()):
                return 2 if i == 0 else 1
        return 0

    def candidates(self, en_entry: dict, lang: str) -> list[str]:
        """英语词在 lang 里的候选对应词，按可信程度排序。"""
        rows = self.con.execute("SELECT word, sense FROM translations WHERE en_id=? AND lang=?",
                                (en_entry["id"], lang)).fetchall()
        if not rows:
            return []
        count = Counter(r["word"] for r in rows)
        first_sense = Counter(r["word"] for r in rows if r["sense"] == rows[0]["sense"])
        cogs = {c["word"] for c in related_words("en", en_entry["etym"], {lang})["cognates"]}
        scored = []
        for w, c in count.items():
            back = self.entries(lang, w)
            reverse = max((self._mentions(e["glosses"], en_entry["word"]) for e in back), default=0)
            score = 3 * reverse + c + first_sense.get(w, 0) + (1 if w in cogs else 0) - (1 if " " in w else 0) - (3 if not back else 0)
            scored.append((score, w))
        scored.sort(key=lambda x: -x[0])
        return [w for _, w in scored]

    def english_for(self, lang: str, word: str) -> list[str]:
        """法语或荷兰语词对应的英语词，按可信程度排序。"""
        score: Counter = Counter()
        for r in self.con.execute(
                "SELECT e.word FROM translations t JOIN entries e ON e.id=t.en_id WHERE t.lang=? AND t.word_norm=?",
                (lang, norm(word))):
            score[r["word"]] += 1
        for e in self.entries(lang, word)[:3]:
            for i, g in enumerate(e["glosses"][:3]):
                head = re.split(r"[;,(:]", g)[0].strip().lower()
                head = re.sub(r"^(a|an|the|to)\s+", "", head)
                if head and len(head.split()) <= 2 and self.entries("en", head):
                    score[head] += 4 if i == 0 else 2
        return [w for w, _ in score.most_common(6)]

    # ---------- 组装 ----------
    def side(self, lang: str, word: str | None, prefer_pos: str | None, alternatives: list[str]) -> dict | None:
        if not word:
            return None
        e = self._best_entry(self.entries(lang, word), prefer_pos)
        if not e:
            return {"lang": lang, "w": word, "pos": None, "glosses": [], "chain": build_chain(lang, word, []),
                    "etym_text": "", "url": wikt_url(word, lang), "alternatives": alternatives, "missing": True}
        return {"lang": lang, "w": e["word"], "pos": e["pos"], "glosses": e["glosses"][:3],
                "chain": build_chain(lang, e["word"], e["etym"]), "etym_text": e["etym_text"],
                "url": wikt_url(e["word"], lang),
                "alternatives": [a for a in alternatives if norm(a) != norm(e["word"])][:5],
                "_etym": e["etym"]}

    def lookup(self, q: str, lang: str | None = None, pick: dict | None = None) -> dict:
        q = (q or "").strip()
        pick = pick or {}
        if not q:
            return {"found": False, "query": q}
        found_in = [l for l in SIDE_LANGS if self.entries(l, q)]
        if lang not in SIDE_LANGS:
            lang = None
        if not found_in:
            return {"found": False, "query": q}
        src = lang if lang in found_in else None

        # 确定英语“中枢词”
        en_entry = None
        if pick.get("en"):
            en_entry = self._best_entry(self.entries("en", pick["en"]))
        if not en_entry and (src in (None, "en")) and "en" in found_in:
            cand = self._best_entry(self.entries("en", q))
            if cand and (cand["n_trans"] or src == "en" or found_in == ["en"]):
                en_entry, src = cand, "en"
        en_alts: list[str] = []
        if not en_entry:
            src = src or next(l for l in ("fr", "nl", "en") if l in found_in)
            if src != "en":
                en_alts = self.english_for(src, q)
                for w in en_alts:
                    en_entry = self._best_entry(self.entries("en", w))
                    if en_entry:
                        break
        src = src or "en"

        result = {"found": True, "query": q, "source_lang": src,
                  "also_in": [l for l in found_in if l != src], "meta": self.meta()}
        if not en_entry:
            only = self.side(src, q, None, [])
            result.update({"en": None, "fr": only if src == "fr" else None, "nl": only if src == "nl" else None,
                           "zh": [], "tags": [], "headline": "没有找到对应的英语词，只能显示这一种语言。",
                           "notes": [], "related": {"cognates": [], "doublets": []}})
            _strip(result)
            return result

        pos = en_entry["pos"]
        sides = {"en": self.side("en", en_entry["word"], pos, en_alts)}
        for l in ("fr", "nl"):
            alts = self.candidates(en_entry, l)
            if src == l:
                chosen = q if not pick.get(l) else pick[l]
                alts = [q] + [a for a in alts if norm(a) != norm(q)]
            else:
                chosen = pick.get(l) or (alts[0] if alts else None)
            sides[l] = self.side(l, chosen, pos, alts)
        zh = [r["word"] for r in self.con.execute(
            "SELECT DISTINCT word FROM translations WHERE en_id=? AND lang='cmn' LIMIT 4", (en_entry["id"],))]

        rel = analyse(*(sides[l] for l in SIDE_LANGS))
        related = related_words("en", en_entry["etym"], {"nl", "fr", "de"})
        if related["cognates"]:
            listed = "、".join(f"{c['lang']} {c['word']}" for c in related["cognates"][:6])
            rel["notes"].append(f"维基词典列出的 {en_entry['word']} 的同源词：{listed}。")
        if related["doublets"]:
            rel["notes"].append(f"英语里和 {en_entry['word']} 同出一源的“双胞胎词”：{'、'.join(related['doublets'])}。")
        result.update(sides)
        result.update({"zh": zh, "related": related, **rel})
        _strip(result)
        return result


def _strip(result: dict) -> None:
    for l in SIDE_LANGS:
        if result.get(l):
            result[l].pop("_etym", None)


def wikt_url(word: str, lang: str) -> str:
    return f"https://en.wiktionary.org/wiki/{quote(word)}#{LANG_NAMES[lang]}"
