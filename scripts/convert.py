#!/usr/bin/env python3
"""Convert the mihomo-tested clash/all.yaml into Shadowrocket, Surge, Quantumult X, Loon, sing-box, Stash and Clash Mi feeds natively (no subconverter)."""
import json, os, re, shutil, yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = ROOT
cfg = yaml.safe_load(open(f'{OUT}/clash/all.yaml', encoding='utf-8'))
P = cfg.get('proxies') or []
if not P: raise SystemExit('clash/all.yaml has no proxies')
for d in ('surge', 'quantumultx', 'loon', 'singbox', 'stash', 'clashmi', 'shadowrocket'): os.makedirs(f'{OUT}/{d}', exist_ok=True)
def clean(n): return re.sub(r'[,=\"]', ' ', n).strip()
ws = lambda p: p.get('network') == 'ws'
wo = lambda p: p.get('ws-opts') or {}
host = lambda p: (wo(p).get('headers') or {}).get('Host') or p.get('servername') or p.get('sni') or ''
sni = lambda p: p.get('servername') or p.get('sni') or ''
# ---- Surge ----
surge = []
for p in P:
    n, t, s, pt = clean(p['name']), p['type'], p['server'], p['port']
    if t == 'ss': l = f"{n} = ss, {s}, {pt}, encrypt-method={p['cipher']}, password={p['password']}, udp-relay=true"
    elif t == 'vmess' and p.get('network', 'tcp') in ('tcp', 'ws') and not (p.get('ws-opts') or {}).get('v2ray-http-upgrade'):
        l = f"{n} = vmess, {s}, {pt}, username={p['uuid']}, vmess-aead={'true' if int(p.get('alterId',0))==0 else 'false'}"
        if ws(p): l += f", ws=true, ws-path={wo(p).get('path','/')}, ws-headers=Host:{host(p)}"
        if p.get('tls'): l += f", tls=true, sni={sni(p) or s}, skip-cert-verify=true"
    elif t == 'trojan' and p.get('network', 'tcp') in ('tcp', 'ws') and not (p.get('ws-opts') or {}).get('v2ray-http-upgrade'):
        l = f"{n} = trojan, {s}, {pt}, password={p['password']}, sni={sni(p) or s}, skip-cert-verify=true"
        if ws(p): l += f", ws=true, ws-path={wo(p).get('path','/')}, ws-headers=Host:{host(p)}"
    elif t == 'hysteria2' and not p.get('obfs'): l = f"{n} = hysteria2, {s}, {pt}, password={p['password']}, sni={sni(p) or s}, skip-cert-verify=true"
    else: continue
    surge.append((n, l))
sl = [n for n, _ in surge]
open(f'{OUT}/surge/surge.conf','w').write('[General]\nloglevel = notify\nskip-proxy = 127.0.0.1, 192.168.0.0/16, 10.0.0.0/8, localhost, *.local\ndns-server = system, 223.5.5.5, 119.29.29.29\n\n[Proxy]\n' + '\n'.join(l for _, l in surge) +
  f"\n\n[Proxy Group]\nPROXY = select, AUTO, {', '.join(sl)}\nAUTO = url-test, {', '.join(sl)}, url=http://www.gstatic.com/generate_204, interval=600\n\n[Rule]\nGEOIP,CN,DIRECT\nFINAL,PROXY,dns-failed\n")
open(f'{OUT}/surge/proxies.list','w').write('\n'.join(l for _, l in surge) + '\n')
# ---- Quantumult X (server_remote resource) ----
qx = []
for p in P:
    n, t, s, pt = clean(p['name']), p['type'], p['server'], p['port']
    if t == 'ss': l = f"shadowsocks={s}:{pt}, method={p['cipher']}, password={p['password']}, udp-relay=true"
    elif t in ('vmess', 'vless', 'trojan') and p.get('network', 'tcp') in ('tcp', 'ws') and not (p.get('ws-opts') or {}).get('v2ray-http-upgrade') and not p.get('reality-opts'):
        if t == 'trojan': l = f"trojan={s}:{pt}, password={p['password']}"
        elif t == 'vmess': l = f"vmess={s}:{pt}, method=chacha20-ietf-poly1305, password={p['uuid']}" + (", aead=false" if int(p.get('alterId',0)) else "")
        else: l = f"vless={s}:{pt}, method=none, password={p['uuid']}"
        tls = p.get('tls') or t == 'trojan'
        if ws(p): l += f", obfs={'wss' if tls else 'ws'}, obfs-host={host(p) or s}, obfs-uri={wo(p).get('path','/')}"
        elif tls: l += (", over-tls=true" if t == 'trojan' else ", obfs=over-tls") + f", {'tls-host' if t=='trojan' else 'obfs-host'}={sni(p) or s}"
        if tls: l += ", tls-verification=false"
    else: continue
    qx.append(l + f", tag={n}")
open(f'{OUT}/quantumultx/qx.txt','w').write('\n'.join(qx) + '\n')
# ---- Loon ----
loon = []
for p in P:
    n, t, s, pt = clean(p['name']), p['type'], p['server'], p['port']
    if t == 'ss': l = f'{n} = Shadowsocks, {s}, {pt}, {p["cipher"]}, "{p["password"]}", udp=true'
    elif t in ('vmess', 'vless') and p.get('network', 'tcp') in ('tcp', 'ws') and not (p.get('ws-opts') or {}).get('v2ray-http-upgrade') and not p.get('reality-opts'):
        l = f'{n} = {"vmess" if t=="vmess" else "VLESS"}, {s}, {pt}, ' + ('auto, ' if t == 'vmess' else '') + f'"{p["uuid"]}"'
        l += f', transport=ws, path={wo(p).get("path","/")}, host={host(p) or s}' if ws(p) else ', transport=tcp'
        if t == 'vmess': l += f', alterId={p.get("alterId",0)}'
        if p.get('tls'): l += f', over-tls=true, sni={sni(p) or s}, skip-cert-verify=true'
    elif t == 'trojan': l = f'{n} = trojan, {s}, {pt}, "{p["password"]}", sni={sni(p) or s}, skip-cert-verify=true'
    elif t == 'hysteria2' and not p.get('obfs'): l = f'{n} = Hysteria2, {s}, {pt}, "{p["password"]}", sni={sni(p) or s}, skip-cert-verify=true, udp=true'
    else: continue
    loon.append(l)
open(f'{OUT}/loon/loon.list','w').write('\n'.join(loon) + '\n')
# ---- sing-box (SFI / Karing / Hiddify / NekoBox) ----
ob = []
for p in P:
    t = p['type']; o = {'tag': p['name'], 'server': p['server'], 'server_port': int(p['port'])}
    if t == 'ss': o.update(type='shadowsocks', method=p['cipher'], password=p['password'])
    elif t == 'vmess': o.update(type='vmess', uuid=p['uuid'], alter_id=int(p.get('alterId', 0)), security='auto')
    elif t == 'vless': o.update(type='vless', uuid=p['uuid']); p.get('flow') and o.update(flow=p['flow'])
    elif t == 'trojan': o.update(type='trojan', password=p['password'])
    elif t == 'hysteria2': o.update(type='hysteria2', password=p['password'], tls={'enabled': True, 'server_name': sni(p) or p['server'], 'insecure': True}); p.get('obfs') and o.update(obfs={'type': p['obfs'], 'password': p.get('obfs-password', '')})
    else: continue
    if t in ('vmess', 'vless', 'trojan'):
        if p.get('tls') or t == 'trojan':
            tl = {'enabled': True, 'server_name': sni(p) or p['server'], 'insecure': True}
            fp = p.get('client-fingerprint')
            if p.get('reality-opts'):
                r = p['reality-opts']; tl['insecure'] = False
                tl['reality'] = {'enabled': True, 'public_key': r.get('public-key', ''), 'short_id': r.get('short-id', '')}
                fp = fp or 'chrome'
            if fp: tl['utls'] = {'enabled': True, 'fingerprint': fp}
            o['tls'] = tl
        if ws(p): o['transport'] = {'type': 'ws', 'path': wo(p).get('path', '/'), 'headers': {'Host': host(p) or p['server']}}
        elif p.get('network') == 'grpc': o['transport'] = {'type': 'grpc', 'service_name': (p.get('grpc-opts') or {}).get('grpc-service-name', '')}
        elif p.get('network') not in (None, 'tcp'): continue
    ob.append(o)
tags = [o['tag'] for o in ob]
sb = {'log': {'level': 'warn'},
      'dns': {'servers': [{'type': 'tls', 'tag': 'remote', 'server': '8.8.8.8', 'detour': 'PROXY'}, {'type': 'udp', 'tag': 'local', 'server': '223.5.5.5'}],
              'final': 'remote'},
      'inbounds': [{'type': 'tun', 'tag': 'tun-in', 'address': ['172.19.0.1/30'], 'auto_route': True, 'strict_route': True, 'stack': 'mixed'}],
      'outbounds': [{'type': 'selector', 'tag': 'PROXY', 'outbounds': ['AUTO'] + tags},
                    {'type': 'urltest', 'tag': 'AUTO', 'outbounds': tags, 'url': 'https://www.gstatic.com/generate_204', 'interval': '5m'}] + ob +
                   [{'type': 'direct', 'tag': 'direct'}],
      'route': {'rules': [{'action': 'sniff'}, {'protocol': 'dns', 'action': 'hijack-dns'}, {'ip_is_private': True, 'outbound': 'direct'}],
                'final': 'PROXY', 'auto_detect_interface': True, 'default_domain_resolver': 'local'}}
shutil.copyfile(f'{OUT}/v2ray/all.txt', f'{OUT}/shadowrocket/sub.txt')
for d in ('stash/stash.yaml', 'clashmi/clashmi.yaml'): shutil.copyfile(f'{OUT}/clash/all.yaml', f'{OUT}/{d}')

# 旧版 Clash for Windows 0.20.x（Clash Premium 内核）只认 http/socks5/ss/ssr/vmess/trojan，
# 不认 hysteria2/vless/tuic/reality 等 Meta 专有协议，混入会导致整份配置加载失败。
CFW_DROP = {'client-fingerprint', 'reality-opts', 'flow', 'xudp', 'packet-encoding', 'global-padding',
            'authenticated-length', 'smux', 'dialer-proxy', 'ip-version', 'tfo', 'mptcp'}
def cfw_ok(p):
    t = p.get('type')
    if t not in ('http', 'socks5', 'ss', 'ssr', 'vmess', 'trojan'): return False
    if p.get('reality-opts') or p.get('flow'): return False
    if t == 'ss' and (str(p.get('cipher', '')).startswith('2022') or p.get('plugin') not in (None, 'obfs', 'v2ray-plugin')): return False
    if t == 'vmess' and p.get('network') not in (None, 'tcp', 'ws', 'http', 'h2', 'grpc'): return False
    if t == 'trojan' and p.get('network') not in (None, 'tcp', 'ws', 'grpc'): return False
    return True
full = yaml.safe_load(open(f'{OUT}/clash/all.yaml', encoding='utf-8'))
cps = [{k: v for k, v in p.items() if k not in CFW_DROP} for p in full.get('proxies', []) if cfw_ok(p)]
if not cps: raise SystemExit('clash/cfw.yaml: no convertible nodes')
names = {p['name'] for p in cps}
groups = []
for g in full.get('proxy-groups', []):
    g = dict(g); g['proxies'] = [x for x in g.get('proxies', []) if x in names or x in ('AUTO', 'PROXY', 'DIRECT', 'REJECT')]
    groups.append(g)
cfw = {k: v for k, v in full.items() if k not in ('proxies', 'proxy-groups')}
cfw['proxies'] = cps; cfw['proxy-groups'] = groups
cfw = {k: cfw[k] for k in list(full.keys()) if k in cfw}
bad = [p['name'] for p in cps if p['type'] not in ('http', 'socks5', 'ss', 'ssr', 'vmess', 'trojan')]
assert not bad, bad
for d in ('clash/cfw.yaml', 'clash/cfw-nodes.yaml'):
    yaml.safe_dump(cfw, open(f'{OUT}/{d}', 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False)
print(f'PASS clash/cfw.yaml: {len(cps)} nodes (Premium-compatible only)')
for f, n in (('surge/surge.conf', len(surge)), ('quantumultx/qx.txt', len(qx)), ('loon/loon.list', len(loon)), ('singbox/singbox.json', len(ob))):
    if n == 0: raise SystemExit(f'{f}: no convertible nodes')
    print(f'PASS {f}: {n} nodes')
