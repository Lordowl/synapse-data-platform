// src/components/Ingest/Ingest.jsx
import React, { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from 'react-toastify';
import apiClient from "../api/apiClient";
import { useAppContext } from '../context/AppContext';
import {
  Play, Filter, ListChecks, ChevronDown, ChevronUp, ChevronsUpDown,
  RefreshCw, Trash2, Download, Layers, TerminalSquare, PlayCircle,
  CheckCircle, XCircle, AlertTriangle, Search,
} from "lucide-react";
import "./Ingest.css";


// --- Funzioni Helper ---
const getStatusBadgeColor = (status) => {
  if (!status) return "bg-gray-100 text-gray-700";
  switch (status.toLowerCase()) {
    case "success":
      return "bg-green-100 text-green-700";
    case "failed":
      return "bg-red-100 text-red-700";
    case "warning":
      return "bg-yellow-100 text-yellow-700";
    case "running":
      return "bg-blue-100 text-blue-700";
    default:
      return "bg-gray-100 text-gray-700";
  }
};
const getLogLevelClass = (level) => {
  if (!level || typeof level !== "string") return "log-level-debug";
  switch (level.toLowerCase()) {
    case "error":
      return "log-level-error";
    case "warning":
      return "log-level-warning";
    case "info":
      return "log-level-info";
    default:
      return "log-level-debug";
  }
};

// --- Sotto-Componente per il Tab Esecuzione Flussi ---
function ExecutionTabContent({
  // Dati da visualizzare (già filtrati e ordinati)
  filteredAndSortedFlows,
  
  // Dati e funzioni per la selezione
  selectedFlows,
  handleSelectFlow,
  handleSelectAllFlows,
  
  // Dati e funzioni per l'esecuzione
  isExecuting,
  handleExecuteSelectedFlows,

  // Dati e funzioni per i parametri generali
  generalParams,
  handleGeneralParamChange,
  
  // Dati e funzioni per l'ordinamento della tabella
  sortConfig,
  requestSort,
  getSortIcon,
}) {
  const weekOptions = [
    { value: "27", label: "Settimana 27" },
    { value: "28", label: "Settimana 28" },
  ];

  // Funzione helper per il colore delle righe (rimane qui perché è solo di visualizzazione)
  const getRowColorByResult = (resultStatus) => {
    if (!resultStatus) return "row-color-default";
    switch (resultStatus.toLowerCase()) {
      case "success": return "row-color-success";
      case "failed": return "row-color-failed";
      case "warning": return "row-color-warning";
      case "running": return "row-color-running";
      default: return "row-color-default";
    }
  };

  return (
    <div className="tab-content-padding">
      {/* SEZIONE SUPERIORE CON IL PULSANTE DI ESECUZIONE */}
      <div className="ingest-section-header execution-tab-header">
        <div className="ingest-section-header-title-group">
          <Filter className="ingest-section-icon" />
          <h2 className="ingest-section-title">Selezione Flussi</h2>
        </div>
        <button
          onClick={handleExecuteSelectedFlows}
          className={`btn ${isExecuting ? "btn-disabled-visual" : "btn-primary"} execution-tab-run-button`}
          disabled={selectedFlows.size === 0 || isExecuting}
        >
          {isExecuting ? (
            <><RefreshCw className="btn-icon-md animate-spin-css" /> Esecuzione...</>
          ) : (
            <><Play className="btn-icon-md" /> Esegui ({selectedFlows.size})</>
          )}
        </button>
      </div>

      {/* LA BARRA DEI FILTRI È STATA SPOSTATA FUORI DA QUESTO COMPONENTE */}

      {/* TABELLA CHE MOSTRA I DATI GIÀ PRONTI */}
      <div className="ingest-table-wrapper">
        <table className="ingest-table">
          <thead>
            <tr>
              <th>
                <input
                  type="checkbox"
                  className="form-checkbox"
                  onChange={handleSelectAllFlows}
                  checked={filteredAndSortedFlows.length > 0 && selectedFlows.size === filteredAndSortedFlows.length}
                  ref={(el) => { if (el) { el.indeterminate = selectedFlows.size > 0 && selectedFlows.size < filteredAndSortedFlows.length; }}}
                  disabled={filteredAndSortedFlows.length === 0 || isExecuting}
                />
              </th>
              <th onClick={() => !isExecuting && requestSort("name")}>Nome Flusso {getSortIcon("name")}</th>
              <th onClick={() => !isExecuting && requestSort("package")}>Package {getSortIcon("package")}</th>
              <th onClick={() => !isExecuting && requestSort("id")}>ID Univoco {getSortIcon("id")}</th>
              <th onClick={() => !isExecuting && requestSort("lastRun")}>Ultima Esecuzione {getSortIcon("lastRun")}</th>
              <th onClick={() => !isExecuting && requestSort("result")}>Risultato {getSortIcon("result")}</th>
            </tr>
          </thead>
          <tbody>
            {filteredAndSortedFlows.map((flow) => (
              <tr key={flow.id} className={`${selectedFlows.has(flow.id) ? "selected-row" : ""} ${getRowColorByResult(flow.result)}`}>
                <td>
                  <input
                    type="checkbox"
                    className="form-checkbox"
                    checked={selectedFlows.has(flow.id)}
                    onChange={() => handleSelectFlow(flow.id)}
                    disabled={isExecuting}
                  />
                </td>
                <td data-label="Nome Flusso">{flow.name}</td>
                <td data-label="Package">{flow.package}</td>
                <td data-label="ID Univoco"><span className="muted-text">{flow.id}</span></td>
                <td data-label="Ultima Esecuzione">{flow.lastRun ? new Date(flow.lastRun).toLocaleString('it-IT') : "N/A"}</td>
                <td data-label="Risultato">
                  <span className={`status-badge ${getStatusBadgeColor(flow.result)}`}>
                    {flow.result || "N/A"}
                  </span>
                </td>
              </tr>
            ))}
            {filteredAndSortedFlows.length === 0 && (
              <tr>
                <td colSpan="6" className="text-center muted-text">
                  Nessun flusso dati trovato per i filtri selezionati.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* SEZIONE PARAMETRI GENERALI */}
      <div className="general-params-section">
        <h3 className="general-params-title">Parametri Generali Esecuzione</h3>
        <div className="param-input-group">
          <label htmlFor="week-select" className="param-label">Settimana di Riferimento:</label>
          <select
            id="week-select"
            className="form-select form-select-sm"
            value={generalParams.selectedWeek}
            onChange={(e) => handleGeneralParamChange("selectedWeek", e.target.value)}
            disabled={isExecuting}
          >
            {weekOptions.map((opt) => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
          </select>
        </div>
      </div>
    </div>
  );
}

// --- Sotto-Componente per il Tab Log Esecuzione ---
function LogsTabContent({
  logs,
  flows,
  logSearchTerm,
  setLogSearchTerm,
  logLevelFilter,
  setLogLevelFilter,
  handleRefreshLogs,
  handleClearLogs,
  handleDownloadLogs,
  filteredLogs,
  isRefreshingLogs,
  isClearingLogs,
  isDownloadingLogs,
}) {
  const anyLogActionLoading =
    isRefreshingLogs || isClearingLogs || isDownloadingLogs;

  // Stato per tenere traccia dei log espansi (ID del log espanso, o null)
  const [expandedLogId, setExpandedLogId] = useState(null);

  const toggleLogDetails = (logId) => {
    setExpandedLogId((prevId) => (prevId === logId ? null : logId));
  };

  // Funzione per ottenere la classe di colore della riga basata sul livello del log
  const getLogRowColorClass = (level) => {
    if (!level || typeof level !== "string") return "log-row-default";
    switch (level.toLowerCase()) {
      case "success": // Assumendo che tu abbia log con livello 'SUCCESS'
        return "log-row-success"; // Verde
      case "error":
        return "log-row-error"; // Rosso
      case "warning":
        return "log-row-warning"; // Giallo
      case "info":
        return "log-row-info"; // Blu chiaro o default
      case "debug":
        return "log-row-debug"; // Grigio o default
      default:
        return "log-row-default";
    }
  };

  return (
    <div className="tab-content-padding">
      <div className="ingest-section-header">
        <ListChecks className="ingest-section-icon" />
        <h2 className="ingest-section-title">Log Esecuzione Flussi</h2>
      </div>
      <div className="ingest-log-controls">
        <input
          type="text"
          placeholder="Cerca nei log..."
          value={logSearchTerm}
          onChange={(e) => setLogSearchTerm(e.target.value)}
          className="form-input logs-search-input"
          disabled={anyLogActionLoading}
        />
        <select
          value={logLevelFilter}
          onChange={(e) => setLogLevelFilter(e.target.value)}
          className="form-select logs-level-select"
          disabled={anyLogActionLoading}
        >
          <option value="all">Tutti i Livelli</option>
          <option value="success">Success</option>{" "}
          {/* Aggiunto Success se lo usi */}
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
          <option value="debug">Debug</option>
        </select>
        <button
          onClick={handleRefreshLogs}
          className="btn btn-outline"
          disabled={anyLogActionLoading}
        >
          {isRefreshingLogs ? (
            <>
              <RefreshCw className="btn-icon-md animate-spin-css" />
              Aggiornando...
            </>
          ) : (
            <>
              <RefreshCw className="btn-icon-md" />
              Aggiorna
            </>
          )}
        </button>
      </div>

      <div className="ingest-log-table-wrapper">
        {" "}
        {/* Nuovo wrapper per lo scroll */}
        <table className="ingest-log-table">
          {" "}
          {/* Nuova classe per la tabella log */}
          <thead>
            <tr>
              <th style={{ width: "180px" }}>Timestamp</th>
              <th style={{ width: "100px" }}>Livello</th>
              <th>Flusso Associato</th>
              <th>Messaggio</th>
              <th style={{ width: "120px" }}>Dettagli</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.length > 0 ? (
              filteredLogs.map((log) => (
                <React.Fragment key={log.id}>
                  <tr
                    className={`log-table-row ${getLogRowColorClass(
                      log.level
                    )} ${expandedLogId === log.id ? "expanded" : ""}`}
                  >
                    <td data-label="Timestamp">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td data-label="Livello">
                      <span
                        className={`log-level-badge ${getLogLevelClass(
                          log.level
                        )}`}
                      >
                        {log.level?.toUpperCase() || "N/D"}
                      </span>
                    </td>
                    <td data-label="Flusso">
                      {log.flowId &&
                      flows.find((f) => f.id === log.flowId)?.name ? (
                        flows.find((f) => f.id === log.flowId)?.name
                      ) : log.flowId ? (
                        <span className="muted-text italic">
                          {log.flowId} (ID non trovato)
                        </span>
                      ) : (
                        <span className="muted-text italic">N/A</span>
                      )}
                    </td>
                    <td data-label="Messaggio" className="log-message-cell">
                      {log.message || (
                        <span className="muted-text italic">
                          (Nessun messaggio)
                        </span>
                      )}
                    </td>
                    <td
                      data-label="Dettagli"
                      className="log-details-action-cell"
                    >
                      {log.details && (
                        <button
                          onClick={() => toggleLogDetails(log.id)}
                          className="btn btn-outline btn-sm log-details-btn" // btn-sm per un bottone più piccolo
                          aria-expanded={expandedLogId === log.id}
                          disabled={anyLogActionLoading}
                        >
                          {expandedLogId === log.id ? (
                            <ChevronUp size={16} />
                          ) : (
                            <ChevronDown size={16} />
                          )}
                          {/* Testo rimosso per più spazio, l'icona dovrebbe bastare */}
                        </button>
                      )}
                    </td>
                  </tr>
                  {expandedLogId === log.id && log.details && (
                    <tr className="log-details-row">
                      <td colSpan="5">
                        <pre className="log-details-content">{log.details}</pre>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))
            ) : (
              <tr>
                <td
                  colSpan="5"
                  className="text-center muted-text ingest-logs-empty-message"
                >
                  Nessun log da visualizzare o corrispondente ai filtri.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="ingest-log-actions">
        <p className="logs-count-info">
          Visualizzati: {filteredLogs.length} (Totali: {logs.length})
        </p>
        <div className="logs-action-buttons">
          <button
            onClick={handleDownloadLogs}
            className="btn btn-primary"
            disabled={anyLogActionLoading}
          >
            {isDownloadingLogs ? (
              <>
                <RefreshCw className="btn-icon-md animate-spin-css" />
                Download...
              </>
            ) : (
              <>
                <Download className="btn-icon-md" />
                Scarica Log
              </>
            )}
          </button>
          <button
            onClick={handleClearLogs}
            className="btn btn-danger"
            disabled={anyLogActionLoading}
          >
            {isClearingLogs ? (
              <>
                <RefreshCw className="btn-icon-md animate-spin-css" />
                Pulizia...
              </>
            ) : (
              <>
                <Trash2 className="btn-icon-md" />
                Pulisci Log
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
// --- Componente Principale Ingest ---
function Ingest() {
  const navigate = useNavigate();
  const { metadataFilePath } = useAppContext();
    const [activeTab, setActiveTab] = useState("execution");
  const [isLoading, setIsLoading] = useState(true);
  const [flowsData, setFlowsData] = useState([]); // Inizia vuoto
  const [logsData, setLogsData] = useState([]);   // Inizia vuoto
  const [isUpdatingFlows, setIsUpdatingFlows] = useState(false);
  // Stati per filtri e interazioni
  const [selectedFlows, setSelectedFlows] = useState(new Set());
  const [searchTerm, setSearchTerm] = useState("");
  const [packageFilter, setpackageFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortConfig, setSortConfig] = useState({ key: "id", direction: "ascending" });

  const [generalParams, setGeneralParams] = useState({ selectedWeek: "27" });
  const [logSearchTerm, setLogSearchTerm] = useState("");
  const [logLevelFilter, setLogLevelFilter] = useState("all");

  const [isExecutingFlows, setIsExecutingFlows] = useState(false);

  const [isRefreshingLogs, setIsRefreshingLogs] = useState(false);
  const [isClearingLogs, setIsClearingLogs] = useState(false);
  const [isDownloadingLogs, setIsDownloadingLogs] = useState(false);

  // in src/components/Ingest/Ingest.jsx

useEffect(() => {
  const fetchInitialData = async () => {
    setIsLoading(true); // Inizia a mostrare lo spinner
    
    try {
      // ==========================================================
      // ---    STEP 1: AGGIORNAMENTO AUTOMATICO DALL'EXCEL     ---
      // ==========================================================
      // Prima di caricare i dati, diciamo al backend di rigenerare il JSON dall'Excel.
      // Usiamo await per bloccare l'esecuzione finché non è completo.
      console.log("-> Avvio aggiornamento automatico flussi da Excel...");
      await apiClient.post('/tasks/update-flows-from-excel', { 
          file_path: metadataFilePath 
        });
      console.log("-> Aggiornamento da Excel completato sul backend.");
      toast.info("Fonte dati aggiornata dall'Excel.");


      // ==========================================================
      // --- STEP 2: CARICAMENTO DEI DATI AGGIORNATI E STORICO ---
      // ==========================================================
      // Ora che il file flows.json è aggiornato, procediamo a caricarlo.
      console.log("-> Caricamento flussi e storico...");
      const [flowsResponse, historyResponse] = await Promise.all([
        apiClient.get('/flows'),
        apiClient.get('/flows/history')
      ]);

      const staticFlows = flowsResponse.data;
      const historyMap = historyResponse.data;

      if (!Array.isArray(staticFlows)) {
        throw new Error("La risposta dei flussi non è valida.");
      }

      // ==========================================================
      // ---          STEP 3: UNIONE E VISUALIZZAZIONE          ---
      // ==========================================================
      console.log("-> Unione dati per la visualizzazione...");
      const combinedFlows = staticFlows.map(flow => {
        const flowId = `${flow.ID}-${flow.SEQ || '0'}`;
        const executionHistory = historyMap[flowId] || {};

        return {
          id: flowId,
          name: flow['Filename out'],
          package: flow['Package'],
          
          year: new Date().getFullYear(),
          lastRun: executionHistory.lastRun || null,
          result: executionHistory.result || 'N/A',
          duration: executionHistory.duration || null,
          lastWeekExecution: null,
        };
      });

      console.log("Dati combinati pronti:", combinedFlows);
      setFlowsData(combinedFlows);
      toast.success("Dati caricati e pronti.");
      
    } catch (error) {
      // Questo 'catch' catturerà qualsiasi errore in tutta la catena
      console.error("Errore nel processo di caricamento e aggiornamento:", error);
      toast.error(error.response?.data?.detail || "Un'operazione è fallita durante il caricamento.");
    } finally {
      // In ogni caso, il caricamento è terminato
      setIsLoading(false);
    }
  };

  fetchInitialData();
}, []); // L'array vuoto [] assicura che venga eseguito solo una volta all'apertura

  const flowPackages= useMemo(
  () => ["all", ...new Set(flowsData.map((f) => f.package).filter(Boolean))], // Usa .package
  [flowsData]
);
  const flowStatuses = useMemo(
    () => ["all", ...new Set(flowsData.map((f) => f.result || "N/A"))],
    [flowsData]
  );
  
  const handleSelectFlow = (flowId) => {
    setSelectedFlows((prev) => {
      const nS = new Set(prev);
      if (nS.has(flowId)) {
        nS.delete(flowId);
      } else {
        nS.add(flowId);
      }
      return nS;
    });
  };
  const handleSelectAllFlows = (e) => {
    if (e.target.checked) {
      setSelectedFlows(new Set(filteredAndSortedFlows.map((f) => f.id)));
    } else {
      setSelectedFlows(new Set());
    }
  };

  const handleGeneralParamChange = (paramName, value) => {
    setGeneralParams((prev) => ({ ...prev, [paramName]: value }));
  };

  const filteredFlows = useMemo(() => {
     console.log("--- Ricalcolo filteredFlows ---");
  console.log("Stato attuale dei filtri:", { searchTerm, packageFilter, statusFilter });
  console.log("Dati di input (flowsData):", flowsData);
  return flowsData.filter(flow =>
      (flow.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
       flow.package?.toLowerCase().includes(searchTerm.toLowerCase())) &&
      (packageFilter === 'all' || flow.package === packageFilter) && // Usa packageFilter
      (statusFilter === 'all' || (flow.result || 'N/A') === statusFilter)
    );
  }, [flowsData, searchTerm, packageFilter, statusFilter])

  // in src/components/Ingest/Ingest.jsx

const filteredAndSortedFlows = useMemo(() => {
  let sortableFlows = [...filteredFlows];

  if (sortConfig.key) {
    sortableFlows.sort((a, b) => {
      // Estraiamo i valori da ordinare
      const aValue = a[sortConfig.key];
      const bValue = b[sortConfig.key];

      // --- NUOVA CONDIZIONE SPECIFICA PER L'ORDINAMENTO NUMERICO DELL'ID ---
      if (sortConfig.key === 'id') {
        // Estraiamo la parte numerica dall'ID (es. da "17-1" prendiamo 17)
        // Usiamo parseInt per convertire la stringa in un numero.
        const numA = parseInt(a.originalId, 10) || 0;
        const numB = parseInt(b.originalId, 10) || 0;
        
        // Se gli ID principali sono diversi, ordiniamo per quelli
        if (numA !== numB) {
            return numA - numB;
        }
        
        // Se gli ID principali sono uguali, ordiniamo per la sequenza (SEQ)
        const seqA = parseInt(a.originalSeq, 10) || 0;
        const seqB = parseInt(b.originalSeq, 10) || 0;
        return seqA - seqB;
      }
      
      // --- Logica esistente per gli altri tipi di dato ---

      // 1. Per le date (es. 'lastRun')
      if (sortConfig.key === 'lastRun') {
        const dateA = aValue ? new Date(aValue).getTime() : 0;
        const dateB = bValue ? new Date(bValue).getTime() : 0;
        return dateA - dateB;
      }
      
      // 2. Per tutte le altre stringhe
      const strA = (aValue || '').toString().toLowerCase();
      const strB = (bValue || '').toString().toLowerCase();
      return strA.localeCompare(strB); // localeCompare è leggermente meglio per le stringhe
    });

    // Applica la direzione (ascendente o discendente)
    if (sortConfig.direction === 'descending') {
      sortableFlows.reverse();
    }
  }

  return sortableFlows;
}, [filteredFlows, sortConfig]);

  const requestSort = (key) => {
    let dir = "ascending";
    if (sortConfig.key === key && sortConfig.direction === "ascending") {
      dir = "descending";
    }
    setSortConfig({ key, direction: dir });
  };
  const getSortIcon = (key) => {
    if (sortConfig.key !== key)
      return <ChevronsUpDown className="inline-icon" />;
    return sortConfig.direction === "ascending" ? (
      <ChevronUp className="inline-icon" />
    ) : (
      <ChevronDown className="inline-icon" />
    );
  };

  const simulateApiCall = (duration = 1500) =>
    new Promise((resolve) => setTimeout(resolve, duration));

  const handleExecuteSelectedFlows = async () => {
    if (selectedFlows.size === 0) {
      showToast("Nessun flusso selezionato per l'esecuzione.", "warning");
      return;
    }
    setIsExecutingFlows(true);
    await simulateApiCall(2500);
    const flowsToRun = Array.from(selectedFlows)
      .map((id) => flowsData.find((f) => f.id === id))
      .filter((f) => f);
    const executionDetails = `Parametri Generali:\n  - Settimana: ${
      generalParams.selectedWeek
    }\n\nFlussi Eseguiti:\n${flowsToRun
      .map((f) => `  - ${f.name} (ID: ${f.id})`)
      .join("\n")}`;
    showToast(
      `Esecuzione con parametri generali completata (simulazione).`,
      "success"
    );
    console.log(
      "DETTAGLI ESECUZIONE (da inviare al backend):",
      executionDetails
    );
    const newExecutionLogs = flowsToRun.map((flow) => ({
      id: `log_exec_${Date.now()}_${flow.id}`,
      timestamp: new Date().toISOString(),
      flowId: flow.id,
      message: `Esecuzione flusso '${flow.name}' con settimana '${generalParams.selectedWeek}' completata (simulazione).`,
      level: "INFO",
    }));
    setLogsData((prev) => [...newExecutionLogs, ...prev].slice(0, 200));
    setSelectedFlows(new Set());
    setIsExecutingFlows(false);
  };

  const filteredLogs = useMemo(() => {
    if (!logsData) return [];
    return logsData
      .filter((log) => {
        const searchTermLower = logSearchTerm.toLowerCase();
        const messageMatch =
          log.message && typeof log.message === "string"
            ? log.message.toLowerCase().includes(searchTermLower)
            : false;
        const flow = log.flowId
          ? flowsData.find((f) => f.id === log.flowId)
          : undefined;
        const flowName = flow ? flow.name : undefined;
        const flowNameMatch =
          flowName && typeof flowName === "string"
            ? flowName.toLowerCase().includes(searchTermLower)
            : false;
        const searchMatch = messageMatch || flowNameMatch;
        const levelMatch =
          logLevelFilter === "all" ||
          (log.level && typeof log.level === "string"
            ? log.level.toLowerCase() === logLevelFilter.toLowerCase()
            : false);
        return searchMatch && levelMatch;
      })
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [logsData, logSearchTerm, logLevelFilter, flowsData]);

  const handleRefreshLogs = async () => {
    setIsRefreshingLogs(true);
    await simulateApiCall(1000);
    const flowExample = flowsData[Math.floor(Math.random() * flowsData.length)];
    setLogsData((prevLogs) =>
      [
        {
          id: `log_refresh_${Date.now()}`,
          timestamp: new Date().toISOString(),
          flowId: flowExample?.id,
          message: `Nuovo evento di log generato per ${
            flowExample?.name || "sistema"
          }.`,
          level: "DEBUG",
        },
        ...prevLogs,
      ].slice(0, 200)
    );
    showToast("Log aggiornati con successo.", "info");
    setIsRefreshingLogs(false);
  };
  const handleClearLogs = async () => {
    if (
      window.confirm("Sei sicuro di voler pulire tutti i log di esecuzione?")
    ) {
      setIsClearingLogs(true);
      await simulateApiCall(1000);
      setLogsData([]);
      showToast("Log puliti con successo.", "success");
      setIsClearingLogs(false);
    }
  };
  const handleDownloadLogs = async () => {
    setIsDownloadingLogs(true);
    showToast("Preparazione download log...", "info");
    await simulateApiCall(2000);
    const logData = filteredLogs
      .map(
        (log) =>
          `${new Date(log.timestamp).toLocaleString()} [${
            log.level?.toUpperCase() || "N/D"
          }] ${log.message || ""}`
      )
      .join("\n");
    const blob = new Blob([logData], { type: "text/plain;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "ingest_logs.txt");
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    showToast("Download avviato.", "success");
    setIsDownloadingLogs(false);
  };


  const TABS = [
    {
      id: "execution",
      label: "Esecuzione",
      icon: PlayCircle,
      description: "Seleziona ed esegui flussi",
    },
    {
      id: "logs",
      label: "Log",
      icon: TerminalSquare,
      description: "Visualizza log di esecuzione",
    },
  ];

  const renderActiveTabContent = () => {
  // --- 1. CONTROLLO DELLO STATO DI CARICAMENTO ---
  // Se stiamo caricando i dati iniziali dei flussi, mostriamo un messaggio
  // e non renderizziamo nessuno dei due tab.
 if (isLoading) {
    return (
      <div className="tab-content-padding loading-container">
        <RefreshCw className="animate-spin-css" />
        <p>Caricamento flussi dal backend...</p>
      </div>
    );
  }

  // --- 2. SWITCH PER DECIDERE QUALE TAB MOSTRARE ---
  // Una volta terminato il caricamento, decidiamo quale componente renderizzare
  // in base allo stato 'activeTab'.
  switch (activeTab) {
    case "execution":
      // Se la tab attiva è "execution", renderizziamo il componente ExecutionTabContent
      return (
        <ExecutionTabContent
          // Gli passiamo tutte le props di cui ha bisogno per funzionare
          selectedFlows={selectedFlows}
          handleSelectFlow={handleSelectFlow}
          handleSelectAllFlows={handleSelectAllFlows}
          searchTerm={searchTerm}
          setSearchTerm={setSearchTerm}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          sortConfig={sortConfig}
          requestSort={requestSort}
          getSortIcon={getSortIcon}
          filteredAndSortedFlows={filteredAndSortedFlows}
          flowPackages={flowPackages}
          flowStatuses={flowStatuses}
          isExecuting={isExecutingFlows}
          generalParams={generalParams}
          handleGeneralParamChange={handleGeneralParamChange}
          handleExecuteSelectedFlows={handleExecuteSelectedFlows}
        />
      );
    case "logs":
      // Se la tab attiva è "logs", renderizziamo il componente LogsTabContent
      return (
        <LogsTabContent
          // Gli passiamo tutte le props di cui ha bisogno
          logs={logsData}
          flows={flowsData} 
          logSearchTerm={logSearchTerm}
          setLogSearchTerm={setLogSearchTerm}
          logLevelFilter={logLevelFilter}
          setLogLevelFilter={setLogLevelFilter}
          handleRefreshLogs={handleRefreshLogs}
          handleClearLogs={handleClearLogs}
          handleDownloadLogs={handleDownloadLogs}
          filteredLogs={filteredLogs} 
          isRefreshingLogs={isRefreshingLogs}
          isClearingLogs={isClearingLogs}
          isDownloadingLogs={isDownloadingLogs}
        />
      );
    default:
      // Se per qualche motivo activeTab non corrisponde a nessun caso, non mostriamo nulla.
      return null;
  }
};

  const isAnyCriticalLoadingOverall =
    isExecutingFlows || isRefreshingLogs || isClearingLogs || isDownloadingLogs;

   return (
    <div className="ingest-container">
      <div className="ingest-content-wrapper">
        <header className="ingest-header-container">
          <div className="ingest-header">
            <div className="ingest-header-title-group">
              <div className="ingest-header-icon-bg">
                <Layers className="ingest-header-icon" />
              </div>
              <div>
                <h1 className="ingest-header-title">Gestione Flussi Dati</h1>
                <p className="ingest-header-subtitle">
                  Esegui flussi e monitora i log di ingestione.
                </p>
              </div>
            </div>
            <div className="ingest-header-actions-group">
              <button
                onClick={() => navigate("/home")}
                className="btn btn-outline ingest-header-back-button"
                disabled={isAnyCriticalLoadingOverall}
              >
                ← Indietro
              </button>
            </div>
          </div>
        </header>

        <nav className="tab-nav-container">
          <div className="tab-nav-grid">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`tab-button ${activeTab === tab.id ? "active" : ""}`}
                  disabled={isAnyCriticalLoadingOverall && activeTab !== tab.id}
                >
                  <div className="tab-button-header">
                    <Icon className="tab-button-icon" />
                    <span className="tab-button-label">{tab.label}</span>
                  </div>
                  <p className="tab-button-description">{tab.description}</p>
                </button>
              );
            })}
          </div>
        </nav>

        {/* ========================================================= */}
        {/* ---       BARRA DEI FILTRI SPOSTATA QUI                 --- */}
        {/* ========================================================= */}
        {/* Mostra i filtri solo se non stiamo caricando e se siamo nel tab "execution" */}
        {!isLoading && activeTab === 'execution' && (
          <div className="ingest-filters-bar">
            <input
              type="text"
              placeholder="Cerca per Nome o Package..."
              className="form-input"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              disabled={isExecutingFlows}
            />
            <select
              className="form-select"
              value={packageFilter}
              onChange={(e) => setpackageFilter(e.target.value)}
              disabled={isExecutingFlows}
            >
              <option value="all">Tutti i Package</option>
              {flowPackages.filter(pkg => pkg !== 'all').map((pkg) => (
                <option key={pkg} value={pkg}>{pkg}</option>
              ))}
            </select>
            <select
              className="form-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              disabled={isExecutingFlows}
            >
              <option value="all">Tutti i Risultati</option>
              {flowStatuses.filter(status => status !== 'all').map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </div>
        )}
        
        <main className="tab-content-main">
          {renderActiveTabContent()}
        </main>
      </div>
    </div>
  );
}
export default Ingest;  
