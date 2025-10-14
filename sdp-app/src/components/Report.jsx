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
  const [packagesReady, setPackagesReady] = useState([]);
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

  // Funzione per caricare i package pronti dalla tabella report_data
  const fetchPackagesReady = useCallback(async () => {
    try {
      // Carica i package disponibili
      const packagesResponse = await apiClient.get("/reportistica/test-packages-v2");
      const availablePackages = packagesResponse.data || [];
      console.log('Available packages:', availablePackages);

      // Carica gli ultimi log di pubblicazione
      let publicationLogs = [];
      try {
        const logsResponse = await apiClient.get("/reportistica/publication-logs/latest");
        publicationLogs = logsResponse.data || [];
        console.log('Latest publication logs:', publicationLogs);
      } catch (logError) {
        console.warn("Nessun log di pubblicazione trovato (normale se prima esecuzione):", logError);
      }

      // Merge dei dati: usa i log se disponibili, altrimenti i default
      const mergedData = availablePackages.map(pkg => {
        // Cerca se esiste un log per questo package
        const logEntry = publicationLogs.find(log => log.package === pkg.package);

        if (logEntry) {
          // L'API restituisce già il messaggio specifico del package nel campo log
          return {
            package: pkg.package,
            ws_precheck: pkg.ws_precheck,
            ws_produzione: pkg.ws_produzione,
            bank: pkg.bank,
            type_reportistica: pkg.type_reportistica, // Aggiungi il tipo di reportistica
            user: logEntry.user || "N/D",
            data_esecuzione: logEntry.data_esecuzione,
            pre_check: logEntry.pre_check,
            prod: logEntry.prod,
            dettagli: logEntry.log || "In attesa di elaborazione"
          };
        } else {
          // Usa i default se non c'è log
          return {
            ...pkg,
            dettagli: null // Nessun dettaglio disponibile
          };
        }
      });

      setPackagesReady(mergedData);
    } catch (error) {
      console.error("Errore nel caricamento packages ready:", error);
      setPackagesReady([]);
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
          nome_file: item.nome_file,
          finalita: item.finalita,
          user: 'N/D', // L'API non fornisce questo campo
          data_esecuzione: item.ultima_modifica || item.updated_at,
          pre_check: false, // Da implementare nella logica di business
          prod: false, // Da implementare nella logica di business
          dettagli: item.dettagli || null,
          anno: item.anno,
          settimana: item.settimana,
          disponibilita_server: item.disponibilita_server
        }));

        console.log('Mapped Data:', mappedData);
        setReportTasks(mappedData);
        await fetchRepoUpdateInfo();
        await fetchPackagesReady();

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

    // Configura polling ogni 3 secondi
    const interval = setInterval(() => {
      fetchData();
    }, 3000);

    // Cleanup interval on unmount
    return () => {
      clearInterval(interval);
    };
  }, [showToast, fetchRepoUpdateInfo, fetchPackagesReady]);

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

  // Status basato sulla prima tabella - reattivo
  const semaphoreStatus = useMemo(() => {
    if (filteredReportTasks.length === 0) {
      return 'danger'; // Rosso se non ci sono dati
    }

    const allGreen = filteredReportTasks.every(task => task.disponibilita_server === true);
    const someGreen = filteredReportTasks.some(task => task.disponibilita_server === true);
    const allRed = filteredReportTasks.every(task => task.disponibilita_server === false);

    if (allGreen) {
      return 'success'; // Verde se tutti disponibili
    } else if (allRed) {
      return 'danger'; // Rosso se tutti non disponibili
    } else if (someGreen) {
      return 'warning'; // Arancione se parzialmente disponibili
    }

    return 'danger'; // Default rosso
  }, [filteredReportTasks]);

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

        try {
          // Chiama l'endpoint API per eseguire lo script Power BI
          // I package vengono letti dalla tabella report_data del DB filtrati per banca
          const response = await apiClient.post('/reportistica/publish-precheck');

          console.log('Risultati pubblicazione:', response.data);
          console.log(`Aggiornati ${response.data.packages.length} package:`, response.data.packages);

          // Ricarica i dati dal database per mostrare i log aggiornati
          await fetchPackagesReady();

          showToast(`Pre-Check pubblicato con successo! (${response.data.packages.length} package aggiornati)`, "success");
        } catch (error) {
          console.error('Errore pubblicazione pre-check:', error);
          showToast(`Errore durante la pubblicazione: ${error.response?.data?.detail || error.message}`, "error");
          throw error; // Re-throw per il catch esterno
        }

      } else if (actionName === 'pubblica-report') {
        showToast(`Avvio pubblicazione Report in Produzione...`, "info");

        // Simula chiamata API
        await new Promise(resolve => setTimeout(resolve, 1500));

        // Setta prod = true per tutti i package pronti
        setPackagesReady(prev => prev.map(pkg => ({
          ...pkg,
          prod: true,
          dettagli: 'Pubblicato in produzione con successo'
        })));

        showToast(`Report pubblicato in Produzione!`, "success");

        // Dopo 2 secondi, resetta tutto e avanza alla settimana successiva
        setTimeout(() => {
          // Reset pre_check e prod per i package pronti
          setPackagesReady(prev => prev.map(pkg => ({
            ...pkg,
            pre_check: false,
            prod: false,
            dettagli: null
          })));

          // Reset disponibilita_server per i report tasks
          setReportTasks(prev => prev.map(task => ({
            ...task,
            disponibilita_server: null,
            dettagli: null,
            // Avanza settimana +1
            settimana: task.settimana !== null ? task.settimana + 1 : task.settimana
          })));

          // Aggiorna repo update info con settimana +1
          setRepoUpdateInfo(prev => ({
            ...prev,
            settimana: prev.settimana + 1
          }));

          showToast(`✅ Sistema avanzato alla settimana ${repoUpdateInfo.settimana + 1}`, "success");
        }, 2000);

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

  // Dati per la tabella di pubblicazione - presi da packagesReady e filtrati per periodicità
  const publicationData = useMemo(() => {
    console.log('=== Filtro Package per Periodicità ===');
    console.log('Totale package disponibili:', packagesReady.length);
    console.log('Periodicità selezionata:', currentPeriodicity);

    // Filtra i package in base alla periodicità corrente
    const filteredPackages = packagesReady.filter(pkg => {
      const typeReportistica = pkg.type_reportistica?.toLowerCase() || '';

      // Se type_reportistica non è definito, NON mostrarlo (comportamento corretto)
      if (!typeReportistica) {
        return false;
      }

      // Settimanale: Type_reportisica contiene "settimanale"
      // Mensile: Type_reportisica contiene "mensile"
      if (currentPeriodicity === 'settimanale') {
        return typeReportistica.includes('settimanale');
      } else if (currentPeriodicity === 'mensile') {
        return typeReportistica.includes('mensile');
      }

      return false;
    });

    console.log(`Package filtrati per ${currentPeriodicity}:`, filteredPackages.length);
    console.log('Package:', filteredPackages.map(p => `${p.package} (${p.type_reportistica})`).join(', '));

    return filteredPackages.map((pkg, index) => ({
      id: `pub-${index}`,
      package: pkg.package,
      user: pkg.user,
      data_esecuzione: pkg.data_esecuzione,
      pre_check: pkg.pre_check,
      prod: pkg.prod,
      dettagli: pkg.dettagli,
      bank: pkg.bank // Aggiungi anche la banca se serve
    }));
  }, [packagesReady, currentPeriodicity]);

  // Verifica se tutte le righe della prima tabella sono verdi (disponibilita_server = true)
  const allFirstTableGreen = useMemo(() => {
    return filteredReportTasks.length > 0 &&
           filteredReportTasks.every(task => task.disponibilita_server === true);
  }, [filteredReportTasks]);

  // Verifica se tutte le righe della seconda tabella hanno pre_check = true
  const allPreCheckGreen = useMemo(() => {
    return publicationData.length > 0 &&
           publicationData.every(item => item.pre_check === true);
  }, [publicationData]);

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
                <p className="report-header-subtitle">Banca: {sessionStorage.getItem("selectedBank") || "N/A"}</p>
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
                  title="Verde - Tutti i server disponibili"
                ></span>
                <span
                  className={`status-dot ${semaphoreStatus === 'warning' ? 'active-warning' : ''}`}
                  title="Arancione - Alcuni server disponibili"
                ></span>
                <span
                  className={`status-dot ${semaphoreStatus === 'danger' ? 'active-danger' : ''}`}
                  title="Rosso - Nessun server disponibile"
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
                  <th>Finalità</th>
                  <th>Package</th>
                  <th>Nome File</th>
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
                    <td colSpan="9" style={{ textAlign: 'center', padding: '2rem' }}>
                      <RefreshCw className="spin" size={20} />
                      <span style={{ marginLeft: '0.5rem' }}>Caricamento dati reportistica...</span>
                    </td>
                  </tr>
                ) : filteredReportTasks.length === 0 ? (
                  <tr>
                    <td colSpan="9" style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
                      Nessuna attività di reportistica {currentPeriodicity} trovata per i filtri selezionati.
                    </td>
                  </tr>
                ) : filteredReportTasks.map(task => {
                  return (
                    <tr key={task.id}>
                      <td>{task.finalita || 'N/D'}</td>
                      <td><strong>{task.package || 'N/D'}</strong></td>
                      <td>{task.nome_file || 'N/D'}</td>
                      <td>{task.banca || 'N/D'}</td>
                      <td>{task.anno || 'N/D'}</td>
                      <td>{task.settimana || 'N/D'}</td>
                      <td>{formatDateTime(task.data_esecuzione)}</td>
                      <td style={{ textAlign: 'center' }}>
                        <div style={{
                          width: '100%',
                          height: '8px',
                          backgroundColor: task.disponibilita_server === true
                            ? '#22c55e'
                            : task.disponibilita_server === false
                              ? '#ef4444'
                              : '#e5e7eb',
                          borderRadius: '4px'
                        }}></div>
                      </td>
                      <td className="text-xs" style={{
                        maxWidth: '300px',
                        whiteSpace: 'pre-wrap',
                        fontSize: '11px',
                        cursor: task.dettagli && task.dettagli.length > 100 ? 'pointer' : 'default'
                      }}
                      title={task.dettagli || 'N/D'}
                      onClick={() => {
                        if (task.dettagli && task.dettagli.length > 100) {
                          alert(task.dettagli);
                        }
                      }}>
                        {task.dettagli ?
                          (task.dettagli.length > 100
                            ? task.dettagli.substring(0, 100) + '... (clicca per vedere tutto)'
                            : task.dettagli)
                          : 'N/D'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Seconda tabella - Package pronti per la pubblicazione */}
        <section className="report-tasks-section" style={{ marginTop: '2rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>✅ Package Pronti per la Pubblicazione</h3>

          <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'flex-start' }}>
            {/* Tabella compatta */}
            <div className="report-table-wrapper" style={{ flex: '1' }}>
              <table className="report-table" style={{ backgroundColor: 'white' }}>
                <thead>
                  <tr>
                    <th style={{ width: '180px' }}>Package</th>
                    <th style={{ width: '100px' }}>User</th>
                    <th style={{ width: '140px' }}>Data Esecuzione</th>
                    <th style={{ width: '80px', textAlign: 'center' }}>Pre Check</th>
                    <th style={{ width: '80px', textAlign: 'center' }}>Prod</th>
                    <th style={{ width: '200px' }}>Dettagli</th>
                  </tr>
                </thead>
                <tbody>
                  {publicationData.length === 0 ? (
                    <tr>
                      <td colSpan="6" style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
                        Nessun package pronto per la pubblicazione.
                      </td>
                    </tr>
                  ) : publicationData.map(item => (
                    <tr key={item.id}>
                      <td><strong>{item.package}</strong></td>
                      <td>{item.user}</td>
                      <td>{formatDateTime(item.data_esecuzione)}</td>
                      <td style={{ textAlign: 'center' }}>
                        <div style={{
                          width: '100%',
                          height: '8px',
                          backgroundColor: item.pre_check === true
                            ? '#22c55e'
                            : item.pre_check === false
                              ? '#ef4444'
                              : '#e5e7eb',
                          borderRadius: '4px'
                        }}></div>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <div style={{
                          width: '100%',
                          height: '8px',
                          backgroundColor: item.prod === true
                            ? '#22c55e'
                            : item.prod === false
                              ? '#ef4444'
                              : '#e5e7eb',
                          borderRadius: '4px'
                        }}></div>
                      </td>
                      <td className="text-xs" style={{
                        maxWidth: '300px',
                        whiteSpace: 'pre-wrap',
                        fontSize: '11px',
                        cursor: item.dettagli && item.dettagli.length > 100 ? 'pointer' : 'default'
                      }}
                      title={item.dettagli || 'N/D'}
                      onClick={() => {
                        if (item.dettagli && item.dettagli.length > 100) {
                          // Mostra dettagli completi in un alert
                          alert(item.dettagli);
                        }
                      }}>
                        {item.dettagli ?
                          (item.dettagli.length > 100
                            ? item.dettagli.substring(0, 100) + '... (clicca per vedere tutto)'
                            : item.dettagli)
                          : 'In attesa di elaborazione'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pulsanti di pubblicazione laterali */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
              minWidth: '250px',
              paddingTop: '0.5rem',
              alignItems: 'stretch'
            }}>
              <button
                className="btn btn-outline"
                onClick={() => handleGlobalAction('pubblica-pre-check')}
                disabled={!allFirstTableGreen || loadingActions.global !== null}
                title={!allFirstTableGreen ? "Tutte le righe della prima tabella devono avere disponibilità server verde" : "Pubblica in Pre-Check"}
                style={{
                  opacity: (!allFirstTableGreen || loadingActions.global !== null) ? '0.4' : '1',
                  cursor: (!allFirstTableGreen || loadingActions.global !== null) ? 'not-allowed' : 'pointer',
                  padding: '0.75rem 1rem',
                  whiteSpace: 'nowrap',
                  width: '100%'
                }}
              >
                <CheckCircle className="btn-icon-md" /> Pubblica in Pre-Check
              </button>
              <button
                className="btn btn-outline"
                onClick={() => handleGlobalAction('pubblica-report')}
                disabled={!allPreCheckGreen || loadingActions.global !== null}
                title={!allPreCheckGreen ? "Tutte le righe devono avere Pre-Check verde" : "Pubblica Report"}
                style={{
                  opacity: (!allPreCheckGreen || loadingActions.global !== null) ? '0.4' : '1',
                  cursor: (!allPreCheckGreen || loadingActions.global !== null) ? 'not-allowed' : 'pointer',
                  padding: '0.75rem 1rem',
                  whiteSpace: 'nowrap',
                  width: '100%'
                }}
              >
                <Send className="btn-icon-md" /> Pubblica Report
              </button>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}

export default Report;