# Build script per Cruscotto Operativo con firma aggiornamenti Tauri
# Uso: .\build-release.ps1

$KeyFile = "$PSScriptRoot\src-tauri\tauri_keys"

if (-not (Test-Path $KeyFile)) {
    Write-Error "Chiave privata non trovata: $KeyFile"
    exit 1
}

$PrivateKey = [System.IO.File]::ReadAllText($KeyFile)

$SecurePassword = Read-Host "Password chiave di firma" -AsSecureString
$Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
)

$env:TAURI_SIGNING_PRIVATE_KEY = $PrivateKey
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = $Password

Write-Host "Avvio build release..." -ForegroundColor Cyan
npm run tauri build

$env:TAURI_SIGNING_PRIVATE_KEY = ""
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = ""

# Genera latest.json con la firma del nuovo installer
$Version = (Get-Content "$PSScriptRoot\src-tauri\tauri.conf.json" | ConvertFrom-Json).version
$BundleDir = "$PSScriptRoot\src-tauri\target\release\bundle\nsis"
$SigFile = Get-ChildItem $BundleDir -Filter "*.sig" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($SigFile) {
    $Signature = [System.IO.File]::ReadAllText($SigFile.FullName)
    $PubDate = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $LatestJson = @{
        version  = $Version
        notes    = "Release $Version"
        pub_date = $PubDate
        platforms = @{
            "windows-x86_64" = @{
                signature          = $Signature
                url                = "https://github.com/Lordowl/synapse-data-updates/releases/download/$Version/Cruscotto.Operativo_${Version}_x64-setup.exe"
                with_elevated_task = $false
            }
        }
    } | ConvertTo-Json -Depth 5

    $LatestPath = "$BundleDir\latest.json"
    $LatestJson | Set-Content $LatestPath -Encoding UTF8
    Write-Host "latest.json generato: $LatestPath" -ForegroundColor Green
} else {
    Write-Warning "File .sig non trovato, latest.json non aggiornato."
}

Write-Host "Build completata." -ForegroundColor Green
