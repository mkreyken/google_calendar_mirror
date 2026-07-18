# Auto-activate Python venv depending on machine
$venvCal = "$HOME\.venv-cal"


if (Test-Path "$venvCal\Scripts\Activate.ps1") {
    & "$venvCal\Scripts\Activate.ps1"
}
else {
  $venv = "$HOME\.venv"
  if (Test-Path "$venv\Scripts\Activate.ps1") {
    & "$venv\Scripts\Activate.ps1"
  }
}



# Ensure script runs from its own directory
Set-Location -Path $PSScriptRoot

# Move up to the project root (where src/ lives)
Set-Location -Path (Join-Path $PSScriptRoot "..")

# --- Ensure required directories exist ---
$logsDir = Join-Path $PSScriptRoot "\..\logs"
$dataDir = Join-Path $PSScriptRoot "\..\data"

if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}

# --- Activate virtual environment ---

## & "$PSScriptRoot\.venv-cal\Scripts\Activate.ps1"

# --- Run the Python application as a module ---
python -m src.services.launcher
