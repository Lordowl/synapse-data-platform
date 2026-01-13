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

// --- Componente Tooltip Personalizzato ---
function CustomTooltip({ children, content, position = 'bottom' }) {
  const [isVisible, setIsVisible] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const timeoutRef = useRef(null);

  const handleMouseEnter = () => {
    setIsVisible(true);
    timeoutRef.current = setTimeout(() => {
      setShowTooltip(true);
    }, 500); // 0.5 secondi di delay
  };

  const handleMouseLeave = () => {
    setIsVisible(false);
    setShowTooltip(false);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (
    <div
      style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      {showTooltip && (
        <div
          style={{
            position: 'absolute',
            zIndex: 1000,
            backgroundColor: '#1f2937',
            color: 'white',
            padding: '0.5rem 0.75rem',
            borderRadius: '6px',
            fontSize: '0.875rem',
            lineHeight: '1.25rem',
            maxWidth: '400px',
            minWidth: '250px',
            whiteSpace: 'normal',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
            ...(position === 'bottom' && {
              top: 'calc(100% + 8px)',
              left: '50%',
              transform: 'translateX(-50%)'
            }),
            ...(position === 'top' && {
              bottom: 'calc(100% + 8px)',
              left: '50%',
              transform: 'translateX(-50%)'
            })
          }}
        >
          {content}
          <div
            style={{
              position: 'absolute',
              width: 0,
              height: 0,
              borderLeft: '6px solid transparent',
              borderRight: '6px solid transparent',
              ...(position === 'bottom' && {
                top: '-6px',
                left: '50%',
                transform: 'translateX(-50%)',
                borderBottom: '6px solid #1f2937'
              }),
              ...(position === 'top' && {
                bottom: '-6px',
                left: '50%',
                transform: 'translateX(-50%)',
                borderTop: '6px solid #1f2937'
              })
            }}
          />
        </div>
      )}
    </div>
  );
}

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
  const [selectedPublishPackages, setSelectedPublishPackages] = useState(new Set()); // Package selezionati per publish
  const [repoUpdateInfo, setRepoUpdateInfo] = useState({ anno: 2025, settimana: 29, mese: 1, semaforo: 0 });
  const [syncRunning, setSyncRunning] = useState(false); // Stato per tracciare se c'è un sync in corso
  const [syncInterval, setSyncInterval] = useState(5); // Intervallo di aggiornamento in secondi
  const [publishStatus, setPublishStatus] = useState(null); // Stato per tracciare la pubblicazione in corso
  const [lastSyncInfo, setLastSyncInfo] = useState(null); // Informazioni sull'ultimo sync

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
      console.log("fetchRepoUpdateInfo response:", response.data);
      if (response.data) {
        setRepoUpdateInfo(response.data);
        console.log("repoUpdateInfo aggiornato con:", response.data);
      }
    } catch (error) {
      console.error("Errore nella fetch repo update info:", error);
      // Mantiene i valori di default se non riesce a caricare
    }
  }, []);

  const fetchSyncStatus = useCallback(async () => {
    try {
      // Usa l'endpoint /is-sync-running che ora include anche last_sync_info
      try {
        const response = await apiClient.get("/reportistica/is-sync-running");
        console.log("Is sync running response:", response.data);
        setSyncRunning(response.data?.is_running || false);
        setSyncInterval(response.data?.update_interval || 5);

        // Aggiorna le informazioni sull'ultimo sync
        if (response.data?.last_sync_time) {
          setLastSyncInfo({
            last_sync_time: response.data.last_sync_time,
            last_sync_ago_seconds: response.data.last_sync_ago_seconds,
            last_sync_ago_human: response.data.last_sync_ago_human
          });
        } else {
          setLastSyncInfo(null);
        }

        return; // Se funziona, usciamo dalla funzione
      } catch (innerError) {
        // Se l'errore è 422, ignoriamo e continuiamo con il fallback
        console.log("Errore previsto, utilizzo fallback:", innerError.response?.status);

        // Per qualsiasi errore, impostiamo semplicemente is_running a false
        setSyncRunning(false);
        setSyncInterval(5);
        setLastSyncInfo(null);
      }
    } catch (error) {
      // Questo catch esterno non dovrebbe mai essere raggiunto, ma per sicurezza
      console.error("Errore critico nel verificare sync status:", error);
      setSyncRunning(false);
      setSyncInterval(5);
      setLastSyncInfo(null);
    }
  }, []);

  const fetchPublishStatus = useCallback(async () => {
    try {
      const response = await apiClient.get("/reportistica/publish-status");
      console.log("Publish status response:", response.data);
      setPublishStatus(response.data);
    } catch (error) {
      console.error("Errore nel recupero publish status:", error);
      setPublishStatus(null);
    }
  }, []);

  // Funzione per caricare i data dalla tabella report_data
  // fetchPackagesReady rimosso - i dati arrivano via WebSocket

  // Ref per tenere traccia se è il primo caricamento
  const isInitialLoad = useRef(true);

  // Fetch reportistica data from API (caricamento iniziale)
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
          mese: item.mese,
          disponibilita_server: item.disponibilita_server
        }));

        console.log('Mapped Data:', mappedData);
        setReportTasks(mappedData);
        await fetchRepoUpdateInfo();
        // packagesReady, syncStatus e publishStatus vengono aggiornati automaticamente via WebSocket

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

    // Carica dati solo al mount iniziale
    fetchData();

  }, [showToast, fetchRepoUpdateInfo, fetchSyncStatus, fetchPublishStatus]);

  // WebSocket per aggiornamenti real-time
  useEffect(() => {
    let ws = null;
    let reconnectTimeout = null;
    let isUnmounting = false;

    const connectWebSocket = () => {
      if (isUnmounting) return;

      try {
        // Ottieni il token dal sessionStorage (dove viene effettivamente salvato)
        const token = sessionStorage.getItem('accessToken');
        if (!token) {
          console.warn('No auth token found, skipping WebSocket connection');
          return;
        }

        // Costruisci URL WebSocket dinamicamente basandoti sull'URL dell'API
        // apiClient potrebbe avere baseURL configurato, altrimenti usa window.location
        const apiBaseUrl = apiClient.defaults?.baseURL || `${window.location.protocol}//${window.location.host}`;

        // Estrai host e porta dall'URL dell'API
        let wsHost = '127.0.0.1:9123'; // default
        try {
          const apiUrl = new URL(apiBaseUrl, window.location.origin);
          wsHost = apiUrl.host; // include porta se presente
        } catch (e) {
          console.warn('Could not parse API base URL, using default WebSocket host');
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${wsHost}/api/v1/reportistica/ws/updates?token=${encodeURIComponent(token)}`;

        console.log('Connecting to WebSocket:', wsUrl.replace(token, 'TOKEN_HIDDEN'));
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log('WebSocket connected');
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);

            // Aggiorna lo stato in base ai dati ricevuti
            if (data.type === 'status_update') {
              // Aggiorna sync status
              if (data.sync_status) {
                setSyncRunning(data.sync_status.is_running || false);
                setSyncInterval(data.sync_status.update_interval || 5);

                if (data.sync_status.last_sync_time) {
                  const syncInfo = {
                    last_sync_time: data.sync_status.last_sync_time,
                    last_sync_ago_seconds: data.sync_status.last_sync_ago_seconds,
                    last_sync_ago_human: data.sync_status.last_sync_ago_human
                  };
                  console.log('[WebSocket] Setting lastSyncInfo:', syncInfo, 'syncRunning:', data.sync_status.is_running);
                  setLastSyncInfo(syncInfo);
                } else {
                  console.log('[WebSocket] No last_sync_time, clearing lastSyncInfo');
                  setLastSyncInfo(null);
                }
              }

              // Aggiorna publish status
              if (data.publish_status !== undefined) {
                setPublishStatus(data.publish_status);
              }

              // Aggiorna dati reportistica (se presenti)
              if (data.reportistica_data && Array.isArray(data.reportistica_data)) {
                console.log('Updating reportistica data from WebSocket:', data.reportistica_data.length, 'items');

                // Mappa i dati come fa fetchData
                const mappedData = data.reportistica_data.map(item => ({
                  id: item.id,
                  banca: item.banca,
                  tipo_reportistica: item.tipo_reportistica,
                  package: item.package || item.nome_file,
                  nome_file: item.nome_file,
                  finalita: item.finalita,
                  user: 'N/D',
                  data_esecuzione: item.ultima_modifica || item.updated_at,
                  pre_check: false,
                  prod: false,
                  dettagli: item.dettagli || null,
                  anno: item.anno,
                  settimana: item.settimana,
                  mese: item.mese,
                  disponibilita_server: item.disponibilita_server
                }));

                setReportTasks(mappedData);
              }

              // Aggiorna packages ready (tabella pubblicazione)
              console.log('[WebSocket] packages_ready received:', data.packages_ready ? `${data.packages_ready.length} items` : 'NOT PRESENT OR NULL');
              if (data.packages_ready && Array.isArray(data.packages_ready)) {
                console.log('Updating packages ready from WebSocket:', data.packages_ready.length, 'items');
                const bancassurance = data.packages_ready.find(p => p.package === 'Bancassurance');
                console.log('Bancassurance data:', bancassurance);
                if (bancassurance) {
                  console.log('  -> pre_check:', bancassurance.pre_check);
                  console.log('  -> prod:', bancassurance.prod);
                }

                // Forza un nuovo array per triggare il re-render React
                setPackagesReady([...data.packages_ready]);
                console.log('[WebSocket] setPackagesReady called with NEW array reference');
              } else {
                console.warn('[WebSocket] packages_ready is missing or not an array:', data.packages_ready);
              }
            }
          } catch (error) {
            console.error('Error processing WebSocket message:', error);
          }
        };

        ws.onerror = (error) => {
          console.error('WebSocket error:', error);
        };

        ws.onclose = () => {
          console.log('WebSocket disconnected');

          // Riconnetti automaticamente dopo 3 secondi se non stiamo smontando
          if (!isUnmounting) {
            reconnectTimeout = setTimeout(() => {
              console.log('Attempting WebSocket reconnection...');
              connectWebSocket();
            }, 3000);
          }
        };

      } catch (error) {
        console.error('Error creating WebSocket:', error);
      }
    };

    // Connetti al WebSocket
    connectWebSocket();

    // Cleanup alla smontatura del componente
    return () => {
      isUnmounting = true;

      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }

      if (ws) {
        ws.close();
      }
    };
  }, []); // Vuoto perché vogliamo connetterci una sola volta

  // Funzione per cambiare periodicità
  const handlePeriodicityChange = (newPeriodicity) => {
    setSearchParams({ type: newPeriodicity });
    // I package vengono aggiornati automaticamente via WebSocket
  };

  const handleFilterChange = (filterName, value) => {
    setFilters(prev => ({ ...prev, [filterName]: value }));
  };

  // Task filtrati per periodicità E banca (per il semaforo)
  const tasksForSemaphore = useMemo(() => {
    const selectedBanca = sessionStorage.getItem("selectedBank");
    return reportTasks.filter(task => {
      // Confronto case-insensitive per la banca
      const matchesBanca = !selectedBanca || task.banca?.toLowerCase() === selectedBanca.toLowerCase();
      const matchesPeriodicity = task.tipo_reportistica?.toLowerCase() === currentPeriodicity.toLowerCase();
      return matchesBanca && matchesPeriodicity;
    });
  }, [reportTasks, currentPeriodicity]);

  // Filtra task per periodicità corrente + altri filtri (per la tabella)
  const filteredReportTasks = useMemo(() => {
    console.log("Esempio task:", reportTasks[0]);
    const selectedBanca = sessionStorage.getItem("selectedBank");

    const filtered = reportTasks.filter(task => {
      // Filtro per banca selezionata (case-insensitive)
      const matchesBanca = !selectedBanca || task.banca?.toLowerCase() === selectedBanca.toLowerCase();

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

      return matchesBanca && matchesPeriodicity && matchesPackage && matchesDisponibilita;
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
        // Verifica che ci siano package selezionati
        if (selectedPublishPackages.size === 0) {
          showToast("Nessun package selezionato per la pubblicazione.", "warning");
          return;
        }

        showToast(`Avvio pubblicazione in Pre-Check (${selectedPublishPackages.size} package)...`, "info");

        try {
          // Costruisci query string con i package selezionati
          const packagesParams = Array.from(selectedPublishPackages).map(pkg => `selected_packages=${encodeURIComponent(pkg)}`).join('&');
          const response = await apiClient.post(`/reportistica/publish-precheck?periodicity=${currentPeriodicity}&${packagesParams}`);

          console.log('Risultati pubblicazione:', response.data);
          console.log(`Aggiornati ${response.data.packages.length} package:`, response.data.packages);

          // I dati vengono aggiornati automaticamente via WebSocket

          showToast(`Pre-Check pubblicato con successo! (${response.data.packages.length} package aggiornati)`, "success");
        } catch (error) {
          console.error('Errore pubblicazione pre-check:', error);
          showToast(`Errore durante la pubblicazione: ${error.response?.data?.detail || error.message}`, "error");
          throw error; // Re-throw per il catch esterno
        }

      } else if (actionName === 'pubblica-report') {
        // Verifica che ci siano package selezionati
        if (selectedPublishPackages.size === 0) {
          showToast("Nessun package selezionato per la pubblicazione.", "warning");
          return;
        }

        showToast(`Avvio pubblicazione Report in Produzione (${selectedPublishPackages.size} package)...`, "info");

        try {
          // Costruisci query string con i package selezionati
          const packagesParams = Array.from(selectedPublishPackages).map(pkg => `selected_packages=${encodeURIComponent(pkg)}`).join('&');
          const response = await apiClient.post(`/reportistica/publish-production?periodicity=${currentPeriodicity}&${packagesParams}`);

          console.log('Risultati pubblicazione produzione:', response.data);
          console.log(`Aggiornati ${response.data.packages.length} package:`, response.data.packages);

          // I dati vengono aggiornati automaticamente via WebSocket

          showToast(`Report pubblicato in Produzione con successo! (${response.data.packages.length} package aggiornati)`, "success");

          // Dopo 2 secondi, resetta tutto e avanza alla settimana/mese successivo
          setTimeout(async () => {
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
              // Avanza settimana o mese in base alla periodicità
              settimana: currentPeriodicity === 'settimanale' && task.settimana !== null ? task.settimana + 1 : task.settimana,
              mese: currentPeriodicity === 'mensile' && task.mese !== null ? task.mese + 1 : task.mese
            })));

            // Aggiorna repo update info con settimana o mese +1
            try {
              if (currentPeriodicity === 'settimanale') {
                const newSettimana = repoUpdateInfo.settimana + 1;
                const response = await apiClient.put('/repo-update/', { settimana: newSettimana });

                // Aggiorna lo stato con la risposta del backend
                if (response.data) {
                  setRepoUpdateInfo(response.data);
                }
                showToast(`✅ Sistema avanzato alla settimana ${newSettimana}`, "success");

                // I pacchetti vengono aggiornati automaticamente via WebSocket
              } else {
                const newMese = repoUpdateInfo.mese + 1;
                const response = await apiClient.put('/repo-update/', { mese: newMese });

                // Aggiorna lo stato con la risposta del backend
                if (response.data) {
                  setRepoUpdateInfo(response.data);
                }
                showToast(`✅ Sistema avanzato al mese ${newMese}`, "success");

                // I pacchetti vengono aggiornati automaticamente via WebSocket
              }
            } catch (error) {
              console.error('Errore aggiornamento periodo dopo pubblicazione:', error);
              showToast(`⚠️ Pubblicazione riuscita ma errore nell'avanzamento del periodo`, "warning");
            }
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
    console.log('=== [useMemo publicationData] RE-CALCULATING ===');
    console.log('packagesReady:', packagesReady);
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
    console.log('filteredPackages DETTAGLI:', filteredPackages);

    const mapped = filteredPackages.map((pkg, index) => ({
      id: `pub-${index}`,
      package: pkg.package,
      user: pkg.user,
      data_esecuzione: pkg.data_esecuzione,
      pre_check: pkg.pre_check,
      prod: pkg.prod,
      dettagli: pkg.dettagli,
      error_precheck: pkg.error_precheck,
      user_prod: pkg.user_prod,
      data_esecuzione_prod: pkg.data_esecuzione_prod,
      dettagli_prod: pkg.dettagli_prod,
      error_prod: pkg.error_prod,
      anno_precheck: pkg.anno_precheck,
      settimana_precheck: pkg.settimana_precheck,
      mese_precheck: pkg.mese_precheck,
      anno_prod: pkg.anno_prod,
      settimana_prod: pkg.settimana_prod,
      mese_prod: pkg.mese_prod,
      bank: pkg.bank, // Aggiungi anche la banca se serve
      obbligatorio: pkg.obbligatorio === true // True se obbligatorio, False altrimenti
    }));

    console.log('publicationData MAPPED:', mapped);
    return mapped;
  }, [packagesReady, currentPeriodicity]);

  // Verifica se tutte le righe della prima tabella sono verdi (disponibilita_server = true)
  // E che appartengano al periodo corrente
  const allFirstTableGreen = useMemo(() => {
    if (tasksForSemaphore.length === 0) return false;

    // Verifica che ogni task sia verde E appartenga al periodo corrente
    return tasksForSemaphore.every(task => {
      const isGreen = task.disponibilita_server === true;

      // Verifica che appartenga al periodo corrente
      const isCurrentPeriod = currentPeriodicity === 'settimanale'
        ? (task.anno === repoUpdateInfo.anno && task.settimana === repoUpdateInfo.settimana)
        : (task.anno === repoUpdateInfo.anno && task.mese === repoUpdateInfo.mese);

      return isGreen && isCurrentPeriod;
    });
  }, [tasksForSemaphore, repoUpdateInfo, currentPeriodicity]);

  // Verifica se tutti i package SELEZIONATI hanno pre_check = true (verde, non error/timeout)
  const allPreCheckGreen = useMemo(() => {
    if (selectedPublishPackages.size === 0) return false;

    // Filtra solo i package selezionati
    const selectedItems = publicationData.filter(item => selectedPublishPackages.has(item.package));

    return selectedItems.length > 0 &&
      selectedItems.every(item => item.pre_check === true);
  }, [publicationData, selectedPublishPackages]);

  // Trova i package con errori (pre_check o prod con errore/timeout)
  const packagesWithErrors = useMemo(() => {
    return publicationData.filter(item =>
      item.pre_check === 'error' ||
      item.pre_check === 'timeout' ||
      item.prod === 'error' ||
      item.prod === 'timeout'
    );
  }, [publicationData]);

  // Handler per rilanciare i package con errori
  const handleRetryErrors = async () => {
    if (packagesWithErrors.length === 0) return;

    const errorPackageNames = packagesWithErrors.map(p => p.package);

    // Determina se rilanciare pre-check o prod in base allo stato degli errori
    // Se ci sono errori in prod, rilancia prod; altrimenti rilancia pre-check
    const hasProductionErrors = packagesWithErrors.some(p => p.prod === 'error' || p.prod === 'timeout');
    const actionName = hasProductionErrors ? 'pubblica-report' : 'pubblica-pre-check';

    setLoadingActions(prev => ({ ...prev, global: actionName }));

    try {
      showToast(`Rilancio ${errorPackageNames.length} package con errori...`, "info");

      const packagesParams = errorPackageNames.map(pkg => `selected_packages=${encodeURIComponent(pkg)}`).join('&');
      const endpoint = hasProductionErrors ? 'publish-production' : 'publish-precheck';
      const response = await apiClient.post(`/reportistica/${endpoint}?periodicity=${currentPeriodicity}&${packagesParams}`);

      console.log('Risultati rilancio:', response.data);
      showToast(`Rilancio completato! (${response.data.packages.length} package)`, "success");

    } catch (error) {
      console.error('Errore rilancio:', error);
      showToast(`Errore durante il rilancio: ${error.response?.data?.detail || error.message}`, "error");
    } finally {
      setLoadingActions(prev => ({ ...prev, global: null }));
    }
  };

  // Inizializza la selezione dei package per publish quando cambiano i dati
  // I package obbligatori sono sempre selezionati
  useEffect(() => {
    if (publicationData.length > 0) {
      // Seleziona automaticamente tutti i package obbligatori
      const obbligatoriPackages = publicationData
        .filter(pkg => pkg.obbligatorio)
        .map(pkg => pkg.package);

      setSelectedPublishPackages(prev => {
        const newSelection = new Set(prev);
        // Aggiungi tutti gli obbligatori
        obbligatoriPackages.forEach(pkg => newSelection.add(pkg));
        return newSelection;
      });
    }
  }, [publicationData]);

  // Handler per toggle selezione package (solo per non-obbligatori)
  const handlePublishPackageToggle = (packageName, isObbligatorio) => {
    if (isObbligatorio) return; // Non permettere deselezionare obbligatori

    setSelectedPublishPackages(prev => {
      const newSelection = new Set(prev);
      if (newSelection.has(packageName)) {
        newSelection.delete(packageName);
      } else {
        newSelection.add(packageName);
      }
      return newSelection;
    });
  };

  // Handler per seleziona/deseleziona tutti (solo non-obbligatori)
  const handleSelectAllPublishPackages = (selectAll) => {
    setSelectedPublishPackages(prev => {
      const newSelection = new Set();
      // Sempre includi gli obbligatori
      publicationData.filter(pkg => pkg.obbligatorio).forEach(pkg => newSelection.add(pkg.package));
      // Se selectAll, aggiungi anche gli opzionali
      if (selectAll) {
        publicationData.filter(pkg => !pkg.obbligatorio).forEach(pkg => newSelection.add(pkg.package));
      }
      return newSelection;
    });
  };

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

            {/* Gruppo controlli sincronizzazione e navigazione */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              flexWrap: 'nowrap'
            }}>
              {/* Indicatore Sync Status */}
              {syncRunning && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  whiteSpace: 'nowrap'
                }}>
                  <RefreshCw className="spin" size={18} style={{ color: '#666' }} />
                  <span style={{ fontSize: '0.875rem', color: '#666' }}>Sincronizzazione in corso...</span>
                </div>
              )}

              {/* Last Sync Info */}
              {lastSyncInfo && !syncRunning && (
                <CustomTooltip
                  content={`Ultimo sync: ${new Date(lastSyncInfo.last_sync_time).toLocaleString('it-IT')}`}
                  position="bottom"
                >
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    fontSize: '0.875rem',
                    color: '#6b7280',
                    padding: '0.25rem 0.75rem',
                    backgroundColor: '#f9fafb',
                    borderRadius: '6px',
                    border: '1px solid #e5e7eb',
                    whiteSpace: 'nowrap'
                  }}>
                    <Clock size={16} style={{ color: '#9ca3af' }} />
                    <span>{lastSyncInfo.last_sync_ago_human}</span>
                  </div>
                </CustomTooltip>
              )}

              {/* Pulsante Aggiorna */}
              <CustomTooltip
                content={syncRunning
                  ? "La sincronizzazione automatica è attiva. Il pulsante è disabilitato durante l'esecuzione."
                  : "Avvia manualmente la sincronizzazione dei dati. Questo aggiornerà tutti i report disponibili."}
                position="bottom"
              >
                <button
                  onClick={async () => {
                    console.log("Refresh button clicked - triggering sync");
                    showToast("Avvio sincronizzazione...", "info");
                    try {
                      const response = await apiClient.post("/reportistica/trigger-sync");
                      console.log("Trigger sync response:", response.data);

                      if (response.data.success) {
                        showToast("Sincronizzazione avviata con successo", "success");
                        setSyncRunning(true);
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
                  style={{
                    opacity: (syncRunning || loadingActions.global !== null) ? '0.5' : '1',
                    cursor: (syncRunning || loadingActions.global !== null) ? 'not-allowed' : 'pointer',
                    whiteSpace: 'nowrap'
                  }}
                >
                  Aggiorna
                </button>
              </CustomTooltip>

              {/* Pulsante Indietro */}
              <button
                onClick={() => {
                  console.log("Navigating back to /home...");
                  navigate("/home", { replace: true });
                }}
                className="btn btn-outline report-header-back-button"
                disabled={loadingActions.global !== null}
                style={{ whiteSpace: 'nowrap' }}
              >
                ← Indietro
              </button>
            </div>
          </div>
        </header>

        <section className="report-filters-section">
          <div className="ingest-filters-bar">
            {currentPeriodicity === 'settimanale' ? (
              <div className="filter-group">
                <label className="form-label" htmlFor="settimana-select">Settimana</label>
                <select
                  id="settimana-select"
                  className="form-select form-select-sm"
                  style={{ height: '1.75rem', minHeight: '1.75rem', maxHeight: '1.75rem', padding: '0.2rem 0.5rem', fontSize: '0.8rem', lineHeight: '1.2', margin: '0', boxSizing: 'border-box' }}
                  value={repoUpdateInfo.settimana || ''}
                  onChange={async (e) => {
                    const newSettimana = parseInt(e.target.value);
                    try {
                      const response = await apiClient.put('/repo-update/', { settimana: newSettimana });
                      // Aggiorna lo stato con la risposta del backend
                      if (response.data) {
                        setRepoUpdateInfo(response.data);
                      }
                      // I pacchetti vengono aggiornati automaticamente via WebSocket
                    } catch (error) {
                      console.error('Errore aggiornamento settimana:', error);
                    }
                  }}
                  disabled={loadingActions.global !== null}
                >
                  {Array.from({ length: 52 }, (_, i) => (
                    <option key={i + 1} value={i + 1}>Settimana {i + 1}</option>
                  ))}
                </select>
              </div>
            ) : (
              <div className="filter-group">
                <label className="form-label" htmlFor="mese-select">Mese</label>
                <select
                  id="mese-select"
                  className="form-select form-select-sm"
                  style={{ height: '1.75rem', minHeight: '1.75rem', maxHeight: '1.75rem', padding: '0.2rem 0.5rem', fontSize: '0.8rem', lineHeight: '1.2', margin: '0', boxSizing: 'border-box' }}
                  value={repoUpdateInfo.mese || ''}
                  onChange={async (e) => {
                    const newMese = parseInt(e.target.value);
                    console.log('🔵 onChange mese - newMese:', newMese);
                    console.log('🔵 onChange mese - payload che sto per inviare:', { mese: newMese });
                    try {
                      const payload = { mese: newMese };
                      console.log('🔵 onChange mese - payload prima della chiamata:', payload);
                      const response = await apiClient.put('/repo-update/', payload);
                      console.log('🔵 onChange mese - response.data ricevuta:', response.data);
                      // Aggiorna lo stato con la risposta del backend
                      if (response.data) {
                        setRepoUpdateInfo(response.data);
                      }
                      // I pacchetti vengono aggiornati automaticamente via WebSocket
                    } catch (error) {
                      console.error('Errore aggiornamento mese:', error);
                    }
                  }}
                  disabled={loadingActions.global !== null}
                >
                  {Array.from({ length: 12 }, (_, i) => (
                    <option key={i + 1} value={i + 1}>Mese {i + 1}</option>
                  ))}
                </select>
              </div>
            )}

            <div className="filter-group">
              <label className="form-label" htmlFor="anno-select">Anno</label>
              <select
                id="anno-select"
                className="form-select form-select-sm"
                style={{ height: '1.75rem', minHeight: '1.75rem', maxHeight: '1.75rem', padding: '0.2rem 0.5rem', fontSize: '0.8rem', lineHeight: '1.2', margin: '0', boxSizing: 'border-box' }}
                value={repoUpdateInfo.anno || ''}
                onChange={async (e) => {
                  const newAnno = parseInt(e.target.value);
                  setRepoUpdateInfo(prev => ({ ...prev, anno: newAnno }));
                  try {
                    await apiClient.put('/repo-update/', { anno: newAnno });
                    // I pacchetti vengono aggiornati automaticamente via WebSocket
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
                  <th>{currentPeriodicity === 'settimanale' ? 'Settimana' : 'Mese'}</th>
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
                      <td>{currentPeriodicity === 'settimanale' ? (task.settimana || 'N/D') : (task.mese || 'N/D')}</td>
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
                        fontSize: '14px',
                        cursor: task.dettagli ? 'pointer' : 'default'
                      }}
                        title="Clicca per vedere i dettagli completi"
                        onClick={() => {
                          if (task.dettagli) {
                            showDetailsModal(`Dettagli - ${task.nome_file}`, task.dettagli);
                          }
                        }}>
                        {/* Mostra messaggio breve - dettagli completi nel popup */}
                        {task.disponibilita_server === true ? (
                          <span>File disponibile ✓</span>
                        ) : task.disponibilita_server === false ? (
                          <span>File non disponibile</span>
                        ) : (
                          <span>Non verificato</span>
                        )}
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
            <div className="report-table-wrapper" style={{ flex: '1', minWidth: '820px' }}>
              <table className="report-table" style={{ backgroundColor: 'white', width: '100%', tableLayout: 'fixed' }}>
                <thead>
                  <tr>
                    <th style={{ width: '50px', textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={publicationData.length > 0 && selectedPublishPackages.size === publicationData.length}
                        onChange={(e) => handleSelectAllPublishPackages(e.target.checked)}
                        disabled={loadingActions.global !== null}
                        title="Seleziona/Deseleziona tutti"
                        style={{ cursor: loadingActions.global !== null ? 'not-allowed' : 'pointer' }}
                      />
                    </th>
                    <th style={{ width: '250px' }}>Package</th>
                    <th style={{ width: '60px', textAlign: 'center' }}>Pre-Check</th>
                    <th style={{ width: '80px' }}>{currentPeriodicity === 'settimanale' ? 'Settimana' : 'Mese'}</th>
                    <th style={{ width: '110px' }}>Data Pre-Check</th>
                    <th style={{ width: '60px', textAlign: 'center' }}>Prod</th>
                    <th style={{ width: '80px' }}>{currentPeriodicity === 'settimanale' ? 'Settimana' : 'Mese'}</th>
                    <th style={{ width: '110px' }}>Data Prod</th>
                    <th style={{ width: '150px' }}>Dettagli</th>
                  </tr>
                </thead>
                <tbody>
                  {publicationData.length === 0 ? (
                    <tr>
                      <td colSpan="9" style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
                        Nessun package pronto per la pubblicazione.
                      </td>
                    </tr>
                  ) : publicationData.map(item => (
                    <tr key={item.id}>
                      <td style={{ textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={selectedPublishPackages.has(item.package)}
                          onChange={() => handlePublishPackageToggle(item.package, item.obbligatorio)}
                          disabled={item.obbligatorio || loadingActions.global !== null}
                          title={item.obbligatorio ? 'Package obbligatorio (non deselezionabile)' : 'Seleziona per la pubblicazione'}
                          style={{
                            cursor: (item.obbligatorio || loadingActions.global !== null) ? 'not-allowed' : 'pointer',
                            opacity: item.obbligatorio ? 0.7 : 1
                          }}
                        />
                      </td>
                      <td style={{ fontSize: '15px', wordBreak: 'break-word' }}>
                        <strong>{item.package}</strong>
                        {item.obbligatorio && (
                          <span style={{ marginLeft: '6px', fontSize: '11px', color: '#dc2626', fontWeight: 'bold' }} title="Obbligatorio">*</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <div style={{
                          width: '100%',
                          height: '10px',
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
                      <td style={{ fontSize: '15px', textAlign: 'center' }}>
                        {currentPeriodicity === 'settimanale'
                          ? (item.settimana_precheck ? `Sett. ${item.settimana_precheck}` : 'N/D')
                          : (item.mese_precheck ? `Mese ${item.mese_precheck}` : 'N/D')}
                      </td>
                      <td style={{ fontSize: '15px' }}>
                        {item.data_esecuzione ? formatDateTime(item.data_esecuzione) : 'N/D'}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <div style={{
                          width: '100%',
                          height: '10px',
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
                      <td style={{ fontSize: '15px', textAlign: 'center' }}>
                        {currentPeriodicity === 'settimanale'
                          ? (item.settimana_prod ? `Sett. ${item.settimana_prod}` : 'N/D')
                          : (item.mese_prod ? `Mese ${item.mese_prod}` : 'N/D')}
                      </td>
                      <td style={{ fontSize: '15px' }}>
                        {item.data_esecuzione_prod ? formatDateTime(item.data_esecuzione_prod) : 'N/D'}
                      </td>
                      <td className="text-xs" style={{
                        maxWidth: '150px',
                        whiteSpace: 'pre-wrap',
                        fontSize: '14px',
                        cursor: item.dettagli || item.dettagli_prod || item.error_precheck || item.error_prod ? 'pointer' : 'default'
                      }}
                        title="Clicca per vedere i dettagli completi"
                        onClick={() => {
                          // Costruisci il contenuto del popup con i dettagli completi
                          if (item.dettagli || item.dettagli_prod || item.error_precheck || item.error_prod) {
                            let content = `Pre-Check:\n${item.dettagli || 'N/D'}\n`;

                            // Aggiungi errore pre-check se presente
                            if (item.error_precheck) {
                              try {
                                const errorObj = JSON.parse(item.error_precheck);
                                content += `\nErrore Pre-Check:\n${JSON.stringify(errorObj, null, 2)}\n`;
                              } catch {
                                content += `\nErrore Pre-Check:\n${item.error_precheck}\n`;
                              }
                            }

                            content += `\nProduction:\n${item.dettagli_prod || 'N/D'}\n`;

                            // Aggiungi errore production se presente
                            if (item.error_prod) {
                              try {
                                const errorObj = JSON.parse(item.error_prod);
                                content += `\nErrore Production:\n${JSON.stringify(errorObj, null, 2)}\n`;
                              } catch {
                                content += `\nErrore Production:\n${item.error_prod}\n`;
                              }
                            }

                            showDetailsModal(`Dettagli Pubblicazione - ${item.package}`, content);
                          }
                        }}>
                        {/* Mostra messaggio breve - dettagli completi nel popup */}
                        {item.prod === true ? (
                          <span style={{ color: '#22c55e' }}>Pubblicato ✓</span>
                        ) : item.prod === 'error' ? (
                          <span style={{ color: '#ef4444', fontWeight: 'bold' }}>Errore pubblicazione</span>
                        ) : item.pre_check === true ? (
                          <span style={{ color: '#22c55e' }}>Pre-check completato ✓</span>
                        ) : item.pre_check === 'error' ? (
                          <span style={{ color: '#ef4444', fontWeight: 'bold' }}>Errore pre-check</span>
                        ) : item.pre_check === 'timeout' ? (
                          <span style={{ color: '#f59e0b' }}>Timeout</span>
                        ) : (
                          <span style={{ color: '#666' }}>In attesa</span>
                        )}
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
              minWidth: '160px',
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
                  padding: '0.5rem 0.75rem',
                  whiteSpace: 'normal',
                  fontSize: '13px',
                  height: 'auto',
                  lineHeight: '1.2',
                  width: '100%'
                }}
              >
                <CheckCircle className="btn-icon-md" /> Pubblica Report {periodicityConfig.label} in Pre-Check
              </button>

              <button
                className="btn btn-outline"
                onClick={() => handleGlobalAction('pubblica-report')}
                disabled={!allFirstTableGreen || !allPreCheckGreen || loadingActions.global !== null}
                title={
                  !allFirstTableGreen ? "Tutte le righe della prima tabella devono avere disponibilità file verde" :
                    !allPreCheckGreen ? "Tutte le righe devono avere Pre-Check verde" :
                      `Pubblica Report ${periodicityConfig.label}`
                }
                style={{
                  opacity: (!allFirstTableGreen || !allPreCheckGreen || loadingActions.global !== null) ? '0.4' : '1',
                  cursor: (!allFirstTableGreen || !allPreCheckGreen || loadingActions.global !== null) ? 'not-allowed' : 'pointer',
                  padding: '0.5rem 0.75rem',
                  whiteSpace: 'normal',
                  fontSize: '13px',
                  height: 'auto',
                  lineHeight: '1.2',
                  width: '100%'
                }}
              >
                <Send className="btn-icon-md" /> Pubblica Report {periodicityConfig.label}
              </button>

              {/* Pulsante Rilancia con Errori - appare solo se ci sono errori */}
              {packagesWithErrors.length > 0 && (
                <button
                  className="btn btn-outline"
                  onClick={handleRetryErrors}
                  disabled={loadingActions.global !== null}
                  title={`Rilancia ${packagesWithErrors.length} package con errori: ${packagesWithErrors.map(p => p.package).join(', ')}`}
                  style={{
                    opacity: loadingActions.global !== null ? '0.4' : '1',
                    cursor: loadingActions.global !== null ? 'not-allowed' : 'pointer',
                    padding: '0.5rem 0.75rem',
                    whiteSpace: 'normal',
                    fontSize: '13px',
                    height: 'auto',
                    lineHeight: '1.2',
                    width: '100%',
                    backgroundColor: '#fef2f2',
                    borderColor: '#fca5a5',
                    color: '#dc2626'
                  }}
                >
                  <RefreshCw className="btn-icon-md" /> Rilancia Package Falliti ({packagesWithErrors.length})
                </button>
              )}

              {/* Indicatore di caricamento durante la pubblicazione */}
              {loadingActions.global && (
                <div style={{
                  marginTop: '1rem',
                  padding: '1rem',
                  backgroundColor: '#f0f9ff',
                  border: '1px solid #bae6fd',
                  borderRadius: '8px',
                  textAlign: 'center',
                  color: '#0369a1'
                }}>
                  <div className="loading-spinner" style={{ marginBottom: '0.5rem' }}></div>
                  <div style={{ fontSize: '14px', fontWeight: '500' }}>
                    {loadingActions.global === 'pubblica-pre-check' ? 'Pubblicazione Pre-Check in corso...' :
                      loadingActions.global === 'pubblica-report' ? 'Pubblicazione Report in corso...' :
                        'Operazione in corso...'}
                  </div>
                  <div style={{ fontSize: '12px', color: '#64748b', marginTop: '0.25rem' }}>
                    La tabella si aggiornerà automaticamente al termine
                  </div>
                </div>
              )}

              {/* Stato Pubblicazione - Sotto i pulsanti */}
              {publishStatus && publishStatus.is_running && publishStatus.data && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.5rem 0.75rem',
                  backgroundColor: '#f3f4f6',
                  borderRadius: '4px',
                  border: '1px solid #d1d5db',
                  fontSize: '0.75rem'
                }}>
                  <RefreshCw size={12} className="spin" style={{ color: '#6b7280' }} />
                  <span style={{ color: '#374151', fontWeight: '500' }}>
                    Pubblicazione in corso
                    {publishStatus.data.phase && (
                      <span style={{ color: '#6b7280', fontWeight: '400' }}>
                        {' - '}
                        {publishStatus.data.phase === 'precheck' ? 'Pre Check' : 'Prod'}
                      </span>
                    )}
                  </span>
                </div>
              )}
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