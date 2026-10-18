"""下载 kaikki.org 的维基词典完整数据（约 2.8 GB 压缩包）。

用法：python download_data.py
中途断了再运行一次，会从断点继续下载。
"""
from __future__ import annotations

import os
import sys
import time
import urllib.request

URL = "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz"
DEST = os.path.join("data", "raw-wiktextract-data.jsonl.gz")


def main() -> None:
    os.makedirs("data", exist_ok=True)
    have = os.path.getsize(DEST) if os.path.exists(DEST) else 0
    req = urllib.request.Request(URL, headers={"User-Agent": "trilingual-etymology/1.0"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code == 416:
            print("文件已经下载完整。")
            return
        sys.exit(f"下载失败：{e}")
    if have and resp.status != 206:
        print("服务器不支持断点续传，从头开始下载。")
        have = 0
    total = have + int(resp.headers.get("Content-Length", 0))
    mode = "ab" if have else "wb"
    t0, done = time.time(), have
    with open(DEST, mode) as out:
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            speed = (done - have) / max(time.time() - t0, 1) / 1e6
            print(f"\r  {done / 1e9:.2f} / {total / 1e9:.2f} GB  ({speed:.1f} MB/s)", end="", flush=True)
    print(f"\n下载完成：{DEST}")
    print("下一步：python import_data.py " + DEST)


if __name__ == "__main__":
    main()
