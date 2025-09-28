// src/components/Report/Report.jsx
import { useState, useMemo, useEffect, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  BarChart3, Filter, Play, FileText, PlusSquare, Copy, UploadCloud, Send,
  RefreshCw, CheckCircle, XCircle, AlertTriangle, ListChecks, Eye, AlertCircle,
  Calendar, Clock
} from "lucide-react";
import "./Report.css";
import apiClient from "../api/apiClient";

// --- Configurazione per periodicità ---
const PERIODICITY_CONFIG = {
  settimanale: {
    label: "Settimanale",
    icon: Clock,
    timeUnit: "settimana",
    timeLabel: "Settimana",
    dateFormat: "S{week}",
    defaultFilters: {}
  },
  mensile: {
    label: "Mensile",
    icon: Calendar,
    timeUnit: "mese",
    timeLabel: "Mese",
    dateFormat: "M{month}",
    defaultFilters: {}
  }
};

// --- Dati di Esempio Unificati (mappati alla nuova struttura DB) ---
const initialReportTasks = [
  {
    id: 1,
    banca: "Sparkasse",
    anno: 2024,
    settimana: 39,
    nome_file: "Clienti_ERP_S39.xlsx",
    package: "Anagrafiche Core",
    disponibilita_server: true,
    ultima_modifica: "2024-09-28T08:00:00Z",
    dettagli: "OK - Aggiornato alla settimana corretta, record presenti.",
    created_at: "2024-09-01T10:00:00Z",
    updated_at: "2024-09-28T08:00:00Z",
    selected: false,
  },
  {
    id: 2,
    banca: "Sparkasse",
    anno: 2024,
    settimana: 39,
    nome_file: "Inventario_S39.csv",
    package: "Logistica",
    disponibilita_server: true,
    ultima_modifica: "2024-09-28T08:30:00Z",
    dettagli: "ATTENZIONE: Campo settimana mancante nel file!",
    created_at: "2024-09-01T10:00:00Z",
    updated_at: "2024-09-28T08:30:00Z",
    selected: false,
  },
  {
    id: 3,
    banca: "Sparkasse",
    anno: 2024,
    settimana: null,
    nome_file: "Report_Vendite_M09.xlsx",
    package: "Commerciale",
    disponibilita_server: false,
    ultima_modifica: null,
    dettagli: "File non prodotto da IRION per il mese corrente.",
    created_at: "2024-09-01T10:00:00Z",
    updated_at: "2024-09-28T08:00:00Z",
    selected: false,
  },
  {
    id: 4,
    banca: "CiviBank",
    anno: 2024,
    settimana: null,
    nome_file: "Budget_Analisi_M09.xlsx",
    package: "Controllo Gestione",
    disponibilita_server: true,
    ultima_modifica: "2024-09-15T10:30:00Z",
    dettagli: "File aggiornato correttamente per il mese.",
    created_at: "2024-09-01T10:00:00Z",
    updated_at: "2024-09-15T10:30:00Z",
    selected: false,
  }
];

// --- Funzioni Helper per la nuova struttura ---
const getDisponibilitaServerBadge = (disponibilita_server) => {
  if (disponibilita_server === true) {
    return 'status-badge-success';
  } else if (disponibilita_server === false) {
    return 'status-badge-danger';
  }
  return 'status-badge-muted';
};

const getDisponibilitaServerText = (disponibilita_server) => {
  if (disponibilita_server === true) {
    return 'Disponibile';
  } else if (disponibilita_server === false) {
    return 'Non disponibile';
  }
  return 'N/D';
};

const formatDateTime = (dateString) => {
  if (!dateString) return 'N/D';
  try {
    return new Date(dateString).toLocaleString('it-IT', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (e) {
    return 'N/D';
  }
};

const formatDate = (dateString) => {
  if (!dateString) return 'N/D';
  try {
    return new Date(dateString).toLocaleDateString('it-IT');
  } catch (e) {
    return 'N/D';
  }
};

// --- Componente Principale Report Unificato ---
function Report() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Leggi la periodicità dai parametri URL o default a 'settimanale'
  const currentPeriodicity = searchParams.get('type') || 'settimanale';
  const periodicityConfig = PERIODICITY_CONFIG[currentPeriodicity] || PERIODICITY_CONFIG.settimanale;

  const [filters, setFilters] = useState({
    banca: "Tutti",
    package: "Tutti",
    // Filtri dinamici basati sulla periodicità (solo mese per report mensili)
    ...periodicityConfig.defaultFilters,
    periodicity: currentPeriodicity // Mantieni per retrocompatibilità
  });

  const [reportTasks, setReportTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTaskIds, setSelectedTaskIds] = useState(new Set());
  const [repoUpdateInfo, setRepoUpdateInfo] = useState({ anno: 2025, settimana: 29, semaforo: 0 });
  const [loadingActions, setLoadingActions] = useState({
    global: null,
  });
  const [toast, setToast] = useState({ message: '', type: 'info', visible: false });

  // Toast functions
  const showToast = useCallback((message, type = 'info') => {
    setToast({ message, type, visible: true });
  }, []);

  const getToastIcon = (type) => {
    switch (type) {
      case 'success': return <CheckCircle size={20} />;
      case 'error': return <XCircle size={20} />;
      case 'warning': return <AlertTriangle size={20} />;
      default: return <AlertCircle size={20} />;
    }
  };

  // Toast management effects
  useEffect(() => {
    if (toast.visible) {
      const timer = setTimeout(() => {
        setToast(prev => ({ ...prev, visible: false }));
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [toast.visible]);

  // Estrai valori univoci per i dropdown dai dati
  const uniqueBanks = useMemo(() => {
    const banks = [...new Set(reportTasks.map(task => task.banca).filter(Boolean))];
    return ["Tutti", ...banks];
  }, [reportTasks]);

  const uniquePackages = useMemo(() => {
    const packages = [...new Set(reportTasks.map(task => task.package).filter(Boolean))];
    return ["Tutti", ...packages];
  }, [reportTasks]);

  // Aggiorna i filtri quando cambia la periodicità
  useEffect(() => {
    setFilters(prev => ({
      ...prev,
      ...periodicityConfig.defaultFilters,
      periodicity: currentPeriodicity
    }));
    setSelectedTaskIds(new Set()); // Reset selezione
  }, [currentPeriodicity]);

  // Funzione per caricare le informazioni di repo update
  const fetchRepoUpdateInfo = useCallback(async () => {
    try {
      const token = apiClient.getToken();
      const response = await fetch("http://127.0.0.1:8001/api/v1/repo-update/", {
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        }
      });

      if (response.ok) {
        const data = await response.json();
        setRepoUpdateInfo(data);
      } else {
        console.error("Errore nel caricamento repo update info:", response.status);
        // Mantiene i valori di default se non riesce a caricare
      }
    } catch (error) {
      console.error("Errore nella fetch repo update info:", error);
      // Mantiene i valori di default se non riesce a caricare
    }
  }, []);

  // Fetch reportistica data from API
  useEffect(() => {
    const isInitialLoad = { current: true };

    const authenticateAndFetchData = async () => {
      try {
        // Only show loading spinner on initial load
        if (isInitialLoad.current) {
          setLoading(true);
        }

        // Always get a fresh token to avoid expiration issues
        const authResponse = await apiClient.post('/auth/token',
          'username=admin&password=admin',
          { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
        );
        const token = authResponse.data.access_token;
        sessionStorage.setItem('accessToken', token);

        // Now fetch the reportistica data
        const response = await apiClient.get('/reportistica/');
        setReportTasks(response.data);

        // Fetch repo update info
        await fetchRepoUpdateInfo();
      } catch (error) {
        console.error('Error fetching reportistica data:', error);

        // Only show toast on initial load to avoid spam
        if (isInitialLoad.current) {
          showToast('Errore nel caricamento dei dati reportistica', 'error');
          // If auth fails, set empty data to avoid infinite loading
          setReportTasks([]);
        }
      } finally {
        if (isInitialLoad.current) {
          setLoading(false);
          isInitialLoad.current = false;
        }
      }
    };

    // Fetch data initially
    authenticateAndFetchData();

    // Set up polling every 3 seconds
    const interval = setInterval(() => {
      authenticateAndFetchData();
    }, 3000);

    // Cleanup interval on unmount
    return () => clearInterval(interval);
  }, [fetchRepoUpdateInfo, showToast]);

  // Status basato sul semaforo dal repo_update_info
  const semaphoreStatus = useMemo(() => {
    switch (repoUpdateInfo.semaforo) {
      case 1:
        return 'success'; // Verde
      case 2:
        return 'warning'; // Arancione
      case 0:
      default:
        return 'danger'; // Rosso
    }
  }, [repoUpdateInfo.semaforo]);


  // Funzione per cambiare periodicità
  const handlePeriodicityChange = (newPeriodicity) => {
    setSearchParams({ type: newPeriodicity });
  };

  const handleFilterChange = (filterName, value) => {
    setFilters(prev => ({ ...prev, [filterName]: value }));
  };

  // Filtra task per periodicità corrente + altri filtri
  const filteredReportTasks = useMemo(() => {
    return reportTasks.filter(task => {
      // Filtro per periodicità: settimanali (hanno settimana) vs mensili (non hanno settimana)
      const isWeeklyTask = task.settimana !== null;
      const isMonthlyTask = task.settimana === null;
      const matchesPeriodicity =
        (currentPeriodicity === 'settimanale' && isWeeklyTask) ||
        (currentPeriodicity === 'mensile' && isMonthlyTask);

      // Filtro per banca (gestisce valori null)
      const matchesBanca = !filters.banca || filters.banca === "Tutti" || task.banca === filters.banca || (!task.banca && filters.banca === "Tutti");

      // Filtro per package
      const matchesPackage = !filters.package || filters.package === "Tutti" || task.package === filters.package;

      return matchesPeriodicity && matchesBanca && matchesPackage;
    });
  }, [reportTasks, currentPeriodicity, filters]);

  const handleTaskSelection = (taskId) => {
    setSelectedTaskIds(prev => {
      const newSelection = new Set(prev);
      if (newSelection.has(taskId)) {
        newSelection.delete(taskId);
      } else {
        newSelection.add(taskId);
      }
      return newSelection;
    });
  };

  const handleSelectAllTasks = (e) => {
    if (e.target.checked) {
      setSelectedTaskIds(new Set(filteredReportTasks.map(t => t.id)));
    } else {
      setSelectedTaskIds(new Set());
    }
  };
  
  const simulateApiCall = (duration = 1500) => 
    new Promise(resolve => setTimeout(resolve, duration));

  const handleGlobalAction = async (actionName) => {
    if (actionName === 'esegui' && selectedTaskIds.size === 0) {
      showToast("Nessun task selezionato per l'esecuzione.", "warning");
      return;
    }
    
    setLoadingActions(prev => ({ ...prev, global: actionName }));
    showToast(`Avvio azione globale '${actionName}'...`, "info");
    await simulateApiCall(2500 + Math.random() * 2000);

    if (actionName === 'esegui') {
      setReportTasks(prevTasks => prevTasks.map(t => {
        if (selectedTaskIds.has(t.id)) {
          if (t.serverStatus !== 'presente' && t.serverStatus !== 'mancante_no_dati_irion') 
            return {...t, serverStatus: 'presente', serverCheckDetails: 'Verifica OK tramite ESEGUI'};
          if (t.sharepointStatus !== 'copiato_ok') 
            return {...t, sharepointStatus: 'copiato_ok', sharepointCopyDate: new Date().toISOString()};
          if (t.powerBIStatus !== 'importato_precheck') 
            return {...t, powerBIStatus: 'importato_precheck'};
        }
        return t;
      }));
      showToast(`Esecuzione ${selectedTaskIds.size} task completata.`, "success");
      setSelectedTaskIds(new Set());
    } else if (actionName === 'creaPeriodo') {
      setReportTasks(prevTasks => prevTasks.map(t => 
        (selectedTaskIds.has(t.id) && t.serverStatus === 'mancante_no_dati_irion') ? 
        {...t, serverStatus: 'presente', serverCheckDetails: `${periodicityConfig.timeLabel} creata per file mancante`} : t
      ));
      showToast(`Azione 'Crea ${periodicityConfig.timeLabel}' applicata ai task selezionati.`, "success");
    } else {
      showToast(`Azione globale '${actionName}' completata (simulazione).`, "success");
    }
    setLoadingActions(prev => ({ ...prev, global: null }));
  };

  const allTasksSelected = filteredReportTasks.length > 0 && selectedTaskIds.size === filteredReportTasks.length;
  const isAnyTaskSelected = selectedTaskIds.size > 0;
  const canImportPBI = filteredReportTasks.length > 0 && filteredReportTasks.every(task => 
    task.sharepointStatus === 'copiato_ok' || task.serverStatus === 'mancante_no_dati_irion'
  );

  // Icona dinamica per il tipo di report
  const ReportIcon = periodicityConfig.icon;

  return (
    <div className="report-container">

      
      <div className="report-content-wrapper">
        <header className="report-header-container">
          <div className="report-header">
            <div className="report-header-title-group">
              <div className="report-header-icon-bg">
                <ReportIcon className="report-header-icon" /> {/* Icona dinamica */}
              </div>
              <div>
                <h1 className="report-header-title">
                  Cruscotto Reportistica
                </h1>
                <p className="report-header-subtitle">
                  Elaborazione e monitoraggio report.
                </p>
              </div>
            </div>
            {/* Pulsante Indietro rimane qui, i pulsanti di periodicità sono stati spostati */}
            <button 
              onClick={() => navigate("/home")} 
              className="btn btn-outline report-header-back-button" 
              disabled={loadingActions.global !== null || loadingActions.taskAction !== null}
            >
              ← Indietro
            </button>
          </div>
        </header>


        <section className="periodicity-selector-section">
          <div className="periodicity-toggle">
            <button 
              className={`btn ${currentPeriodicity === 'settimanale' ? 'btn-primary-action' : 'btn-outline'} periodicity-toggle-btn`}
              onClick={() => handlePeriodicityChange('settimanale')}
              disabled={loadingActions.global !== null}
            >
              <Clock size={16} className="btn-icon-sm"/> Report Settimanali
            </button>
            <button 
              className={`btn ${currentPeriodicity === 'mensile' ? 'btn-primary-action' : 'btn-outline'} periodicity-toggle-btn`}
              onClick={() => handlePeriodicityChange('mensile')}
              disabled={loadingActions.global !== null}
            >
              <Calendar size={16} className="btn-icon-sm"/> Report Mensili
            </button>
          </div>
        </section>


        <section className="report-filters-section">
          <div className="filter-row">
            <div className="filter-group">
              <label htmlFor="banca-filter" className="form-label">Banca</label>
              <select
                id="banca-filter"
                className="form-select"
                value={filters.banca}
                onChange={e => handleFilterChange('banca', e.target.value)}
                disabled={loadingActions.global !== null}
              >
                {uniqueBanks.map(bank => (
                  <option key={bank} value={bank}>{bank}</option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label htmlFor="package-filter" className="form-label">Package</label>
              <select
                id="package-filter"
                className="form-select"
                value={filters.package}
                onChange={e => handleFilterChange('package', e.target.value)}
                disabled={loadingActions.global !== null}
              >
                {uniquePackages.map(pkg => (
                  <option key={pkg} value={pkg}>{pkg}</option>
                ))}
              </select>
            </div>

            <div className="filter-group overall-status-group">
              <label className="form-label">Status Complessivo</label>
              <div className="status-indicators">
                <span
                  className={`status-dot ${semaphoreStatus === 'success' ? 'active-success' : ''}`}
                  title="Verde (Semaforo = 1)"
                ></span>
                <span
                  className={`status-dot ${semaphoreStatus === 'warning' ? 'active-warning' : ''}`}
                  title="Arancione (Semaforo = 2)"
                ></span>
                <span
                  className={`status-dot ${semaphoreStatus === 'danger' ? 'active-danger' : ''}`}
                  title="Rosso (Semaforo = 0)"
                ></span>
              </div>
            </div>
          </div>
        </section>

        <section className="report-tasks-section">
          <div className="report-table-wrapper">
            <table className="report-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      className="form-checkbox"
                      onChange={handleSelectAllTasks}
                      checked={allTasksSelected}
                      disabled={filteredReportTasks.length === 0 || loadingActions.global !== null}
                    />
                  </th>
                  <th>Banca</th>
                  <th>Anno</th>
                  <th>Settimana</th>
                  <th>Nome File</th>
                  <th>Package</th>
                  <th>Disponibilità Server</th>
                  <th>Ultima Modifica</th>
                  <th>Dettagli</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan="8" style={{ textAlign: 'center', padding: '2rem' }}>
                      <RefreshCw className="spin" size={20} />
                      <span style={{ marginLeft: '0.5rem' }}>Caricamento dati reportistica...</span>
                    </td>
                  </tr>
                ) : filteredReportTasks.length === 0 ? (
                  <tr>
                    <td colSpan="8" style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
                      Nessuna attività di reportistica {currentPeriodicity} trovata per i filtri selezionati.
                    </td>
                  </tr>
                ) : filteredReportTasks.map(task => {
                  return (
                    <tr key={task.id} className={selectedTaskIds.has(task.id) ? 'selected-row' : ''}>
                      <td>
                        <input
                          type="checkbox"
                          className="form-checkbox"
                          checked={selectedTaskIds.has(task.id)}
                          onChange={() => handleTaskSelection(task.id)}
                          disabled={loadingActions.global !== null || loadingActions.taskAction === task.id}
                        />
                      </td>
                      <td>{task.banca || 'N/D'}</td>
                      <td>{task.anno || 'N/D'}</td>
                      <td>{task.settimana || 'N/D'}</td>
                      <td>
                        <strong>{task.nome_file}</strong>
                      </td>
                      <td>{task.package || 'N/D'}</td>
                      <td>
                        <span
                          className={`status-badge ${getDisponibilitaServerBadge(task.disponibilita_server)}`}
                          style={{
                            backgroundColor: task.disponibilita_server === true ? '#22c55e' : '#ef4444',
                            color: 'white',
                            border: 'none'
                          }}
                        >
                          {getDisponibilitaServerText(task.disponibilita_server)}
                        </span>
                      </td>
                      <td>{formatDateTime(task.ultima_modifica)}</td>
                      <td className="text-xs">{task.dettagli || 'N/D'}</td>
                    </tr>
                  );
                })}
                {filteredReportTasks.length === 0 && (
                  <tr>
                    <td colSpan="10" className="text-center muted-text">
                      Nessuna attività di reportistica {currentPeriodicity} trovata per i filtri selezionati.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="publish-section">
          <h3>Dati di Pubblicazione</h3>
          <div className="publish-controls">
            <div className="filter-group">
              <label htmlFor="anno-select" className="form-label">Anno</label>
              <select
                id="anno-select"
                value={repoUpdateInfo.anno || ''}
                onChange={(e) => setRepoUpdateInfo(prev => ({...prev, anno: parseInt(e.target.value)}))}
                className="form-select"
              >
                <option value="2024">2024</option>
                <option value="2025">2025</option>
                <option value="2026">2026</option>
              </select>
            </div>
            <div className="filter-group">
              <label htmlFor="settimana-select" className="form-label">Settimana</label>
              <select
                id="settimana-select"
                value={repoUpdateInfo.settimana || ''}
                onChange={(e) => setRepoUpdateInfo(prev => ({...prev, settimana: parseInt(e.target.value)}))}
                className="form-select"
              >
                {Array.from({length: 52}, (_, i) => (
                  <option key={i + 1} value={i + 1}>{i + 1}</option>
                ))}
              </select>
            </div>
            <div className="publish-button-group">
              <button
                className="btn btn-success"
                onClick={() => handleGlobalAction('pubblica')}
                disabled={repoUpdateInfo.semaforo !== 1 || loadingActions.global !== null}
              >
                <Send className="btn-icon-md" /> PUBBLICA REPORT
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default Report;