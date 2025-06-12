// src/components/Login.jsx

import React, { useState } from "react";
import { useNavigate } from "react-router-dom"; // <-- IMPORTANTE: Importa l'hook useNavigate
import apiClient from "../api/apiClient";
import "./Login.css";

function Login({ setIsAuthenticated }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Inizializza l'hook per poterlo usare dopo
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const response = await apiClient.post('/auth/token', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
      
      const token = response.data.access_token;
      sessionStorage.setItem("accessToken", token);
      setIsAuthenticated(true);
      
      // Ora questa chiamata funzionerà e reindirizzerà l'utente
      // Nota: nel tuo App.jsx la rotta per la Home è "/dashboard"
      navigate("/dashboard"); 

    } catch (err) {
      console.error("Login Error:", err);

      // Logica robusta per la gestione degli errori
      if (err.response) {
        // Il server ha risposto (es. 401 Unauthorized)
        setError(err.response.data.detail || "Username o password non validi.");
      } else if (err.request) {
        // La richiesta è partita ma non c'è stata risposta (server spento)
        setError("Impossibile connettersi al server. Verificare che sia attivo.");
      } else {
        // Qualsiasi altro errore
        setError("Si è verificato un errore imprevisto.");
      }
    } finally {
      setLoading(false);
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
        
        {/* Mostra il messaggio di errore nella UI */}
        {error && <p className="error-message">{error}</p>}

        <button type="submit" disabled={loading}>
          {loading ? 'Accesso in corso...' : 'Login'}
        </button>
      </form>
    </div>
  );
}

export default Login;