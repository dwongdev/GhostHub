# Helper script for deploy_to_pi.bat - creates zip with directory structure
# Gets source from script location, outputs to temp folder

$exclude = @('__pycache__', '.git', '.pytest_cache', 'venv', 'node_modules', 
             '*.pyc', '*.log', 'instance', '.env', '*.db', 'tests', 'stress_tests', 
             'deploy_to_pi.*', 'deploy_helper.ps1')

# Use script's directory as source
$src = Split-Path -Parent $MyInvocation.MyCommand.Path

# Output zip path - write to a known location
$OutZip = Join-Path $env:TEMP "ghosthub_deploy.zip"

$tempDir = Join-Path $env:TEMP "ghosthub_staging_$(Get-Random)"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

Get-ChildItem -Path $src -Recurse | ForEach-Object {
    $rel = $_.FullName.Substring($src.Length + 1)
    
    # Check exclusions
    $skip = $false
    foreach ($ex in $exclude) {
        if ($rel -like "*$ex*") { $skip = $true; break }
    }
    
    if (-not $skip) {
        $dest = Join-Path $tempDir $rel
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Path $dest -Force | Out-Null
        } else {
            $destDir = Split-Path $dest -Parent
            if (!(Test-Path $destDir)) { 
                New-Item -ItemType Directory -Path $destDir -Force | Out-Null 
            }
            Copy-Item $_.FullName $dest
        }
    }
}

# Create zip
if (Test-Path $OutZip) { Remove-Item $OutZip -Force }
Compress-Archive -Path (Join-Path $tempDir '*') -DestinationPath $OutZip -Force

# Cleanup
Remove-Item $tempDir -Recurse -Force

Write-Host "Created: $OutZip"
