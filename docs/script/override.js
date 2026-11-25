// ============================================================
// free-nodes 扩展脚本（覆写）v1.1  2026-11-26
// 适用：Clash Verge Rev「扩展脚本」/ Mihomo Party(Clash Party)「覆写 → 远程 JS」/ FlClash「脚本」
// 订阅：https://passionsu-su.github.io/free-nodes/script/override.js
//
// 对任意订阅（机场或 free-nodes 的 clash/all.yaml 等）生效：
// 1. 去广告：微信广告专项 + anti-AD + 217heidai adblockfilters + Sukka reject（🛑 广告拦截 可切 DIRECT 关闭）
// 2. DNS 防泄漏：fake-ip；国内域名走阿里/腾讯 DoH，其余走境外 DoH 并经代理发出（respect-rules）
// 3. 绕过局域网 / 私有地址；国内直连（Sukka domestic/china_ip、微软苹果国内 CDN、blackmatrix7 ChinaMax、MetaCubeX cn）、国外代理；AI、YouTube、Netflix、Telegram、Google、微软、苹果、Steam 分流
// 4. 优化：地区自动测速、故障转移、TCP 并发、统一延迟、嗅探、保存选择、YouTube 屏蔽 QUIC 走 TCP 更稳
// 只要求 mihomo（Clash Meta）内核，不支持旧版 Clash Premium。
// ============================================================

const CDN = "https://testingcf.jsdelivr.net/gh";
const GEO = `${CDN}/MetaCubeX/meta-rules-dat@meta/geo`;
const TEST_URL = "https://www.gstatic.com/generate_204";

// ---------- 通用设置 ----------
const BASE = {
  "allow-lan": false,
  mode: "rule",
  "log-level": "warning",
  ipv6: false,
  "unified-delay": true,
  "tcp-concurrent": true,
  "find-process-mode": "strict",
  "keep-alive-interval": 30,
  profile: { "store-selected": true, "store-fake-ip": true },
  "geo-auto-update": true,
  "geo-update-interval": 24,
  "geox-url": {
    geoip: `${CDN}/MetaCubeX/meta-rules-dat@release/geoip.dat`,
    geosite: `${CDN}/MetaCubeX/meta-rules-dat@release/geosite.dat`,
    mmdb: `${CDN}/MetaCubeX/meta-rules-dat@release/country.mmdb`,
    asn: `${CDN}/MetaCubeX/meta-rules-dat@release/GeoLite2-ASN.mmdb`,
  },
};

// ---------- DNS 防泄漏 ----------
const CN_DOH = ["https://dns.alidns.com/dns-query", "https://doh.pub/dns-query"];
const FOREIGN_DOH = ["https://1.1.1.1/dns-query", "https://8.8.8.8/dns-query"];
const DNS = {
  enable: true,
  listen: "0.0.0.0:1053",
  ipv6: false,
  "enhanced-mode": "fake-ip",
  "fake-ip-range": "198.18.0.1/16",
  "fake-ip-filter-mode": "rule",
  "fake-ip-filter": [
    "RULE-SET,wechat-ads,fake-ip",
    "RULE-SET,private,real-ip",
    "DOMAIN-SUFFIX,lan,real-ip",
    "DOMAIN-SUFFIX,local,real-ip",
    "DOMAIN-SUFFIX,home.arpa,real-ip",
    "DOMAIN-SUFFIX,msftconnecttest.com,real-ip",
    "DOMAIN-SUFFIX,msftncsi.com,real-ip",
    "DOMAIN-SUFFIX,ntp.org,real-ip",
    "DOMAIN-SUFFIX,time.windows.com,real-ip",
    "DOMAIN,localhost.ptlogin2.qq.com,real-ip",
    "DOMAIN-SUFFIX,push.apple.com,real-ip",
    "DOMAIN-SUFFIX,qq.com,real-ip",
    "DOMAIN-SUFFIX,wechat.com,real-ip",
    "DOMAIN-SUFFIX,stun.l.google.com,real-ip",
    "MATCH,fake-ip",
  ],
  "use-hosts": true,
  // 节点域名、直连流量用国内 DoH；其余经代理查询境外 DoH，运营商看不到你查了什么
  "respect-rules": true,
  "default-nameserver": ["223.5.5.5", "119.29.29.29"],
  "proxy-server-nameserver": CN_DOH,
  "direct-nameserver": CN_DOH,
  "direct-nameserver-follow-policy": false,
  nameserver: FOREIGN_DOH,
  "nameserver-policy": {
    "rule-set:private,cn,apple-cn,microsoft-cn,steam-cn": CN_DOH,
  },
};

const SNIFFER = {
  enable: true,
  "force-dns-mapping": true,
  "parse-pure-ip": true,
  "override-destination": false,
  sniff: {
    HTTP: { ports: [80, "8080-8880"], "override-destination": true },
    TLS: { ports: [443, 8443] },
    QUIC: { ports: [443, 8443] },
  },
  "skip-domain": ["Mijia Cloud", "+.push.apple.com", "+.qq.com", "+.wechat.com"],
};

// ---------- 规则集 ----------
const mrs = (behavior, name, path) => ({
  type: "http", behavior, format: "mrs", interval: 86400, proxy: "DIRECT",
  url: `${GEO}/${behavior === "ipcidr" ? "geoip" : "geosite"}/${path}.mrs`,
  path: `./ruleset/fn-${name}.mrs`,
});
const skk = (behavior, path) => ({
  type: "http", behavior, format: "text", interval: 43200, proxy: "DIRECT",
  url: `https://ruleset.skk.moe/Clash/${path}.txt`,
  path: `./ruleset/fn-sukka-${path.replace("/", "-")}.txt`,
});
const RULE_PROVIDERS = {
  "wechat-ads": {
    type: "inline", behavior: "domain", format: "yaml",
    payload: [
      "wxsnsdy.wxs.qq.com", "wxsnsdythumb.wxs.qq.com", "wxsnsdyvip.wxs.qq.com", "wxsnsdy.tc.qq.com",
      "adsmind.gdtimg.com", "adsmind.apdcdn.tc.qq.com", "+.pgdt.gtimg.cn", "+.pgdt.gtimg.com",
      "+.gdt.qq.com", "e.qq.com", "l.qq.com", "adsfile.qq.com",
      "ad.weixin.qq.com", "ad.video.qq.com", "wa.gtimg.com",
    ],
  },
  "anti-ad": {
    type: "http", behavior: "domain", format: "yaml", interval: 86400, proxy: "DIRECT",
    url: `${CDN}/privacy-protection-tools/anti-AD@master/anti-ad-clash.yaml`,
    path: "./ruleset/fn-anti-ad.yaml",
  },
  "adb-heidai": {
    type: "http", behavior: "domain", format: "mrs", interval: 86400, proxy: "DIRECT",
    url: `${CDN}/217heidai/adblockfilters@main/rules/adblockmihomo.mrs`,
    path: "./ruleset/fn-adb-heidai.mrs",
  },
  // Sukka（ruleset.skk.moe）reject 三件套
  "sukka-reject-nonip": skk("classical", "non_ip/reject"),
  "sukka-reject-domain": skk("domain", "domainset/reject"),
  "sukka-reject-ip": skk("classical", "ip/reject"),
  // Sukka 直连：国内域名、国内 IP、微软 / 苹果国内 CDN
  "sukka-domestic": skk("classical", "non_ip/domestic"),
  "sukka-china-ip": skk("ipcidr", "ip/china_ip"),
  "sukka-microsoft-cdn": skk("classical", "non_ip/microsoft_cdn"),
  "sukka-apple-cdn": skk("domain", "domainset/apple_cdn"),
  // blackmatrix7 ChinaMax（域名 + IP 分开，避免 classical 混合规则触发多余 DNS 解析）
  "chinamax-domain": {
    type: "http", behavior: "domain", format: "text", interval: 86400, proxy: "DIRECT",
    url: `${CDN}/blackmatrix7/ios_rule_script@master/rule/Clash/ChinaMax/ChinaMax_Domain_For_Clash.txt`,
    path: "./ruleset/fn-chinamax-domain.txt",
  },
  "chinamax-ip": {
    type: "http", behavior: "ipcidr", format: "text", interval: 86400, proxy: "DIRECT",
    url: `${CDN}/blackmatrix7/ios_rule_script@master/rule/Clash/ChinaMax/ChinaMax_IP.txt`,
    path: "./ruleset/fn-chinamax-ip.txt",
  },
  private: mrs("domain", "private", "private"),
  ai: mrs("domain", "ai", "category-ai-!cn"),
  youtube: mrs("domain", "youtube", "youtube"),
  netflix: mrs("domain", "netflix", "netflix"),
  telegram: mrs("domain", "telegram", "telegram"),
  google: mrs("domain", "google", "google"),
  github: mrs("domain", "github", "github"),
  "microsoft-cn": mrs("domain", "microsoft-cn", "microsoft@cn"),
  microsoft: mrs("domain", "microsoft", "microsoft"),
  "apple-cn": mrs("domain", "apple-cn", "apple-cn"),
  apple: mrs("domain", "apple", "apple"),
  "steam-cn": mrs("domain", "steam-cn", "steam@cn"),
  steam: mrs("domain", "steam", "steam"),
  gfw: mrs("domain", "gfw", "gfw"),
  cn: mrs("domain", "cn", "cn"),
  "not-cn": mrs("domain", "not-cn", "geolocation-!cn"),
  "ip-private": mrs("ipcidr", "ip-private", "private"),
  "ip-telegram": mrs("ipcidr", "ip-telegram", "telegram"),
  "ip-netflix": mrs("ipcidr", "ip-netflix", "netflix"),
  "ip-google": mrs("ipcidr", "ip-google", "google"),
  "ip-cn": mrs("ipcidr", "ip-cn", "cn"),
};

const P = "🚀 节点选择", AUTO = "♻️ 自动选择", FB = "🔯 故障转移", CN = "🎯 国内直连",
  AD = "🛑 广告拦截", FINAL = "🐟 漏网之鱼";

const RULES = [
  // 去广告
  `RULE-SET,wechat-ads,${AD}`,
  `RULE-SET,anti-ad,${AD}`,
  `RULE-SET,adb-heidai,${AD}`,
  `RULE-SET,sukka-reject-nonip,${AD}`,
  `RULE-SET,sukka-reject-domain,${AD}`,
  // 局域网 / 私有地址
  "RULE-SET,private,DIRECT",
  "RULE-SET,ip-private,DIRECT,no-resolve",
  "DOMAIN-SUFFIX,local,DIRECT",
  // 微信、QQ 进程直连（安卓 / 桌面）
  "PROCESS-NAME,com.tencent.mm,DIRECT",
  "PROCESS-NAME,com.tencent.mobileqq,DIRECT",
  "PROCESS-NAME,WeChat.exe,DIRECT",
  "PROCESS-NAME,Weixin.exe,DIRECT",
  "PROCESS-NAME,QQ.exe,DIRECT",
  // YouTube 屏蔽 QUIC，强制走 TCP，免费节点上更稳
  "AND,((NETWORK,UDP),(DST-PORT,443),(RULE-SET,youtube)),REJECT",
  // 海外服务
  "RULE-SET,ai,🤖 AI",
  "RULE-SET,youtube,📺 YouTube",
  "RULE-SET,netflix,🎬 Netflix",
  "RULE-SET,telegram,✈️ Telegram",
  "RULE-SET,github,🐱 GitHub",
  "RULE-SET,google,🔍 Google",
  // 国内可直连的大厂（微软 / 苹果国内 CDN 下载最耗流量，优先直连）
  `RULE-SET,sukka-microsoft-cdn,${CN}`,
  `RULE-SET,sukka-apple-cdn,${CN}`,
  `RULE-SET,microsoft-cn,${CN}`,
  "RULE-SET,microsoft,Ⓜ️ 微软",
  `RULE-SET,apple-cn,${CN}`,
  "RULE-SET,apple,🍎 苹果",
  `RULE-SET,steam-cn,${CN}`,
  "RULE-SET,steam,🎮 Steam",
  // 国内外分流
  `RULE-SET,gfw,${P}`,
  `RULE-SET,sukka-domestic,${CN}`,
  `RULE-SET,chinamax-domain,${CN}`,
  `RULE-SET,cn,${CN}`,
  `RULE-SET,not-cn,${P}`,
  // IP 规则
  `RULE-SET,sukka-reject-ip,${AD}`,
  "RULE-SET,ip-telegram,✈️ Telegram,no-resolve",
  "RULE-SET,ip-netflix,🎬 Netflix,no-resolve",
  "RULE-SET,ip-google,🔍 Google,no-resolve",
  `RULE-SET,sukka-china-ip,${CN}`,
  `RULE-SET,chinamax-ip,${CN}`,
  `RULE-SET,ip-cn,${CN}`,
  `MATCH,${FINAL}`,
];

const REGIONS = [
  ["🇭🇰 香港", "(?i)港|🇭🇰|hk|hong ?kong"],
  ["🇹🇼 台湾", "(?i)台|🇹🇼|tw|taiwan"],
  ["🇯🇵 日本", "(?i)日本|东京|大阪|🇯🇵|jp|japan"],
  ["🇸🇬 新加坡", "(?i)新加坡|狮城|🇸🇬|sg|singapore"],
  ["🇰🇷 韩国", "(?i)韩|🇰🇷|kr|korea"],
  ["🇺🇸 美国", "(?i)美|🇺🇸|us|united ?states|america"],
];
const JUNK = "(?i)剩余|流量|到期|官网|套餐|重置|expire|traffic";

function main(config) {
  config = config || {};
  const proxies = Array.isArray(config.proxies) ? config.proxies : [];
  const providers = config["proxy-providers"] || {};
  const hasProviders = Object.keys(providers).length > 0;
  if (!proxies.length && !hasProviders) throw new Error("订阅里没有节点");

  Object.assign(config, BASE);
  config.dns = DNS;
  config.sniffer = SNIFFER;

  const jsRe = (re) => new RegExp(re.replace("(?i)", ""), "i");
  const junk = jsRe(JUNK);
  const names = proxies.map((p) => p.name).filter((n) => !junk.test(n));
  const regionGroups = REGIONS.filter(([, re]) => {
    if (hasProviders) return true;
    const r = jsRe(re);
    return names.some((n) => r.test(n));
  }).map(([name, re]) => ({
    name, type: "url-test", url: TEST_URL, interval: 300, tolerance: 50, lazy: true,
    "include-all": true, filter: re, "exclude-filter": JUNK,
  }));
  const regionNames = regionGroups.map((g) => g.name);
  const all = { "include-all": true, "exclude-filter": JUNK };
  const pick = (first) => ({ type: "select", proxies: [first, P, AUTO, ...regionNames, "DIRECT"].filter((v, i, a) => a.indexOf(v) === i) });

  config["proxy-groups"] = [
    { name: P, type: "select", proxies: [AUTO, FB, ...regionNames, "DIRECT"], ...all },
    { name: AUTO, type: "url-test", url: TEST_URL, interval: 300, tolerance: 50, lazy: true, ...all },
    { name: FB, type: "fallback", url: TEST_URL, interval: 300, lazy: true, ...all },
    { name: "🤖 AI", ...pick(regionNames.includes("🇺🇸 美国") ? "🇺🇸 美国" : P) },
    { name: "📺 YouTube", ...pick(P) },
    { name: "🎬 Netflix", ...pick(P) },
    { name: "✈️ Telegram", ...pick(P) },
    { name: "🐱 GitHub", ...pick(P) },
    { name: "🔍 Google", ...pick(P) },
    { name: "Ⓜ️ 微软", type: "select", proxies: ["DIRECT", P] },
    { name: "🍎 苹果", type: "select", proxies: ["DIRECT", P] },
    { name: "🎮 Steam", type: "select", proxies: ["DIRECT", P] },
    { name: CN, type: "select", proxies: ["DIRECT", P] },
    { name: AD, type: "select", proxies: ["REJECT", "DIRECT"] },
    { name: FINAL, type: "select", proxies: [P, "DIRECT", AUTO] },
    ...regionGroups,
  ];

  config["rule-providers"] = Object.assign({}, config["rule-providers"] || {}, RULE_PROVIDERS);
  config.rules = RULES;
  return config;
}

if (typeof module !== "undefined") module.exports = { main };
