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

// Rimuovi i dati di esempio - ora usa solo dati reali dall'API

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

  const [filters, setFilters] = useState(() => {
    // Imposta automaticamente la banca selezionata dal sessionStorage
    const selectedBank = sessionStorage.getItem("selectedBank");
    return {
      banca: selectedBank || "Tutti",
      package: "Tutti",
      // Filtri dinamici basati sulla periodicità (solo mese per report mensili)
      ...periodicityConfig.defaultFilters,
      periodicity: currentPeriodicity // Mantieni per retrocompatibilità
    };
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
    // La banca è già filtrata dalla query, quindi mostra solo quella selezionata
    const selectedBank = sessionStorage.getItem("selectedBank");
    const banks = [...new Set(reportTasks.map(task => task.banca).filter(Boolean))];

    // Se abbiamo una banca selezionata e i dati sono filtrati, mostra solo quella
    if (selectedBank && banks.length > 0) {
      return banks.includes(selectedBank) ? [selectedBank] : banks;
    }

    return banks;
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
      const response = await apiClient.get("/repo-update/");
      setRepoUpdateInfo(response.data);
    } catch (error) {
      console.error("Errore nella fetch repo update info:", error);
      // Mantiene i valori di default se non riesce a caricare
    }
  }, []);

  // Ref per tenere traccia se è il primo caricamento
  const isInitialLoad = useRef(true);

  // Fetch reportistica data from API
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Mostra loading spinner solo al primo caricamento
        if (isInitialLoad.current) {
          setLoading(true);
        }

        // Recupera la banca selezionata dal sessionStorage
        const selectedBank = sessionStorage.getItem("selectedBank");

        // Costruisce la query con il filtro per banca se disponibile
        let queryUrl = '/reportistica/';
        if (selectedBank) {
          queryUrl += `?banca=${encodeURIComponent(selectedBank)}`;
        }

        const response = await apiClient.get(queryUrl);
        setReportTasks(response.data);
        await fetchRepoUpdateInfo();

      } catch (error) {
        console.error('Error fetching reportistica data:', error);

        // Mostra toast di errore solo al primo caricamento
        if (isInitialLoad.current) {
          showToast('Errore nel caricamento dei dati reportistica', 'error');
          setReportTasks([]);
        }
      } finally {
        if (isInitialLoad.current) {
          setLoading(false);
          isInitialLoad.current = false;
        }
      }
    };

    // Carica dati immediatamente
    fetchData();

    // Configura polling ogni 3 secondi
    const interval = setInterval(() => {
      fetchData();
    }, 3000);

    // Cleanup interval on unmount
    return () => clearInterval(interval);
  }, []);

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

      // Filtro per banca: ora i dati sono già filtrati dalla query API,
      // quindi questo filtro frontend è principalmente per consistenza dell'UI
      const selectedBank = sessionStorage.getItem("selectedBank");
      const matchesBanca = !selectedBank || !filters.banca || filters.banca === "Tutti" || task.banca === filters.banca;

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
  
  const handleGlobalAction = async (actionName) => {
    if (actionName === 'esegui' && selectedTaskIds.size === 0) {
      showToast("Nessun task selezionato per l'esecuzione.", "warning");
      return;
    }

    setLoadingActions(prev => ({ ...prev, global: actionName }));
    showToast(`Avvio azione globale '${actionName}'...`, "info");

    try {
      // Qui andrà la logica per chiamare le API reali
      // Per ora solo un messaggio di conferma
      await new Promise(resolve => setTimeout(resolve, 1000));
      showToast(`Azione '${actionName}' completata.`, "success");

      if (actionName === 'esegui') {
        setSelectedTaskIds(new Set());
      }
    } catch (error) {
      console.error('Errore nell\'azione:', error);
      showToast(`Errore nell'esecuzione di '${actionName}'.`, "error");
    } finally {
      setLoadingActions(prev => ({ ...prev, global: null }));
    }
  };

  const allTasksSelected = filteredReportTasks.length > 0 && selectedTaskIds.size === filteredReportTasks.length;
  const isAnyTaskSelected = selectedTaskIds.size > 0;

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
              onClick={() => {
                console.log("Navigating back to /home...");
                navigate("/home", { replace: true });
              }}
              className="btn btn-outline report-header-back-button"
              disabled={loadingActions.global !== null}
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