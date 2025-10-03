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

// --- Dati Mock per Test ---
const MOCK_REPORT_DATA = [
  {
    id: 1,
    banca: "BancaTest",
    package: "Flussi Netti",
    user: "mario.rossi",
    data_esecuzione: "2025-01-15T10:30:00",
    pre_check: true,
    prod: false,
    log: "Esecuzione completata con successo",
    anno: 2025,
    settimana: 3
  },
  {
    id: 2,
    banca: "BancaTest",
    package: "Package 2",
    user: "giulia.verdi",
    data_esecuzione: "2025-01-15T11:45:00",
    pre_check: true,
    prod: true,
    log: "Pubblicato in produzione",
    anno: 2025,
    settimana: 3
  },
  {
    id: 3,
    banca: "BancaTest",
    package: "Flussi Netti",
    user: "luca.bianchi",
    data_esecuzione: "2025-01-14T09:15:00",
    pre_check: false,
    prod: false,
    log: "In attesa di pre-check",
    anno: 2025,
    settimana: 2
  },
  {
    id: 4,
    banca: "BancaTest",
    package: "Report Mensile",
    user: "anna.ferrari",
    data_esecuzione: "2025-01-10T14:20:00",
    pre_check: true,
    prod: true,
    log: "Report mensile pubblicato",
    anno: 2025,
    settimana: null // Report mensile
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

// Funzione per stabilizzare le date (sottrae 1 settimana)
const stabilizzaDate = (anno, settimana, lunedi) => {
  // Crea oggetto datetime dal lunedì
  const dataLunedi = new Date(lunedi);

  // Sottrai 1 settimana (7 giorni)
  const delta1Settimana = new Date(dataLunedi);
  delta1Settimana.setDate(dataLunedi.getDate() - 7);

  // Calcola il numero della settimana ISO per la nuova data
  const getISOWeek = (date) => {
    const tempDate = new Date(date.valueOf());
    tempDate.setHours(0, 0, 0, 0);
    tempDate.setDate(tempDate.getDate() + 4 - (tempDate.getDay() || 7));
    const yearStart = new Date(tempDate.getFullYear(), 0, 1);
    return Math.ceil((((tempDate - yearStart) / 86400000) + 1) / 7);
  };

  const nuovaSettimana = getISOWeek(delta1Settimana);
  const nuovoAnno = delta1Settimana.getFullYear();

  // Trova il lunedì della settimana stabilizzata
  const nuovoLunedi = new Date(delta1Settimana);
  const giorno = nuovoLunedi.getDay();
  const diff = (giorno === 0 ? -6 : 1) - giorno;
  nuovoLunedi.setDate(nuovoLunedi.getDate() + diff);

  return {
    anno: nuovoAnno,
    settimana: nuovaSettimana,
    lunedi: nuovoLunedi.toISOString().split('T')[0]
  };
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
    const banks = [...new Set(reportTasks.map(task => task.banca).filter(Boolean))];

    // Aggiungi "Tutti" all'inizio se ci sono banche
    if (banks.length > 0) {
      return ["Tutti", ...banks];
    }

    return ["Tutti"];
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
      if (response.data) {
        setRepoUpdateInfo(response.data);
      }
    } catch (error) {
      console.error("Errore nella fetch repo update info:", error);
      // Mantiene i valori di default se non riesce a caricare
    }
  }, []);

  // Ref per tenere traccia se è il primo caricamento
  const isInitialLoad = useRef(true);

  // Stato per abilitare/disabilitare dati mock
  const [useMockData, setUseMockData] = useState(false); // FALSE = usa sempre dati API reali

  // Fetch reportistica data from API
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Mostra loading spinner solo al primo caricamento
        if (isInitialLoad.current) {
          setLoading(true);
        }

        // Se useMockData è true, usa i dati finti
        if (useMockData) {
          await new Promise(resolve => setTimeout(resolve, 500)); // Simula delay API
          setReportTasks(MOCK_REPORT_DATA);
          setRepoUpdateInfo({ anno: 2025, settimana: 3, semaforo: 1 });
          if (isInitialLoad.current) {
            showToast('Dati mock caricati per test', 'info');
          }
        } else {
          // Non filtrare per banca - prendi tutti i dati
          let queryUrl = '/reportistica/';

          console.log('Fetching from:', queryUrl);
          const response = await apiClient.get(queryUrl);
          console.log('API Response:', response.data);

          // Mappa i dati dell'API alla struttura attesa dal componente
          const mappedData = (response.data || []).map(item => ({
            id: item.id,
            banca: item.banca,
            package: item.package || item.nome_file,
            user: 'N/D', // L'API non fornisce questo campo
            data_esecuzione: item.ultima_modifica || item.updated_at,
            pre_check: false, // Da implementare nella logica di business
            prod: false, // Da implementare nella logica di business
            log: item.dettagli || 'N/D',
            anno: item.anno,
            settimana: item.settimana,
            disponibilita_server: item.disponibilita_server
          }));

          console.log('Mapped Data:', mappedData);
          setReportTasks(mappedData);
          await fetchRepoUpdateInfo();
        }

      } catch (error) {
        console.error('Error fetching reportistica data:', error);
        console.error('Error details:', error.response?.data);
        console.error('Error status:', error.response?.status);

        // Mostra toast di errore solo al primo caricamento
        if (isInitialLoad.current) {
          const errorMsg = error.response?.data?.detail || 'Errore nel caricamento dei dati reportistica';
          showToast(errorMsg, 'error');
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

    // Configura polling ogni 3 secondi solo se non usa mock
    let interval;
    if (!useMockData) {
      interval = setInterval(() => {
        fetchData();
      }, 3000);
    }

    // Cleanup interval on unmount
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [useMockData, showToast, fetchRepoUpdateInfo]);

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
    const filtered = reportTasks.filter(task => {
      // Filtro per periodicità: settimanali (hanno settimana) vs mensili (non hanno settimana)
      const isWeeklyTask = task.settimana !== null && task.settimana !== undefined;
      const isMonthlyTask = task.settimana === null || task.settimana === undefined;
      const matchesPeriodicity =
        (currentPeriodicity === 'settimanale' && isWeeklyTask) ||
        (currentPeriodicity === 'mensile' && isMonthlyTask);

      // Filtro per banca - sempre true per ora (disabilitato)
      const matchesBanca = true;

      // Filtro per package
      const matchesPackage = !filters.package || filters.package === "Tutti" || task.package === filters.package;

      return matchesPeriodicity && matchesBanca && matchesPackage;
    });

    console.log('Filtered tasks:', filtered);
    console.log('Current periodicity:', currentPeriodicity);
    console.log('Filters:', filters);
    return filtered;
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

    try {
      if (actionName === 'pubblica-pre-check') {
        showToast(`Avvio pubblicazione in Pre-Check...`, "info");

        // Simula chiamata API
        await new Promise(resolve => setTimeout(resolve, 1500));

        // Test della funzione stabilizzaDate
        const lunediCorrente = '2025-01-20'; // Lunedì della settimana 3, 2025
        const dateStabilizzate = stabilizzaDate(
          repoUpdateInfo.anno,
          repoUpdateInfo.settimana,
          lunediCorrente
        );

        console.log('Date stabilizzate:', dateStabilizzate);
        showToast(
          `Pre-Check pubblicato! Date stabilizzate: Anno ${dateStabilizzate.anno}, Settimana ${dateStabilizzate.settimana}`,
          "success"
        );

        // Aggiorna i dati mock per simulare pre_check = true
        if (useMockData) {
          setReportTasks(prev => prev.map(task =>
            selectedTaskIds.has(task.id)
              ? { ...task, pre_check: true, log: 'Pre-check completato' }
              : task
          ));

          // Aggiungi dati stabilizzati alla seconda tabella
          const nuoviDatiStabilizzati = Array.from(selectedTaskIds).map(taskId => {
            const task = reportTasks.find(t => t.id === taskId);
            if (task && task.settimana) {
              const lunediTest = '2025-01-20'; // Simula lunedì corrente
              const risultato = stabilizzaDate(task.anno, task.settimana, lunediTest);
              return {
                id: `stab-${taskId}`,
                package: task.package,
                anno_originale: task.anno,
                settimana_originale: task.settimana,
                ...risultato
              };
            }
            return null;
          }).filter(Boolean);

          setStabilizedData(prev => [...prev, ...nuoviDatiStabilizzati]);
        }

      } else if (actionName === 'pubblica-report') {
        showToast(`Avvio pubblicazione Report in Produzione...`, "info");

        // Verifica semaforo verde
        if (repoUpdateInfo.semaforo !== 1) {
          showToast('Semaforo non verde! Impossibile pubblicare in produzione.', 'error');
          return;
        }

        // Simula chiamata API
        await new Promise(resolve => setTimeout(resolve, 2000));

        showToast(
          `Report pubblicato in Produzione! Anno ${repoUpdateInfo.anno}, Settimana ${repoUpdateInfo.settimana}`,
          "success"
        );

        // Aggiorna i dati mock per simulare prod = true
        if (useMockData) {
          setReportTasks(prev => prev.map(task =>
            task.pre_check
              ? { ...task, prod: true, log: 'Pubblicato in produzione' }
              : task
          ));
        }

      } else {
        // Azioni generiche
        showToast(`Avvio azione globale '${actionName}'...`, "info");
        await new Promise(resolve => setTimeout(resolve, 1000));
        showToast(`Azione '${actionName}' completata.`, "success");
      }

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

  // Calcola automaticamente i dati stabilizzati (delta -1 settimana) dalla prima tabella
  const stabilizedData = useMemo(() => {
    return filteredReportTasks
      .filter(task => task.settimana !== null && task.settimana !== undefined) // Solo report settimanali
      .map(task => {
        // Calcola il lunedì della settimana corrente (ISO 8601)
        const getISOWeekMonday = (year, week) => {
          const simple = new Date(year, 0, 1 + (week - 1) * 7);
          const dow = simple.getDay();
          const ISOweekStart = simple;
          if (dow <= 4)
            ISOweekStart.setDate(simple.getDate() - simple.getDay() + 1);
          else
            ISOweekStart.setDate(simple.getDate() + 8 - simple.getDay());
          return ISOweekStart;
        };

        const lunediCorrente = getISOWeekMonday(task.anno, task.settimana);

        // Calcola delta -1 settimana
        const result = stabilizzaDate(task.anno, task.settimana, lunediCorrente.toISOString().split('T')[0]);

        return {
          id: `stab-${task.id}`,
          package: task.package,
          anno_originale: task.anno,
          settimana_originale: task.settimana,
          anno: result.anno,
          settimana: result.settimana,
          lunedi: result.lunedi
        };
      });
  }, [filteredReportTasks]);

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
            {/* Pulsante Indietro */}
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

          {/* Dati di Controllo spostati qui sotto i filtri */}
          <div className="filter-row" style={{ marginTop: '1rem' }}>
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
          </div>
        </section>

        <section className="report-tasks-section">
          <div className="report-table-wrapper">
            <table className="report-table">
              <thead>
                <tr>
                  <th>Package</th>
                  <th>Banca</th>
                  <th>Anno</th>
                  <th>Settimana</th>
                  <th>Data Modifica</th>
                  <th>Disponibilità Server</th>
                  <th>Dettagli</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>
                      <RefreshCw className="spin" size={20} />
                      <span style={{ marginLeft: '0.5rem' }}>Caricamento dati reportistica...</span>
                    </td>
                  </tr>
                ) : filteredReportTasks.length === 0 ? (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
                      Nessuna attività di reportistica {currentPeriodicity} trovata per i filtri selezionati.
                    </td>
                  </tr>
                ) : filteredReportTasks.map(task => {
                  return (
                    <tr key={task.id}>
                      <td><strong>{task.package || 'N/D'}</strong></td>
                      <td>{task.banca || 'N/D'}</td>
                      <td>{task.anno || 'N/D'}</td>
                      <td>{task.settimana || 'N/D'}</td>
                      <td>{formatDateTime(task.data_esecuzione)}</td>
                      <td>
                        <span className={`status-badge ${task.disponibilita_server ? 'status-badge-success' : 'status-badge-danger'}`}>
                          {task.disponibilita_server ? 'Disponibile' : 'Non disponibile'}
                        </span>
                      </td>
                      <td className="text-xs">{task.log || 'N/D'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Seconda tabella - solo struttura visibile senza dati */}
        <section className="report-tasks-section" style={{ marginTop: '2rem', border: '2px solid #22c55e', borderRadius: '8px', padding: '1.5rem', backgroundColor: '#f0fdf4' }}>
          <h3 style={{ marginBottom: '1rem', color: '#166534' }}>📊 Dati Stabilizzati (Delta -1 Settimana)</h3>
          <div className="report-table-wrapper">
            <table className="report-table" style={{ backgroundColor: 'white' }}>
              <thead>
                <tr>
                  <th style={{ width: '200px' }}>Package</th>
                  <th style={{ width: '100px', textAlign: 'center' }}>Anno Orig.</th>
                  <th style={{ width: '100px', textAlign: 'center' }}>Sett. Orig.</th>
                  <th style={{ width: '100px', textAlign: 'center', backgroundColor: '#dcfce7' }}>Anno Stab.</th>
                  <th style={{ width: '100px', textAlign: 'center', backgroundColor: '#dcfce7' }}>Sett. Stab.</th>
                  <th style={{ width: '150px', textAlign: 'center', backgroundColor: '#dcfce7' }}>Lunedì Stab.</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
                    Nessun dato stabilizzato disponibile.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Form di Pubblicazione - Tabella attivata solo se semaforo check file è verde */}
        {semaphoreStatus === 'success' && (
          <section className="report-tasks-section" style={{ marginTop: '2rem' }}>
            <h3 style={{ marginBottom: '1rem' }}>Form di Pubblicazione</h3>
            <div className="report-table-wrapper">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Package</th>
                    <th>User</th>
                    <th>Data Esecuzione</th>
                    <th>Pre Check</th>
                    <th>Prod</th>
                    <th>Log</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredReportTasks.map(task => {
                    const preCheckStatus = task.pre_check ? 'success' : 'danger';
                    const prodStatus = task.prod ? 'success' : 'danger';

                    return (
                      <tr key={task.id}>
                        <td><strong>{task.package}</strong></td>
                        <td>{task.user || 'N/D'}</td>
                        <td>{formatDateTime(task.data_esecuzione)}</td>
                        <td>
                          <div style={{
                            width: '100%',
                            height: '8px',
                            backgroundColor: preCheckStatus === 'success' ? '#22c55e' : '#ef4444',
                            borderRadius: '4px'
                          }}></div>
                        </td>
                        <td>
                          <div style={{
                            width: '100%',
                            height: '8px',
                            backgroundColor: prodStatus === 'success' ? '#22c55e' : '#ef4444',
                            borderRadius: '4px'
                          }}></div>
                        </td>
                        <td className="text-xs">{task.log || 'N/D'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="publish-button-group" style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <button
                className="btn btn-outline"
                onClick={() => handleGlobalAction('pubblica-pre-check')}
                disabled={loadingActions.global !== null || selectedTaskIds.size === 0}
                title={selectedTaskIds.size === 0 ? "Seleziona almeno un task dalla tabella" : "Pubblica i task selezionati in Pre-Check"}
              >
                <CheckCircle className="btn-icon-md" /> Pubblica in Pre-Check
              </button>
              <button
                className="btn btn-success"
                onClick={() => handleGlobalAction('pubblica-report')}
                disabled={
                  loadingActions.global !== null ||
                  filteredReportTasks.length === 0 ||
                  !filteredReportTasks.every(t => t.pre_check && t.prod)
                }
                title={
                  !filteredReportTasks.every(t => t.pre_check && t.prod)
                    ? "Tutte le barre Pre Check e Prod devono essere verdi"
                    : "Pubblica tutti i report in produzione"
                }
              >
                <Send className="btn-icon-md" /> Pubblica Report
              </button>
              {!filteredReportTasks.every(t => t.pre_check && t.prod) && filteredReportTasks.length > 0 && (
                <span style={{ fontSize: '0.875rem', color: '#dc2626', fontWeight: '500' }}>
                  ⚠️ Completare tutti i Pre-Check e Prod prima di pubblicare
                </span>
              )}
            </div>

            {useMockData && (
              <div style={{ marginTop: '1rem', padding: '0.75rem', backgroundColor: '#fef3c7', borderRadius: '8px', fontSize: '0.875rem' }}>
                <strong>⚠️ Modalità Test:</strong> Il form di pubblicazione è visibile perché il semaforo check file è verde. "Pubblica Report" si abilita solo quando tutte le barre Pre Check e Prod sono verdi.
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

export default Report;