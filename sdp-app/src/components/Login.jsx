// src/components/Login.jsx (MODIFICATO)

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/apiClient";
import "./Login.css";

function Login({ setIsAuthenticated }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(""); // Usiamo uno stato per l'errore per mostrarlo nella UI
  const [loading, setLoading] = useState(false); // Stato di caricamento per disabilitare il pulsante

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(""); // Pulisce l'errore precedente
    setLoading(true); // Inizia il caricamento

    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const response = await apiClient.post('/auth/token', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
      
      const token = response.data.access_token;
      localStorage.setItem("accessToken", token);
      setIsAuthenticated(true);
      navigate("/home");

    } catch (err) {
      console.error("Login Error:", err); // Logghiamo l'errore completo per il debug

      // --- QUI C'È LA NUOVA LOGICA DI GESTIONE ERRORI ---
      if (err.response) {
        // Il server ha risposto con un codice di errore (es. 401, 404)
        // Solitamente un errore di credenziali
        setError(err.response.data.detail || "Username o password non validi.");
      } else if (err.request) {
        // La richiesta è stata fatta ma non c'è stata risposta (server spento o irraggiungibile)
        setError("Impossibile connettersi al server");
      } else {
        // Errore generico (es. errore nella configurazione della richiesta)
        setError("Si è verificato un errore imprevisto.");
      }
    } finally {
        setLoading(false); // Fine del caricamento, in ogni caso
    }
  };

  return (
    <div className="login-page">
      <h2 className="title">Welcome back!</h2>
      <form onSubmit={handleSubmit}>
        <label>Username</label>
        <input
          type="text"
          placeholder="Username"
          id="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={loading} // Disabilita durante il caricamento
        />
        <label>Password</label>
        <input
          type="password"
          placeholder="Password"
          id="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={loading} // Disabilita durante il caricamento
        />
        
        {/* Mostra il messaggio di errore se presente */}
        {error && <p className="error-message">{error}</p>}

        <button type="submit" disabled={loading}>
            {loading ? 'Accesso in corso...' : 'Login'}
        </button>
      </form>
    </div>
  );
}

export default Login;