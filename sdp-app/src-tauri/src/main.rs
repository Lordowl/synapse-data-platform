// src-tauri/src/main.rs

// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{generate_context, Manager, WindowEvent};
use std::process::{Command as StdCommand, Stdio};
use std::path::PathBuf;
use std::fs::File;
use std::net::TcpStream;
use std::time::Duration;
use std::sync::Mutex;

// State per mantenere il PID del backend
struct BackendState {
    pid: Option<u32>,
}

impl BackendState {
    fn new() -> Self {
        Self { pid: None }
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(Mutex::new(BackendState::new()))
        .setup(|app| {
            // Prova prima il percorso delle binaries (dev), poi il resource dir (installed)
            let binaries_dir = PathBuf::from("C:\\Users\\EmanueleDeFeo\\Documents\\Projects\\Synapse-Data-Platform\\sdp-app\\src-tauri\\binaries");
            let dev_exe = binaries_dir.join("sdp-api-x86_64-pc-windows-msvc.exe");

            let (exe_path, working_dir) = if dev_exe.exists() {
                // Modalità sviluppo
                (dev_exe, binaries_dir)
            } else {
                // App installata - prova diversi percorsi possibili
                let resource_dir = app.path().resource_dir().expect("Failed to get resource dir");

                // Prova vari percorsi possibili
                let paths_to_try = vec![
                    resource_dir.join("sdp-api.exe"),  // Nome usato da Tauri nel bundle
                    resource_dir.join("sdp-api-x86_64-pc-windows-msvc.exe"),
                    resource_dir.join("sdp-api-x86_64-pc-windows-msvc"),
                    resource_dir.join("binaries").join("sdp-api-x86_64-pc-windows-msvc.exe"),
                    app.path().resolve("sdp-api", tauri::path::BaseDirectory::Resource).ok()
                        .unwrap_or_else(|| PathBuf::from("not_found")),
                ];

                let mut found_path = None;
                for path in &paths_to_try {
                    if path.exists() {
                        found_path = Some(path.clone());
                        break;
                    }
                }

                if let Some(exe) = found_path {
                    let working_dir = exe.parent().expect("Failed to get parent dir").to_path_buf();
                    (exe, working_dir)
                } else {
                    // Mostra tutti i percorsi provati
                    let paths_str = paths_to_try.iter()
                        .map(|p| format!("{:?}", p))
                        .collect::<Vec<_>>()
                        .join("\n");

                    #[cfg(target_os = "windows")]
                    {
                        use std::ffi::OsStr;
                        use std::os::windows::ffi::OsStrExt;
                        let msg = format!("Backend not found. Tried:\n{}", paths_str);
                        let wide: Vec<u16> = OsStr::new(&msg).encode_wide().chain(std::iter::once(0)).collect();
                        let title: Vec<u16> = OsStr::new("SDP Error").encode_wide().chain(std::iter::once(0)).collect();
                        unsafe {
                            windows::Win32::UI::WindowsAndMessaging::MessageBoxW(
                                None,
                                windows::core::PCWSTR(wide.as_ptr()),
                                windows::core::PCWSTR(title.as_ptr()),
                                windows::Win32::UI::WindowsAndMessaging::MB_OK | windows::Win32::UI::WindowsAndMessaging::MB_ICONERROR
                            );
                        }
                    }

                    // Usa il primo path come fallback (non esiste ma almeno non crasha)
                    (paths_to_try[0].clone(), resource_dir)
                }
            };

            println!("🚀 Avvio backend: {:?}", exe_path);
            println!("📁 Working directory: {:?}", working_dir);

            // Se il file non esiste, esci (già mostrato errore sopra)
            if !exe_path.exists() {
                return Ok(());
            }

            // Controlla se il backend è già in esecuzione
            if TcpStream::connect_timeout(
                &"127.0.0.1:9123".parse().unwrap(),
                Duration::from_millis(500)
            ).is_ok() {
                println!("ℹ️  Backend già in esecuzione sulla porta 9123, skip avvio");
                return Ok(());
            }

            // Percorsi log in temp directory o home
            let log_dir = if cfg!(debug_assertions) {
                PathBuf::from("C:\\Users\\EmanueleDeFeo\\Documents\\Projects\\Synapse-Data-Platform\\sdp-app")
            } else {
                app.path().app_log_dir().expect("Failed to get log dir")
            };

            std::fs::create_dir_all(&log_dir).ok();

            let stdout_file = File::create(log_dir.join("backend-stdout.log"))
                .expect("Failed to create stdout log");
            let stderr_file = File::create(log_dir.join("backend-stderr.log"))
                .expect("Failed to create stderr log");

            // Lancia il backend
            #[cfg(target_os = "windows")]
            {
                use std::os::windows::process::CommandExt;
                const CREATE_NO_WINDOW: u32 = 0x08000000;

                match StdCommand::new(&exe_path)
                    .args(&["--host", "127.0.0.1", "--port", "9123"])
                    .current_dir(&working_dir)
                    .stdout(Stdio::from(stdout_file))
                    .stderr(Stdio::from(stderr_file))
                    .creation_flags(CREATE_NO_WINDOW)
                    .spawn()
                {
                    Ok(child) => {
                        let pid = child.id();
                        println!("✅ Backend avviato con PID: {}", pid);
                        println!("📋 Log salvati in {:?}", log_dir);

                        // Salva il PID nello state
                        let state = app.state::<Mutex<BackendState>>();
                        state.lock().unwrap().pid = Some(pid);

                        // Aspetta che il backend sia pronto (max 30 secondi)
                        println!("⏳ Attesa avvio backend...");
                        let max_attempts = 60; // 60 tentativi * 500ms = 30 secondi
                        let mut attempts = 0;
                        let backend_ready = loop {
                            attempts += 1;

                            // Prova a connettersi alla porta
                            if TcpStream::connect_timeout(
                                &"127.0.0.1:9123".parse().unwrap(),
                                Duration::from_millis(500)
                            ).is_ok() {
                                println!("✅ Backend pronto dopo {} tentativi!", attempts);
                                break true;
                            }

                            if attempts >= max_attempts {
                                eprintln!("❌ Timeout: backend non risponde dopo {} secondi", max_attempts / 2);
                                break false;
                            }

                            std::thread::sleep(Duration::from_millis(500));
                        };

                        if !backend_ready {
                            use std::ffi::OsStr;
                            use std::os::windows::ffi::OsStrExt;
                            let msg = "Il backend non si è avviato correttamente.\nControlla i log per maggiori dettagli.";
                            let wide: Vec<u16> = OsStr::new(msg).encode_wide().chain(std::iter::once(0)).collect();
                            let title: Vec<u16> = OsStr::new("Errore Avvio Backend").encode_wide().chain(std::iter::once(0)).collect();
                            unsafe {
                                windows::Win32::UI::WindowsAndMessaging::MessageBoxW(
                                    None,
                                    windows::core::PCWSTR(wide.as_ptr()),
                                    windows::core::PCWSTR(title.as_ptr()),
                                    windows::Win32::UI::WindowsAndMessaging::MB_OK | windows::Win32::UI::WindowsAndMessaging::MB_ICONWARNING
                                );
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!("❌ Errore avvio backend: {}", e);
                    }
                }
            }

            #[cfg(not(target_os = "windows"))]
            {
                match StdCommand::new(&exe_path)
                    .args(&["--host", "127.0.0.1", "--port", "9123"])
                    .current_dir(&working_dir)
                    .stdout(Stdio::from(stdout_file))
                    .stderr(Stdio::from(stderr_file))
                    .spawn()
                {
                    Ok(child) => {
                        let pid = child.id();
                        println!("✅ Backend avviato con PID: {}", pid);
                        println!("📋 Log salvati in {:?}", log_dir);

                        // Salva il PID nello state
                        let state = app.state::<Mutex<BackendState>>();
                        state.lock().unwrap().pid = Some(pid);

                        // Aspetta che il backend sia pronto (max 30 secondi)
                        println!("⏳ Attesa avvio backend...");
                        let max_attempts = 60; // 60 tentativi * 500ms = 30 secondi
                        let mut attempts = 0;
                        let backend_ready = loop {
                            attempts += 1;

                            // Prova a connettersi alla porta
                            if TcpStream::connect_timeout(
                                &"127.0.0.1:9123".parse().unwrap(),
                                Duration::from_millis(500)
                            ).is_ok() {
                                println!("✅ Backend pronto dopo {} tentativi!", attempts);
                                break true;
                            }

                            if attempts >= max_attempts {
                                eprintln!("❌ Timeout: backend non risponde dopo {} secondi", max_attempts / 2);
                                break false;
                            }

                            std::thread::sleep(Duration::from_millis(500));
                        };

                        if !backend_ready {
                            eprintln!("⚠️  Il backend non si è avviato correttamente. Controlla i log.");
                        }
                    }
                    Err(e) => {
                        eprintln!("❌ Errore avvio backend: {}", e);
                    }
                }
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { .. } = event {
                // Termina il backend prima di uscire
                if let Some(state) = window.try_state::<Mutex<BackendState>>() {
                    if let Some(pid) = state.lock().unwrap().pid {
                        println!("🛑 Terminazione backend con PID: {}", pid);

                        #[cfg(target_os = "windows")]
                        {
                            // Su Windows usa taskkill per terminare il processo
                            let _ = StdCommand::new("taskkill")
                                .args(&["/PID", &pid.to_string(), "/F", "/T"])
                                .spawn();
                        }

                        #[cfg(not(target_os = "windows"))]
                        {
                            // Su Unix-like usa kill
                            unsafe {
                                libc::kill(pid as i32, libc::SIGTERM);
                            }
                        }
                    }
                }
                std::process::exit(0);
            }
        })
        .run(generate_context!())
        .expect("Errore nell'avvio dell'app");
}
