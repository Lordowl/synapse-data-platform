import { checkUpdate, installUpdate } from '@tauri-apps/api/updater'
import { relaunch } from '@tauri-apps/api/process'

export async function autoUpdate() {
  try {
    const update = await checkUpdate()
    if (update.shouldUpdate) {
      console.log("🔄 Aggiornamento disponibile, installazione in corso...")
      await installUpdate()
      await relaunch()
    } else {
      console.log("✅ Nessun aggiornamento disponibile.")
    }
  } catch (error) {
    console.error("❌ Errore durante l'aggiornamento:", error)
  }
}
