# Unattended shim probe run on Windows: boot a probe image, let it save its log
# to the userdata scratch area (shim/plog.c) and return to fastboot by itself,
# then boot OrangeFox temporarily, read the log with adb and go back to
# fastboot. Nothing is flashed.
#
#   tools\sweet-probe-loop.ps1 -Image shim\out\shim-gpuprobe3a.img [-Out logs\probe.txt]
#
# Needs: platform-tools (fastboot.exe/adb.exe), recovery\recovery.img (OrangeFox
# R12.0_2 for sweet, not in git), the phone in fastboot on USB.
param(
	[Parameter(Mandatory = $true)][string]$Image,
	[string]$Out = "",
	[string]$Tools = "$PSScriptRoot\..\..\tools-win\platform-tools",
	[string]$Recovery = "$PSScriptRoot\..\recovery\recovery.img",
	[int]$ProbeSeconds = 150
)
$ErrorActionPreference = "Stop"
$fastboot = Join-Path $Tools "fastboot.exe"
$adb = Join-Path $Tools "adb.exe"
$PLOG_BLOCKS = 32
$XNU_LOG_TAIL = 1025

function Log($m) { Write-Host ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $m) }

function Wait-Fastboot([int]$secs) {
	$end = (Get-Date).AddSeconds($secs)
	while ((Get-Date) -lt $end) {
		$d = & $fastboot devices 2>$null
		if ($d -match "fastboot") { return $true }
		Start-Sleep -Seconds 2
	}
	return $false
}

# fastboot boot with a timeout: Xiaomi's ABL sometimes hangs at "Sending".
function Boot-Image([string]$img) {
	$j = Start-Job { param($f, $i) & $f boot $i 2>&1 } -ArgumentList $fastboot, (Resolve-Path $img).Path
	if (Wait-Job $j -Timeout 60) {
		$r = Receive-Job $j
		Log ($r -join " | ")
		return ($r -join " ") -match "Booting\s+OKAY"
	}
	Stop-Job $j
	Get-Process fastboot -ErrorAction SilentlyContinue | Stop-Process -Force
	Log "fastboot boot timed out (ABL hung): re-enter fastboot by hand (Power + Vol-)"
	return $false
}

if (-not (Wait-Fastboot 5)) { throw "no device in fastboot" }
Log "booting probe $Image"
if (-not (Boot-Image $Image)) { throw "probe boot failed" }
Start-Sleep -Seconds 10
Log "waiting up to $ProbeSeconds s for the probe to return to fastboot"
if (-not (Wait-Fastboot $ProbeSeconds)) { throw "phone did not come back to fastboot (hung without watchdog reset?)" }

Log "booting OrangeFox to read the log"
if (-not (Boot-Image $Recovery)) { throw "recovery boot failed" }
$end = (Get-Date).AddSeconds(120)
$ok = $false
while ((Get-Date) -lt $end) {
	$s = & $adb get-state 2>$null
	if ($s -match "recovery|device") { $ok = $true; break }
	Start-Sleep -Seconds 2
}
if (-not $ok) { throw "adb did not come up in recovery" }
# Run 3a: adb answers before ueventd has made the by-name links.
$dev = $null
for ($i = 0; $i -lt 30 -and -not $dev; $i++) {
	Start-Sleep -Seconds 2
	$r = & $adb shell "readlink -f /dev/block/by-name/userdata 2>/dev/null" 2>$null
	if ($r -and $r.Trim() -match "^/dev/block/sd") { $dev = $r.Trim() }
}
if (-not $dev) { throw "userdata block device not found in recovery" }
$bytes = [int64](& $adb shell "blockdev --getsize64 $dev").Trim()
$blocks = [int64]($bytes / 4096)
$skip = $blocks - $XNU_LOG_TAIL - $PLOG_BLOCKS
Log "userdata $dev, $blocks blocks, scratch at block $skip"
$tmp = [System.IO.Path]::GetTempFileName()
& cmd /c "`"$adb`" exec-out dd if=$dev bs=4096 skip=$skip count=$PLOG_BLOCKS 2>NUL > `"$tmp`""
$raw = [System.IO.File]::ReadAllBytes($tmp)
Remove-Item $tmp

& $adb reboot bootloader | Out-Null
Log "sent adb reboot bootloader"

if ($raw.Length -lt 8192) { throw "short read ($($raw.Length) bytes)" }
$m0 = [BitConverter]::ToUInt32($raw, 0); $m1 = [BitConverter]::ToUInt32($raw, 4)
if ($m0 -ne 0x52505753 -or $m1 -ne 0x3145424f) { throw "no probe log in the scratch area (magic $('{0:x8}' -f $m0))" }
$seq = [BitConverter]::ToUInt32($raw, 8)
$len = [BitConverter]::ToUInt32($raw, 12)
$why = [System.Text.Encoding]::ASCII.GetString($raw, 16, 256).TrimEnd([char]0)
$text = [System.Text.Encoding]::ASCII.GetString($raw, 4096, [Math]::Min($len, $raw.Length - 4096))
$report = "probe log: save #$seq, last step '$why', $len bytes`n$text"
Write-Host $report
if ($Out) { Set-Content -Path $Out -Value $report -Encoding ascii; Log "saved $Out" }
if (-not (Wait-Fastboot 90)) { Log "warning: phone not back in fastboot yet" }
