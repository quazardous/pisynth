<#
.SYNOPSIS
    install.ps1 — the Windows counterpart of deploy.sh. Run from this repo folder:

        powershell -ExecutionPolicy Bypass -File .\install.ps1

    Pushes this repo to the Pi and applies migrations + app sync over SSH (asks the
    Pi's sudo password once). Same outcome as `./deploy.sh`, for Windows users who have
    no bash / WSL.

.DESCRIPTION
    Starting point (see docs/install.md): a Pi running Raspberry Pi OS, reachable over
    the network, that accepts your SSH key. This script needs only the tools that ship
    with Windows 10/11: the OpenSSH client (ssh, scp), tar (bsdtar) and robocopy.

    Transfer mechanism:
      * Default — stage with robocopy (excludes .git etc.), pack with tar, scp the
        archive to the Pi, extract it into ~/pisynth. Overlay copy (no remote delete),
        which is what an install wants.
      * -UseRsync — if you have rsync on PATH (Git-for-Windows, scoop, WSL), use it
        with the same flags as deploy.sh (-az --delete). Closest parity, but rsync's
        Windows path handling is finicky, so it is opt-in.

    The Pi target is resolved like deploy.sh: -PiHost arg > $env:PISYNTH_HOST >
    pisynth.conf > pisynth.conf.dist > pi@raspberrypi.local.

.PARAMETER PiHost
    SSH target user@host. Overrides pisynth.conf / the env var.

.PARAMETER UseRsync
    Use rsync instead of the built-in tar+scp transfer (requires rsync on PATH).

.PARAMETER NoApply
    Push the files but skip `sudo apply.sh` (rarely needed; deploy.sh always applies).
#>
[CmdletBinding()]
param(
    [string]$PiHost,
    [switch]$UseRsync,
    [switch]$NoApply
)

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$log  = Join-Path $repo 'deploy.log'

function Write-Log($msg) {
    Write-Host $msg
    Add-Content -Path $log -Value $msg
}

function Get-ConfValue($file, $key) {
    if (-not (Test-Path $file)) { return $null }
    foreach ($line in Get-Content $file) {
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        if ($t -match "^\s*$key\s*=\s*(.+?)\s*$") {
            return $matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Require-Tool($name, $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "'$name' not found. $hint"
    }
}

# --- preflight ----------------------------------------------------------------
Require-Tool 'ssh' 'Install the OpenSSH client: Settings > Apps > Optional Features > OpenSSH Client.'
Require-Tool 'scp' 'Install the OpenSSH client: Settings > Apps > Optional Features > OpenSSH Client.'
Require-Tool 'tar' 'Windows 10 1803+ ships tar. Update Windows or install bsdtar.'

# --- resolve the Pi target (mirrors deploy.sh) --------------------------------
$pi = $PiHost
if (-not $pi) { $pi = $env:PISYNTH_HOST }
if (-not $pi) { $pi = Get-ConfValue (Join-Path $repo 'pisynth.conf')      'PISYNTH_HOST' }
if (-not $pi) { $pi = Get-ConfValue (Join-Path $repo 'pisynth.conf.dist') 'PISYNTH_HOST' }
if (-not $pi) { $pi = 'pi@raspberrypi.local' }

Write-Log ''
Write-Log "===== install $(Get-Date -Format o)  ->  $pi ====="

# --- transfer -----------------------------------------------------------------
if ($UseRsync) {
    Require-Tool 'rsync' 'rsync not on PATH. Drop -UseRsync to use the built-in tar+scp transfer.'
    Write-Log "-> rsync  $repo/  ->  ${pi}:~/pisynth/"
    # rsync from MSYS/Cygwin wants forward slashes; pass the repo as-is and let it cope.
    & rsync -az --delete `
        --exclude '.git' --exclude '*.bak' --exclude 'deploy.log' --exclude 'last-shot.png' `
        "$repo/" "${pi}:pisynth/"
    if ($LASTEXITCODE -ne 0) { throw "rsync failed (exit $LASTEXITCODE)" }
}
else {
    $stage = Join-Path $env:TEMP "pisynth-stage-$([System.Guid]::NewGuid().ToString('N'))"
    $tgz   = Join-Path $env:TEMP "pisynth-$([System.Guid]::NewGuid().ToString('N')).tgz"
    try {
        Write-Log "-> stage (robocopy, excluding .git/*.bak/logs)  ->  $stage"
        # robocopy returns 0-7 on success, >=8 on real errors.
        & robocopy $repo $stage /MIR /XD '.git' /XF '*.bak' 'deploy.log' 'last-shot.png' `
            /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed (exit $LASTEXITCODE)" }

        Write-Log "-> pack (tar)  ->  $tgz"
        & tar -czf $tgz -C $stage .
        if ($LASTEXITCODE -ne 0) { throw "tar failed (exit $LASTEXITCODE)" }

        Write-Log "-> scp archive  ->  ${pi}:/tmp/"
        & scp $tgz "${pi}:/tmp/pisynth-install.tgz"
        if ($LASTEXITCODE -ne 0) { throw "scp failed (exit $LASTEXITCODE)" }

        Write-Log "-> extract into ~/pisynth on $pi"
        & ssh $pi 'mkdir -p ~/pisynth && tar xzf /tmp/pisynth-install.tgz -C ~/pisynth && rm -f /tmp/pisynth-install.tgz'
        if ($LASTEXITCODE -ne 0) { throw "remote extract failed (exit $LASTEXITCODE)" }
    }
    finally {
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $stage, $tgz
    }
}

# --- apply (migrations + sync), interactive sudo password ----------------------
if (-not $NoApply) {
    Write-Log "-> apply migrations + sync on $pi (sudo)"
    & ssh -t $pi 'sudo bash ~/pisynth/apply.sh'
    if ($LASTEXITCODE -ne 0) { throw "apply.sh failed (exit $LASTEXITCODE)" }
}

Write-Log "===== end $(Get-Date -Format o)  rc=0 ====="
