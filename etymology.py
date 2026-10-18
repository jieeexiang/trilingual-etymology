"""词源分析：把维基词典的词源模板（etymology_templates）变成词源链，并判断三种语言之间的关系。"""
from __future__ import annotations

import unicodedata

# 维基词典语言代码 -> (中文名, 语系)
# 语系：G 日耳曼语支  R 法语/罗曼语  L 拉丁语  O 其他
LANGS: dict[str, tuple[str, str]] = {
    # 日耳曼语支
    "en": ("英语", "G"), "enm": ("中古英语", "G"), "ang": ("古英语", "G"),
    "sco": ("苏格兰语", "G"),
    "nl": ("荷兰语", "G"), "dum": ("中古荷兰语", "G"), "odt": ("古荷兰语", "G"),
    "vls": ("西佛兰芒语", "G"), "zea": ("泽兰语", "G"), "li": ("林堡语", "G"),
    "frk": ("法兰克语", "G"),
    "gem-pro": ("原始日耳曼语", "G"), "gmw-pro": ("原始西日耳曼语", "G"),
    "ine-pro": ("原始印欧语", "O"),
    "de": ("德语", "G"), "gmh": ("中古高地德语", "G"), "goh": ("古高地德语", "G"),
    "nds": ("低地德语", "G"), "gml": ("中古低地德语", "G"), "osx": ("古撒克逊语", "G"),
    "fy": ("西弗里斯兰语", "G"), "ofs": ("古弗里斯兰语", "G"),
    "non": ("古诺尔斯语", "G"), "da": ("丹麦语", "G"), "sv": ("瑞典语", "G"),
    "nb": ("书面挪威语", "G"), "nn": ("新挪威语", "G"), "no": ("挪威语", "G"),
    "is": ("冰岛语", "G"), "got": ("哥特语", "G"), "yi": ("意第绪语", "G"),
    "gmq-pro": ("原始北日耳曼语", "G"), "gme-pro": ("原始东日耳曼语", "G"),
    # 法语 / 罗曼语
    "fr": ("法语", "R"), "frm": ("中古法语", "R"), "fro": ("古法语", "R"),
    "xno": ("盎格鲁-诺曼语", "R"), "fro-nor": ("古北部法语", "R"),
    "fro-pic": ("古皮卡第语", "R"), "pcd": ("皮卡第语", "R"), "wa": ("瓦隆语", "R"),
    "pro": ("古奥克语", "R"), "oc": ("奥克语", "R"),
    "it": ("意大利语", "R"), "es": ("西班牙语", "R"), "pt": ("葡萄牙语", "R"),
    "ca": ("加泰罗尼亚语", "R"), "ro": ("罗马尼亚语", "R"),
    "roa-opt": ("古葡萄牙语", "R"), "osp": ("古西班牙语", "R"),
    # 拉丁语
    "la": ("拉丁语", "L"), "la-lat": ("晚期拉丁语", "L"), "la-med": ("中世纪拉丁语", "L"),
    "la-vul": ("通俗拉丁语", "L"), "VL.": ("通俗拉丁语", "L"), "la-ecc": ("教会拉丁语", "L"),
    "la-new": ("新拉丁语", "L"), "la-cla": ("古典拉丁语", "L"), "ML.": ("中世纪拉丁语", "L"),
    "LL.": ("晚期拉丁语", "L"), "itc-pro": ("原始意大利语", "L"),
    # 其他常见来源
    "grc": ("古希腊语", "O"), "el": ("希腊语", "O"), "gkm": ("中古希腊语", "O"),
    "ar": ("阿拉伯语", "O"), "fa": ("波斯语", "O"), "he": ("希伯来语", "O"),
    "cel-pro": ("原始凯尔特语", "O"), "cel-gau": ("高卢语", "O"), "xtg": ("高卢语", "O"),
    "ga": ("爱尔兰语", "O"), "cy": ("威尔士语", "O"), "sa": ("梵语", "O"),
    "tr": ("土耳其语", "O"), "ja": ("日语", "O"), "zh": ("汉语", "O"), "cmn": ("普通话", "O"),
}

FAMILY_NAMES = {"G": "日耳曼语支", "R": "法语 / 罗曼语", "L": "拉丁语", "O": "其他"}
FRENCH_LINE = {"fr", "frm", "fro", "xno", "fro-nor", "fro-pic", "pcd", "wa"}

# 构成“从哪里来”的模板（参数 1 = 本词语言，2 = 来源语言，3 = 来源词形）
CHAIN_TEMPLATES = {
    "inh": "继承", "inh+": "继承", "inh-lite": "继承",
    "der": "源自", "der+": "源自", "der-lite": "源自", "uder": "源自",
    "bor": "借自", "bor+": "借自", "lbor": "借自", "slbor": "借自",
    "obor": "借自", "ubor": "借自", "lbor+": "借自",
    "cal": "仿译自", "calque": "仿译自", "sl": "意义借自", "semantic loan": "意义借自",
}
MORPH_TEMPLATES = {"af", "affix", "compound", "com", "com+", "prefix", "suffix", "confix", "blend"}
KEEP_TEMPLATES = set(CHAIN_TEMPLATES) | MORPH_TEMPLATES | {"cog", "doublet", "root"}


def lang_info(code: str) -> tuple[str, str]:
    if code in LANGS:
        return LANGS[code]
    if code.startswith("la-"):
        return ("拉丁语", "L")
    return (code, "O")


def norm(s: str) -> str:
    """查词用的规范化：小写、去掉重音和星号。"""
    s = (s or "").strip().lower().replace("œ", "oe").replace("æ", "ae").lstrip("*")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def base_code(code: str) -> str:
    """比较祖先时把同一语言的变体合并：la-vul -> la，fro-nor -> fro；原始语保持原样。"""
    if code.endswith("-pro"):
        return code
    if code in ("VL.", "LL.", "ML."):
        return "la"
    return code.split("-")[0]


def _arg(args: dict, *keys: str) -> str:
    for k in keys:
        v = args.get(k)
        if v and v != "-":
            return str(v)
    return ""


def build_chain(lang: str, word: str, templates: list[dict]) -> list[dict]:
    """返回从近到远的词源链，第一个节点是词本身。"""
    name, fam = lang_info(lang)
    chain = [{"code": lang, "lang": name, "fam": fam, "form": word, "how": "", "mean": ""}]
    seen = {(base_code(lang), norm(word))}
    morph = None
    for t in templates or []:
        tname = t.get("name", "")
        args = t.get("args") or {}
        if tname in CHAIN_TEMPLATES:
            if args.get("1") != lang:
                continue
            src = _arg(args, "2")
            if not src:
                continue
            form = _arg(args, "3", "4")
            mean = _arg(args, "5", "t", "gloss")
            key = (base_code(src), norm(form))
            if key in seen and form:
                continue
            seen.add(key)
            sname, sfam = lang_info(src)
            chain.append({"code": src, "lang": sname, "fam": sfam, "form": form or "（未写明词形）",
                          "how": CHAIN_TEMPLATES[tname], "mean": mean})
        elif tname in MORPH_TEMPLATES and morph is None and args.get("1") == lang:
            parts = [str(args[k]) for k in sorted((k for k in args if k.isdigit() and k != "1"), key=int) if args[k]]
            if len(parts) >= 2:
                morph = {"code": lang, "lang": "构词", "fam": fam, "form": " + ".join(parts),
                         "how": "由几部分组成", "mean": ""}
    if len(chain) == 1 and morph:
        chain.append(morph)
    return chain[:8]


def related_words(lang: str, templates: list[dict], want: set[str]) -> dict:
    """维基词典明确列出的同源词（cog）和双胞胎词（doublet）。"""
    cogs, doublets = [], []
    for t in templates or []:
        args = t.get("args") or {}
        if t.get("name") == "cog" and args.get("1") in want and args.get("2"):
            cogs.append({"code": args["1"], "lang": lang_info(args["1"])[0], "word": args["2"]})
        elif t.get("name") == "doublet" and args.get("1") == lang:
            for k in sorted((k for k in args if k.isdigit() and k != "1"), key=int):
                if args[k]:
                    doublets.append(args[k])
    # 去重
    seen, uniq = set(), []
    for c in cogs:
        k = (c["code"], c["word"])
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return {"cognates": uniq[:12], "doublets": list(dict.fromkeys(doublets))[:6]}


def shared_ancestor(a: list[dict], b: list[dict]) -> dict | None:
    """两条词源链里最近的共同祖先（相同语言 + 相同词形）。"""
    index = {(base_code(n["code"]), norm(n["form"])): n for n in b}
    for n in a:
        hit = index.get((base_code(n["code"]), norm(n["form"])))
        if hit and n["form"] and not n["form"].startswith("（"):
            return n
    return None


def _first_index(chain: list[dict], pred) -> int:
    for i, n in enumerate(chain[1:], start=1):
        if pred(n):
            return i
    return -1


def analyse(en: dict | None, fr: dict | None, nl: dict | None) -> dict:
    """根据三条链判断关系。每个参数是 {"w":..., "chain":[...]} 或 None。"""
    tags: list[str] = []
    notes: list[str] = []
    E = en["chain"] if en else []
    F = fr["chain"] if fr else []
    N = nl["chain"] if nl else []
    ew, fw, nw = (en or {}).get("w", ""), (fr or {}).get("w", ""), (nl or {}).get("w", "")

    def fmt(n):
        return f"{n['lang']} {n['form']}"

    # 1. 英语是否经法语进入
    fr_i = _first_index(E, lambda n: n["code"] in FRENCH_LINE)
    via_french = fr_i > 0
    loop = via_french and _first_index(E[fr_i:], lambda n: n["fam"] == "G") > 0
    if loop:
        tags.append("loop")
        germ = next(n for n in E[fr_i:] if n["fam"] == "G")
        notes.append(f"英语 {ew} 的根是日耳曼语（{fmt(germ)}），先进入法语，再经 {fmt(E[fr_i])} 传进英语。")
    elif via_french:
        tags.append("borrow")
        notes.append(f"英语 {ew} 是经 {fmt(E[fr_i])} 进入英语的。")

    # 2. 两两共同祖先
    en_nl = shared_ancestor(E, N) if E and N else None
    en_fr = shared_ancestor(E, F) if E and F else None
    fr_nl = shared_ancestor(F, N) if F and N else None

    if en_nl and en_nl["fam"] == "G":
        tags.append("cognate")
        notes.append(f"英语 {ew} 和荷兰语 {nw} 是日耳曼同源词，共同来源是 {fmt(en_nl)}。")
    if en_fr:
        if en_fr["code"] in FRENCH_LINE:
            notes.append(f"英语 {ew} 和法语 {fw} 本来就是同一个词（{fmt(en_fr)}）。")
        else:
            notes.append(f"英语 {ew} 和法语 {fw} 有共同来源：{fmt(en_fr)}。")
    if fr_nl and not (en_nl and en_fr):
        notes.append(f"法语 {fw} 和荷兰语 {nw} 有共同来源：{fmt(fr_nl)}。")

    lat = [x for x in (en_nl, en_fr, fr_nl) if x and x["fam"] == "L"]
    if en_fr and fr_nl and en_nl and lat:
        tags.append("latin")
    elif en_fr and fr_nl and lat and lat[0]["fam"] == "L":
        tags.append("latin")

    # 3. 没有共同祖先时，说明各自的来源
    for label, w, ch in (("英语", ew, E), ("法语", fw, F), ("荷兰语", nw, N)):
        if len(ch) > 1 and ch[-1]["lang"] == "构词":
            notes.append(f"{label} {w} 是由 {ch[-1]['form']} 组合成的词。")
        elif len(ch) > 1 and not any(f"{label} {w}" in x for x in notes):
            notes.append(f"{label} {w} 的最远可追溯来源：{fmt(ch[-1])}（{FAMILY_NAMES[ch[-1]['fam']]}）。")
        elif len(ch) <= 1 and w:
            notes.append(f"维基词典里 {label} {w} 的词源没有结构化标记，请看下面的原文。")

    return {"tags": list(dict.fromkeys(tags)), "notes": notes,
            "headline": headline(tags, ew, fw, nw, en_nl, en_fr, fr_nl, F)}


def headline(tags, ew, fw, nw, en_nl, en_fr, fr_nl, F) -> str:
    parts = []
    if "latin" in tags:
        root = next(x for x in (en_fr, fr_nl, en_nl) if x and x["fam"] == "L")
        return f"三个词都可以追溯到 {root['lang']} {root['form']}，只是进入各语言的路线不同。"
    if "loop" in tags:
        parts.append(f"{ew} 本是日耳曼词，绕道法语才进入英语")
    elif "borrow" in tags:
        parts.append(f"英语 {ew} 借自法语")
    if "cognate" in tags:
        parts.append(f"{ew} 和 {nw} 是日耳曼同源词")
    elif nw and not fr_nl:
        parts.append(f"荷兰语 {nw} 走的是另一条路")
    if fw and not en_fr and len(F) > 1 and "loop" not in tags:
        parts.append(f"法语 {fw} 来自{F[-1]['lang']}")
    if not parts:
        return "维基词典的结构化数据里，没有显示这三个词有共同来源。"
    return "；".join(parts) + "。"
