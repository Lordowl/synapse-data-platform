// src/App.jsx

import { Routes, Route, Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { ToastContainer } from 'react-toastify';
import apiClient from "./api/apiClient";
import { autoUpdate } from "./utils/updater"; // ✅ IMPORTA IL MODULO

import Home from "./components/Home";
import Ingest from "./components/Ingest";
import Report from "./components/Report";
import Settings from "./components/Settings";
import Login from "./components/Login";
import "./styles.css";

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      const token = sessionStorage.getItem("accessToken");
      if (!token) {
        setIsAuthenticated(false);
        setIsLoading(false);
        return;
      }

      try {
        await apiClient.get("/users/me");
        setIsAuthenticated(true);
      } catch (error) {
        console.error("Token verification failed:", error);
        setIsAuthenticated(false);
        sessionStorage.removeItem("accessToken");
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();

    // ✅ Avvia controllo aggiornamenti all'avvio
    autoUpdate();
  }, []);

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="App">
      <ToastContainer />
      <Routes>
        {!isAuthenticated ? (
          <>
            <Route path="/login" element={<Login setIsAuthenticated={setIsAuthenticated} />} />
            <Route path="*" element={<Navigate to="/login" />} />
          </>
        ) : (
          <>
            <Route path="/" element={<Home />} />
            <Route path="/ingest" element={<Ingest />} />
            <Route path="/report" element={<Report />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" />} />
          </>
        )}
      </Routes>
    </div>
  );
}

export default App;
