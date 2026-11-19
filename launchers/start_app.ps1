# Start the diffusion analysis app on this PC (Windows). Called from 解析アプリを起動.bat.
# Saved as UTF-8 with BOM so that Windows PowerShell 5.1 reads the Japanese text correctly.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "初回の準備をしています。uv（Python の管理ツール）を入れます..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

Write-Host "アプリを起動しています。ブラウザが開くまで待ってください（初回は数分かかります）。"
Write-Host "使い終わったら、この画面を閉じてください。"
$env:UV_LINK_MODE = "copy"
# Only this PC can open the app: unpublished data must not be visible on the LAN.
uv run --frozen --no-dev streamlit run streamlit_app.py --server.address localhost
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "起動できませんでした。この画面の内容を開発者に送ってください。"
    exit 1
}
