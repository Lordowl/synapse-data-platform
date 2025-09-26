import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { open } from "@tauri-apps/plugin-dialog";
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
        const token = sessionStorage.getItem("accessToken") || "";

        // Folder corrente
        const folderResp = await fetch(`${baseURL}/folder/current`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (folderResp.ok) {
          const folderData = await folderResp.json();
          if (folderData.folder_path) {
            setSelectedFolder(folderData.folder_path);
          }
        }

        // Banche disponibili
        const banksResp = await fetch(`${baseURL}/banks/available`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (banksResp.ok) {
          const banksData = await banksResp.json();
          setAvailableBanks(banksData.banks || []);
          if (banksData.current_bank) {
            setSelectedBank(banksData.current_bank);
          }
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
    const folderPath = Array.isArray(selected) ? selected[0] : selected;
    setSelectedFolder(folderPath);

    try {
      const response = await fetch(`${baseURL}/folder/update`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${sessionStorage.getItem("accessToken") || ""}`,
        },
        body: JSON.stringify({ folder_path: folderPath }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Errore aggiornamento folder path");
      }

      console.log("Folder aggiornato correttamente");
    } catch (err) {
      console.error("Errore aggiornamento folder:", err);
      setError(err.message);
    }
  };

  // Cambia banca
  const handleBankChange = async (bankValue) => {
    setSelectedBank(bankValue);
    try {
      const token = sessionStorage.getItem("accessToken") || "";
      const response = await fetch(`${baseURL}/banks/update`, { // <-- correzione banks
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ value: bankValue }), // backend si aspetta { value: "bank1" }
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Errore aggiornamento banca");
      }

      console.log("Banca aggiornata correttamente!");
    } catch (err) {
      console.error("Errore aggiornamento banca:", err);
      setError(err.message);
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
      setIsAuthenticated(true);
      navigate("/");

      // Aggiorna folder e banca dopo login
      const updatePromises = [];
      if (selectedFolder) {
        updatePromises.push(
          fetch(`${baseURL}/folder/update`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ folder_path: selectedFolder }),
          })
        );
      }
      if (selectedBank) {
        updatePromises.push(
          fetch(`${baseURL}/banks/update`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ value: selectedBank }),
          })
        );
      }
      await Promise.all(updatePromises);
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
          <label htmlFor="apiFolder">API Folder</label>
          <div className="input-group">
            <input type="text" id="apiFolder" value={selectedFolder} readOnly disabled={loading} />
            <button type="button" onClick={handleFolderSelect} disabled={loading}>
              Seleziona Cartella
            </button>
          </div>
        </div>

        <div className="bank-selection">
          <label htmlFor="bankSelect">Banca</label>
          <select
            id="bankSelect"
            value={selectedBank}
            onChange={(e) => handleBankChange(e.target.value)}
            disabled={loading}
            required
          >
            <option value="">Seleziona una banca...</option>
            {availableBanks.map((bank) => (
              <option key={bank.value} value={bank.value}>
                {bank.label}
              </option>
            ))}
          </select>
        </div>

        <label>Username</label>
        <input
          type="text"
          placeholder="Username"
          id="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={loading}
          required
        />

        <label>Password</label>
        <input
          type="password"
          placeholder="Password"
          id="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={loading}
          required
        />

        {error && <p className="error-message">{error}</p>}

        <button type="submit" disabled={loading}>
          {loading ? "Accesso in corso..." : "Login"}
        </button>
      </form>
    </div>
  );
}

export default Login;
