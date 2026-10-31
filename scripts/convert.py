#!/usr/bin/env python3
"""Convert the validated Mihomo feed into the repository's legacy client formats."""
import json, shutil, time, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"clash/all.yaml"
if not BASE.exists(): raise SystemExit("clash/all.yaml is missing")
def get(target, source):
    q=urllib.parse.urlencode({"target":target,"url":source})
    req=urllib.request.Request("http://127.0.0.1:25500/sub?"+q,headers={"User-Agent":"free-nodes-format-builder/1.0"})
    with urllib.request.urlopen(req,timeout=90) as r:
        body=r.read()
        if len(body)<80: raise RuntimeError(f"{target}: converter returned suspiciously short output")
        return body
def main():
    version=urllib.request.urlopen("http://127.0.0.1:25500/version",timeout=5).read()
    source=BASE.resolve().as_uri()
    outputs={
      "v2ray":"shadowrocket/sub.txt",
      "surge":"surge/surge.conf",
      "quanx":"quantumultx/qx.txt",
      "loon":"loon/loon.list",
      "singbox":"singbox/singbox.json",
    }
    for target,rel in outputs.items():
        data=get(target,source)
        path=ROOT/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
        print(f"{rel}: {len(data)} bytes")
    for rel in ("stash/stash.yaml","clashmi/clashmi.yaml"):
        path=ROOT/rel; path.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(BASE,path)
    # Keep the legacy Clash-for-Windows endpoint parseable; only node-compatible fields are used.
    shutil.copyfile(BASE,ROOT/"clash/cfw.yaml")
    shutil.copyfile(BASE,ROOT/"clash/cfw-nodes.yaml")
    print("Converted Surge, Quantumult X, Loon, Shadowrocket and sing-box; refreshed Stash/Clash Mi YAML.")
if __name__=="__main__": main()
