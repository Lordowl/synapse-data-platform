# Firma l'installer e genera latest.json
# Uso: .\sign-release.ps1

$KeyFile   = "$PSScriptRoot\src-tauri\tauri_keys"
$BundleDir = "$PSScriptRoot\src-tauri\target\release\bundle\nsis"
$Version   = ([System.IO.File]::ReadAllText("$PSScriptRoot\src-tauri\tauri.conf.json") | ConvertFrom-Json).version
$Installer = "$BundleDir\Cruscotto Operativo_${Version}_x64-setup.exe"

if (-not (Test-Path $Installer)) {
    Write-Error "Installer non trovato: $Installer"
    exit 1
}

$SecurePassword = Read-Host "Password chiave di firma" -AsSecureString
$Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
)

$PrivateKey = [System.IO.File]::ReadAllText($KeyFile)
$env:TAURI_SIGNING_PRIVATE_KEY          = $PrivateKey
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = $Password

Write-Host "Firmo l'installer $Version..." -ForegroundColor Cyan
npx tauri signer sign "$Installer"

$env:TAURI_SIGNING_PRIVATE_KEY          = ""
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = ""

$SigFile = "$Installer.sig"
if (-not (Test-Path $SigFile)) {
    Write-Error "Firma non generata. Controlla la password o il percorso."
    exit 1
}

$Signature = [System.IO.File]::ReadAllText($SigFile)
$PubDate   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

$LatestJson = [ordered]@{
    version  = $Version
    notes    = "Release $Version"
    pub_date = $PubDate
    platforms = [ordered]@{
        "windows-x86_64" = [ordered]@{
            signature          = $Signature
            url                = "https://github.com/Lordowl/synapse-data-updates/releases/download/$Version/Cruscotto.Operativo_${Version}_x64-setup.exe"
            with_elevated_task = $false
        }
    }
} | ConvertTo-Json -Depth 5

$LatestJson | Set-Content "$BundleDir\latest.json" -Encoding UTF8
Write-Host "latest.json generato per la versione $Version" -ForegroundColor Green
