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

      // Piccola pausa per assicurarsi che il processo sia terminato
      await new Promise(resolve => setTimeout(resolve, 1000));

      console.log("📦 Download in corso...");
      await update.downloadAndInstall();
      console.log("✅ Download completato, riavvio...");
      await relaunch();
    } else {
      console.log("✅ Nessun aggiornamento disponibile.");
    }
  } catch (error) {
    console.error("❌ Errore durante l'aggiornamento:", error);
    console.error("🔍 Dettagli errore:", JSON.stringify(error, null, 2));
  }
}