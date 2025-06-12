// src/components/Home.jsx

import React, { useState, useEffect } from 'react'; // Importa useState e useEffect
import { Link } from 'react-router-dom';
import apiClient from '../api/apiClient'; // Importa il nostro client API
import './Home.css';
import logoImage from '../assets/logo.png';

function Home() {
  // 1. Aggiungiamo gli stati per memorizzare i dati dell'utente, il caricamento e gli errori
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // 2. Usiamo useEffect per eseguire la chiamata API quando il componente viene montato
  useEffect(() => {
    const fetchUserData = async () => {
      try {
        // La chiamata all'endpoint protetto.
        // L'interceptor in apiClient aggiunge automaticamente il token.
        const response = await apiClient.get('/users/me');
        setUser(response.data); // Salviamo i dati dell'utente nello stato
      } catch (err) {
        console.error("Errore nel recuperare i dati utente:", err);
        setError('Impossibile caricare i dati del profilo. Prova a fare di nuovo il login.');
        // In un'app più complessa, qui potresti forzare il logout
      } finally {
        setLoading(false); // In ogni caso, il caricamento è terminato
      }
    };

    fetchUserData();
  }, []); // L'array vuoto [] assicura che l'effetto venga eseguito solo una volta

  return (
    <div className="home-page-wrapper">
      <div className="home-header">
        <img src={logoImage} alt="Il Mio Logo" className="home-logo" />
        <h1>Control Center</h1>
      </div>
      
      {/* 3. Mostriamo le informazioni dell'utente */}
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
      </div>
    </div>
  );
}

export default Home;