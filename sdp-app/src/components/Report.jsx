// src/components/Report/Report.jsx
import { useState, useMemo, useEffect, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  BarChart3, Filter, Play, FileText, PlusSquare, Copy, UploadCloud, Send,
  RefreshCw, CheckCircle, XCircle, AlertTriangle, ListChecks, Eye, AlertCircle,
  Calendar, Clock, X
} from "lucide-react";
import "./Report.css";
import apiClient from "../api/apiClient";

// --- Componente Modal per Dettagli ---
function DetailsModal({ isOpen, onClose, title, content }) {
  // Chiudi modal con tasto ESC
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEsc);
      document.body.style.overflow = 'hidden'; // Previeni scroll del body
    }

    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">{title}</h3>
          <button className="modal-close-btn" onClick={onClose} aria-label="Chiudi modal">
            <X size={20} />
          </button>
        </div>
        <div className="modal-body">
          <pre className="details-content">{content}</pre>
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={handleCopy}>
            <Copy size={16} className="btn-icon-sm" /> Copia
          </button>
          <button className="btn btn-primary-action" onClick={onClose}>
            Chiudi
          </button>
        </div>
      </div>
    </div>
  );
}

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
  return '';
};

const formatDateTime = (dateString) => {
  if (!dateString) return '';
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
    return {
      package: "Tutti",
      disponibilita_server: "Tutti", // Nuovo filtro per disponibilità server
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
  const [syncRunning, setSyncRunning] = useState(false); // Stato per tracciare se c'è un sync in corso
  const [syncInterval, setSyncInterval] = useState(5); // Intervallo di aggiornamento in secondi

  // Stato per tracciare le azioni in corso (es. "pubblica-pre-check", "pubblica-report")
  // Quando global !== null, tutti i controlli vengono disabilitati per prevenire azioni concorrenti
  const [loadingActions, setLoadingActions] = useState({
    global: null, // null = nessuna azione in corso, altrimenti contiene il nome dell'azione
  });

  const [toast, setToast] = useState({ message: '', type: 'info', visible: false });

  // Stato per il modal dei dettagli
  const [detailsModal, setDetailsModal] = useState({ isOpen: false, title: '', content: '' });

  // Toast functions
  const showToast = useCallback((message, type = 'info') => {
    setToast({ message, type, visible: true });
  }, []);

  // Modal functions
  const showDetailsModal = useCallback((title, content) => {
    setDetailsModal({ isOpen: true, title, content });
  }, []);

  const closeDetailsModal = useCallback(() => {
    setDetailsModal({ isOpen: false, title: '', content: '' });
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

  // Debug: log quando syncRunning cambia
  useEffect(() => {
    console.log("syncRunning changed to:", syncRunning);
  }, [syncRunning]);

  // Estrai valori univoci per i dropdown dai dati
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

 const fetchSyncStatus = useCallback(async () => {
  try {
    // Usa l'endpoint /is-sync-running
    try {
      const response = await apiClient.get("/reportistica/is-sync-running");
      console.log("Is sync running response:", response.data);
      setSyncRunning(response.data?.is_running || false);
      setSyncInterval(response.data?.update_interval || 5);
      return; // Se funziona, usciamo dalla funzione
    } catch (innerError) {
      // Se l'errore è 422, ignoriamo e continuiamo con il fallback
      console.log("Errore previsto, utilizzo fallback:", innerError.response?.status);

      // Per qualsiasi errore, impostiamo semplicemente is_running a false
      setSyncRunning(false);
      setSyncInterval(5);
    }
  } catch (error) {
    // Questo catch esterno non dovrebbe mai essere raggiunto, ma per sicurezza
    console.error("Errore critico nel verificare sync status:", error);
    setSyncRunning(false);
    setSyncInterval(5);
  }
}, []);

  // Funzione per caricare i data dalla tabella report_data
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
        console.log('First item from API:', response.data[0]);

        // Mappa i dati dell'API alla struttura attesa dal componente
        const mappedData = (response.data || []).map(item => ({
          id: item.id,
          banca: item.banca,
          tipo_reportistica: item.tipo_reportistica,
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
        await fetchSyncStatus(); // Verifica se c'è un sync in corso

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
  }, [showToast, fetchRepoUpdateInfo, fetchPackagesReady, fetchSyncStatus]);

  // Funzione per cambiare periodicità
  const handlePeriodicityChange = (newPeriodicity) => {
    setSearchParams({ type: newPeriodicity });
  };

  const handleFilterChange = (filterName, value) => {
    setFilters(prev => ({ ...prev, [filterName]: value }));
  };

  // Task filtrati SOLO per periodicità (per il semaforo)
  const tasksForSemaphore = useMemo(() => {
    return reportTasks.filter(task => 
      task.tipo_reportistica?.toLowerCase() === currentPeriodicity.toLowerCase()
    );
  }, [reportTasks, currentPeriodicity]); 

  // Filtra task per periodicità corrente + altri filtri (per la tabella)
  const filteredReportTasks = useMemo(() => {
    console.log("Esempio task:", reportTasks[0]);
    const filtered = reportTasks.filter(task => {
      // Filtro per periodicità basato sul tab selezionato (case-insensitive)
      const matchesPeriodicity = task.tipo_reportistica?.toLowerCase() === currentPeriodicity.toLowerCase();

      // Filtro per package
      const matchesPackage = !filters.package || filters.package === "Tutti" || task.package === filters.package;

      // Filtro per disponibilità server
      const matchesDisponibilita =
        !filters.disponibilita_server ||
        filters.disponibilita_server === "Tutti" ||
        (filters.disponibilita_server === "Disponibile" && task.disponibilita_server === true) ||
        (filters.disponibilita_server === "Non disponibile" && task.disponibilita_server === false) ||
        (filters.disponibilita_server === "N/D" && task.disponibilita_server === null);

      return matchesPeriodicity && matchesPackage && matchesDisponibilita;
    });

    console.log('Filtered tasks:', filtered);
    console.log('Current periodicity:', currentPeriodicity);
    console.log('Filters:', filters);
    console.log('Sample task tipo_reportistica:', reportTasks[0]?.tipo_reportistica);
    console.log('All task tipos:', reportTasks);
    return filtered;
  }, [reportTasks, currentPeriodicity, filters]);

  // Status basato SOLO sui task della periodicità corrente (non sui filtri)
  const semaphoreStatus = useMemo(() => {
    const tasks = tasksForSemaphore; // Usa il nuovo array filtrato solo per periodicità

    if (tasks.length === 0) {
      return 'muted'; // Grigio se non ci sono dati per questa periodicità
    }

    // Controlla se almeno uno è stato eseguito (non è null)
    const hasBeenRun = tasks.some(task => task.disponibilita_server !== null);
    if (!hasBeenRun) {
      return 'muted'; // Grigio se nessuno è stato ancora eseguito
    }

    // ROSSO: Se c'è ALMENO UN file non disponibile (false)
    const hasRedTask = tasks.some(task => task.disponibilita_server === false);
    if (hasRedTask) {
      return 'danger';
    }

    // VERDE: Tutti i file eseguiti sono disponibili (true)
    const executedTasks = tasks.filter(t => t.disponibilita_server !== null);
    if (executedTasks.length > 0 && executedTasks.every(task => task.disponibilita_server === true)) {
      return 'success';
    }

    // Fallback a muted
    return 'muted';

  }, [tasksForSemaphore]); 

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

    // INIZIO AZIONE: imposta loadingActions.global al nome dell'azione
    // Questo disabilita tutti i controlli dell'interfaccia tramite disabled={loadingActions.global !== null}
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

        try {
          // Chiama lo stesso endpoint API di pre-check
          const response = await apiClient.post('/reportistica/publish-precheck');

          console.log('Risultati pubblicazione produzione:', response.data);
          console.log(`Aggiornati ${response.data.packages.length} package:`, response.data.packages);

          // Ricarica i dati dal database per mostrare i log aggiornati
          await fetchPackagesReady();

          showToast(`Report pubblicato in Produzione con successo! (${response.data.packages.length} package aggiornati)`, "success");

          // Dopo 2 secondi, resetta tutto e avanza alla settimana successiva
          setTimeout(() => {
            // Reset pre_check e prod per i data
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

        } catch (error) {
          console.error('Errore pubblicazione produzione:', error);
          showToast(`Errore durante la pubblicazione: ${error.response?.data?.detail || error.message}`, "error");
          throw error; // Re-throw per il catch esterno
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
      // FINE AZIONE: resetta loadingActions.global a null
      // Questo riabilita tutti i controlli dell'interfaccia
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
  // Usa tasksForSemaphore (filtrati solo per periodicità)
  const allFirstTableGreen = useMemo(() => {
    return tasksForSemaphore.length > 0 &&
           tasksForSemaphore.every(task => task.disponibilita_server === true);
  }, [tasksForSemaphore]);

  // Verifica se tutte le righe della seconda tabella hanno pre_check = true (verde, non error/timeout)
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

            {/* Tab periodicità nell'header */}
            <nav className="tab-nav-container">
              <div className="tab-nav-grid">
                <button
                  onClick={() => handlePeriodicityChange('settimanale')}
                  className={`tab-button ${currentPeriodicity === 'settimanale' ? 'active' : ''}`}
                  disabled={loadingActions.global !== null}
                >
                  <div className="tab-button-header">
                    <Clock className="tab-button-icon" />
                    <span className="tab-button-label">Settimanale</span>
                  </div>
                </button>
                <button
                  onClick={() => handlePeriodicityChange('mensile')}
                  className={`tab-button ${currentPeriodicity === 'mensile' ? 'active' : ''}`}
                  disabled={loadingActions.global !== null}
                >
                  <div className="tab-button-header">
                    <Calendar className="tab-button-icon" />
                    <span className="tab-button-label">Mensile</span>
                  </div>
                </button>
              </div>
            </nav>

            {/* Indicatore Auto-aggiornamento */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '0.875rem',
              color: '#666'
            }}>
              <span>Sincronizzazione attiva</span>
              <span
                className={`status-dot ${syncRunning ? 'active-success' : 'active-danger'}`}
                title={syncRunning
                  ? `Il sistema esegue automaticamente controlli e sincronizzazioni ogni ${syncInterval} ${syncInterval === 1 ? 'minuto' : 'minuti'} per mantenere i dati sempre aggiornati.`

                  : `L’autoaggiornamento è disattivato. L’ultimo intervallo configurato era di ${syncInterval} ${syncInterval === 1 ? 'minuto' : 'minuti'}; i controlli e le sincronizzazioni devono essere avviati manualmente.`
}
              ></span>
            </div>

            {/* Pulsante Aggiorna */}
            <button
              onClick={async () => {
                console.log("Refresh button clicked - triggering sync");
                showToast("Avvio sincronizzazione...", "info");
                try {
                  const response = await apiClient.post("/reportistica/trigger-sync");
                  console.log("Trigger sync response:", response.data);

                  if (response.data.success) {
                    showToast("Sincronizzazione avviata con successo", "success");
                    // Aggiorna subito lo stato per disabilitare il pulsante
                    setSyncRunning(true);
                    // Aggiorna i dati dopo un breve delay
                    setTimeout(() => {
                      fetchData();
                    }, 2000);
                  } else {
                    showToast(response.data.message || "Sync già in corso", "warning");
                  }
                } catch (error) {
                  console.error("Errore nell'avvio sync:", error);
                  showToast(
                    error.response?.data?.detail || "Errore nell'avvio della sincronizzazione",
                    "error"
                  );
                }
              }}
              className="btn btn-outline"
              disabled={syncRunning || loadingActions.global !== null}
              title={syncRunning ? "Auto-aggiornamento in corso" : "Avvia sincronizzazione"}
              style={{
                opacity: (syncRunning || loadingActions.global !== null) ? '0.5' : '1',
                cursor: (syncRunning || loadingActions.global !== null) ? 'not-allowed' : 'pointer'
              }}
            >
              Aggiorna
            </button>

            {/* Pulsante Indietro */}
            <button
              onClick={() => {
                console.log("Navigating back to /home...");
                navigate("/home", { replace: true });
              }}
              className="btn btn-outline report-header-back-button"
              // Disabilitato quando c'è un'azione in corso (loadingActions.global !== null)
              disabled={loadingActions.global !== null}
            >
              ← Indietro
            </button>
          </div>
        </header>

        <section className="report-filters-section">
          <div className="ingest-filters-bar">
            <div className="filter-group">
              <label className="form-label" htmlFor="settimana-select">Settimana</label>
              <select
                id="settimana-select"
                className="form-select form-select-sm"
                style={{ height: '1.75rem', minHeight: '1.75rem', maxHeight: '1.75rem', padding: '0.2rem 0.5rem', fontSize: '0.8rem', lineHeight: '1.2', margin: '0', boxSizing: 'border-box' }}
                value={repoUpdateInfo.settimana || ''}
                onChange={async (e) => {
                  const newSettimana = parseInt(e.target.value);
                  setRepoUpdateInfo(prev => ({...prev, settimana: newSettimana}));
                  try {
                    await apiClient.put('/repo-update/', { settimana: newSettimana });
                    // Ricarica i dati della reportistica con la nuova settimana
                    await fetchData();
                  } catch (error) {
                    console.error('Errore aggiornamento settimana:', error);
                  }
                }}
                disabled={loadingActions.global !== null}
              >
                {Array.from({length: 52}, (_, i) => (
                  <option key={i + 1} value={i + 1}>Settimana {i + 1}</option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label className="form-label" htmlFor="anno-select">Anno</label>
              <select
                id="anno-select"
                className="form-select form-select-sm"
                style={{ height: '1.75rem', minHeight: '1.75rem', maxHeight: '1.75rem', padding: '0.2rem 0.5rem', fontSize: '0.8rem', lineHeight: '1.2', margin: '0', boxSizing: 'border-box' }}
                value={repoUpdateInfo.anno || ''}
                onChange={async (e) => {
                  const newAnno = parseInt(e.target.value);
                  setRepoUpdateInfo(prev => ({...prev, anno: newAnno}));
                  try {
                    await apiClient.put('/repo-update/', { anno: newAnno });
                    // Ricarica i dati della reportistica con il nuovo anno
                    await fetchData();
                  } catch (error) {
                    console.error('Errore aggiornamento anno:', error);
                  }
                }}
                disabled={loadingActions.global !== null}
              >
                <option value="2024">2024</option>
                <option value="2025">2025</option>
                <option value="2026">2026</option>
              </select>
            </div>

            <div className="filter-group">
              <label className="form-label" htmlFor="package-filter">Package</label>
              <select
                id="package-filter"
                className="form-select"
                style={{ height: '1.75rem', minHeight: '1.75rem', maxHeight: '1.75rem', padding: '0.2rem 0.5rem', fontSize: '0.8rem', lineHeight: '1.2', margin: '0', boxSizing: 'border-box' }}
                value={filters.package}
                onChange={e => handleFilterChange('package', e.target.value)}
                disabled={loadingActions.global !== null}
              >
                <option value="Tutti">Tutti i Package</option>
                {uniquePackages.filter(pkg => pkg !== "Tutti").map(pkg => (
                  <option key={pkg} value={pkg}>{pkg}</option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label className="form-label" htmlFor="disponibilita-filter">Disponibilità File</label>
              <select
                id="disponibilita-filter"
                className="form-select"
                style={{ height: '1.75rem', minHeight: '1.75rem', maxHeight: '1.75rem', padding: '0.2rem 0.5rem', fontSize: '0.8rem', lineHeight: '1.2', margin: '0', boxSizing: 'border-box' }}
                value={filters.disponibilita_server}
                onChange={e => handleFilterChange('disponibilita_server', e.target.value)}
                disabled={loadingActions.global !== null}
              >
                <option value="Tutti">Tutti</option>
                <option value="Disponibile">Disponibile</option>
                <option value="Non disponibile">Non disponibile</option>
              </select>
            </div>

            <div className="filter-group overall-status-group">
              <label className="form-label">Status Complessivo</label>
              <div className="status-indicators">
                <span
                  className={`status-dot ${semaphoreStatus === 'success' ? 'active-success' : ''}`}
                  title="Verde - Tutti i file disponibili"
                ></span>
                <span
                  className={`status-dot ${semaphoreStatus === 'danger' ? 'active-danger' : ''}`}
                  title="Rosso - Almeno un file non disponibile"
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
                  <th>Finalità</th>
                  <th>Package</th>
                  <th>Nome File</th>
                  <th>Anno</th>
                  <th>Settimana</th>
                  <th>Data Modifica</th>
                  <th>Disponibilità File</th>
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
                    <tr key={task.id}>
                      <td>{task.finalita || 'N/D'}</td>
                      <td><strong>{task.package || 'N/D'}</strong></td>
                      <td>{task.nome_file || 'N/D'}</td>
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
                              : 'transparent',
                          border: task.disponibilita_server === null || task.disponibilita_server === undefined
                            ? '1px solid #9ca3af'
                            : 'none',
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
                          showDetailsModal(`Dettagli - ${task.nome_file}`, task.dettagli);
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

        {/* Seconda tabella - data per la pubblicazione */}
        <section className="report-tasks-section" style={{ marginTop: '2rem' }}>
          <h3 style={{ marginBottom: '1rem' }}> Package per la Pubblicazione</h3>

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
                          backgroundColor:
                            item.pre_check === true ? '#22c55e' :  // Verde - successo
                            item.pre_check === 'error' ? '#ef4444' :  // Rosso - errore
                            item.pre_check === 'timeout' ? '#f59e0b' :  // Arancione - timeout
                            'transparent',  // Grigio - in attesa
                          border: (item.pre_check !== true && item.pre_check !== 'error' && item.pre_check !== 'timeout')
                            ? '1px solid #9ca3af'
                            : 'none',
                          borderRadius: '4px'
                        }}></div>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <div style={{
                          width: '100%',
                          height: '8px',
                          backgroundColor:
                            item.prod === true ? '#22c55e' :  // Verde - successo
                            item.prod === 'error' ? '#ef4444' :  // Rosso - errore
                            item.prod === 'timeout' ? '#f59e0b' :  // Arancione - timeout
                            'transparent',  // Grigio - in attesa
                          border: (item.prod !== true && item.prod !== 'error' && item.prod !== 'timeout')
                            ? '1px solid #9ca3af'
                            : 'none',
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
                          showDetailsModal(`Dettagli Pubblicazione - ${item.package}`, item.dettagli);
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
                title={!allFirstTableGreen ? "Tutte le righe della prima tabella devono avere disponibilità file verde" : `Pubblica Report ${periodicityConfig.label} in Pre-Check`}
                style={{
                  opacity: (!allFirstTableGreen || loadingActions.global !== null) ? '0.4' : '1',
                  cursor: (!allFirstTableGreen || loadingActions.global !== null) ? 'not-allowed' : 'pointer',
                  padding: '0.75rem 1rem',
                  whiteSpace: 'nowrap',
                  width: '100%'
                }}
              >
                <CheckCircle className="btn-icon-md" /> Pubblica Report {periodicityConfig.label} in Pre-Check
              </button>
              <button
                className="btn btn-outline"
                onClick={() => handleGlobalAction('pubblica-report')}
                disabled={!allPreCheckGreen || loadingActions.global !== null}
                title={!allPreCheckGreen ? "Tutte le righe devono avere Pre-Check verde" : `Pubblica Report ${periodicityConfig.label}`}
                style={{
                  opacity: (!allPreCheckGreen || loadingActions.global !== null) ? '0.4' : '1',
                  cursor: (!allPreCheckGreen || loadingActions.global !== null) ? 'not-allowed' : 'pointer',
                  padding: '0.75rem 1rem',
                  whiteSpace: 'nowrap',
                  width: '100%'
                }}
              >
                <Send className="btn-icon-md" /> Pubblica Report {periodicityConfig.label}
              </button>
            </div>
          </div>
        </section>

      </div>

      {/* Modal per i dettagli */}
      <DetailsModal
        isOpen={detailsModal.isOpen}
        onClose={closeDetailsModal}
        title={detailsModal.title}
        content={detailsModal.content}
      />
    </div>
  );
}

export default Report;