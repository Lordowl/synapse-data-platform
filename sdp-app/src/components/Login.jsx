import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { open } from "@tauri-apps/plugin-dialog";
import "./Login.css";

function Login({ setIsAuthenticated }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [selectedFolder, setSelectedFolder] = useState(""); 
  const [apiAddress, setApiAddress] = useState("http://127.0.0.1");
  const [apiPort, setApiPort] = useState("8000");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const baseURL = `${apiAddress}:${apiPort}/api/v1`;

  const handleFolderSelect = async () => {
    const selected = await open({
      directory: true,
      multiple: false,
      title: 'Seleziona Cartella API'
    });

    if (!selected) return;

    const folderPath = Array.isArray(selected) ? selected[0] : selected;
    setSelectedFolder(folderPath);

    // Invia il path tramite POST appena viene selezionato
    try {
      const response = await fetch(`${baseURL}/folder/update`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${sessionStorage.getItem("accessToken") || ""}`
        },
        body: JSON.stringify({ folder_path: folderPath })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Errore nell'invio del folder path.");
      }

      console.log("Folder path aggiornato correttamente!");
    } catch (err) {
      console.error("Errore aggiornamento folder path:", err);
      setError(err.message);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const response = await fetch(`${baseURL}/auth/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString()
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Username o password non validi.");
      }

      const token = data.access_token;

      sessionStorage.setItem("accessToken", token);
      sessionStorage.setItem("apiBaseURL", baseURL);
      setIsAuthenticated(true);
      navigate("/");

      // Se il folder era già selezionato prima del login, lo inviamo subito
      if (selectedFolder) {
        await fetch(`${baseURL}/folder/update`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ folder_path: selectedFolder })
        });
      }

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
          <div className="api-address-port">
            <div className="input-group">
              <input
                type="text"
                placeholder="Select API Folder"
                id="apiFolder"
                value={selectedFolder}
                readOnly
                disabled={loading}
              />
              <button type="button" onClick={handleFolderSelect} disabled={loading}>
                Seleziona Cartella
              </button>
            </div>
          </div>
        </div>

        <label>Username</label>
        <input
          type="text"
          placeholder="Username"
          id="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={loading}
        />
        <label>Password</label>
        <input
          type="password"
          placeholder="Password"
          id="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={loading}
        />

        {error && <p className="error-message">{error}</p>}

        <button type="submit" disabled={loading}>
          {loading ? 'Accesso in corso...' : 'Login'}
        </button>
      </form>
    </div>
  );
}

export default Login;
