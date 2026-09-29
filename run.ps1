$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    throw "Environment not found. Run .\setup.ps1 first."
}

& ".\.venv\Scripts\python.exe" -m streamlit run app.py --server.address localhost --server.port 8501

