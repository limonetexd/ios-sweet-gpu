param(
	[string]$Tools = "$PSScriptRoot\..\..\tools-win\platform-tools",
	[string]$Recovery = "$PSScriptRoot\..\recovery\recovery.img",
	[string]$Out = "",
	[switch]$BootRecovery,
	[int]$AdbSeconds = 300
)
$ErrorActionPreference = "Continue"
$adb = Join-Path $Tools "adb.exe"
$fb = Join-Path $Tools "fastboot.exe"
function Log($m) { Write-Host ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $m) }

if ($BootRecovery) {
	Log "booting recovery $Recovery"
	& cmd /c "`"$fb`" boot `"$Recovery`" 2>&1" | Out-Host
}
$end = (Get-Date).AddSeconds($AdbSeconds)
$ok = $false
while ((Get-Date) -lt $end) {
	$s = & cmd /c "`"$adb`" get-state 2>NUL"
	if ($s -match "recovery|device|sideload") { $ok = $true; break }
	Start-Sleep -Seconds 2
}
if (-not $ok) { throw "adb did not come up in $AdbSeconds s" }
Log "adb up: $s"

# ueventd needs a moment before the by-name links exist.
$dev = $null
for ($i = 0; $i -lt 30 -and -not $dev; $i++) {
	$r = & cmd /c "`"$adb`" shell readlink -f /dev/block/by-name/userdata 2>NUL"
	if ($r -and $r.Trim() -match "^/dev/block/sd") { $dev = $r.Trim() }
	if (-not $dev) { Start-Sleep -Seconds 2 }
}
if (-not $dev) { throw "userdata block device not found" }
$bytes = [int64]((& cmd /c "`"$adb`" shell blockdev --getsize64 $dev 2>NUL").Trim())
$blocks = [int64]($bytes / 4096)
$tail = 1025
$skip = $blocks - $tail
$bin = [System.IO.Path]::GetTempFileName()
& cmd /c "`"$adb`" exec-out dd if=$dev bs=4096 skip=$skip count=$tail 2>NUL > `"$bin`""
Log "read $((Get-Item $bin).Length) bytes from $dev (block $skip)"

$sbin = [System.IO.Path]::GetTempFileName()
& cmd /c "`"$adb`" exec-out dd if=$dev bs=4096 skip=$($skip - 32) count=32 2>NUL > `"$sbin`""
$sraw = [System.IO.File]::ReadAllBytes($sbin)
Remove-Item $sbin
if ($Out -and $sraw.Length -ge 8192 -and [BitConverter]::ToUInt32($sraw, 0) -eq 0x52505753) {
	$slen = [BitConverter]::ToUInt32($sraw, 12)
	$stext = [System.Text.Encoding]::ASCII.GetString($sraw, 4096, [Math]::Min($slen, $sraw.Length - 4096))
	Set-Content -Path "$Out.shim.txt" -Value $stext -Encoding ascii
	Log "shim log saved $Out.shim.txt"
}

& cmd /c "`"$adb`" reboot bootloader 2>NUL" | Out-Null
Log "sent adb reboot bootloader"

$wbin = (& wsl -d Ubuntu -- wslpath -a ($bin -replace '\\', '/')).Trim()
$txt = if ($Out) { $Out } else { [System.IO.Path]::GetTempFileName() }
$dir = Split-Path $txt -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
$wtxt = (& wsl -d Ubuntu -- wslpath -a ((Resolve-Path -LiteralPath $dir).Path -replace '\\', '/')).Trim() + "/" + (Split-Path $txt -Leaf)
$wtool = (& wsl -d Ubuntu -- wslpath -a ("$PSScriptRoot\sweet-log.py" -replace '\\', '/')).Trim()
& wsl -d Ubuntu -- python3 -I $wtool $wbin $wtxt
Remove-Item $bin
Log "XNU ring saved to $txt"
Get-Content $txt -Tail 8
