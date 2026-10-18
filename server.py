"""三语词源对照：本地网页服务器。

用法：
    python server.py                 # 只在本机使用，自动打开浏览器
    python server.py --host 0.0.0.0  # 放到服务器上，让别的设备访问
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import webbrowser

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from lookup import Dictionary

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("TRILINGUAL_DB", os.path.join(HERE, "data", "words.db"))
CONFIG_PATH = os.path.join(HERE, "config.json")


def load_config() -> dict:
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    key = os.environ.get("ANTHROPIC_API_KEY") or cfg.get("anthropic_api_key") or ""
    return {"key": key if key and not key.startswith("在这里") else "",
            "model": os.environ.get("CLAUDE_MODEL") or cfg.get("model") or "claude-haiku-5-5"}


CONFIG = load_config()
app = FastAPI(title="三语词源对照")
_dict: Dictionary | None = None


def get_dict() -> Dictionary:
    global _dict
    if _dict is None:
        if not os.path.exists(DB_PATH):
            raise HTTPException(503, "还没有导入词典数据，请先运行 download_data.py 和 import_data.py。")
        _dict = Dictionary(DB_PATH)
    return _dict


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


@app.get("/api/status")
def status():
    ready = os.path.exists(DB_PATH)
    return {"db_ready": ready, "meta": get_dict().meta() if ready else {},
            "ai_enabled": bool(CONFIG["key"]), "model": CONFIG["model"] if CONFIG["key"] else None}


@app.get("/api/lookup")
def lookup(q: str = Query(..., max_length=80), lang: str | None = None,
           en: str | None = None, fr: str | None = None, nl: str | None = None):
    return get_dict().lookup(q, lang, {"en": en, "fr": fr, "nl": nl})


class ExplainRequest(BaseModel):
    q: str
    lang: str | None = None
    en: str | None = None
    fr: str | None = None
    nl: str | None = None


PROMPT = """你是一位给中文母语者讲欧洲语言的老师。学生住在比利时佛兰德斯，在学英语、法语和荷兰语（佛兰芒语）。
下面是从维基词典数据里自动整理出的一个词条：三个对应词、各自的词源链（从近到远），以及程序判断出的关系。
请用中文写 3 到 5 句通俗的讲解，说明这三个词之间的关系，最后给一个能同时记住它们的小窍门。
要求：
- 只使用下面数据里的事实，不要补充数据里没有的词源说法。
- 如果数据显示某个词没有词源信息，就直说不清楚，不要猜。
- 不要用标题、列表或 Markdown；外语单词保持原样拼写；带星号的形式是语言学家构拟的古词。

数据：
{data}"""


def _compact(r: dict) -> dict:
    out = {"英语中文意思": r.get("zh"), "程序判断": r.get("headline"), "要点": r.get("notes")}
    for l, name in (("en", "英语"), ("fr", "法语"), ("nl", "荷兰语")):
        s = r.get(l)
        if s:
            out[name] = {"词": s["w"], "英文释义": s["glosses"][:2],
                         "词源链": [f"{n['lang']} {n['form']}" + (f"（{n['mean']}）" if n["mean"] else "") for n in s["chain"]],
                         "维基词典词源原文": (s.get("etym_text") or "")[:600]}
    return out


@app.post("/api/explain")
def explain(req: ExplainRequest):
    if not CONFIG["key"]:
        raise HTTPException(400, "没有设置 Anthropic API 密钥，AI 讲解功能未开启。")
    r = get_dict().lookup(req.q, req.lang, {"en": req.en, "fr": req.fr, "nl": req.nl})
    if not r.get("found"):
        raise HTTPException(404, "词典里没有这个词。")
    import anthropic

    client = anthropic.Anthropic(api_key=CONFIG["key"])
    prompt = PROMPT.format(data=json.dumps(_compact(r), ensure_ascii=False, indent=1))

    def gen():
        try:
            with client.messages.stream(model=CONFIG["model"], max_tokens=800,
                                        messages=[{"role": "user", "content": prompt}]) as stream:
                for text in stream.text_stream:
                    yield text
        except anthropic.AuthenticationError:
            yield "\n\n[API 密钥无效，请检查 config.json。]"
        except anthropic.RateLimitError:
            yield "\n\n[请求太频繁或额度用完了，请稍后再试。]"
        except anthropic.APIError as e:
            yield f"\n\n[AI 服务出错：{getattr(e, 'message', e)}]"

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")


if __name__ == "__main__":
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(DB_PATH):
        print("提示：还没有词典数据库。先运行  python download_data.py  再运行  python import_data.py data/raw-wiktextract-data.jsonl.gz")
    print(f"AI 讲解：{'已开启（' + CONFIG['model'] + '）' if CONFIG['key'] else '未开启（config.json 里没有 API 密钥）'}")
    url = f"http://127.0.0.1:{a.port}"
    print(f"打开浏览器访问 {url}  （按 Ctrl+C 停止）")
    if not a.no_browser and a.host in ("127.0.0.1", "localhost"):
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")
