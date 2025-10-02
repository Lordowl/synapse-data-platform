// src-tauri/src/main.rs

// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{generate_context, WindowEvent};
use std::process::{Command as StdCommand, Stdio};
use std::path::PathBuf;
use std::fs::File;

fn main() {
    // Percorsi per backend exe e working directory
    let (exe_path, working_dir) = if cfg!(debug_assertions) {
        let binaries_dir = PathBuf::from("C:\\Users\\EmanueleDeFeo\\Documents\\Projects\\Synapse-Data-Platform\\sdp-app\\src-tauri\\binaries");
        let exe = binaries_dir.join("sdp-api-x86_64-pc-windows-msvc.exe");
        (exe, binaries_dir)
    } else {
        let binaries_dir = PathBuf::from("binaries");
        let exe = binaries_dir.join("sdp-api-x86_64-pc-windows-msvc.exe");
        (exe, binaries_dir)
    };

    println!("🚀 Avvio backend: {:?}", exe_path);
    println!("📁 Working directory: {:?}", working_dir);

    // Crea file per catturare stdout e stderr
    let stdout_file = File::create("C:\\Users\\EmanueleDeFeo\\Documents\\Projects\\Synapse-Data-Platform\\sdp-app\\backend-stdout.log")
        .expect("Failed to create stdout log");
    let stderr_file = File::create("C:\\Users\\EmanueleDeFeo\\Documents\\Projects\\Synapse-Data-Platform\\sdp-app\\backend-stderr.log")
        .expect("Failed to create stderr log");

    // Lancia il backend direttamente con working directory corretta
    match StdCommand::new(&exe_path)
        .args(&["--host", "127.0.0.1", "--port", "8000"])
        .current_dir(&working_dir)
        .stdout(Stdio::from(stdout_file))
        .stderr(Stdio::from(stderr_file))
        .spawn()
    {
        Ok(child) => {
            println!("✅ Backend avviato con PID: {}", child.id());
            println!("📋 Log salvati in backend-stdout.log e backend-stderr.log");
        }
        Err(e) => {
            eprintln!("❌ Errore avvio backend: {}", e);
        }
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_dialog::init())
        .on_window_event(|_window, event| {
            if let WindowEvent::CloseRequested { .. } = event {
                std::process::exit(0);
            }
        })
        .run(generate_context!())
        .expect("Errore nell'avvio dell'app");
}
