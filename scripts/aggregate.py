#!/usr/bin/env python3
"""Collect public proxy subscriptions, validate them with mihomo, and publish stable feeds."""
import base64, concurrent.futures, ipaddress, json, os, re, subprocess, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
BJT=timezone(timedelta(hours=8))
UA={"User-Agent":"free-nodes-aggregator/1.0"}
SOURCES=[
 ("ermaozi","https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml","clash"),
 ("NoMoreWalls","https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.meta.yml","clash"),
 ("AutoMerge","https://raw.githubusercontent.com/chengaopan/AutoMergePublicNodes/master/list.meta.yml","clash"),
 ("freeSub","https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/clash.yaml","clash"),
 ("free18","https://raw.githubusercontent.com/free18/v2ray/main/c.yaml","clash"),
 ("zhuhaiuk","https://raw.githubusercontent.com/zhuhaiuk/free-nodes/main/clash_config.yaml","clash"),
 ("Eternity","https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.yml","clash"),
 ("Pawdroid","https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub","share"),
 ("roosterkid","https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_RAW.txt","share"),
]
REGIONS={"hk":["香港","hong kong","🇭🇰","HK"],"tw":["台湾","taiwan","🇹🇼","TW"],"jp":["日本","japan","🇯🇵","JP"],"sg":["新加坡","singapore","🇸🇬","SG"],"kr":["韩国","south korea","🇰🇷","KR"],"us":["美国","united states","🇺🇸","USA","US-"],"eu":["英国","德国","法国","荷兰","欧洲","🇬🇧","🇩🇪","🇫🇷","🇳🇱","🇪🇺","UK","GB-","DE-","FR-","NL-"]}
def fetch(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=35) as r: return r.read().decode("utf-8","replace")
def b64decode(s):
    s=re.sub(r"\s+","",s); return base64.urlsafe_b64decode(s+"="*(-len(s)%4)).decode("utf-8","replace")
def parse_uri(line):
    line=line.strip().replace("&amp;","&")
    try:
        u=urllib.parse.urlsplit(line); scheme=u.scheme.lower(); q=dict(urllib.parse.parse_qsl(u.query))
        name=urllib.parse.unquote(u.fragment) or scheme
        if scheme=="vmess":
            j=json.loads(b64decode(line[8:])); p={"name":j.get("ps") or name,"type":"vmess","server":j["add"],"port":int(j["port"]),"uuid":j["id"],"alterId":int(j.get("aid") or 0),"cipher":j.get("scy") or "auto","network":j.get("net") or "tcp"}
            if j.get("tls")=="tls": p.update(tls=True,servername=j.get("sni") or j.get("host"))
            if p["network"]=="ws": p["ws-opts"]={"path":j.get("path") or "/","headers":{"Host":j.get("host")} if j.get("host") else {}}
            return p
        if scheme=="ss":
            body=line[5:].split("#",1)[0]
            if "@" not in body: body=b64decode(body)
            auth,hostport=body.rsplit("@",1)
            if ":" not in auth: auth=b64decode(auth)
            method,password=auth.split(":",1); host,port=hostport.split(":",1)
            return {"name":name,"type":"ss","server":host.strip("[]"),"port":int(port.split("/")[0]),"cipher":method,"password":password}
        if scheme in ("vless","trojan","hysteria2","hy2"):
            host=u.hostname; port=u.port
            if scheme=="vless":
                p={"name":name,"type":"vless","server":host,"port":port,"uuid":urllib.parse.unquote(u.username or ""),"encryption":"none"}
                if q.get("security") in ("tls","reality"): p.update({"tls":True,"servername":q.get("sni"),"skip-cert-verify":True})
                if q.get("security")=="reality": p["reality-opts"]={"public-key":q.get("pbk",""),"short-id":q.get("sid","")}
                if q.get("flow"): p["flow"]=q["flow"]
            elif scheme=="trojan": p={"name":name,"type":"trojan","server":host,"port":port,"password":urllib.parse.unquote(u.username or ""),"sni":q.get("sni"),"tls":True,"skip-cert-verify":q.get("allowInsecure")=="1"}
            else: p={"name":name,"type":"hysteria2","server":host,"port":port,"password":urllib.parse.unquote(u.username or ""),"sni":q.get("sni"),"skip-cert-verify":q.get("insecure")=="1"}
            if q.get("type")=="ws": p.update(network="ws",**{"ws-opts":{"path":q.get("path","/"),"headers":{"Host":q.get("host")} if q.get("host") else {}}})
            return p
    except Exception: return None
    return None
def parse_source(raw,kind):
    try:
        obj=yaml.safe_load(raw)
        if isinstance(obj,dict) and isinstance(obj.get("proxies"),list): return [p for p in obj["proxies"] if isinstance(p,dict)]
    except Exception: pass
    text=raw
    if kind=="share" or "://" not in text:
        try:
            decoded=b64decode(text)
            if "://" in decoded: text=decoded
        except Exception: pass
    out=[]
    for line in text.splitlines():
        if "://" in line:
            p=parse_uri(line)
            if p: out.append(p)
    return out
def valid(p):
    t=str(p.get("type","")).lower()
    required={"ss":["cipher","password"],"vmess":["uuid"],"vless":["uuid"],"trojan":["password"],"hysteria2":["password"],"tuic":["uuid","password"],"http":[],"socks5":[]}
    if t not in required or not p.get("server"): return False
    try: port=int(p["port"])
    except Exception: return False
    if not 1<=port<=65535 or any(p.get(k) in (None,"") for k in required[t]): return False
    p["port"]=port
    try: ipaddress.ip_address(str(p["server"]).strip("[]"))
    except ValueError:
        if not re.fullmatch(r"[a-zA-Z0-9.-]{1,253}",str(p["server"])): return False
    return True
def key(p):
    q={k:v for k,v in p.items() if k!="name"}
    return json.dumps(q,sort_keys=True,ensure_ascii=False,default=str)
def request_json(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=8) as r: return json.loads(r.read())
def test_nodes(nodes):
    cfg={"mixed-port":17890,"allow-lan":False,"mode":"rule","log-level":"info","external-controller":"127.0.0.1:9090","secret":"","proxies":nodes,"proxy-groups":[{"name":"TEST","type":"select","proxies":[p["name"] for p in nodes]}],"rules":["MATCH,TEST"]}
    (ROOT/"mihomo-test.yaml").write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False),encoding="utf-8")
    binary=ROOT/"mihomo"
    if not binary.exists(): raise RuntimeError("mihomo binary missing")
    log_path=ROOT/"mihomo-test.log"
    log_file=log_path.open("w",encoding="utf-8")
    proc=subprocess.Popen([str(binary),"-d",str(ROOT/"mihomo-data"),"-f",str(ROOT/"mihomo-test.yaml")],stdout=log_file,stderr=subprocess.STDOUT)
    try:
        for _ in range(30):
            try: request_json("http://127.0.0.1:9090/version"); break
            except Exception:
                if proc.poll() is not None:
                    log_file.flush()
                    raise RuntimeError("mihomo exited during startup: "+log_path.read_text(encoding="utf-8",errors="replace")[-5000:])
                time.sleep(1)
        else: raise RuntimeError("mihomo external controller did not start: "+log_path.read_text(encoding="utf-8",errors="replace")[-5000:])
        def one(p):
            url="http://127.0.0.1:9090/proxies/"+urllib.parse.quote(p["name"],safe="")+"/delay?url="+urllib.parse.quote("https://www.gstatic.com/generate_204",safe="")+"&timeout=6000"
            try:
                d=request_json(url).get("delay",0)
                return (p,int(d)) if 0<int(d)<=6000 else None
            except Exception: return None
        passed=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
            futures=[pool.submit(one,p) for p in nodes]
            for f in concurrent.futures.as_completed(futures):
                x=f.result()
                if x: passed.append(x)
        return sorted(passed,key=lambda x:x[1])
    finally:
        proc.terminate()
        try: proc.wait(timeout=8)
        except subprocess.TimeoutExpired: proc.kill()
        log_file.close()
def region_of(p):
    s=str(p.get("name","")).lower()
    for code,terms in REGIONS.items():
        if any(t.lower() in s for t in terms): return code
    return "other"
def uri(p):
    t=p["type"]; host=p["server"]; port=p["port"]; name=urllib.parse.quote(p["name"],safe="")
    q=lambda x: urllib.parse.quote(str(x),safe="")
    if t=="ss":
        user=base64.urlsafe_b64encode(f'{p["cipher"]}:{p["password"]}'.encode()).decode().rstrip("=")
        return f"ss://{user}@{host}:{port}#{name}"
    if t=="vmess":
        j={"v":"2","ps":p["name"],"add":host,"port":str(port),"id":p["uuid"],"aid":str(p.get("alterId",0)),"scy":p.get("cipher","auto"),"net":p.get("network","tcp"),"type":"none","host":"","path":"","tls":"tls" if p.get("tls") else ""}
        ws=p.get("ws-opts",{}); j["path"]=ws.get("path","/"); j["host"]=(ws.get("headers") or {}).get("Host","")
        if p.get("servername"): j["sni"]=p["servername"]
        return "vmess://"+base64.b64encode(json.dumps(j,ensure_ascii=False).encode()).decode()
    if t=="vless":
        params={"encryption":"none","security":"reality" if p.get("reality-opts") else ("tls" if p.get("tls") else "none"),"type":p.get("network","tcp")}
        if p.get("servername"): params["sni"]=p["servername"]
        if p.get("flow"): params["flow"]=p["flow"]
        if p.get("reality-opts"):
            params["pbk"]=p["reality-opts"].get("public-key",""); params["sid"]=p["reality-opts"].get("short-id","")
        ws=p.get("ws-opts",{})
        if p.get("network")=="ws": params.update(path=ws.get("path","/"),host=(ws.get("headers") or {}).get("Host",""))
        return f'vless://{p["uuid"]}@{host}:{port}?'+urllib.parse.urlencode(params)+f'#{name}'
    if t=="trojan":
        params={"security":"tls","sni":p.get("sni") or p.get("servername") or host,"allowInsecure":"1" if p.get("skip-cert-verify") else "0"}
        return f'trojan://{q(p["password"])}@{host}:{port}?'+urllib.parse.urlencode(params)+f'#{name}'
    if t=="hysteria2": return f'hysteria2://{q(p["password"])}@{host}:{port}?sni={q(p.get("sni") or host)}&insecure=1#{name}'
    return None
def build_yaml(nodes):
    names=[p["name"] for p in nodes]
    if names:
        groups=[{"name":"AUTO","type":"url-test","url":"https://www.gstatic.com/generate_204","interval":300,"tolerance":100,"proxies":names},{"name":"PROXY","type":"select","proxies":["AUTO"]+names}]
    else:
        # Empty regional feeds remain valid importable configs instead of
        # creating url-test/select groups with no usable members.
        groups=[{"name":"AUTO","type":"select","proxies":["DIRECT"]},{"name":"PROXY","type":"select","proxies":["DIRECT"]}]
    return {"mixed-port":7890,"allow-lan":False,"mode":"rule","log-level":"info","ipv6":False,"proxies":nodes,"proxy-groups":groups,"rules":["GEOIP,CN,DIRECT","MATCH,PROXY"]}
def write_yaml(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(yaml.safe_dump(obj,allow_unicode=True,sort_keys=False),encoding="utf-8")
def main():
    merged=[]; seen=set(); stats={}
    for tag,url,kind in SOURCES:
        try: raw=fetch(url); candidates=parse_source(raw,kind)
        except Exception as e: print(f"[{tag}] fetch failed: {e}"); stats[tag]={"count":0,"error":str(e)[:180]}; continue
        n=0
        for p in candidates:
            if not valid(p): continue
            p=dict(p); p["name"]=f"[{tag}] "+str(p.get("name") or p["server"])
            k=key(p)
            if k in seen: continue
            seen.add(k); merged.append(p); n+=1
        stats[tag]={"count":n,"error":None}; print(f"[{tag}] {n} unique candidates")
    if not merged: raise RuntimeError("all upstream sources failed or returned no valid nodes; keeping previous feeds")
    # Cap concurrent test load while retaining source diversity.
    merged=merged[:1600]
    # Mihomo requires unique proxy names even when endpoints are different.
    # Some upstream lists reuse a display name for several servers.
    used_names=set()
    for p in merged:
        base=str(p.get("name") or p["server"])
        candidate=base
        suffix=2
        while candidate in used_names:
            candidate=f"{base} ({suffix})"
            suffix+=1
        p["name"]=candidate
        used_names.add(candidate)
    passed=test_nodes(merged)
    nodes=[]
    for p,delay in passed:
        p=dict(p); p["name"]=p["name"]+" | "+str(delay)+"ms"; nodes.append(p)
    if not nodes: raise RuntimeError("mihomo connection test returned zero working nodes; keeping previous feeds")
    write_yaml(ROOT/"clash/all.yaml",build_yaml(nodes))
    links=[uri(p) for p in nodes]; links=[x for x in links if x]
    (ROOT/"v2ray/all.txt").parent.mkdir(parents=True,exist_ok=True)
    (ROOT/"v2ray/all.txt").write_text(base64.b64encode("\n".join(links).encode()).decode(),encoding="utf-8")
    region_stats={}
    for code in ["hk","tw","jp","sg","kr","us","eu","other"]:
        subset=[p for p in nodes if region_of(p)==code]
        region_stats[code]=len(subset)
        write_yaml(ROOT/f"region/clash/{code}.yaml",build_yaml(subset))
        lines=[uri(p) for p in subset]; lines=[x for x in lines if x]
        (ROOT/f"region/{code}.txt").write_text(base64.b64encode("\n".join(lines).encode()).decode(),encoding="utf-8")
    now=datetime.now(BJT).strftime("%Y-%m-%d %H:%M")
    report={"time":now,"sources":stats,"candidates":len(merged),"tested":len(merged),"alive":len(nodes),"v2ray":len(links),"region":region_stats,"test":"mihomo API / gstatic generate_204"}
    (ROOT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    readme=ROOT/"README.md"; text=readme.read_text(encoding="utf-8")
    marker="<!-- AUTO-STATUS -->"
    block=f"<!-- AUTO-STATUS -->\n自动更新于 **{now}（北京时间）**；候选 **{len(merged)}**，mihomo 真连接测试通过 **{len(nodes)}**，v2ray 分享链接 **{len(links)}**。每 8 小时运行一次；测试出口为 GitHub Actions 海外 Runner，国内连通性可能不同。\n<!-- /AUTO-STATUS -->"
    if marker in text: text=re.sub(r"<!-- AUTO-STATUS -->.*?<!-- /AUTO-STATUS -->",block,text,flags=re.S)
    else: text=text.replace("# free-nodes","# free-nodes\n\n"+block,1)
    readme.write_text(text,encoding="utf-8")
    print(f"PASS: {len(nodes)}/{len(merged)} nodes passed mihomo real connection test")
if __name__=="__main__": main()
