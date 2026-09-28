<#
.SYNOPSIS
    Firma l'installer e genera latest.json per l'auto-update Tauri.

.DESCRIPTION
    Automatizza i passi 2 e 3 di README_RELEASE_AUTOUPDATE.md. La build (passo 1)
    va lanciata prima con `npm run tauri build`.

    La password della chiave viene chiesta in modo sicuro e non viene mai scritta
    su disco ne' registrata nella cronologia di PowerShell.

.PARAMETER Version
    Versione da rilasciare. Se omessa viene letta da package.json.

.EXAMPLE
    cd sdp-app
    .\release.ps1

.EXAMPLE
    .\release.ps1 -Version 0.2.44
#>
param(
    [string]$Version
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# --- Versione ---------------------------------------------------------------
if (-not $Version) {
    $Version = (Get-Content package.json -Raw | ConvertFrom-Json).version
    Write-Host "Versione letta da package.json: $Version"
}

# Coerenza fra i file che la dichiarano
$tauriVersion = (Get-Content src-tauri\tauri.conf.json -Raw | ConvertFrom-Json).version
$cargoVersion = (Select-String -Path src-tauri\Cargo.toml -Pattern '^version = "(.+)"').Matches[0].Groups[1].Value
if ($tauriVersion -ne $Version -or $cargoVersion -ne $Version) {
    Write-Host "ERRORE: versioni non allineate." -ForegroundColor Red
    Write-Host "  package.json     : $Version"
    Write-Host "  tauri.conf.json  : $tauriVersion"
    Write-Host "  Cargo.toml       : $cargoVersion"
    exit 1
}
Write-Host "Versioni allineate su $Version" -ForegroundColor Green

# --- Sidecar sdp-api --------------------------------------------------------
# L'API viaggia dentro l'installer come sidecar Tauri (externalBin) e nulla nella
# build la rigenera: npm run tauri build impacchetta l'exe che trova. Se e' piu'
# vecchio dei sorgenti .py la release esce con un backend datato, senza errori.
$sidecar = "src-tauri\binaries\sdp-api-x86_64-pc-windows-msvc.exe"
if (-not (Test-Path $sidecar)) {
    Write-Host "ERRORE: sidecar mancante: $sidecar" -ForegroundColor Red
    exit 1
}

$ultimoPy = Get-ChildItem ..\sdp-api -Recurse -Filter *.py |
    Where-Object { $_.FullName -notmatch '\\(venv|build|dist|__pycache__)\\' } |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($ultimoPy -and $ultimoPy.LastWriteTime -gt (Get-Item $sidecar).LastWriteTime) {
    Write-Host "ERRORE: il sidecar non contiene le ultime modifiche Python." -ForegroundColor Red
    Write-Host "  piu' recente : $($ultimoPy.Name) - $($ultimoPy.LastWriteTime)"
    Write-Host "  sidecar      : $((Get-Item $sidecar).LastWriteTime)"
    Write-Host ""
    Write-Host "Rigeneralo con:"
    Write-Host "  cd ..\sdp-api"
    Write-Host "  .\venv\Scripts\python.exe -m PyInstaller sdp-api.spec --noconfirm --clean"
    Write-Host "  Copy-Item dist\sdp-api.exe ..\sdp-app\$sidecar -Force"
    exit 1
}
Write-Host "Sidecar sdp-api aggiornato rispetto ai sorgenti" -ForegroundColor Green

# --- Installer --------------------------------------------------------------
$bundleDir = "src-tauri\target\release\bundle\nsis"
$exeName = "Cruscotto Operativo_${Version}_x64-setup.exe"
$exePath = Join-Path $bundleDir $exeName

if (-not (Test-Path $exePath)) {
    Write-Host "ERRORE: installer non trovato: $exePath" -ForegroundColor Red
    Write-Host "Lancia prima: npm run tauri build"
    exit 1
}
$sizeMb = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
Write-Host "Installer trovato: $exeName ($sizeMb MB)" -ForegroundColor Green

# --- Firma ------------------------------------------------------------------
$sigPath = "$exePath.sig"
if (Test-Path $sigPath) {
    Write-Host "Firma gia' presente, la rigenero."
    Remove-Item $sigPath
}

$securePwd = Read-Host -Prompt "Password della chiave (src-tauri\tauri_keys)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePwd)
try {
    $plainPwd = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    Write-Host "Firma in corso..."
    npx tauri signer sign -f "src-tauri\tauri_keys" -p $plainPwd "$exePath"
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    $plainPwd = $null
}

if (-not (Test-Path $sigPath)) {
    Write-Host "ERRORE: la firma non ha prodotto il file .sig" -ForegroundColor Red
    exit 1
}
Write-Host "Firma creata: $exeName.sig" -ForegroundColor Green

# --- latest.json ------------------------------------------------------------
$sig = (Get-Content -Raw $sigPath).Trim()
$pubDate = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# GitHub normalizza i nomi degli asset: ogni carattere che non sia alfanumerico,
# punto, underscore o trattino diventa un punto. Lo spazio in "Cruscotto Operativo"
# quindi NON va codificato come %20, altrimenti l'URL nel latest.json da' 404 e
# l'auto-update fallisce dopo aver annunciato l'aggiornamento.
$urlName = $exeName -replace '[^A-Za-z0-9._-]', '.'
Write-Host "Nome asset su GitHub: $urlName"

$json = @"
{
  "version": "$Version",
  "notes": "Release $Version",
  "pub_date": "$pubDate",
  "platforms": {
    "windows-x86_64": {
      "signature": "$sig",
      "url": "https://github.com/Lordowl/synapse-data-updates/releases/download/$Version/$urlName",
      "with_elevated_task": false
    }
  }
}
"@

$latestPath = Join-Path $bundleDir "latest.json"
Set-Content -Path $latestPath -Value $json -Encoding Ascii
Write-Host "Generato: latest.json" -ForegroundColor Green

# --- Istruzioni finali ------------------------------------------------------
Write-Host ""
Write-Host "=== PRONTO PER LA RELEASE ===" -ForegroundColor Cyan
Write-Host "Cartella: $(Resolve-Path $bundleDir)"
Write-Host ""
Write-Host "File da allegare alla release con tag '$Version' su Lordowl/synapse-data-updates:"
Write-Host "  - $exeName"
Write-Host "  - $exeName.sig"
Write-Host "  - latest.json"
Write-Host ""

if (Get-Command gh -ErrorAction SilentlyContinue) {
    Write-Host "gh CLI disponibile. Per pubblicare:"
    Write-Host "  gh release create $Version ``"
    Write-Host "    `"$exePath`" ``"
    Write-Host "    `"$sigPath`" ``"
    Write-Host "    `"$latestPath`" ``"
    Write-Host "    --repo Lordowl/synapse-data-updates --title `"$Version`" --notes `"Release $Version`""
} else {
    Write-Host "gh CLI non installato: crea la release dall'interfaccia web"
    Write-Host "  https://github.com/Lordowl/synapse-data-updates/releases/new"
    Write-Host "  Tag: $Version"
}
Write-Host ""
Write-Host "ATTENZIONE: latest.json deve stare nella release 'latest', altrimenti"
Write-Host "l'endpoint dell'updater non lo trova."
