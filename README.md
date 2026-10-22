# free-nodes

每日自动整理的公开免费节点订阅，按客户端分类。更新时间：2026-10-22 18:41（北京时间）

## 一键复制订阅网页
- GitHub Pages：https://passionsu-su.github.io/free-nodes/
- Hark 页面：https://hark.site/s/547f5c1e-13fe-4f08-94e3-44f772b0cf44?hark_region=us

## iOS
| 客户端 | 订阅/配置链接 | 节点 | 导入方式 |
| --- | --- | --- | --- |
| Shadowrocket 小火箭 | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/shadowrocket/sub.txt | 181 | 右上角 + → 类型 Subscribe |
| Surge | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/surge/surge.conf | 9 | 配置 → 从 URL 下载配置（仅 vmess/trojan/ss/hy2，Surge 不支持 vless） |
| Surge（仅节点） | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/surge/proxies.list | 9 | 策略组 policy-path 引用 |
| Quantumult X 圈X | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/quantumultx/qx.txt | 83 | 节点 → 引用(订阅) → 添加 |
| Stash | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/stash/stash.yaml | 123 | 配置 → 从 URL 下载 |
| Clash Mi | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/clashmi/clashmi.yaml | 123 | 添加配置 → URL |
| Loon | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/loon/loon.list | 88 | 节点 → 订阅节点 → 添加 |
| sing-box(SFI) / Karing / Hiddify | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/singbox/singbox.json | 121 | 新建远程配置 |

## 按地区订阅（小火箭 / v2rayNG / v2rayN / NekoBox 通用，已按延迟从低到高排序）
| 地区 | 链接 | 节点 |
| --- | --- | --- |
| 香港 | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/region/hk.txt | 12 |
| 台湾 | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/region/tw.txt | 0 |
| 日本 | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/region/jp.txt | 10 |
| 新加坡 | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/region/sg.txt | 8 |
| 韩国 | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/region/kr.txt | 4 |
| 美国 | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/region/us.txt | 37 |
| 欧洲 | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/region/eu.txt | 83 |
| 其他 | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/region/other.txt | 27 |

延迟为海外服务器 TCP 握手耗时，仅作粗排；Hysteria2/TUIC 走 UDP 无法检查，排在最后。导入后在 App 里点“连通性测试/按延迟排序”以本机实测为准。

## 安卓 / 桌面
| 客户端 | 链接 | 节点 |
| --- | --- | --- |
| Clash Verge / Clash Meta / FlClash | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/clash/all.yaml | 123 |
| v2rayNG / v2rayN / NekoBox | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/v2ray/all.txt | 181 |
| 明文链接 | https://raw.githubusercontent.com/passionsu-su/free-nodes/main/v2ray/all_raw.txt | 181 |

已过滤 fp=unsafe、内网/假节点；Clash 系配置里的 TCP 节点经过端口连通检查（检查发起于海外服务器，不代表国内可连），未测速，导入后请先做真连接测试。

免费公共节点可能被记录流量，勿用于银行、支付等敏感账号。
