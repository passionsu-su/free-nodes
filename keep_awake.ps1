# keep_awake.ps1 - 防止 Windows 云电脑休眠（供 GitHub self-hosted runner 使用）
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File keep_awake.ps1 -Mode <check|auto|start|status|stop|harden|restore|requests>
#   check    查看当前电源设置、保活任务状态、阻止休眠的请求
#   auto     harden + 注册开机/登录自启的保活任务 + 立即启动（推荐，需管理员）
#   start    立即在后台启动保活进程（SetThreadExecutionState）
#   status   同 check
#   stop     停止保活进程并删除自启任务
#   harden   关闭睡眠/休眠/硬盘/显示器超时（先备份，可 restore）
#   restore  恢复 harden 之前的电源设置
#   requests 显示 powercfg /requests
#   loop     (内部) 保活循环本体
param([ValidateSet('check','auto','start','status','stop','harden','restore','requests','loop')][string]$Mode = 'check')
$ErrorActionPreference = 'Continue'
$Dir    = 'C:\ProgramData\KeepAwake'
$Self   = Join-Path $Dir 'keep_awake.ps1'
$Backup = Join-Path $Dir 'power-backup.json'
$Log    = Join-Path $Dir 'keep_awake.log'
$Task   = 'KeepAwake'
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
if ($PSCommandPath -and ($PSCommandPath -ne $Self)) { Copy-Item $PSCommandPath $Self -Force }

function IsAdmin { ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) }
function Get-Timeout($sub, $set) {
  $o = powercfg /query SCHEME_CURRENT $sub $set 2>$null
  # 输出最后两个 0x 值依次是交流(AC)、直流(DC)索引，与系统语言无关
  $h = @($o | Select-String ':\s*0x([0-9a-fA-F]+)\s*$' | ForEach-Object { [Convert]::ToInt64($_.Matches[0].Groups[1].Value,16) })
  if ($h.Count -ge 2) { [pscustomobject]@{ ac = $h[-2]; dc = $h[-1] } } else { [pscustomobject]@{ ac = $null; dc = $null } }
}
$Settings = @(
  @{ n='standby';   sub='SUB_SLEEP';   set='STANDBYIDLE' },
  @{ n='hibernate'; sub='SUB_SLEEP';   set='HIBERNATEIDLE' },
  @{ n='disk';      sub='SUB_DISK';    set='DISKIDLE' },
  @{ n='monitor';   sub='SUB_VIDEO';   set='VIDEOIDLE' }
)
function Show-Status {
  Write-Host "== 电源超时（秒，0=从不）=="
  foreach ($s in $Settings) { $t = Get-Timeout $s.sub $s.set; Write-Host ("{0,-10} AC={1} DC={2}" -f $s.n, $t.ac, $t.dc) }
  Write-Host "== 保活任务 =="
  $t = Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue
  if ($t) { Write-Host "任务: $($t.State)" } else { Write-Host "任务: 未注册" }
  $p = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*keep_awake.ps1*-Mode loop*' }
  Write-Host ("保活进程: " + $(if ($p) { "运行中 PID " + ($p.ProcessId -join ',') } else { "未运行" }))
  if (Test-Path $Backup) { Write-Host "已有备份: $Backup（可 -Mode restore）" }
  if (Test-Path $Log) { Write-Host "最近心跳: $((Get-Content $Log -Tail 1))" }
  Write-Host "== 阻止休眠的请求 =="; powercfg /requests
}
function Harden {
  if (-not (IsAdmin)) { Write-Warning "harden 需要管理员 PowerShell"; return }
  if (-not (Test-Path $Backup)) {
    $b = @{}; foreach ($s in $Settings) { $b[$s.n] = Get-Timeout $s.sub $s.set }
    $b | ConvertTo-Json | Set-Content $Backup -Encoding UTF8; Write-Host "已备份原设置 -> $Backup"
  }
  foreach ($s in @('standby','hibernate','disk','monitor')) { powercfg /change "$s-timeout-ac" 0; powercfg /change "$s-timeout-dc" 0 }
  powercfg /hibernate off 2>$null
  Write-Host "已关闭睡眠/休眠/硬盘/显示器超时，并关闭休眠文件"
}
function Restore {
  if (-not (Test-Path $Backup)) { Write-Warning "没有备份"; return }
  $b = Get-Content $Backup -Raw | ConvertFrom-Json
  foreach ($s in $Settings) {
    $v = $b.($s.n); if ($null -eq $v) { continue }
    if ($null -ne $v.ac) { powercfg /setacvalueindex SCHEME_CURRENT $s.sub $s.set $v.ac }
    if ($null -ne $v.dc) { powercfg /setdcvalueindex SCHEME_CURRENT $s.sub $s.set $v.dc }
  }
  powercfg /setactive SCHEME_CURRENT; Remove-Item $Backup -Force; Write-Host "已恢复原电源设置"
}
function Start-Loop {
  $p = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*keep_awake.ps1*-Mode loop*' }
  if ($p) { Write-Host "保活进程已在运行 PID $($p.ProcessId -join ',')"; return }
  Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$Self`" -Mode loop"
  Start-Sleep 2; Write-Host "保活进程已启动"
}
function Register-Task {
  if (-not (IsAdmin)) { Write-Warning "注册自启任务需要管理员 PowerShell"; return }
  $a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Self`" -Mode loop"
  $tr = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -AtLogOn))
  $st = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
  $pr = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
  Register-ScheduledTask -TaskName $Task -Action $a -Trigger $tr -Settings $st -Principal $pr -Force | Out-Null
  Start-ScheduledTask -TaskName $Task; Write-Host "已注册并启动自启任务 $Task（SYSTEM，开机/登录自动运行）"
}
function Stop-All {
  Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*keep_awake.ps1*-Mode loop*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  if (Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $Task -Confirm:$false }
  Write-Host "已停止保活并删除自启任务"
}
function Loop {
  Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
  while ($true) {
    [void][W.P]::SetThreadExecutionState([uint32]2147483713)
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') alive" | Set-Content $Log -Encoding UTF8
    Start-Sleep 60
  }
}
switch ($Mode) {
  'check'    { Show-Status }
  'status'   { Show-Status }
  'requests' { powercfg /requests }
  'harden'   { Harden }
  'restore'  { Restore }
  'start'    { Start-Loop }
  'stop'     { Stop-All }
  'auto'     { Harden; if (IsAdmin) { Register-Task } else { Start-Loop }; Start-Sleep 3; Show-Status }
  'loop'     { Loop }
}
