$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip --retries 10
if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip." }

if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv pip install --python ".\.venv\Scripts\python.exe" -r requirements.txt
} else {
    & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt --retries 10
}
if ($LASTEXITCODE -ne 0) { throw "Could not install project dependencies." }

& ".\.venv\Scripts\python.exe" scripts\generate_demo_data.py
if ($LASTEXITCODE -ne 0) { throw "Could not generate the demo dataset." }

& ".\.venv\Scripts\python.exe" scripts\run_pipeline.py
if ($LASTEXITCODE -ne 0) { throw "Could not run the scoring pipeline." }

Write-Host "Setup complete. Run .\run.ps1 to start the dashboard."

