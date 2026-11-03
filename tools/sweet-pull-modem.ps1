param(
	[string]$Tools = "$PSScriptRoot\..\..\tools-win\platform-tools",
	[string]$Recovery = "$PSScriptRoot\..\recovery\recovery.img",
	[string]$OutDir = "$PSScriptRoot\..\.tmp-hfsplus\firmware",
	[int]$AdbSeconds = 300
)
$ErrorActionPreference = "Continue"
$adb = Join-Path $Tools "adb.exe"
$fb = Join-Path $Tools "fastboot.exe"
function Log($m) { Write-Host ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $m) }
function AdbWait() {
	for ($i = 0; $i -lt 60; $i++) {
		$s = & $adb get-state 2>$null
		if ($s -match "recovery|device|sideload") { return $true }
		Start-Sleep -Seconds 2
	}
	return $false
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Log "booting recovery"
& $fb boot $Recovery 2>&1 | Out-Host
if (-not (AdbWait)) { throw "adb did not come up" }
Log "adb up"
# OrangeFox: adb is up before ueventd/by-name; wait for the links and the UI settle.
Start-Sleep -Seconds 15
$dev = $null
for ($i = 0; $i -lt 60; $i++) {
	$lines = & $adb shell "ls /dev/block/by-name" 2>$null
	$d = (& $adb shell "readlink -f /dev/block/by-name/modem" 2>$null)
	if ($lines -and $lines.Count -gt 20 -and $d -match '^/dev/block/sd') { $dev = $d.Trim(); break }
	Start-Sleep -Seconds 2
}
if (-not $dev) { throw "by-name/modem not ready" }
Log "modem device $dev"
& $adb shell "mkdir -p /mnt/modem; mount -t vfat -o ro $dev /mnt/modem" 2>&1 | Out-Host
$img = $null
for ($i = 0; $i -lt 15; $i++) {
	$img = & $adb shell "ls /mnt/modem/image" 2>$null
	if ($img -and $img.Count -gt 10) { break }
	Start-Sleep -Seconds 2
}
Log "modem image files: $(if ($img) { $img.Count } else { 0 })"
$tools = & $adb shell "command -v tar; command -v gzip; command -v dd" 2>$null
Log "tools: $($tools -join ' ')"

$wanted = @(
	@{name='modemst1'; file='modemst1.img'},
	@{name='modemst2'; file='modemst2.img'},
	@{name='fsg';     file='fsg.img'},
	@{name='fsc';     file='fsc.img'}
)
foreach ($p in $wanted) {
	$d = (& $adb shell "readlink -f /dev/block/by-name/$($p.name)" 2>$null)
	if (-not $d -or $d -notmatch '^/dev/block/sd') { Log "SKIP $($p.name) ($d)"; continue }
	$remote = "/tmp/$($p.name).img"
	Log "dd $($p.name) $d"
	& $adb shell "dd if=$d of=$remote bs=1M" 2>&1 | Out-Host
	$out = Join-Path $OutDir $p.file
	& $adb pull $remote $out 2>&1 | Out-Host
	if (Test-Path $out) { Log "  $($p.name) $((Get-Item $out).Length) bytes" }
	& $adb shell "rm -f $remote" 2>$null | Out-Null
}

Log "tar/gzip Wi-Fi/modem firmware"
& $adb shell "cd /mnt/modem/image && tar cf - modem.* wlanmdsp.mbn bdwlan.* *.jsn modem_pr 2>/dev/null | gzip -1 > /tmp/wifi.tgz" 2>&1 | Out-Host
$sz = (& $adb shell "stat -c %s /tmp/wifi.tgz" 2>$null)
if (-not $sz) { $sz = (& $adb shell "wc -c < /tmp/wifi.tgz" 2>$null) }
$sz = ([string]$sz).Trim()
Log "wifi.tgz $sz bytes"
if ($sz -match '^\d+$' -and [int64]$sz -gt 0) {
	$n = [math]::Ceiling([int64]$sz / (8MB))
	$parts = @()
	for ($i=0; $i -lt $n; $i++) {
		$part = "/tmp/wifi.part$i"
		& $adb shell "dd if=/tmp/wifi.tgz of=$part bs=1M skip=$($i*8) count=8" 2>$null | Out-Null
		$local = Join-Path $OutDir ("wifi.part{0}" -f $i)
		$got = $false
		for ($try=0; $try -lt 3 -and -not $got; $try++) {
			if (Test-Path $local) { Remove-Item -Force $local }
			& $adb pull $part $local 2>&1 | Out-Host
			if (Test-Path $local) {
				$want = [Math]::Min(8MB, [int64]$sz - $i*8MB)
				if ((Get-Item $local).Length -eq $want) { $got = $true }
			}
			if (-not $got) { Start-Sleep -Seconds 2; if (-not (AdbWait)) { Log "adb lost at part $i"; break } }
		}
		if ($got) { $parts += $local; Log "  part $i $((Get-Item $local).Length) bytes" }
		& $adb shell "rm -f $part" 2>$null | Out-Null
	}
	if ($parts.Count -gt 0) {
		$tgz = Join-Path $OutDir "wifi.tgz"
		if (Test-Path $tgz) { Remove-Item -Force $tgz }
		$fs = [System.IO.File]::Open($tgz, 'Create')
		foreach ($p in $parts) { $b = [System.IO.File]::ReadAllBytes($p); $fs.Write($b,0,$b.Length) }
		$fs.Close()
		Log "wifi.tgz host $((Get-Item $tgz).Length) bytes"
	}
}
& $adb shell "rm -f /tmp/wifi.tgz" 2>$null | Out-Null
& $adb reboot bootloader 2>$null | Out-Null
Log "sent adb reboot bootloader"
