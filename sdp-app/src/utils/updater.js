import { check } from "@tauri-apps/plugin-updater";
import { exit } from '@tauri-apps/plugin-process';
import { invoke } from '@tauri-apps/api/core';

export async function autoUpdate() {
  try {
    console.log("🔍 Controllo aggiornamenti...");
    const update = await check();
    if (update) {
      console.log("🔄 Aggiornamento disponibile:", update.version);
      console.log("📄 Note:", update.body);

      // 1. Scarica prima (app ancora in memoria, nessun file lock)
      console.log("📦 Download in corso...");
      let downloaded = 0;
      let total = 0;
      await update.download((progress) => {
        if (progress.event === 'Started') {
          total = progress.data.contentLength ?? 0;
          console.log(`📦 Download avviato, dimensione: ${total} bytes`);
        } else if (progress.event === 'Progress') {
          downloaded += progress.data.chunkLength;
          const pct = total > 0 ? Math.round((downloaded / total) * 100) : '?';
          console.log(`⬇️ Download: ${pct}% (${downloaded}/${total})`);
        } else if (progress.event === 'Finished') {
          console.log("✅ Download completato.");
        }
      });

      // 2. Ferma il backend
      console.log("🛑 Arresto backend...");
      try {
        await invoke('stop_backend');
        console.log("✅ Backend arrestato.");
      } catch (stopError) {
        console.warn("⚠️ Errore arresto backend (continuo comunque):", stopError);
      }

      // 3. Attendi che il processo sia terminato
      await new Promise(resolve => setTimeout(resolve, 3000));

      // 4. Avvia l'installer (processo separato)
      console.log("📦 Avvio installer...");
      await update.install();

      // 5. Esci dall'app — libera il file lock su sdp-app.exe
      console.log("🚪 Chiusura app per permettere l'installazione...");
      await exit(0);

    } else {
      console.log("✅ Nessun aggiornamento disponibile.");
    }
  } catch (error) {
    console.error("❌ Errore durante l'aggiornamento:", error);
    console.error("🔍 Dettagli errore:", JSON.stringify(error, null, 2));
  }
}