import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from '@tauri-apps/plugin-process';
import { invoke } from '@tauri-apps/api/core';

export async function autoUpdate() {
  try {
    console.log("🔍 Controllo aggiornamenti...");
    const update = await check();
    if (update) {
      console.log("🔄 Aggiornamento disponibile:", update.version);
      console.log("📄 Note:", update.body);

      // Ferma il backend prima di scaricare/installare l'aggiornamento
      console.log("🛑 Arresto backend prima dell'aggiornamento...");
      try {
        const stopResult = await invoke('stop_backend');
        console.log("✅ Backend arrestato:", stopResult);
      } catch (stopError) {
        console.warn("⚠️ Errore arresto backend (continuo comunque):", stopError);
      }

      // Pausa per assicurarsi che il processo sia completamente terminato
      await new Promise(resolve => setTimeout(resolve, 3000));

      console.log("📦 Download in corso...");
      let downloaded = 0;
      let total = 0;
      await update.downloadAndInstall((progress) => {
        if (progress.event === 'Started') {
          total = progress.data.contentLength ?? 0;
          console.log(`📦 Download avviato, dimensione: ${total} bytes`);
        } else if (progress.event === 'Progress') {
          downloaded += progress.data.chunkLength;
          const pct = total > 0 ? Math.round((downloaded / total) * 100) : '?';
          console.log(`⬇️ Download: ${pct}% (${downloaded}/${total})`);
        } else if (progress.event === 'Finished') {
          console.log("✅ Download completato, installazione in corso...");
        }
      });
      console.log("🔄 Riavvio...");
      await relaunch();
    } else {
      console.log("✅ Nessun aggiornamento disponibile.");
    }
  } catch (error) {
    console.error("❌ Errore durante l'aggiornamento:", error);
    console.error("🔍 Dettagli errore:", JSON.stringify(error, null, 2));
  }
}