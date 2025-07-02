// src/components/Home.jsx

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom'; // Importa useNavigate
import apiClient from '../api/apiClient';
import './Home.css';
import logoImage from '../assets/logo.png';

function Home({ setIsAuthenticated }) { // Ricevi setIsAuthenticated come prop
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate(); // Inizializza useNavigate

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const response = await apiClient.get('/users/me');
        setUser(response.data);
      } catch (err) {
        console.error("Errore nel recuperare i dati utente:", err);
        setError('Impossibile caricare i dati del profilo. Prova a fare di nuovo il login.');
      } finally {
        setLoading(false);
      }
    };

    fetchUserData();
  }, []);

  const handleLogout = () => {
    sessionStorage.removeItem("accessToken"); // Pulisci il token
    sessionStorage.removeItem("apiBaseURL"); // Pulisci l'URL base
    setIsAuthenticated(false); // Aggiorna lo stato di autenticazione
    navigate("/login"); // Reindirizza alla pagina di login
  };

  return (
    <div className="home-page-wrapper">
      <div className="home-header">
        <img src={logoImage} alt="Il Mio Logo" className="home-logo" />
        <h1>Control Center</h1>
      </div>

      <div className="user-info-box">
        {loading && <p>Caricamento profilo...</p>}
        {error && <p className="error-message">{error}</p>}
        {user && (
          <>
            <p>Benvenuto, <strong>{user.username}</strong>!</p>
            <p>Ruolo: <em>{user.role}</em></p>
          </>
        )}
      </div>

      <div className="home-button-container">
        <Link to="/ingest"><button className="btn">Ingest</button></Link>
        <Link to="/report"><button className="btn">Report</button></Link>
        <Link to="/settings"><button className="btn">Settings</button></Link>
          <div className="logout-container">
        <button className="btn" onClick={handleLogout}>Logout</button>
      </div>
      </div>
    </div>
  );
}

export default Home;