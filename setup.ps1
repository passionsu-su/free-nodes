# setup.ps1 - 把 mihomo.exe 放进 GitHub runner 工具缓存，并安装防休眠保活
# 用法（管理员 PowerShell）:
#   iwr https://cdn.jsdelivr.net/gh/passionsu-su/free-nodes@tools/setup.ps1 -OutFile $env:TEMP\s.ps1; powershell -ep bypass -f $env:TEMP\s.ps1
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$Bases = @('https://cdn.jsdelivr.net/gh/passionsu-su/free-nodes@tools/',
           'https://fastly.jsdelivr.net/gh/passionsu-su/free-nodes@tools/',
           'https://gcore.jsdelivr.net/gh/passionsu-su/free-nodes@tools/',
           'https://raw.githubusercontent.com/passionsu-su/free-nodes/tools/')
function Get-File($name, $out) {
  foreach ($b in $Bases) {
    try { Invoke-WebRequest -UseBasicParsing -Uri ($b + $name) -OutFile $out -TimeoutSec 300; if ((Get-Item $out).Length -gt 0) { return } }
    catch { Write-Host "  $b 失败: $($_.Exception.Message)" }
  }
  throw "下载失败: $name"
}
$tmp = Join-Path $env:TEMP 'mihomo-setup'; New-Item -ItemType Directory -Force $tmp | Out-Null
Write-Host "[1/4] 下载 mihomo v1.19.34 (windows-amd64-compatible)..."
$zip = Join-Path $tmp 'mihomo.zip'; $fs = [IO.File]::Create($zip)
foreach ($i in 0..2) { $p = Join-Path $tmp "part$i"; Get-File "mihomo.zip.part$i" $p; $bytes = [IO.File]::ReadAllBytes($p); $fs.Write($bytes, 0, $bytes.Length); Write-Host "  分片 $i OK" }
$fs.Close()
Get-File 'mihomo.zip.sha256' (Join-Path $tmp 'sha')
$want = (Get-Content (Join-Path $tmp 'sha') -Raw).Trim().ToLower(); $got = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
if ($want -ne $got) { throw "SHA256 不匹配: $got" }
Write-Host "  校验通过"
Expand-Archive $zip -DestinationPath $tmp -Force
$exe = Get-ChildItem $tmp -Filter 'mihomo*.exe' | Select-Object -First 1

Write-Host "[2/4] 查找 runner 目录..."
$runners = @()
$drives = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Free -ne $null } | ForEach-Object { $_.Root }
foreach ($d in $drives) {
  foreach ($c in @(Get-ChildItem $d -Directory -ErrorAction SilentlyContinue) + @(Get-ChildItem $d -Directory -ErrorAction SilentlyContinue | ForEach-Object { Get-ChildItem $_.FullName -Directory -ErrorAction SilentlyContinue })) {
    if ((Test-Path (Join-Path $c.FullName '.runner')) -or (Test-Path (Join-Path $c.FullName 'config.cmd'))) { $runners += $c.FullName }
  }
}
Get-CimInstance Win32_Service -Filter "Name like 'actions.runner.%'" -ErrorAction SilentlyContinue | ForEach-Object {
  $p = ($_.PathName -replace '"','') -replace '\\bin\\RunnerService\.exe.*$',''; if ($p -and (Test-Path $p)) { $runners += $p } }
$runners = $runners | Sort-Object -Unique
if (-not $runners) { $runners = @('C:\actions-runner'); Write-Warning "没找到 runner，默认放到 C:\actions-runner" }

Write-Host "[3/4] 放置 mihomo.exe..."
foreach ($r in $runners) {
  $dst = Join-Path $r '_work\_tool\mihomo'; New-Item -ItemType Directory -Force $dst | Out-Null
  Copy-Item $exe.FullName (Join-Path $dst 'mihomo.exe') -Force
  $v = try { (& (Join-Path $dst 'mihomo.exe') -v | Select-Object -First 1) } catch { '版本读取失败' }
  Write-Host "  OK $dst\mihomo.exe  ->  $v"
}

Write-Host "[4/4] 安装防休眠保活..."
$kdir = 'C:\ProgramData\KeepAwake'; New-Item -ItemType Directory -Force $kdir | Out-Null
Get-File 'keep_awake.ps1' (Join-Path $kdir 'keep_awake.ps1')
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $kdir 'keep_awake.ps1') -Mode auto
Write-Host ""
Write-Host "完成。以后可用: powershell -NoProfile -ExecutionPolicy Bypass -File C:\ProgramData\KeepAwake\keep_awake.ps1 -Mode check"
