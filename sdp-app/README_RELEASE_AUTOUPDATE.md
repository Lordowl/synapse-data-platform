# Release Auto-Update (Tauri) - Comandi Rapidi

Questa guida serve per pubblicare una release che l'app scarica automaticamente da GitHub.

## Prerequisiti

1. Versione coerente in:
   - `package.json`
   - `src-tauri/tauri.conf.json`
   - `src-tauri/Cargo.toml`
2. Repo release updater: `Lordowl/synapse-data-updates`
3. Key Tauri disponibile in `src-tauri/tauri_keys`

## 0) Rigenera il backend e aggiorna il sidecar

> **Da non saltare quando hai toccato codice Python.** L'API viaggia dentro
> l'installer come sidecar Tauri (`externalBin: binaries/sdp-api`) e nulla nella
> build la rigenera: `npm run tauri build` impacchetta l'exe che trova gia' in
> `src-tauri/binaries`. Se lo salti, la release esce con un backend vecchio senza
> dare nessun errore.

```powershell
cd ..\sdp-api
.\venv\Scripts\python.exe -m PyInstaller sdp-api.spec --noconfirm --clean
Copy-Item dist\sdp-api.exe ..\sdp-app\src-tauri\binaries\sdp-api-x86_64-pc-windows-msvc.exe -Force
cd ..\sdp-app
```

`release.ps1` controlla da solo che il sidecar sia piu' recente dei sorgenti `.py`
e si ferma se non lo e', ma la rigenerazione resta manuale.

## 1) Build release

```powershell
cd sdp-app
npm run tauri build
```

Output atteso (Windows):
- `src-tauri\target\release\bundle\nsis\Cruscotto Operativo_<VERSION>_x64-setup.exe`

## 2) Firma dell'installer (`.sig`)

```powershell
$VERSION="0.2.47"
$PASSWORD="<PASSWORD_KEY>"
$EXE="src-tauri\target\release\bundle\nsis\Cruscotto Operativo_${VERSION}_x64-setup.exe"

npx tauri signer sign -f "src-tauri\tauri_keys" -p $PASSWORD $EXE
```

Output atteso:
- `src-tauri\target\release\bundle\nsis\Cruscotto Operativo_<VERSION>_x64-setup.exe.sig`

## 3) Genera `latest.json`

> **Attenzione al nome del file nell URL.** GitHub normalizza i nomi degli asset:
> ogni carattere che non sia alfanumerico, punto, underscore o trattino diventa un
> punto. Lo spazio di "Cruscotto Operativo" diventa quindi un punto, e l URL deve
> usare `Cruscotto.Operativo_...`, non `Cruscotto%20Operativo_...`. Con `%20`
> l update viene annunciato ai client ma il download restituisce 404.

```powershell
$VERSION="0.2.47"
$EXE_NAME="Cruscotto Operativo_${VERSION}_x64-setup.exe"
$SIG=(Get-Content -Raw "src-tauri\target\release\bundle\nsis\${EXE_NAME}.sig").Trim()
$PUB_DATE=(Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

$json = @"
{
  "version": "$VERSION",
  "notes": "Release $VERSION",
  "pub_date": "$PUB_DATE",
  "platforms": {
    "windows-x86_64": {
      "signature": "$SIG",
      "url": "https://github.com/Lordowl/synapse-data-updates/releases/download/$VERSION/Cruscotto.Operativo_${VERSION}_x64-setup.exe",
      "with_elevated_task": false
    }
  }
}
"@

Set-Content -Path "src-tauri\target\release\bundle\nsis\latest.json" -Value $json -Encoding Ascii
```

## 4) Verifica file pronti

```powershell
$VERSION="0.2.47"
Get-ChildItem -File `
  "src-tauri\target\release\bundle\nsis\Cruscotto Operativo_${VERSION}_x64-setup.exe", `
  "src-tauri\target\release\bundle\nsis\Cruscotto Operativo_${VERSION}_x64-setup.exe.sig", `
  "src-tauri\target\release\bundle\nsis\latest.json"
```

## 5) Upload manuale su GitHub

Nel repo `Lordowl/synapse-data-updates`:

1. Crea release con tag `0.2.47`
2. Carica questi 3 asset:
   - `Cruscotto Operativo_0.2.47_x64-setup.exe`
   - `Cruscotto Operativo_0.2.47_x64-setup.exe.sig`
   - `latest.json`
3. Pubblica la release (non draft)

## 6) Check finale auto-update

Controlla:

`https://github.com/Lordowl/synapse-data-updates/releases/latest/download/latest.json`

Deve mostrare `"version": "0.2.47"`.
