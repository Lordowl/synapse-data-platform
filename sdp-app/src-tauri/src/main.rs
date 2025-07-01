// src-tauri/src/main.rs

// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

// Non è più necessario importare il modulo 'auth'
// mod auth; 

// Non è necessario importare `command` se non hai altri comandi
// use tauri::command;

use tauri::generate_context;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .run(generate_context!())
        .expect("Errore nell'avvio dell'app");
}