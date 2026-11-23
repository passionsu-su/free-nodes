#!/usr/bin/env python3
"""Collect public proxy subscriptions, validate them with mihomo, and publish stable feeds."""
import base64, concurrent.futures, ipaddress, json, os, re, socket, subprocess, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
# Windows consoles default to a legacy codepage (e.g. cp936); node names
# printed to the log contain CJK/emoji, which would raise
# UnicodeEncodeError and kill the run. Force UTF-8 output (no-op on
# Linux/macOS, where stdout is already UTF-8).
for _s in (sys.stdout,sys.stderr):
    try: _s.reconfigure(encoding="utf-8",errors="replace")
    except Exception: pass
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
# Name-keyword terms (substring match): full country names in Chinese and
# English plus flags. Short ISO codes are NOT here: they are matched on
# token boundaries in REGION_CODES below, so "zhuhai.uk" is not UK,
# "Kronecker" is not KR and "trojan" is not TR.
REGIONS={"hk":["香港","hong kong","🇭🇰"],"tw":["台湾","taiwan","🇹🇼"],"jp":["日本","japan","🇯🇵"],"sg":["新加坡","singapore","🇸🇬"],"kr":["韩国","south korea","🇰🇷"],"us":["美国","united states","🇺🇸"],"eu":["英国","德国","法国","荷兰","欧洲","europe","🇬🇧","🇩🇪","🇫🇷","🇳🇱","🇪🇺","意大利","italy","🇮🇹","西班牙","spain","🇪🇸","瑞典","sweden","🇸🇪","芬兰","finland","🇫🇮","瑞士","switzerland","🇨🇭","奥地利","austria","🇦🇹","比利时","belgium","🇧🇪","希腊","greece","🇬🇷","挪威","norway","🇳🇴","波兰","poland","🇵🇱","捷克","czechia","czech","🇨🇿","爱沙尼亚","estonia","🇪🇪","拉脱维亚","latvia","🇱🇻","立陶宛","lithuania","🇱🇹","爱尔兰","ireland","🇮🇪","葡萄牙","portugal","🇵🇹","丹麦","denmark","🇩🇰","匈牙利","hungary","🇭🇺","罗马尼亚","romania","🇷🇴","乌克兰","ukraine","🇺🇦","白俄罗斯","belarus","🇧🇾","阿尔巴尼亚","albania","🇦🇱","克罗地亚","croatia","🇭🇷","斯洛文尼亚","slovenia","🇸🇮","斯洛伐克","slovakia","🇸🇰","冰岛","iceland","🇮🇸","卢森堡","luxembourg","🇱🇺","马耳他","malta","🇲🇹","摩尔多瓦","moldova","🇲🇩","俄罗斯","russia","🇷🇺","土耳其","turkey","🇹🇷","netherlands","holland"]}
# ISO 3166-1 codes (alpha-2 and alpha-3) matched on token boundaries: a
# code must not touch a letter or a dot on either side. Digits and
# separators (- _ space brackets emoji CJK) may sit next to it, so
# "US_9", "NL_speednode", "DE-1", "USA 5", "NLD 4" all match, while
# "zhuhai.uk", "Kronecker", "music" and "USAGE" do not.
REGION_CODES={"hk":("HK","HKG"),"tw":("TW","TWN"),"jp":("JP","JPN"),"sg":("SG","SGP"),"kr":("KR","KOR"),"us":("US","USA"),"eu":("GB","UK","DE","FR","NL","IT","ES","SE","FI","CH","AT","BE","GR","NO","PL","CZ","EE","LV","LT","IE","PT","DK","HU","RO","UA","BY","AL","HR","SI","SK","IS","LU","MT","MD","RU","TR","EU","GBR","DEU","FRA","NLD","ITA","ESP","SWE","FIN","CHE","AUT","BEL","GRC","NOR","POL","CZE","EST","LVA","LTU","IRL","PRT","DNK","HUN","ROU","UKR","BLR","ALB","HRV","SVN","SVK","ISL","LUX","MLT","MDA","RUS","TUR")}
_CODE_RES={c:re.compile(r"(?<![A-Za-z.])"+c.lower()+r"(?![A-Za-z.])") for codes in REGION_CODES.values() for c in codes}
# European country codes (ISO alpha-2). RU/TR count as Europe here, matching
# the 2026-11-19 GeoIP verification's convention.
EU_COUNTRY_CODES=frozenset("GB DE FR NL IT ES SE FI CH AT BE GR NO PL CZ EE LV LT IE PT DK HU RO UA BY AL HR SI SK IS LU MT MD RU TR".split())
# Cloudflare anycast ranges: ip-api returns the registration country
# (Canada) for these, not where the node serves from; prefer the name.
ANYCAST_NETS=(ipaddress.ip_network("104.16.0.0/13"),ipaddress.ip_network("172.64.0.0/13"))
# Networks is_global() misses on some Python versions (multicast is
# "global" on 3.12; 198.18.0.0/15 is rejected by is_global on 3.12 but
# the explicit entry guards other versions).
NON_GLOBAL_NETS=(ipaddress.ip_network("198.18.0.0/15"),)
# GeoIP batch lookup (ip-api.com free tier: 45 req/min, no key needed).
GEOIP_BATCH_URL="http://ip-api.com/batch"
GEOIP_BATCH_SIZE=100
GEOIP_BATCH_SLEEP_S=2
# A tested node slower than this is unusable in practice; drop it instead of
# publishing a 5-6s entry at the bottom of the list.
MAX_DELAY_MS = 4000
GSTASTIC_TEST_URL = "https://www.gstatic.com/generate_204"
# Second-round target hosted in mainland China (Huawei connectivity check).
# The runner is overseas, so this measures node -> China, not user -> node;
# it is still a strictly better China proxy than runner -> node -> Google.
# Override with env CN_TEST_URL; if the target is unreachable the China
# round is skipped and the run continues with the gstatic results only.
CN_TEST_URL = os.environ.get("CN_TEST_URL", "https://connectivitycheck.platform.hicloud.com/generate_204")
# Optional GitHub download proxies (comma separated prefixes), used only when a
# direct GitHub fetch fails, e.g. on the self-hosted runner in China.
GH_MIRRORS=[m.strip() for m in os.environ.get("GH_MIRRORS","").split(",") if m.strip()]

def _fetch_once(url,timeout):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=timeout) as r: return r.read().decode("utf-8","replace")

def fetch(url):
    try:
        return _fetch_once(url,35)
    except Exception as e:
        if not GH_MIRRORS or "githubusercontent.com" not in url and "github.com" not in url: raise
        last=e
        for m in GH_MIRRORS:
            try: return _fetch_once(m.rstrip("/")+"/"+url,35)
            except Exception as e2: last=e2
        raise last
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
    if not 1<=port<=65535: return False
    p["port"]=port
    # Upstream lists sometimes serialise a missing credential as the literal
    # string "null" (notably http proxies). Treat it as absent.
    for k in ("username","password"):
        if p.get(k)=="null": p[k]=None
    if any(p.get(k) in (None,"") for k in required[t]): return False
    ro=p.get("reality-opts")
    if ro is not None:
        if not isinstance(ro,dict) or not ro.get("public-key"): return False
        sid=str(ro.get("short-id") or "")
        if sid and not (len(sid)<=16 and len(sid)%2==0 and re.fullmatch(r"[0-9a-fA-F]+",sid)): return False
    # Reject non-routable targets. Upstream lists now inject loopback fakes
    # (e.g. server 127.0.0.53, name "防范境外势力渗透"); a public proxy
    # server must have a globally routable IP. Note is_global() is True
    # for multicast on Python 3.12, and 198.18.0.0/15 (benchmarking) is
    # only rejected by it on some versions, so both are blocked explicitly.
    try:
        ip=ipaddress.ip_address(str(p["server"]).strip("[]"))
        if ip.is_multicast: return False
        if not ip.is_global: return False
        if ip.version==4 and any(ip in n for n in NON_GLOBAL_NETS): return False
    except ValueError:
        host=str(p["server"]).lower()
        if host in ("localhost",) or host.endswith((".local",".internal",".lan",".home",".invalid")): return False
        if not re.fullmatch(r"[a-zA-Z0-9.-]{1,253}",str(p["server"])): return False
    return True
def key(p):
    q={k:v for k,v in p.items() if k!="name"}
    return json.dumps(q,sort_keys=True,ensure_ascii=False,default=str)
def request_json(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=8) as r: return json.loads(r.read())
def test_nodes(nodes):
    # One malformed upstream node makes mihomo refuse the whole config.
    # Drop the proxy it names and retry instead of failing the run.
    for attempt in range(40):
        try: return _delay_test(nodes, GSTASTIC_TEST_URL, 6000)
        except RuntimeError as e:
            m=re.search(r"Parse config error: proxy (\d+)",str(e))
            if not m: raise
            i=int(m.group(1))
            if not 0<=i<len(nodes): raise
            print(f"dropping proxy {i} rejected by mihomo: {nodes[i].get('name')} -> {str(e).splitlines()[-1][-160:]}")
            nodes=nodes[:i]+nodes[i+1:]
    raise RuntimeError("too many proxies rejected by mihomo")
def test_china(nodes):
    """Second-round delay test against a China-hosted target, for nodes that
    already passed the gstatic test. Best-effort: any failure skips the
    China round and the run continues with the gstatic results only."""
    if not nodes: return []
    try: return _delay_test(nodes, CN_TEST_URL, 6000)
    except Exception as e:
        print(f"[china-test] skipped: {e}")
        return []
def filter_tested(passed):
    """passed: [(proxy, delay_ms)] delay-sorted. Drop the unusable slow tail,
    then collapse duplicate endpoints: the same server:port:type often appears
    under several names/credentials from different upstreams; keep the
    fastest-tested entry only. Returns (kept, dropped_slow, dropped_dup)."""
    slow=sum(1 for _,d in passed if d>MAX_DELAY_MS)
    kept=[(p,d) for p,d in passed if d<=MAX_DELAY_MS]
    best={}
    for p,d in kept:  # already delay-sorted: first hit per endpoint is fastest
        k=(str(p["server"]).lower(),int(p["port"]),str(p["type"]).lower())
        if k not in best: best[k]=(p,d)
    dup=len(kept)-len(best)
    return sorted(best.values(),key=lambda x:x[1]),slow,dup
def mihomo_binary():
    """Local mihomo binary. It ships as `mihomo` on Linux/macOS and
    `mihomo.exe` on Windows; prefer the platform-native name but accept
    either, so a misplaced binary still works."""
    names=("mihomo.exe","mihomo") if os.name=="nt" else ("mihomo","mihomo.exe")
    for name in names:
        p=ROOT/name
        if p.exists(): return p
    raise RuntimeError("mihomo binary missing")
def _delay_test(nodes, url, timeout_ms):
    cfg={"mixed-port":17890,"allow-lan":False,"mode":"rule","log-level":"info","external-controller":"127.0.0.1:9090","secret":"","proxies":nodes,"proxy-groups":[{"name":"TEST","type":"select","proxies":[p["name"] for p in nodes]}],"rules":["MATCH,TEST"]}
    (ROOT/"mihomo-test.yaml").write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False),encoding="utf-8")
    binary=mihomo_binary()
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
            u="http://127.0.0.1:9090/proxies/"+urllib.parse.quote(p["name"],safe="")+"/delay?url="+urllib.parse.quote(url,safe="")+"&timeout="+str(timeout_ms)
            try:
                d=request_json(u).get("delay",0)
                return (p,int(d)) if 0<int(d)<=timeout_ms else None
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
def region_for_country(cc):
    cc=(cc or "").upper()
    if cc in ("HK","TW","JP","SG","KR","US"): return cc.lower()
    if cc in EU_COUNTRY_CODES: return "eu"
    return "other"
def region_of_name(p):
    """Name-keyword classifier (fallback only). ISO codes match on token
    boundaries; full names and flags match as substrings."""
    s=str(p.get("name","")).lower()
    for code,codes in REGION_CODES.items():
        if any(_CODE_RES[c].search(s) for c in codes): return code
    for code,terms in REGIONS.items():
        if any(t.lower() in s for t in terms): return code
    return "other"
def _in_nets(ip_str,nets):
    try:
        ip=ipaddress.ip_address(ip_str)
        return any(ip.version==n.version and ip in n for n in nets)
    except ValueError:
        return False
def _resolve_one(server):
    try: return str(ipaddress.ip_address(str(server).strip("[]")))
    except ValueError: pass
    try:
        infos=socket.getaddrinfo(str(server),None,proto=socket.IPPROTO_TCP)
        if infos: return infos[0][4][0]
    except Exception: return None
    return None
def resolve_servers(servers):
    """Resolve server strings to IPs (literal IPs pass through). Bounded:
    the whole batch gets 90s; anything still unresolved becomes None."""
    out={}
    if not servers: return out
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        futs={pool.submit(_resolve_one,s):s for s in servers}
        try: concurrent.futures.wait(futs,timeout=90)
        except Exception: pass
        for f,s in futs.items():
            try: out[s]=f.result(timeout=0) if f.done() else None
            except Exception: out[s]=None
    return out
def geoip_lookup(ips):
    """Batch country lookup via ip-api.com (free tier, 45 req/min, no key).
    Never raises: on any failure returns what was collected so far
    (possibly {}) and the caller falls back to name classification."""
    out={}
    uniq=[]
    for ip in ips:
        if ip and ip not in uniq: uniq.append(ip)
    for i in range(0,len(uniq),GEOIP_BATCH_SIZE):
        batch=uniq[i:i+GEOIP_BATCH_SIZE]
        try:
            body=json.dumps([{"query":ip,"fields":"status,countryCode,query"} for ip in batch]).encode()
            req=urllib.request.Request(GEOIP_BATCH_URL,data=body,headers={"Content-Type":"application/json","User-Agent":"free-nodes-geoip/1.0"})
            with urllib.request.urlopen(req,timeout=15) as r: rows=json.loads(r.read())
            for row in rows:
                if isinstance(row,dict) and row.get("status")=="success" and row.get("countryCode") and row.get("query"):
                    out[row["query"]]=row["countryCode"]
        except Exception as e:
            print(f"[geoip] batch {i//GEOIP_BATCH_SIZE+1} failed: {e}")
            break
        if i+GEOIP_BATCH_SIZE<len(uniq): time.sleep(GEOIP_BATCH_SLEEP_S)
    return out
def classify_geoip(nodes):
    """GeoIP-first region map {server_ip: region} for the given nodes.
    Returns (geoip_map, resolved_map, stats). Anycast IPs and
    unresolvable/unlocatable servers are left out so region_of() falls
    back to the name classifier for those nodes."""
    servers={str(p["server"]) for p in nodes if p.get("server")}
    resolved=resolve_servers(sorted(servers))
    ips=sorted({ip for ip in resolved.values() if ip})
    anycast={ip for ip in ips if _in_nets(ip,ANYCAST_NETS)}
    to_query=[ip for ip in ips if ip not in anycast]
    cc_by_ip=geoip_lookup(to_query)
    geoip={ip: region_for_country(cc) for ip,cc in cc_by_ip.items()}
    stats={"enabled":True,"servers":len(servers),"resolved":sum(1 for v in resolved.values() if v),"ips_queried":len(to_query),"located":len(cc_by_ip),"anycast_skipped":len(anycast),"unresolved_servers":sum(1 for v in resolved.values() if not v)}
    return geoip,resolved,stats
def region_of(p,geoip=None,resolved=None):
    """Region for a node. GeoIP-first when a {ip: region} map is given
    (resolved maps server->ip, computed once per run); otherwise the
    name-keyword classifier. region_of(p) with no map is name-only."""
    if geoip is not None:
        srv=str(p.get("server") or "")
        ip=(resolved.get(srv) if resolved is not None else _resolve_one(srv)) if srv else None
        if ip and ip in geoip: return geoip[ip]
    return region_of_name(p)
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
def refresh_readme(now, candidates, alive, v2ray_n, region_stats, txt_counts, cn_stats, note=""):
    """Keep README numbers honest: the AUTO-STATUS line, the update time and
    the region tables are regenerated from this run's real outputs every time.
    Marker blocks that do not exist yet are left alone."""
    readme=ROOT/"README.md"; text=readme.read_text(encoding="utf-8")
    cn_line=""
    if cn_stats.get("alive"):
        cn_line=f"国内优选（到中国目标复测） **{cn_stats['alive']}**，中位延迟 **{cn_stats.get('median_ms')}ms**。"
    elif cn_stats.get("stale"):
        cn_line="国内优选本次复测未完成，沿用上一版。"
    block=(f"<!-- AUTO-STATUS -->\n自动更新于 **{now}（北京时间）**；候选 **{candidates}**，mihomo 真连接测试通过 **{alive}**，v2ray 分享链接 **{v2ray_n}**。{cn_line}"
           f"每 8 小时运行一次；测试出口为 GitHub Actions 海外 Runner，国内连通性可能不同。{note}\n<!-- /AUTO-STATUS -->")
    marker="<!-- AUTO-STATUS -->"
    if marker in text: text=re.sub(r"<!-- AUTO-STATUS -->.*?<!-- /AUTO-STATUS -->",block,text,flags=re.S)
    else: text=text.replace("# free-nodes","# free-nodes\n\n"+block,1)
    text=re.sub(r"更新时间：.*?（北京时间）",f"更新时间：{now}（北京时间）",text,count=1)
    base="https://raw.githubusercontent.com/passionsu-su/free-nodes/main/"
    names={"hk":"香港","tw":"台湾","jp":"日本","sg":"新加坡","kr":"韩国","us":"美国","eu":"欧洲","other":"其他"}
    for kind,counts,path_tmpl in (("txt",txt_counts,"region/{code}.txt"),("clash",region_stats,"region/clash/{code}.yaml")):
        m=f"<!-- REGION-{kind.upper()} -->"
        if m not in text: continue
        rows=[f"| {names[c]} | {base}{path_tmpl.format(code=c)} | {counts.get(c,0)} |" for c in ["hk","tw","jp","sg","kr","us","eu","other"]]
        table=f"{m}\n| 地区 | 链接 | 节点 |\n| --- | --- | --- |\n"+"\n".join(rows)+f"\n<!-- /REGION-{kind.upper()} -->"
        text=re.sub(rf"{m}.*?<!-- /REGION-{kind.upper()} -->",table,text,flags=re.S)
    m="<!-- CN-FEED -->"
    if m in text:
        if cn_stats.get("alive"):
            body=(f"{m}\n## 国内优选（按到中国大陆目标的实测延迟排序）\n\n| 格式 | 链接 | 节点 |\n| --- | --- | --- |\n"
                  f"| Clash YAML | {base}clash/cn.yaml | {cn_stats['alive']} |\n| base64 | {base}v2ray/cn.txt | {cn_stats.get('v2ray',0)} |\n\n"
                  "节点先经过 mihomo 真连接测试，再对中国大陆境内目标（connectivitycheck.platform.hicloud.com/generate_204）复测并按延迟排序。"
                  "注意：测试仍发起于海外 Runner，测的是“节点→中国”这一段，不是“你→节点”；人在国内时优先用这个文件，导入后仍建议在 App 里再测一次。\n<!-- /CN-FEED -->")
        else:
            body=(f"{m}\n## 国内优选（按到中国大陆目标的实测延迟排序）\n\n本次复测未完成（中国目标不可达或复测失败），沿用上一版 clash/cn.yaml（如有）；下次运行成功后自动恢复。\n<!-- /CN-FEED -->")
        text=re.sub(r"<!-- CN-FEED -->.*?<!-- /CN-FEED -->",body,text,flags=re.S)
    readme.write_text(text,encoding="utf-8")
def main():
    merged=[]; seen=set(); stats={}
    for tag,url,kind in SOURCES:
        try: raw=fetch(url); candidates=parse_source(raw,kind)
        except Exception as e: print(f"[{tag}] fetch failed: {e}"); stats[tag]={"parsed":0,"count":0,"error":str(e)[:180]}; continue
        parsed=0; n=0
        for p in candidates:
            if not valid(p): continue
            parsed+=1
            p=dict(p); p["name"]=f"[{tag}] "+str(p.get("name") or p["server"])
            k=key(p)
            if k in seen: continue
            seen.add(k); merged.append(p); n+=1
        # "parsed" = valid nodes this source offered; "count" = newly added
        # after cross-source dedup. A meta-aggregator can legitimately show
        # parsed>0 but count=0 when its content duplicates earlier sources.
        stats[tag]={"parsed":parsed,"count":n,"error":None}; print(f"[{tag}] {parsed} valid, {n} new")
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
    passed,dropped_slow,dropped_dup=filter_tested(passed)
    print(f"[filter] dropped {dropped_slow} nodes slower than {MAX_DELAY_MS}ms, {dropped_dup} duplicate endpoints")
    nodes=[]
    for p,delay in passed:
        p=dict(p); p["name"]=p["name"]+" | "+str(delay)+"ms"; nodes.append(p)
    if not nodes: raise RuntimeError("mihomo connection test returned zero working nodes; keeping previous feeds")
    # GeoIP-first region classification. Best-effort: any failure here
    # (API down, DNS trouble) falls back to name keywords for every node
    # and the run continues; region data must never block publishing.
    geoip_map={}; resolved={}; geoip_stats={"enabled":False}
    try:
        geoip_map,resolved,geoip_stats=classify_geoip(nodes)
    except Exception as e:
        print(f"[geoip] disabled: {e}")
    write_yaml(ROOT/"clash/all.yaml",build_yaml(nodes))
    links=[uri(p) for p in nodes]; links=[x for x in links if x]
    (ROOT/"v2ray/all.txt").parent.mkdir(parents=True,exist_ok=True)
    (ROOT/"v2ray/all.txt").write_text(base64.b64encode("\n".join(links).encode()).decode(),encoding="utf-8")
    region_stats={}; txt_counts={}
    for code in ["hk","tw","jp","sg","kr","us","eu","other"]:
        subset=[p for p in nodes if region_of(p,geoip_map,resolved)==code]
        region_stats[code]=len(subset)
        write_yaml(ROOT/f"region/clash/{code}.yaml",build_yaml(subset))
        lines=[uri(p) for p in subset]; lines=[x for x in lines if x]
        txt_counts[code]=len(lines)
        (ROOT/f"region/{code}.txt").write_text(base64.b64encode("\n".join(lines).encode()).decode(),encoding="utf-8")
    # How much did GeoIP actually change? Compare each node's GeoIP region
    # with what the name alone would have said; the differences are logged
    # for the Actions log so mislabelled upstream names stay visible.
    matched=mismatched=fallback=0; mismatch_lines=[]
    for p in nodes:
        name_r=region_of_name(p)
        ip=resolved.get(str(p.get("server") or ""))
        if ip and ip in geoip_map:
            if geoip_map[ip]==name_r: matched+=1
            else:
                mismatched+=1
                mismatch_lines.append(f"{ip} | {p['name']} | name={name_r} -> geo={geoip_map[ip]}")
        else: fallback+=1
    geoip_stats.update({"geoip_classified":matched+mismatched,"name_fallback":fallback,"matched":matched,"mismatched":mismatched,"mismatch_sample":mismatch_lines[:10]})
    if mismatch_lines:
        print(f"[geoip] {mismatched} nodes where GeoIP disagrees with the name (GeoIP wins):")
        for line in mismatch_lines: print(f"[geoip]   {line}")
    print(f"[geoip] classified {matched+mismatched} by GeoIP ({matched} agree with name), {fallback} by name fallback")
    # Second-round China test: re-measure survivors against a China-hosted
    # target and publish a combined low-latency-for-China feed, sorted by
    # that measurement. If the round fails, keep the previous cn feed.
    cn_passed=test_china(nodes)
    cn_nodes=[]; cn_links=[]
    if cn_passed:
        cn_nodes=[dict(p) for p,_ in cn_passed]
        cn_links=[x for x in (uri(p) for p in cn_nodes) if x]
        write_yaml(ROOT/"clash/cn.yaml",build_yaml(cn_nodes))
        (ROOT/"v2ray/cn.txt").write_text(base64.b64encode("\n".join(cn_links).encode()).decode(),encoding="utf-8")
        cn_stats={"alive":len(cn_nodes),"v2ray":len(cn_links),"median_ms":sorted(d for _,d in cn_passed)[len(cn_passed)//2],"test":CN_TEST_URL}
        print(f"[china-test] {len(cn_nodes)} nodes reached the China target (median {cn_stats['median_ms']}ms)")
    else:
        cn_stats={"alive":0,"v2ray":0,"median_ms":None,"test":CN_TEST_URL,"stale":True}
        print("[china-test] no China results; keeping previous cn feed if present")
    now=datetime.now(BJT).strftime("%Y-%m-%d %H:%M")
    report={"time":now,"sources":stats,"candidates":len(merged),"tested":len(merged),"alive":len(nodes),"v2ray":len(links),"dropped_slow":dropped_slow,"dropped_dup":dropped_dup,"region":region_stats,"geoip":geoip_stats,"cn":cn_stats,"test":"mihomo API / gstatic generate_204"}
    (ROOT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    refresh_readme(now, len(merged), len(nodes), len(links), region_stats, txt_counts, cn_stats)
    print(f"PASS: {len(nodes)}/{len(merged)} nodes passed mihomo real connection test")
if __name__=="__main__": main()
