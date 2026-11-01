#!/usr/bin/env python3
"""Convert the validated Mihomo feed into the repository's legacy client formats."""
import json
import shutil
import threading
import urllib.error
import urllib.parse
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "clash" / "all.yaml"
if not BASE.exists():
    raise SystemExit("clash/all.yaml is missing")


def start_feed_server():
    # Subconverter's API mode rejects file:// inputs. Serve the generated feed
    # over loopback HTTP so the converter reads exactly the same validated file.
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 8765), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def get(target, source):
    query = urllib.parse.urlencode({"target": target, "url": source})
    url = "http://127.0.0.1:25500/sub?" + query
    request = urllib.request.Request(
        url, headers={"User-Agent": "free-nodes-format-builder/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(
            f"subconverter failed for target={target}, HTTP {error.code}: {detail}"
        ) from error
    if len(body) < 80:
        raise RuntimeError(
            f"subconverter returned suspiciously short output for {target}: "
            f"{body[:500]!r}"
        )
    return body


def main():
    with urllib.request.urlopen("http://127.0.0.1:25500/version", timeout=5) as response:
        print("Converter:", response.read().decode("utf-8", errors="replace").strip())

    server = start_feed_server()
    source = "http://127.0.0.1:8765/clash/all.yaml"
    try:
        with urllib.request.urlopen(source, timeout=10) as response:
            if response.status != 200 or len(response.read()) < 80:
                raise RuntimeError("Loopback feed server failed to serve clash/all.yaml")

        outputs = {
            "v2ray": "shadowrocket/sub.txt",
            "surge": "surge/surge.conf",
            "quanx": "quantumultx/qx.txt",
            "loon": "loon/loon.list",
            "singbox": "singbox/singbox.json",
        }
        for target, relative_path in outputs.items():
            data = get(target, source)
            path = ROOT / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            print(f"PASS {relative_path}: {len(data)} bytes")

        for relative_path in ("stash/stash.yaml", "clashmi/clashmi.yaml"):
            path = ROOT / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(BASE, path)

        shutil.copyfile(BASE, ROOT / "clash/cfw.yaml")
        shutil.copyfile(BASE, ROOT / "clash/cfw-nodes.yaml")
        print(
            "PASS: converted Shadowrocket, Surge, Quantumult X, Loon and "
            "sing-box; refreshed Stash/Clash Mi YAML."
        )
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
