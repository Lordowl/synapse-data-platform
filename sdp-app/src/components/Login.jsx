import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { open } from "@tauri-apps/plugin-dialog";
import { FolderOpen, Building, User, Lock, LogIn, Loader2 } from "lucide-react";
import axios from "axios";
import apiClient from "../api/apiClient";
import "./Login.css";

function Login({ setIsAuthenticated }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [selectedFolder, setSelectedFolder] = useState("");
  const [selectedBank, setSelectedBank] = useState("");
  const [availableBanks, setAvailableBanks] = useState([]);
  const [apiAddress, setApiAddress] = useState("http://127.0.0.1");
  const [apiPort, setApiPort] = useState("8000");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const baseURL = `${apiAddress}:${apiPort}/api/v1`;

  // Recupera folder corrente e banche disponibili
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        // Crea un client axios temporaneo senza autenticazione
        const tempClient = axios.create({
          baseURL: baseURL,
          headers: { 'Content-Type': 'application/json' },
        });

        // Folder corrente
        try {
          const folderData = await tempClient.get("/folder/current");
          if (folderData.data.folder_path) setSelectedFolder(folderData.data.folder_path);
        } catch {
          console.log("Nessun folder configurato");
        }

        // Banche disponibili
        try {
          const banksData = await tempClient.get("/banks/available");
          setAvailableBanks(banksData.data.banks || []);
          if (banksData.data.current_bank) setSelectedBank(banksData.data.current_bank);
        } catch {
          console.log("Nessuna banca configurata");
        }
      } catch (err) {
        console.error("Errore fetch dati iniziali:", err);
      }
    };

    fetchInitialData();
  }, [baseURL]);

  // Seleziona cartella
  const handleFolderSelect = async () => {
    const selected = await open({
      directory: true,
      multiple: false,
      title: "Seleziona Cartella API",
    });

    if (!selected) return;
    let folderPath = Array.isArray(selected) ? selected[0] : selected;

    if (!folderPath.endsWith("App\\Ingestion") && !folderPath.endsWith("App/Ingestion")) {
      folderPath = `${folderPath}${folderPath.endsWith("\\") || folderPath.endsWith("/") ? "" : "\\"}App\\Ingestion`;
    }

    setSelectedFolder(folderPath);

    // Aggiorna il folder sul backend (ora è pubblico, non serve token)
    try {
      // Crea un client axios temporaneo per questa chiamata pre-login
      const tempClient = axios.create({
        baseURL: baseURL,
        headers: { 'Content-Type': 'application/json' },
      });

      const response = await tempClient.post("/folder/update", { folder_path: folderPath });

      // Mostra informazioni sugli account admin creati
      if (response.data.admin_accounts && response.data.admin_accounts.length > 0) {
        console.log("📋 Account admin creati:");
        response.data.admin_accounts.forEach(account => {
          console.log(`   🏦 ${account.bank}: ${account.username} / ${account.password}`);
        });
      }

      // Dopo aver aggiornato il folder, ricarica le banche disponibili
      try {
        const banksData = await tempClient.get("/banks/available");
        setAvailableBanks(banksData.data.banks || []);
        if (banksData.data.current_bank) setSelectedBank(banksData.data.current_bank);
      } catch {
        console.log("Errore caricamento banche");
      }

      setError("");

      // Mostra messaggio di successo con info sugli admin
      if (response.data.note) {
        console.log("✅ " + response.data.note);
      }
    } catch (err) {
      console.error("Errore aggiornamento folder:", err);
      setError(err.response?.data?.detail || err.message);
    }
  };

  // Cambia banca
  const handleBankChange = async (bankLabel) => {
    setSelectedBank(bankLabel);
    try {
      const token = sessionStorage.getItem("accessToken") || "";
      if (token) {
        await apiClient.post("/banks/update", { label: bankLabel });
      }
      setError("");
    } catch (err) {
      console.error("Errore aggiornamento banca:", err);
      setError(err.response?.data?.detail || err.message);
    }
  };

  // Login
  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    if (!selectedBank) {
      setError("Seleziona una banca prima di procedere.");
      setLoading(false);
      return;
    }

    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);
    formData.append("bank", selectedBank); // ora invia label

    try {
      const response = await fetch(`${baseURL}/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData.toString(),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Username o password non validi");

      const token = data.access_token;
      sessionStorage.setItem("accessToken", token);
      sessionStorage.setItem("apiBaseURL", baseURL);
      sessionStorage.setItem("selectedBank", selectedBank);

      apiClient.defaults.headers.common["Authorization"] = `Bearer ${token}`;

      // Aggiornamento folder e banca post-login
      try {
        if (selectedFolder) await apiClient.post("/folder/update", { folder_path: selectedFolder });
        await apiClient.post("/banks/update", { label: selectedBank });
      } catch (updateErr) {
        console.warn("Errore aggiornamento post-login:", updateErr);
      }

      setIsAuthenticated(true);
      navigate("/");
    } catch (err) {
      console.error("Login Error:", err);
      setError(err.message || "Si è verificato un errore.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <h2 className="title">Welcome back!</h2>
      <form onSubmit={handleSubmit}>
        <div className="api-connection">
          <label htmlFor="apiFolder">
            <FolderOpen size={16} />
            API Folder
          </label>
          <div className="input-group">
            <input
              type="text"
              id="apiFolder"
              value={selectedFolder}
              readOnly
              disabled={loading}
              placeholder="Seleziona la cartella di configurazione..."
            />
            <button
              type="button"
              onClick={handleFolderSelect}
              disabled={loading}
              className="folder-select-btn"
            >
              <FolderOpen size={16} />
              Seleziona
            </button>
          </div>
        </div>

        <div className="bank-selection">
          <label htmlFor="bankSelect">
            <Building size={16} />
            Banca
          </label>
          <div className="select-wrapper">
            <Building size={16} className="select-icon" />
            <select
              id="bankSelect"
              value={selectedBank}
              onChange={(e) => handleBankChange(e.target.value)}
              disabled={loading}
              required
            >
              <option value="">Seleziona una banca...</option>
              {availableBanks.map((bank, index) => (
                <option key={bank.value || index} value={bank.label}>
                  {bank.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="input-field">
          <label htmlFor="username">
            <User size={16} />
            Username
          </label>
          <div className="input-wrapper">
            <User size={16} className="input-icon" />
            <input
              type="text"
              placeholder="Inserisci username"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
              required
            />
          </div>
        </div>

        <div className="input-field">
          <label htmlFor="password">
            <Lock size={16} />
            Password
          </label>
          <div className="input-wrapper">
            <Lock size={16} className="input-icon" />
            <input
              type="password"
              placeholder="Inserisci password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              required
            />
          </div>
        </div>

        {error && <div className="error-message">{error}</div>}

        <button type="submit" disabled={loading} className="login-btn">
          {loading ? (
            <>
              <Loader2 size={16} className="loading-spin" />
              Accesso in corso...
            </>
          ) : (
            <>
              <LogIn size={16} />
              Login
            </>
          )}
        </button>
      </form>
    </div>
  );
}

export default Login;
