import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Database,
  BarChart3,
  Settings,
  LogOut,
  User,
  Building,
  Layers,
} from "lucide-react";
import apiClient from "../api/apiClient";
import { useAppContext } from "../context/AppContext";
import "./Home.css";

import sparkasseLogo from "../assets/sparkasse.png";
import civibankLogo from "../assets/civibank.png";
import defaultLogo from "../assets/logo.png";

function Home({ setIsAuthenticated }) {
  const { metadataFilePath } = useAppContext();
  const [user, setUser] = useState(null);
  const [iniData, setIniData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const bankLogos = {
    Sparkasse: sparkasseLogo,
    CiviBank: civibankLogo,
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Usa apiClient per entrambe le chiamate per coerenza
        const [responseUser, responseIni] = await Promise.all([
          apiClient.get("/users/me"),
          apiClient.get("/folder/ini"),
        ]);

        setUser(responseUser.data);
        setIniData(responseIni.data.inis);
      } catch (err) {
        console.error("Errore nel recuperare i dati:", err);
        setError(
          "Impossibile caricare i dati. Prova a fare di nuovo il login."
        );
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
        <h1>Cruscotto operativo</h1>
      </div>

      <div className="user-info-box">
        {loading && (
          <div className="loading-state">
            <User className="loading-icon" />
            <p>Caricamento profilo...</p>
          </div>
        )}
        {error && <p className="error-message">{error}</p>}
        {user && (
          <div className="user-details">
            <div className="user-item">
              <User size={20} />
              <span>
                Benvenuto, <strong>{user.username}</strong>!
              </span>
            </div>
            <div className="user-item">
              <Settings size={20} />
              <span>
                Ruolo: <em>{user.role}</em>
              </span>
            </div>
            {selectedBank && (
              <div className="user-item">
                <Building size={20} />
                <span>
                  Banca: <strong>{selectedBank}</strong>
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="home-button-container">
        <div className="main-actions">
          {/* Mostra il pulsante Ingest solo se l'utente ha il permesso 'ingest' */}
          {user?.permissions?.includes("ingest") &&
            (!loading ? (
              // Usa metadataFilePath dal context se disponibile, altrimenti dal file INI
              metadataFilePath || currentIni?.data?.DEFAULT?.filemetadati ? (
                <Link
                  to="/ingest"
                  state={{
                    metadataFilePath:
                      metadataFilePath || currentIni.data.DEFAULT.filemetadati,
                  }}
                  className="nav-link"
                >
                  <button className="btn btn-primary">
                    <Layers size={20} />
                    <span>Ingestion</span>
                  </button>
                </Link>
              ) : (
                <div className="error-state">
                  <p className="error-message">
                    File metadati non trovato. Caricalo da Settings o configura
                    il file INI.
                  </p>
                </div>
              )
            ) : (
              <div className="loading-state">
                <Layers className="loading-icon" />
                <p>Caricamento dati INI...</p>
              </div>
            ))}

          {/* Mostra il pulsante Reportistica solo se l'utente ha il permesso 'reportistica' */}
          {user?.permissions?.includes("reportistica") && (
            <Link to="/report" className="nav-link">
              <button className="btn btn-primary">
                <BarChart3 size={20} />
                <span>Reportistica</span>
              </button>
            </Link>
          )}
        </div>

        <div className="secondary-actions">
          <Link to="/settings" className="nav-link">
            <button className="btn btn-outline">
              <Settings size={20} />
              <span>Impostazioni</span>
            </button>
          </Link>

          <button className="btn btn-danger logout-btn" onClick={handleLogout}>
            <LogOut size={20} />
            <span>Esci</span>
          </button>
        </div>
      </div>

      <div className="version-footer">
        <small style={{ color: "#666", fontSize: "12px" }}>
          Versione 0.2.26{" "}
        </small>
      </div>
    </div>
  );
}

export default Home;
