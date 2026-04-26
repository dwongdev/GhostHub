# GhostHub Deployment Script for Windows
# Uploads local folder to Pi via SSH and runs install script
# Usage: .\deploy_to_pi.ps1 [-PiHost <hostname>] [-PiUser <user>] [-KeyFile <path>] [-TargetDir <path>]
#
# Examples:
#   .\deploy_to_pi.ps1                         # Normal deployment
#   .\deploy_to_pi.ps1 -Update                 # Local update, preserve runtime state
#   .\deploy_to_pi.ps1 -Golden                 # Fresh local install + image prep
#   .\deploy_to_pi.ps1 -PiHost 192.168.1.100 -PiUser myuser  # Custom host/user
#   .\deploy_to_pi.ps1 -SkipUpload             # Skip upload, just run install
#   .\deploy_to_pi.ps1 -FullInstall            # Force full system reconfiguration
#
# Local deploy mode:
#   - Uses /tmp/ghosthub_deploy.zip uploaded by this script
#   - Never downloads Ghosthub_pi_github.zip from GitHub Releases
#   - Still installs system dependencies and configures GhostHub
#
# Image prep mode:
#   - Performs a full local zip install
#   - Stops GhostHub service cleanly
#   - Clears the instance/ folder (db, config, auth - all runtime state)
#   - Removes deployment temp files
#   - Prints a "ready for SD image capture" confirmation
#   - Shuts down the Pi (NOT reboot) so you can pull the SD card safely

param(
    [string]$PiHost = "ghosthub.local",
    [string]$PiUser = "ghost",
    [string]$KeyFile = "",
    [string]$TargetDir = "/home/ghost/ghosthub",
    [string]$Password = "",
    [switch]$SkipUpload,
    [switch]$FullInstall,
    [switch]$LocalOnly,
    [switch]$Update,
    [switch]$Golden
)

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Status { param($msg) Write-Host "[*] $msg" -ForegroundColor Cyan }
function Write-Success { param($msg) Write-Host "[+] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host "[X] $msg" -ForegroundColor Red }
function Find-Python39 {
    $candidates = @("python3.9", "py -3.9", "python", "python3")
    foreach ($candidate in $candidates) {
        try {
            if ($candidate -eq "py -3.9") {
                $version = & py -3.9 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                if ($LASTEXITCODE -eq 0 -and $version -eq "3.9") { return "py -3.9" }
            } else {
                $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
                if ($cmd) {
                    $version = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
                    if ($LASTEXITCODE -eq 0 -and $version -eq "3.9") { return $candidate }
                }
            }
        } catch {
            continue
        }
    }
    return $null
}
function Invoke-Python39 {
    param(
        [string]$Python39,
        [string[]]$Arguments
    )
    if ($Python39 -eq "py -3.9") {
        & py -3.9 @Arguments
    } else {
        & $Python39 @Arguments
    }
}
function Write-Python39Help {
    Write-Host ""
    Write-Err "Python 3.9 was not found."
    Write-Host ""
    Write-Host "Install Python 3.9, then rerun this deploy script."
    Write-Host ""
    Write-Host "Windows:" -ForegroundColor Cyan
    Write-Host "  Install Python 3.9 from https://www.python.org/downloads/release/python-3913/"
    Write-Host "  Or install with winget if available:"
    Write-Host "  winget install Python.Python.3.9" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "macOS with Homebrew:" -ForegroundColor Cyan
    Write-Host "  brew install python@3.9" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Ubuntu/Debian:" -ForegroundColor Cyan
    Write-Host "  sudo apt update"
    Write-Host "  sudo apt install python3.9 python3.9-venv python3.9-dev" -ForegroundColor Yellow
    Write-Host ""
}
function Ensure-LocalBuildEnv {
    Write-Host ""
    Write-Host "--- LOCAL BUILD ENVIRONMENT ---" -ForegroundColor Cyan

    $Python39 = Find-Python39
    if (-not $Python39) {
        Write-Python39Help
        exit 1
    }
    Write-Status "Using Python 3.9: $Python39"

    $script:LocalPython = Join-Path $ProjectDir "venv\Scripts\python.exe"
    if (-not (Test-Path $script:LocalPython)) {
        $script:LocalPython = Join-Path $ProjectDir "venv\bin\python"
    }

    if (-not (Test-Path $script:LocalPython)) {
        Write-Status "Creating virtualenv..."
        Invoke-Python39 -Python39 $Python39 -Arguments @("-m", "venv", (Join-Path $ProjectDir "venv"))
        $script:LocalPython = Join-Path $ProjectDir "venv\Scripts\python.exe"
        if (-not (Test-Path $script:LocalPython)) {
            $script:LocalPython = Join-Path $ProjectDir "venv\bin\python"
        }
    }

    if (-not (Test-Path $script:LocalPython)) {
        Write-Err "Virtualenv was not created correctly."
        exit 1
    }

    Write-Status "Installing Python dependencies..."
    & $script:LocalPython -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $script:LocalPython -m pip install -r (Join-Path $ProjectDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npmCmd) {
        Write-Err "npm was not found. Install Node.js/npm, then rerun this deploy script."
        Write-Warn "Recommended: install the current Node.js LTS from https://nodejs.org/"
        exit 1
    }

    $NodeModules = Join-Path $ProjectDir "static\js\node_modules"
    $VitestBin = Join-Path $ProjectDir "static\js\node_modules\.bin\vitest"
    $VitestCmd = Join-Path $ProjectDir "static\js\node_modules\.bin\vitest.cmd"
    if (-not (Test-Path $NodeModules) -or ((-not (Test-Path $VitestBin)) -and (-not (Test-Path $VitestCmd)))) {
        Write-Status "Installing JavaScript dependencies..."
        Push-Location (Join-Path $ProjectDir "static\js")
        try {
            npm install
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        } finally {
            Pop-Location
        }
    } else {
        Write-Status "JavaScript dependencies already installed."
    }
}
function Write-FreshPiHelp {
    Write-Host ""
    Write-Host "Fresh Raspberry Pi OS Lite setup expected by this deploy script:" -ForegroundColor Cyan
    Write-Host "  Image:    2022-01-28-raspios-bullseye-armhf-lite"
    Write-Host "  Tool:     Raspberry Pi Imager v1.8.5"
    Write-Host "  Hostname: ghosthub"
    Write-Host "  Username: ghost"
    Write-Host "  SSH:      enabled"
    Write-Host ""
    Write-Host "In Raspberry Pi Imager v1.8.5, open advanced options before writing the card,"
    Write-Host "set hostname to ghosthub, create the ghost user, enable SSH, and set a password."
    Write-Host "Then boot the Pi and try:"
    Write-Host "  ssh ghost@ghosthub.local" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If mDNS is not resolving, use the Pi IP address:"
    Write-Host "  .\scripts\deploy_to_pi.ps1 -PiHost <pi-ip-address>" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If SSH reports a host key warning after reflashing the Pi, clear the old key:"
    Write-Host "  ssh-keygen -R ghosthub.local" -ForegroundColor Yellow
    Write-Host "  ssh-keygen -R <pi-ip-address>" -ForegroundColor Yellow
    Write-Host ""
}

# Interactive menu when no parameters are provided, matching deploy_to_pi.sh.
if ($PSBoundParameters.Count -eq 0) {
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Magenta
    Write-Host "  GhostHub Deployment v3.0" -ForegroundColor Magenta
    Write-Host "======================================" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "TARGET: $PiUser@$PiHost`:$TargetDir" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "CHOOSE DEPLOYMENT MODE:" -ForegroundColor Cyan
    Write-Host "  [1] Standard   (Fresh local install from this repo)"
    Write-Host "  [2] Update     (Local update, preserve /instance and /venv)"
    Write-Host "  [3] Image Prep (Fresh local install + clear state + power off)"
    Write-Host "  [4] Abort"
    Write-Host ""

    $choice = Read-Host "Selection [1]"
    if ([string]::IsNullOrWhiteSpace($choice)) { $choice = "1" }

    switch ($choice) {
        "1" { }
        "2" { $Update = $true }
        "3" { $Golden = $true }
        "4" { exit 0 }
        default {
            Write-Err "Invalid selection"
            exit 1
        }
    }
}

# deploy_to_pi is a local-source deploy tool. It always installs from the zip it
# builds and uploads to /tmp; GitHub Releases are used by the public installer
# and admin update flow.
$LocalOnly = $true

Write-Host ""
Write-Host "======================================" -ForegroundColor Magenta
if ($Golden) {
    Write-Host "  GhostHub Image Prep Builder" -ForegroundColor Magenta
    Write-Host "  (Fresh Local Install + Image Prep)" -ForegroundColor Gray
} elseif ($LocalOnly) {
    Write-Host "  GhostHub Local Setup Script" -ForegroundColor Magenta
    Write-Host "  (Local Source Deploy)" -ForegroundColor Gray
} else {
    Write-Host "  GhostHub Local Deployment Script" -ForegroundColor Magenta
}
Write-Host "======================================" -ForegroundColor Magenta
Write-Host ""

# Get script directory (where this script is located)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Project directory is the parent of scripts folder
$ProjectDir = Split-Path -Parent $ScriptDir

Write-Status "Project directory: $ProjectDir"
Write-Status "Target: $PiUser@$PiHost`:$TargetDir"
if ($Golden) {
    Write-Status "Mode: Image Prep (local zip install + instance clear + shutdown)"
} elseif ($LocalOnly) {
    Write-Status "Mode: Local source deploy"
}

# Prompt for password if not using key file and password not provided
if (-not $KeyFile -and -not $Password) {
    $SecurePassword = Read-Host "Enter Pi password" -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
    $Password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    Write-Status "Password saved for this session"
}

# Automatically build the production package (Ghostpack)
if (-not $SkipUpload) {
    Ensure-LocalBuildEnv
    Write-Status "Building fresh Ghostpack production package..."
    & $script:LocalPython "$ProjectDir\scripts\ghostpack.py" --zip
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Ghostpack build failed! Aborting deployment."
        exit 1
    }
    Write-Success "Ghostpack build successful"
}

# Check if we should use PuTTY tools (plink/pscp) for password auth
$UsePutty = $false
$PlinkExe = $null
$PscpExe = $null

if ($Password -and -not $KeyFile) {
    # Try to find plink/pscp in PATH first
    $plinkCmd = Get-Command plink -ErrorAction SilentlyContinue
    $pscpCmd = Get-Command pscp -ErrorAction SilentlyContinue
    
    if ($plinkCmd -and $pscpCmd) {
        $PlinkExe = "plink"
        $PscpExe = "pscp"
        $UsePutty = $true
    } else {
        # Check common installation paths
        $puttyPaths = @(
            "C:\Program Files\PuTTY",
            "C:\Program Files (x86)\PuTTY",
            "$env:LOCALAPPDATA\Programs\PuTTY",
            "$env:ProgramFiles\PuTTY",
            "${env:ProgramFiles(x86)}\PuTTY"
        )
        
        foreach ($path in $puttyPaths) {
            $plinkPath = Join-Path $path "plink.exe"
            $pscpPath = Join-Path $path "pscp.exe"
            if ((Test-Path $plinkPath) -and (Test-Path $pscpPath)) {
                $PlinkExe = $plinkPath
                $PscpExe = $pscpPath
                $UsePutty = $true
                Write-Status "Found PuTTY at: $path"
                break
            }
        }
    }
    
    if ($UsePutty) {
        Write-Status "Using PuTTY tools for password authentication"
    } else {
        Write-Warn "PuTTY tools not found - you'll need to enter password multiple times"
        Write-Warn "Install from: https://www.putty.org/"
        Write-Warn "Or restart PowerShell if you just installed it"
    }
}

# Build SSH/SCP options
$SshOpts = @("-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10")
if ($KeyFile -and (Test-Path $KeyFile)) {
    $SshOpts += @("-i", $KeyFile)
    Write-Status "Using SSH key: $KeyFile"
}

# Test SSH connection
Write-Status "Testing SSH connection..."
try {
    if ($UsePutty) {
        # First, accept the host key (plink will prompt otherwise)
        echo y | & $PlinkExe -pw $Password "$PiUser@$PiHost" "exit" 2>&1 | Out-Null
        # Now test the connection
        $result = & $PlinkExe -batch -pw $Password "$PiUser@$PiHost" "echo connected" 2>&1 | Select-Object -Last 1
    } else {
        $result = & ssh @SshOpts "$PiUser@$PiHost" "echo 'connected'" 2>&1
    }
    if ($result -notmatch "connected") {
        throw "SSH connection failed"
    }
    Write-Success "SSH connection successful"
} catch {
    Write-Err "Cannot connect to Pi at $PiHost"
    Write-FreshPiHelp
    Write-Warn "Make sure:"
    Write-Warn "  1. Pi is powered on and connected"
    Write-Warn "  2. You're on the GhostHub WiFi network (or Pi's network)"
    Write-Warn "  3. SSH is enabled on the Pi"
    Write-Warn "  4. Credentials are correct (default: ghost@192.168.4.1)"
    exit 1
}

if (-not $SkipUpload) {
    # Choose newest zip artifact to avoid uploading stale builds.
    $DistZipPath = Join-Path $ProjectDir "dist/Ghosthub_pi_github.zip"
    $RootZipPath = Join-Path $ProjectDir "Ghosthub_pi_github.zip"
    $ZipPath = $null
    
    if ((Test-Path $DistZipPath) -and (Test-Path $RootZipPath)) {
        $distZip = Get-Item $DistZipPath
        $rootZip = Get-Item $RootZipPath
        $ZipPath = if ($distZip.LastWriteTime -ge $rootZip.LastWriteTime) { $DistZipPath } else { $RootZipPath }
    } elseif (Test-Path $DistZipPath) {
        $ZipPath = $DistZipPath
    } elseif (Test-Path $RootZipPath) {
        $ZipPath = $RootZipPath
    } else {
        Write-Err "Zip file not found in either location:"
        Write-Err "  $DistZipPath"
        Write-Err "  $RootZipPath"
        Write-Err "Please run ghostpack.py first to create the production package:"
        Write-Err "  .\venv\Scripts\python.exe scripts\ghostpack.py --zip"
        exit 1
    }
    Write-Status "Using zip artifact: $ZipPath"
    
    $ZipSize = [math]::Round((Get-Item $ZipPath).Length / 1MB, 2)
    Write-Success "Using existing production package: $ZipSize MB"
    
    # Upload zip to Pi
    Write-Status "Uploading to Pi (this may take a minute)..."
    $RemoteZip = "/tmp/ghosthub_deploy.zip"
    
    try {
        if ($UsePutty) {
            & $PscpExe -batch -pw $Password $ZipPath "$PiUser@$PiHost`:$RemoteZip"
        } else {
            & scp @SshOpts $ZipPath "$PiUser@$PiHost`:$RemoteZip"
        }
        Write-Success "Upload complete"
    } catch {
        Write-Err "Upload failed: $_"
        exit 1
    }
    
    # Extract on Pi and run install
    Write-Status "Extracting files on Pi..."
    
    if ($Update) {
        # Update mode - preserve instance and venv
        Write-Status "Update mode - preserving instance and venv folders"
        $ExtractCmd = "set -e && sudo mkdir -p $TargetDir && sudo chown -R ghost:ghost $TargetDir && cd $TargetDir && if [ -d instance ]; then sudo rm -rf /tmp/ghosthub_instance_backup && sudo mkdir -p /tmp/ghosthub_instance_backup && sudo chown -R ghost:ghost /tmp/ghosthub_instance_backup && sudo -u ghost cp -r instance/* /tmp/ghosthub_instance_backup/ 2>/dev/null || true; fi && if [ -d venv ]; then sudo rm -rf /tmp/ghosthub_venv_backup && sudo mkdir -p /tmp/ghosthub_venv_backup && sudo chown -R ghost:ghost /tmp/ghosthub_venv_backup && sudo -u ghost cp -r venv/* /tmp/ghosthub_venv_backup/ 2>/dev/null || true; fi && find . -maxdepth 1 -not -name 'instance' -not -name 'venv' -not -name '.requirements_hash' -not -name 'cloudflared' -not -name 'headscale' -not -name '.headscale_version' -not -name '.install_complete' -not -name '.' -exec rm -rf {} + 2>/dev/null && unzip -o $RemoteZip -d . && if [ -d Ghosthub_pi_github ]; then rm -rf Ghosthub_pi_github/instance Ghosthub_pi_github/venv; shopt -s dotglob nullglob; for path in Ghosthub_pi_github/*; do mv ""$path"" .; done; shopt -u dotglob nullglob; rm -rf Ghosthub_pi_github; fi && if [ -d /tmp/ghosthub_instance_backup ]; then sudo mkdir -p instance && sudo chown ghost:ghost instance && sudo -u ghost cp -r /tmp/ghosthub_instance_backup/* instance/ 2>/dev/null || true && rm -rf /tmp/ghosthub_instance_backup; fi && if [ -d /tmp/ghosthub_venv_backup ]; then sudo mkdir -p venv && sudo chown ghost:ghost venv && sudo -u ghost cp -r /tmp/ghosthub_venv_backup/* venv/ 2>/dev/null || true && rm -rf /tmp/ghosthub_venv_backup; fi && chmod +x install_ghosthub.sh && echo '[+] Done - checking files:' && ls -la main.py install_ghosthub.sh"
    } else {
        # Clean deployment for master image creation - no backups
        Write-Status "Clean install mode - deleting existing installation"
        $ExtractCmd = "set -e && sudo rm -rf $TargetDir && sudo mkdir -p $TargetDir && sudo chown -R ghost:ghost $TargetDir && cd $TargetDir && unzip -o $RemoteZip -d . && if [ -d Ghosthub_pi_github ]; then mv Ghosthub_pi_github/* . && rm -rf Ghosthub_pi_github; fi && chmod +x install_ghosthub.sh && echo '[+] Done - checking files:' && ls -la main.py install_ghosthub.sh"
    }
    
    if ($UsePutty) {
        & $PlinkExe -batch -pw $Password "$PiUser@$PiHost" $ExtractCmd
    } else {
        & ssh @SshOpts "$PiUser@$PiHost" $ExtractCmd
    }
    Write-Success "Files extracted to $TargetDir"
}

# Run the install script
Write-Status "Running install script..."
Write-Host ""

$InstallFlags = "--no-self-update"
if ($LocalOnly) {
    $InstallFlags += " --local-only"
    Write-Status "Local zip mode"
}
if ($Update) {
    $InstallFlags += " --update"
} elseif ($FullInstall) {
    $InstallFlags += " --full-install"
    Write-Warn "Full install mode - this will reconfigure system settings"
}

$InstallCmd = "cd $TargetDir && sudo bash install_ghosthub.sh $InstallFlags"

Write-Host "----------------------------------------" -ForegroundColor DarkGray
if ($UsePutty) {
    & $PlinkExe -batch -pw $Password -t "$PiUser@$PiHost" $InstallCmd
} else {
    & ssh @SshOpts -t "$PiUser@$PiHost" $InstallCmd
}
$ExitCode = $LASTEXITCODE
Write-Host "----------------------------------------" -ForegroundColor DarkGray

Write-Host ""
if ($ExitCode -eq 0) {
    Write-Success "Deployment completed successfully!"
    Write-Host ""

    if ($Golden) {
        # ---- Golden image preparation ----
        Write-Host "========================================" -ForegroundColor Magenta
        Write-Host "  IMAGE PREP" -ForegroundColor Magenta
        Write-Host "========================================" -ForegroundColor Magenta
        Write-Host ""

        Write-Status "Stopping GhostHub service..."
        $StopCmd = "sudo systemctl stop ghosthub ghosthub-kiosk 2>/dev/null || true && sudo pkill -9 gunicorn 2>/dev/null || true && echo '[+] Services stopped'"
        if ($UsePutty) {
            & $PlinkExe -batch -pw $Password "$PiUser@$PiHost" $StopCmd
        } else {
            & ssh @SshOpts "$PiUser@$PiHost" $StopCmd
        }

        Write-Status "Clearing instance folder (runtime state)..."
        $ClearCmd = "sudo rm -rf $TargetDir/instance/* $TargetDir/instance/.* 2>/dev/null || true && echo '[+] Instance folder cleared'"
        if ($UsePutty) {
            & $PlinkExe -batch -pw $Password "$PiUser@$PiHost" $ClearCmd
        } else {
            & ssh @SshOpts "$PiUser@$PiHost" $ClearCmd
        }

        Write-Status "Removing deployment temp files..."
        $CleanCmd = "rm -f /tmp/ghosthub_deploy.zip && sudo journalctl --rotate --vacuum-time=1s 2>/dev/null || true && echo '[+] Temp files cleaned'"
        if ($UsePutty) {
            & $PlinkExe -batch -pw $Password "$PiUser@$PiHost" $CleanCmd
        } else {
            & ssh @SshOpts "$PiUser@$PiHost" $CleanCmd
        }

        Write-Host ""
        Write-Host "  ============================================" -ForegroundColor Green
        Write-Host "   GHOSTHUB IS READY FOR SD IMAGE CAPTURE" -ForegroundColor Green
        Write-Host "  ============================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "  The Pi is shutting down now." -ForegroundColor White
        Write-Host "  Wait for the green activity LED to stop," -ForegroundColor Gray
        Write-Host "  then unplug power and pull the SD card." -ForegroundColor Gray
        Write-Host ""

        # Shutdown (not reboot) - fire-and-forget, SSH will drop
        Write-Status "Sending shutdown command..."
        $ShutdownCmd = "sudo shutdown -h now"
        try {
            if ($UsePutty) {
                & $PlinkExe -batch -pw $Password "$PiUser@$PiHost" $ShutdownCmd 2>&1 | Out-Null
            } else {
                & ssh @SshOpts "$PiUser@$PiHost" $ShutdownCmd 2>&1 | Out-Null
            }
        } catch {
            # SSH drops during shutdown - that's expected, not an error
        }
        Write-Success "Shutdown command sent. Pi is powering off."

    } elseif ($LocalOnly) {
        Write-Host "  Local zip setup complete!" -ForegroundColor White
        Write-Host "  GhostHub is ready for local use" -ForegroundColor Gray
    } else {
        Write-Host "  Access GhostHub at:" -ForegroundColor White
        Write-Host "    http://192.168.4.1:5000" -ForegroundColor Yellow
        Write-Host "    http://ghosthub.local:5000" -ForegroundColor Yellow
    }
} else {
    Write-Warn "Install script exited with code $ExitCode"
    Write-Warn "Check the Pi for errors: sudo journalctl -u ghosthub -n 50"
}

Write-Host ""
