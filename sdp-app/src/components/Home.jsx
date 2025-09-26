import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import apiClient from "../api/apiClient";
import "./Home.css";

import sparkasseLogo from "../assets/sparkasse.png";
import civibankLogo from "../assets/civibank.png";
import defaultLogo from "../assets/logo.png";

function Home({ setIsAuthenticated }) {
  const [user, setUser] = useState(null);
  const [iniData, setIniData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const bankLogos = {
    sparkasse: sparkasseLogo,
    civibank: civibankLogo,
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const responseUser = await apiClient.get("/users/me");
        setUser(responseUser.data);

        const baseURL = sessionStorage.getItem("apiBaseURL");
        const token = sessionStorage.getItem("accessToken");

        const responseIni = await fetch(`${baseURL}/folder/ini`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!responseIni.ok) throw new Error("Errore nel recuperare il file INI");

        const iniJson = await responseIni.json();
        setIniData(iniJson.inis); // <-- aggiorniamo qui
      } catch (err) {
        console.error("Errore nel recuperare i dati:", err);
        setError("Impossibile caricare i dati. Prova a fare di nuovo il login.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleLogout = () => {
    sessionStorage.removeItem("accessToken");
    sessionStorage.removeItem("apiBaseURL");
    sessionStorage.removeItem("selectedBank");
    setIsAuthenticated(false);
    navigate("/login");
  };

  const selectedBank = sessionStorage.getItem("selectedBank");
  const logoToShow = bankLogos[selectedBank] || defaultLogo;

  const currentIni = selectedBank && iniData ? iniData[selectedBank] : null;

  return (
    <div className="home-page-wrapper">
      <div className="home-header">
        <img src={logoToShow} alt="Logo Banca" className="home-logo" />
        <h1>Control Center</h1>
      </div>

      <div className="user-info-box">
        {loading && <p>Caricamento profilo...</p>}
        {error && <p className="error-message">{error}</p>}
        {user && (
          <>
            <p>
              Benvenuto, <strong>{user.username}</strong>!
            </p>
            <p>
              Ruolo: <em>{user.role}</em>
            </p>
            {selectedBank && (
              <p>
                Banca selezionata: <strong>{selectedBank}</strong>
              </p>
            )}
          </>
        )}
      </div>

      <div className="home-button-container">
        {loading && <p>Caricamento dati INI...</p>}

        {!loading ? (
          currentIni?.data?.DEFAULT?.filemetadati ? (
            <Link
              to="/ingest"
              state={{ metadataFilePath: currentIni.data.DEFAULT.filemetadati }}
            >
              <button className="btn">Ingest</button>
            </Link>
          ) : (
            <p className="error-message">
              File INI non trovato o percorso mancante per la banca selezionata.
            </p>
          )
        ) : (
          <p>Caricamento dati INI...</p>
        )}

        <Link to="/report">
          <button className="btn">Report</button>
        </Link>
        <Link to="/settings">
          <button className="btn">Settings</button>
        </Link>
        <div className="logout-container">
          <button className="btn" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>
    </div>
  );
}

export default Home;
