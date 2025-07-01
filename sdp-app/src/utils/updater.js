import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from '@tauri-apps/plugin-process';

export async function autoUpdate() {
  try {
    const update = await check();
    if (update) {
      console.log("🔄 Aggiornamento disponibile, installazione in corso...");
      await update.downloadAndInstall();
      await relaunch();
    } else {
      console.log("✅ Nessun aggiornamento disponibile.");
    }
  } catch (error) {
    console.error("❌ Errore durante l'aggiornamento:", error);
  }
}