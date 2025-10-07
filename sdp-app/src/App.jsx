// src/App.jsx

import { Routes, Route, Navigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { ToastContainer } from 'react-toastify';
import apiClient from "./api/apiClient";
import { autoUpdate } from "./utils/updater";
import { startInactivityTracking, stopInactivityTracking } from "./utils/sessionTimeout";

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
      const apiBaseURL = sessionStorage.getItem("apiBaseURL");

      if (!token || !apiBaseURL) {
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
        sessionStorage.removeItem("apiBaseURL");
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();

    autoUpdate();
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      startInactivityTracking();
    }

    return () => {
      stopInactivityTracking();
    };
  }, [isAuthenticated]);

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="App">
        <ToastContainer
        position="bottom-right" // Puoi scegliere: bottom-left, bottom-right, bottom-center, top-left, top-right, top-center
        autoClose={2000}       // Durata di default in ms
        hideProgressBar={false} // Mostra o nasconde la barra di progresso
        newestOnTop={true}      // I toast più recenti sopra
        closeOnClick             // Si chiude al click
      />
      <Routes>
        {!isAuthenticated ? (
          <>
            <Route path="/login" element={<Login setIsAuthenticated={setIsAuthenticated} />} />
            <Route path="*" element={<Navigate to="/login" />} />
          </>
        ) : (
          <>
            <Route path="/" element={<Home setIsAuthenticated={setIsAuthenticated} />} /> {/* PASSAGGIO FONDAMENTALE */}
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