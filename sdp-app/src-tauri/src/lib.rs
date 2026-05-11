use std::process::{Command as StdCommand, Stdio};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;
use std::sync::Mutex;

static BACKEND_PID: Mutex<Option<u32>> = Mutex::new(None);

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust! v2", name)
}

#[tauri::command]
fn stop_backend() -> String {
    let mut pid_lock = BACKEND_PID.lock().unwrap();
    if let Some(pid) = *pid_lock {
        let result = StdCommand::new("taskkill")
            .args(["/PID", &pid.to_string(), "/F"])
            .output();
        *pid_lock = None;
        match result {
            Ok(_) => {
                let msg = format!("Backend process {} killed", pid);
                log_to_file(&msg);
                return msg;
            }
            Err(e) => {
                let msg = format!("Failed to kill backend PID {}: {}", pid, e);
                log_to_file(&msg);
            }
        }
    }
    // Fallback: kill per porta nel caso il PID non fosse salvato
    kill_process_on_port(9123);
    "Backend stopped (by port fallback)".to_string()
}

fn kill_process_on_port(port: u16) {
    log_to_file(&format!("Killing any existing process on port {}...", port));
    let _ = StdCommand::new("cmd")
        .args([
            "/C",
            &format!(
                "for /f \"tokens=5\" %a in ('netstat -ano ^| findstr :{} ^| findstr LISTENING') do taskkill /PID %a /F",
                port
            ),
        ])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
}

fn log_to_file(message: &str) {
    let log_path = dirs::home_dir()
        .map(|h| h.join(".sdp-api").join("tauri-backend.log"))
        .unwrap_or_else(|| std::path::PathBuf::from("tauri-backend.log"));

    if let Some(parent) = log_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }

    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
    {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        let _ = writeln!(file, "[{}] {}", timestamp, message);
    }
}

fn start_backend(backend_path: &str) {
    // Uccide qualsiasi processo già in ascolto sulla porta prima di avviarne uno nuovo
    kill_process_on_port(9123);
    std::thread::sleep(std::time::Duration::from_millis(500));

    log_to_file(&format!("Starting backend: {}", backend_path));

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;

        match StdCommand::new(backend_path)
            .args(["--host", "127.0.0.1", "--port", "9123"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(CREATE_NO_WINDOW)
            .spawn()
        {
            Ok(child) => {
                let pid = child.id();
                *BACKEND_PID.lock().unwrap() = Some(pid);
                let msg = format!("Backend started with PID: {}", pid);
                log_to_file(&msg);
                println!("{}", msg);
            }
            Err(e) => {
                let msg = format!("Failed to start backend: {}", e);
                log_to_file(&msg);
                eprintln!("{}", msg);
            }
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        match StdCommand::new(backend_path)
            .args(["--host", "127.0.0.1", "--port", "9123"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
        {
            Ok(child) => {
                let pid = child.id();
                *BACKEND_PID.lock().unwrap() = Some(pid);
                let msg = format!("Backend started with PID: {}", pid);
                log_to_file(&msg);
                println!("{}", msg);
            }
            Err(e) => {
                let msg = format!("Failed to start backend: {}", e);
                log_to_file(&msg);
                eprintln!("{}", msg);
            }
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|_app| {
            log_to_file("=== SETUP TAURI STARTED ===");

            let backend_path = if cfg!(debug_assertions) {
                "C:\\Users\\EmanueleDeFeo\\Documents\\Projects\\Synapse-Data-Platform\\sdp-app\\src-tauri\\binaries\\sdp-api-x86_64-pc-windows-msvc.exe"
            } else {
                "binaries/sdp-api-x86_64-pc-windows-msvc.exe"
            };

            log_to_file(&format!("Backend path: {}", backend_path));

            if !Path::new(backend_path).exists() {
                log_to_file("ERROR: Backend exe NOT FOUND!");
                eprintln!("Backend exe not found at: {}", backend_path);
                return Ok(());
            }

            start_backend(backend_path);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet, stop_backend])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
