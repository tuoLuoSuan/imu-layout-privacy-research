param([string[]]$Tasks = @('testDebugUnitTest','assembleDebug'))
$ErrorActionPreference = 'Stop'
$sourceRoot = Split-Path -Parent $PSScriptRoot
$workspaceSource = [IO.Path]::GetFullPath((Join-Path $sourceRoot '../..'))
$workspaceRoot = 'D:/Project/imu-recorder-local'
if (!(Test-Path -LiteralPath $workspaceRoot)) {
    New-Item -ItemType Junction -Path $workspaceRoot -Target $workspaceSource | Out-Null
}
$alias = Get-Item -LiteralPath $workspaceRoot -Force
if ($alias.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath($alias.Target) -ne $workspaceSource) {
    throw '英文构建入口已存在且目标不同；未修改它。'
}
$projectRoot = Join-Path $workspaceRoot 'collection/phone-imu-recorder'
$env:JAVA_HOME = 'C:/Program Files/Java/latest/jdk-21'
$env:ANDROID_HOME = Join-Path $workspaceRoot '.cache/android-sdk'
$env:GRADLE_USER_HOME = Join-Path $workspaceRoot '.cache/gradle-home'
$env:PATH = "$env:JAVA_HOME/bin;$env:PATH"
Push-Location -LiteralPath $projectRoot
try {
    & (Join-Path $projectRoot 'gradlew.bat') --no-daemon -p $projectRoot @Tasks
    if ($LASTEXITCODE -ne 0) { throw "构建失败，退出码 $LASTEXITCODE" }
} finally { Pop-Location }
