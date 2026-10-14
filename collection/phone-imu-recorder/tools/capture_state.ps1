param(
    [string]$AdbPath = 'D:/Project/imu环境重建/.cache/android-platform-tools/platform-tools/adb.exe',
    [Parameter(Mandatory)][string]$Serial,
    [string]$PackageName = 'org.imulayout.recorder',
    [Parameter(Mandatory)][string]$OutputDir,
    [Parameter(Mandatory)][ValidateSet('foreground','other_app','screen_off','returned')][string]$Phase
)
$ErrorActionPreference='Stop'
if ($Serial -notmatch '^[A-Za-z0-9._:-]+$' -or $PackageName -notmatch '^[a-zA-Z][a-zA-Z0-9_.]+$') { throw '设备或包名格式无效' }
$projectRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$target=[IO.Path]::GetFullPath($OutputDir)
$reports=[IO.Path]::GetFullPath((Join-Path $projectRoot 'environment/reports'))
if (!$target.StartsWith($reports+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw '输出必须放在本项目 environment/reports 内' }
$capture=Join-Path $target ((Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'_'+$Phase)
New-Item -ItemType Directory -Path $capture | Out-Null
$records=[Collections.Generic.List[object]]::new()
function Read-Adb([string]$Name,[string[]]$Arguments) {
    $begin=[DateTimeOffset]::UtcNow.ToString('o')
    $content=(& $AdbPath -s $Serial @Arguments 2>&1 | Out-String)
    $code=$LASTEXITCODE
    $end=[DateTimeOffset]::UtcNow.ToString('o')
    $file=Join-Path $capture ($Name+'.txt')
    [IO.File]::WriteAllText($file,$content,[Text.UTF8Encoding]::new($false))
    $records.Add([ordered]@{name=$Name;arguments=$Arguments;begin_utc=$begin;end_utc=$end;exit_code=$code;sha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()})
    if ($code -ne 0) { throw "只读查询失败：$Name，退出码 $code，原输出已保存" }
    return $content
}
try {
    $state=Read-Adb 'device_state' @('get-state')
    if ($state.Trim() -ne 'device') { throw '设备未授权或未连接' }
    $package=Read-Adb 'package' @('shell','dumpsys','package',$PackageName)
    $deviceUser=(Read-Adb 'current_user' @('shell','am','get-current-user')).Trim()
    if ($deviceUser -notmatch '^\d+$') { throw '当前 Android 用户编号未确认' }
    $uidLine=Read-Adb 'package_uid' @('shell','cmd','package','list','packages','-U','--user',$deviceUser,$PackageName)
    $uidPattern='(?m)^package:'+([regex]::Escape($PackageName))+'\s+.*?uid:(\d+)\b'
    if ($uidLine -notmatch $uidPattern) { throw '本包当前用户 UID 未找到，不能复用旧 UID' }
    $deviceUid=$Matches[1]
    $devicePid=Read-Adb 'pid' @('shell','pidof',$PackageName)
    Read-Adb 'device_uptime_before' @('shell','cat','/proc/uptime') | Out-Null
    Read-Adb 'device_wall_before' @('shell','date','+%s%3N') | Out-Null
    Read-Adb 'services' @('shell','dumpsys','activity','services',$PackageName) | Out-Null
    Read-Adb 'sensorservice' @('shell','dumpsys','sensorservice') | Out-Null
    Read-Adb 'uid_state' @('shell','cmd','activity','get-uid-state',$deviceUid) | Out-Null
    Read-Adb 'power' @('shell','dumpsys','power') | Out-Null
    Read-Adb 'device_wall_after' @('shell','date','+%s%3N') | Out-Null
    Read-Adb 'device_uptime_after' @('shell','cat','/proc/uptime') | Out-Null
    $summary=[ordered]@{phase=$Phase;package=$PackageName;uid=$deviceUid;pid=$devicePid.Trim();commands=$records;simultaneous=$false;causal_trace=$false;error=$null}
} catch {
    $summary=[ordered]@{phase=$Phase;package=$PackageName;commands=$records;error=$_.Exception.Message}
    [IO.File]::WriteAllText((Join-Path $capture 'summary.json'),($summary|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
    throw
}
[IO.File]::WriteAllText((Join-Path $capture 'summary.json'),($summary|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
Write-Output "只读状态已保存：$capture"
