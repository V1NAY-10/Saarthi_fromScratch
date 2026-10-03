# Starts Saarthi: FastAPI backend (:8000) + Vite frontend (:5173)
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path "$root\backend\.venv")) {
  python -m venv "$root\backend\.venv"
  & "$root\backend\.venv\Scripts\python" -m pip install -r "$root\backend\requirements.txt"
}
if (-not (Test-Path "$root\backend\.env")) { Copy-Item "$root\backend\.env.example" "$root\backend\.env" }
if (-not (Test-Path "$root\frontend\node_modules")) { Push-Location "$root\frontend"; npm install; Pop-Location }
Start-Process -WorkingDirectory "$root\backend" -FilePath "$root\backend\.venv\Scripts\python" -ArgumentList "-m","uvicorn","app.main:app","--port","8000"
Push-Location "$root\frontend"; npm run dev; Pop-Location
