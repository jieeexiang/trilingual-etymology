"""生成一份小样例数据（格式与 kaikki.org 的原始数据相同），用来在没下载大文件时测试程序。

用法：python tests/make_sample.py  → 生成 tests/sample.jsonl.gz
"""
import gzip
import json
import os


def T(name, *pos, **kw):
    args = {str(i + 1): v for i, v in enumerate(pos)}
    args.update(kw)
    return {"name": name, "args": args, "expansion": ""}


def E(lang, word, pos, glosses, etym=(), etext="", trans=()):
    names = {"en": "English", "fr": "French", "nl": "Dutch", "de": "German"}
    return {"word": word, "lang": names[lang], "lang_code": lang, "pos": pos,
            "senses": [{"glosses": [g]} for g in glosses],
            "etymology_text": etext, "etymology_templates": list(etym),
            "translations": [{"code": c, "lang": c, "word": w, "sense": s} for c, w, s in trans]}


SAMPLE = [
    E("en", "garden", "noun", ["An outdoor area containing one or more types of plants."],
      [T("root", "en", "ine-pro", "*gʰerdʰ-"), T("inh", "en", "enm", "gardyn"), T("der", "en", "xno", "gardin"),
       T("der", "en", "frk", "*gardō", "*gardin-"), T("der", "en", "gem-pro", "*gardô", "", "enclosure, garden, house"),
       T("cog", "en", "yard"), T("doublet", "en", "jardin"), T("cog", "nl", "gaard"), T("cog", "de", "Garten"),
       T("cog", "fr", "jardin")],
      "From Middle English gardyn, from Anglo-Norman gardin, from Frankish *gardō …",
      [("fr", "parc", "gardens with public access"), ("fr", "jardin public", "gardens with public access"),
       ("fr", "jardin", "grounds at the front or back of a house"), ("nl", "park", "gardens with public access"),
       ("nl", "tuin", "gardens with public access"), ("nl", "tuin", "grounds at the front or back of a house"),
       ("cmn", "花园", ""), ("cmn", "园子", "")]),
    E("en", "garden", "verb", ["To grow plants in a garden."]),
    E("fr", "jardin", "noun", ["garden"],
      [T("inh", "fr", "fro", "jardin"), T("der", "fr", "frk", "*gardō"), T("der", "fr", "gem-pro", "*gardô")],
      "From Old French jardin, from Frankish *gardō."),
    E("fr", "parc", "noun", ["park"], [T("inh", "fr", "fro", "parc"), T("der", "fr", "ML.", "parricus")]),
    E("nl", "tuin", "noun", ["garden, yard", "fence"],
      [T("inh", "nl", "dum", "tûn"), T("inh", "nl", "odt", "*tūn"), T("inh", "nl", "gmw-pro", "*tūn"),
       T("inh", "nl", "gem-pro", "*tūną"), T("cog", "en", "town")],
      "From Middle Dutch tûn, from Old Dutch *tūn, from Proto-Germanic *tūną."),
    E("nl", "park", "noun", ["park"], [T("bor", "nl", "fr", "parc")]),
    E("en", "house", "noun", ["A structure built as a dwelling."],
      [T("inh", "en", "enm", "hous"), T("inh", "en", "ang", "hūs"), T("inh", "en", "gmw-pro", "*hūs"),
       T("inh", "en", "gem-pro", "*hūsą"), T("cog", "nl", "huis")],
      "From Middle English hous, from Old English hūs …",
      [("fr", "maison", "dwelling"), ("nl", "huis", "dwelling"), ("nl", "woning", "dwelling"), ("cmn", "房子", "")]),
    E("fr", "maison", "noun", ["house, home"], [T("inh", "fr", "fro", "maison"), T("inh", "fr", "la", "mānsiōnem")]),
    E("nl", "huis", "noun", ["house"],
      [T("inh", "nl", "dum", "hûs"), T("inh", "nl", "odt", "*hūs"), T("inh", "nl", "gmw-pro", "*hūs"),
       T("inh", "nl", "gem-pro", "*hūsą")]),
    E("nl", "woning", "noun", ["dwelling, residence"], [T("af", "nl", "wonen", "-ing")]),
    E("en", "war", "noun", ["Organized, large-scale, armed conflict."],
      [T("inh", "en", "enm", "werre"), T("inh", "en", "ang", "werre"), T("der", "en", "fro-nor", "werre"),
       T("der", "en", "ML.", "werra"), T("der", "en", "frk", "*werru", "", "confusion; quarrel")],
      "From Middle English werre, from Late Old English werre, from Old Northern French werre …",
      [("fr", "guerre", ""), ("nl", "oorlog", ""), ("nl", "krijg", ""), ("cmn", "战争", "")]),
    E("fr", "guerre", "noun", ["war"], [T("inh", "fr", "fro", "guerre"), T("der", "fr", "frk", "*werru")]),
    E("nl", "oorlog", "noun", ["war"], [T("inh", "nl", "dum", "orloge"), T("inh", "nl", "odt", "*urlagi"),
                                        T("inh", "nl", "gem-pro", "*uzlagą")]),
    E("en", "table", "noun", ["Item of furniture with a flat top."],
      [T("inh", "en", "enm", "table"), T("inh", "en", "ang", "tabele"), T("der", "en", "fro", "table"),
       T("der", "en", "la", "tabula")], "From Middle English table, from Old English tabele and Old French table …",
      [("fr", "table", "furniture"), ("nl", "tafel", "furniture"), ("nl", "tabel", "arrangement of data"),
       ("cmn", "桌子", "")]),
    E("fr", "table", "noun", ["table"], [T("inh", "fr", "fro", "table"), T("inh", "fr", "la", "tabula")]),
    E("nl", "tafel", "noun", ["table (piece of furniture)"],
      [T("inh", "nl", "dum", "tâfele"), T("inh", "nl", "odt", "tavala"), T("der", "nl", "la", "tabula")]),
    E("nl", "tabel", "noun", ["table (arrangement of data)"], [T("bor", "nl", "la", "tabula")]),
    E("en", "beef", "noun", ["The meat from a cow."],
      [T("inh", "en", "enm", "beef"), T("der", "en", "xno", "boef"), T("der", "en", "fro", "buef"),
       T("der", "en", "la", "bovem")], "",
      [("fr", "bœuf", ""), ("nl", "rundvlees", ""), ("cmn", "牛肉", "")]),
    E("fr", "bœuf", "noun", ["ox; beef"], [T("inh", "fr", "fro", "buef"), T("inh", "fr", "la", "bovem")]),
    E("nl", "rundvlees", "noun", ["beef"], [T("compound", "nl", "rund", "vlees")]),
    # 干扰项：其他语言的词条应该被跳过
    E("de", "Garten", "noun", ["garden"]),
]

if __name__ == "__main__":
    path = os.path.join(os.path.dirname(__file__), "sample.jsonl.gz")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for e in SAMPLE:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"已生成 {path}（{len(SAMPLE)} 条）")
