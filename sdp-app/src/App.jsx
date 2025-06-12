// src/App.jsx (MODIFICATO)

import { Routes, Route, Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
// NON USIAMO PIÙ INVOKE
// import { invoke } from "@tauri-apps/api/core";
import apiClient from "./api/apiClient"; // IMPORTIAMO IL CLIENT API

import Home from "./components/Home";
import Ingest from "./components/Ingest";
import Report from "./components/Report";
import Settings from "./components/Settings";
import Login from "./components/Login";
import "./styles.css";

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true); // Aggiungiamo uno stato di caricamento

  useEffect(() => {
    const checkAuth = async () => {
      // Il nome della chiave è 'authToken' come nel tuo codice originale
      const token = localStorage.getItem("accessToken");
      if (!token) {
        setIsAuthenticated(false);
        setIsLoading(false); // Finito di caricare
        return;
      }

      try {
        // Facciamo una chiamata a un endpoint protetto per verificare il token.
        // /users/me è perfetto per questo.
        // L'interceptor in apiClient aggiungerà automaticamente il token all'header.
        await apiClient.get("/users/me");
        
        // Se la chiamata ha successo, il token è valido.
        setIsAuthenticated(true);
      } catch (error) {
        console.error("Token verification failed:", error);
        setIsAuthenticated(false);
        localStorage.removeItem("accessToken"); // Rimuove il token non valido o scaduto
      } finally {
        setIsLoading(false); // In ogni caso, abbiamo finito di caricare
      }
    };

    checkAuth();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("authToken");
    setIsAuthenticated(false);
  };

  // Mostra uno spinner o un messaggio di caricamento mentre verifichiamo il token
  if (isLoading) {
    return <div>Verifica autenticazione...</div>;
  }

  // Il resto della tua logica di routing è quasi perfetta.
  // Un piccolo miglioramento: la rotta "/" dovrebbe puntare a /login, non a se stessa.
  return (
    <div className="app-container">
      {isAuthenticated && (
        <nav className="app-navbar">
          <button onClick={handleLogout} className="logout-button">
            Logout
          </button>
        </nav>
      )}
      <div className="app-content">
        <Routes>
          <Route 
            path="/login" 
            element={
              !isAuthenticated ? <Login setIsAuthenticated={setIsAuthenticated} /> : <Navigate to="/home" replace />
            }
          />
          <Route 
            path="/home" 
            element={isAuthenticated ? <Home /> : <Navigate to="/login" replace />} 
          />
          <Route 
            path="/ingest" 
            element={isAuthenticated ? <Ingest /> : <Navigate to="/login" replace />} 
          />
          <Route 
            path="/report" 
            element={isAuthenticated ? <Report /> : <Navigate to="/login" replace />} 
          />
          <Route 
            path="/settings" 
            element={isAuthenticated ? <Settings /> : <Navigate to="/login" replace />} 
          />
          {/* Reindirizzamento principale */}
          <Route 
            path="/" 
            element={<Navigate to={isAuthenticated ? "/home" : "/login"} replace />} 
          />
        </Routes>
      </div>
    </div>
  );
}
export default App;