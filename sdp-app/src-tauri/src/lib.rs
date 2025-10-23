use std::process::{Command as StdCommand, Stdio};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust! v2", name)
}

fn log_to_file(message: &str) {
    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open("C:\\Users\\EmanueleDeFeo\\Documents\\Projects\\Synapse-Data-Platform\\sdp-app\\tauri-backend.log")
    {
        let _ = writeln!(file, "{}", message);
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|_app| {
            // Test immediato - crea il file subito
            std::fs::write(
                "C:\\Users\\EmanueleDeFeo\\Documents\\Projects\\Synapse-Data-Platform\\sdp-app\\SETUP_EXECUTED.txt",
                "Setup was executed!"
            ).ok();

            log_to_file("=== SETUP TAURI STARTED ===");

            let backend_path = if cfg!(debug_assertions) {
                "C:\\Users\\EmanueleDeFeo\\Documents\\Projects\\Synapse-Data-Platform\\sdp-app\\src-tauri\\binaries\\sdp-api-x86_64-pc-windows-msvc.exe"
            } else {
                "binaries/sdp-api-x86_64-pc-windows-msvc.exe"
            };

            log_to_file(&format!("Backend path: {}", backend_path));

            // Verifica che il file esista
            if !Path::new(backend_path).exists() {
                log_to_file("ERROR: Backend exe NOT FOUND!");
                eprintln!("❌ Backend exe not found at: {}", backend_path);
                return Ok(());
            }

            log_to_file("Backend exe found, attempting to start...");

            // Avvia il backend
            #[cfg(target_os = "windows")]
            {
                use std::os::windows::process::CommandExt;
                const CREATE_NO_WINDOW: u32 = 0x08000000;

                match StdCommand::new(backend_path)
                    .args(&["--host", "127.0.0.1", "--port", "9123"])
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .creation_flags(CREATE_NO_WINDOW)
                    .spawn()
                {
                    Ok(child) => {
                        let msg = format!("✅ Backend started with PID: {}", child.id());
                        log_to_file(&msg);
                        println!("{}", msg);
                    }
                    Err(e) => {
                        let msg = format!("❌ Failed to start backend: {}", e);
                        log_to_file(&msg);
                        eprintln!("{}", msg);
                    }
                }
            }

            #[cfg(not(target_os = "windows"))]
            {
                match StdCommand::new(backend_path)
                    .args(&["--host", "127.0.0.1", "--port", "9123"])
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .spawn()
                {
                    Ok(child) => {
                        let msg = format!("✅ Backend started with PID: {}", child.id());
                        log_to_file(&msg);
                        println!("{}", msg);
                    }
                    Err(e) => {
                        let msg = format!("❌ Failed to start backend: {}", e);
                        log_to_file(&msg);
                        eprintln!("{}", msg);
                    }
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
