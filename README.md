# tools 分支
Windows self-hosted runner 辅助文件（经 jsDelivr 分发，国内可下载）：
- mihomo v1.19.34 windows-amd64-compatible（zip 分 3 片，sha256 校验）
- setup.ps1：放置到 runner `_work\_tool\mihomo\mihomo.exe` 并安装保活
- keep_awake.ps1：防休眠，`-Mode check|auto|start|status|stop|harden|restore|requests`

管理员 PowerShell 一行执行：
iwr https://cdn.jsdelivr.net/gh/passionsu-su/free-nodes@tools/setup.ps1 -OutFile $env:TEMP\s.ps1; powershell -ep bypass -f $env:TEMP\s.ps1
