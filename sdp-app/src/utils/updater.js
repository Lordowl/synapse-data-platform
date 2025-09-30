import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from '@tauri-apps/plugin-process';

export async function autoUpdate() {
  try {
    console.log("🔍 Controllo aggiornamenti...");
    const update = await check();
    if (update) {
      console.log("🔄 Aggiornamento disponibile:", update.version);
      console.log("📄 Note:", update.body);
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