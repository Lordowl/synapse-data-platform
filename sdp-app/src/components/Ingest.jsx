// src/components/Ingest/Ingest.jsx
import React, { useState, useMemo, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "react-toastify";
import apiClient from "../api/apiClient";
import { useAppContext } from "../context/AppContext";
import {
  Play,
  Filter,
  ListChecks,
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
  RefreshCw,
  Trash2,
  Download,
  Layers,
  TerminalSquare,
  PlayCircle,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Search,
} from "lucide-react";
import "./Ingest.css";

const weekOptions = [
  { value: "1", label: "Settimana 1" },
  { value: "2", label: "Settimana 2" },
  { value: "3", label: "Settimana 3" },
  { value: "4", label: "Settimana 4" },
  { value: "5", label: "Settimana 5" },
  { value: "6", label: "Settimana 6" },
  { value: "7", label: "Settimana 7" },
  { value: "8", label: "Settimana 8" },
  { value: "9", label: "Settimana 9" },
  { value: "10", label: "Settimana 10" },
  { value: "11", label: "Settimana 11" },
  { value: "12", label: "Settimana 12" },
  { value: "13", label: "Settimana 13" },
  { value: "14", label: "Settimana 14" },
  { value: "15", label: "Settimana 15" },
  { value: "16", label: "Settimana 16" },
  { value: "17", label: "Settimana 17" },
  { value: "18", label: "Settimana 18" },
  { value: "19", label: "Settimana 19" },
  { value: "20", label: "Settimana 20" },
  { value: "21", label: "Settimana 21" },
  { value: "22", label: "Settimana 22" },
  { value: "23", label: "Settimana 23" },
  { value: "24", label: "Settimana 24" },
  { value: "25", label: "Settimana 25" },
  { value: "26", label: "Settimana 26" },
  { value: "27", label: "Settimana 27" },
  { value: "28", label: "Settimana 28" },
  { value: "29", label: "Settimana 29" },
  { value: "30", label: "Settimana 30" },
  { value: "31", label: "Settimana 31" },
  { value: "32", label: "Settimana 32" },
  { value: "33", label: "Settimana 33" },
  { value: "34", label: "Settimana 34" },
  { value: "35", label: "Settimana 35" },
  { value: "36", label: "Settimana 36" },
  { value: "37", label: "Settimana 37" },
  { value: "38", label: "Settimana 38" },
  { value: "39", label: "Settimana 39" },
  { value: "40", label: "Settimana 40" },
  { value: "41", label: "Settimana 41" },
  { value: "42", label: "Settimana 42" },
  { value: "43", label: "Settimana 43" },
  { value: "44", label: "Settimana 44" },
  { value: "45", label: "Settimana 45" },
  { value: "46", label: "Settimana 46" },
  { value: "47", label: "Settimana 47" },
  { value: "48", label: "Settimana 48" },
  { value: "49", label: "Settimana 49" },
  { value: "50", label: "Settimana 50" },
  { value: "51", label: "Settimana 51" },
  { value: "52", label: "Settimana 52" },
];

const currentYear = new Date().getFullYear();
const yearOptions = Array.from({ length: 2 }, (_, i) => currentYear - i).map(
  (year) => ({ value: year.toString(), label: year.toString() })
);

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
    case "failed":
      return "log-level-error";
    case "warning":
      return "log-level-warning";
    case "info":
      return "log-level-info";
    case "success":
      return "log-level-success";
    default:
      return "log-level-debug";
  }
};

// --- Funzione per mappare il log del backend al formato frontend ---
const mapBackendLogToFrontend = (backendLog, flows) => {
  // Cerca il flusso che ha originalId uguale a element_id
  const flow = flows.find((f) => f.originalId === backendLog.element_id);

  return {
    id: backendLog.id,
    timestamp: backendLog.timestamp,
    flowId: backendLog.element_id, // conserva element_id
    flowName: flow?.name || backendLog.element_id, // nome leggibile
    message:
      backendLog.details?.message ||
      `Esecuzione flusso ${backendLog.element_id}`,
    level:
      backendLog.status?.toLowerCase() === "success"
        ? "success"
        : backendLog.status?.toLowerCase() === "failed"
        ? "error"
        : "info",
    details: backendLog.details
      ? JSON.stringify(backendLog.details, null, 2)
      : null,
  };
};


// --- Sotto-Componente per il Tab Esecuzione Flussi ---
function ExecutionTabContent({
  filteredAndSortedFlows,
  selectedFlows,
  handleSelectFlow,
  handleSelectAllFlows,
  isExecuting,
  handleExecuteSelectedFlows,
  generalParams,
  handleGeneralParamChange,
  sortConfig,
  requestSort,
  getSortIcon,
}) {
 const getRowColorByResult = (resultStatus) => {
  if (!resultStatus) return "row-color-default";
  switch (resultStatus.toLowerCase()) {
    case "success":
      return "row-color-success";
    case "failed":
      return "row-color-failed";
    case "warning":
      return "row-color-warning";
    case "running":
      return "row-color-running";
    case "n/a":
      return "row-color-na"; // definisci questa classe nel CSS
    default:
      return "row-color-default";
  }
};

  return (
    <div className="tab-content-padding">
      <div className="ingest-section-header execution-tab-header">
        <div className="ingest-section-header-title-group">
          <Filter className="ingest-section-icon" />
          <h2 className="ingest-section-title">Selezione Flussi</h2>
        </div>
        <button
          onClick={handleExecuteSelectedFlows}
          className={`btn ${
            isExecuting ? "btn-disabled-visual" : "btn-primary"
          } execution-tab-run-button`}
          disabled={selectedFlows.size === 0 || isExecuting}
        >
          {isExecuting ? (
            <>
              <RefreshCw className="btn-icon-md animate-spin-css" />
              Esecuzione...
            </>
          ) : (
            <>
              <Play className="btn-icon-md" /> Esegui ({selectedFlows.size})
            </>
          )}
        </button>
      </div>

      <div className="ingest-table-wrapper">
        <table className="ingest-table">
          <thead>
            <tr>
              <th>
                <input
                  type="checkbox"
                  className="form-checkbox"
                  onChange={handleSelectAllFlows}
                  checked={
                    filteredAndSortedFlows.length > 0 &&
                    selectedFlows.size === filteredAndSortedFlows.length
                  }
                  ref={(el) => {
                    if (el) {
                      el.indeterminate =
                        selectedFlows.size > 0 &&
                        selectedFlows.size < filteredAndSortedFlows.length;
                    }
                  }}
                  disabled={filteredAndSortedFlows.length === 0 || isExecuting}
                />
              </th>
              <th onClick={() => !isExecuting && requestSort("name")}>
                Nome Flusso {getSortIcon("name")}
              </th>
              <th onClick={() => !isExecuting && requestSort("package")}>
                Package {getSortIcon("package")}
              </th>
              <th onClick={() => !isExecuting && requestSort("id")}>
                ID -SEQ {getSortIcon("id")}
              </th>
              <th onClick={() => !isExecuting && requestSort("lastRun")}>
                Ultima Esecuzione {getSortIcon("lastRun")}
              </th>
              <th onClick={() => !isExecuting && requestSort("result")}>
                Risultato {getSortIcon("result")}
              </th>
              <th>Dettagli</th>
            </tr>
          </thead>
          <tbody>
            {filteredAndSortedFlows.map((flow) => (
              <tr
                key={flow.id}
                className={`${
                  selectedFlows.has(flow.id) ? "selected-row" : ""
                } ${getRowColorByResult(flow.result)}`}
              >
                <td>
                  <input
                    type="checkbox"
                    className="form-checkbox"
                    checked={selectedFlows.has(flow.id)}
                    onChange={() => handleSelectFlow(flow.id)}
                    disabled={isExecuting}
                  />
                </td>
                <td data-label="Flusso">
                  {flow.name ? (
                    flow.name
                  ) : (
                    <span className="muted-text italic">{flow.id}</span>
                  )}
                </td>
                <td data-label="Package">{flow.package}</td>
                <td data-label="ID Univoco">
                  <span className="muted-text">{flow.id}</span>
                </td>
                <td data-label="Ultima Esecuzione">
                  {flow.lastRun
                    ? new Date(flow.lastRun).toLocaleString("it-IT")
                    : "N/A"}
                </td>
                <td data-label="Risultato">
                  <span
                    className={`status-badge ${getStatusBadgeColor(
                      flow.result
                    )}`}
                  >
                    {flow.result || "N/A"}
                  </span>
                </td>
                <td data-label="Dettagli">
                  {flow.detail ? (
                    <pre className="flow-detail-content">{flow.detail}</pre>
                  ) : (
                    <span className="muted-text italic">Nessun dettaglio</span>
                  )}
                </td>
              </tr>
            ))}
            {filteredAndSortedFlows.length === 0 && (
              <tr>
                <td colSpan="7" className="text-center muted-text">
                  Nessun flusso dati trovato per i filtri selezionati.
                </td>
              </tr>
            )}
          </tbody>
        </table>
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

  const [expandedLogId, setExpandedLogId] = useState(null);

  const toggleLogDetails = (logId) => {
    setExpandedLogId((prevId) => (prevId === logId ? null : logId));
  };

  const getLogRowColorClass = (level) => {
    if (!level || typeof level !== "string") return "log-row-default";
    switch (level.toLowerCase()) {
      case "success":
        return "log-row-success";
      case "error":
      case "failed":
        return "log-row-error";
      case "warning":
        return "log-row-warning";
      case "info":
        return "log-row-info";
      case "debug":
        return "log-row-debug";
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
          <option value="success">Success</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
          <option value="failed">Failed</option>
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
        <table className="ingest-log-table">
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
                      {new Date(log.timestamp).toLocaleString("it-IT")}
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
                      flows.find((f) => f.originalId === log.flowId)?.name ? (
                        flows.find((f) => f.originalId === log.flowId)?.name
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
                          className="btn btn-outline btn-sm log-details-btn"
                          aria-expanded={expandedLogId === log.id}
                          disabled={anyLogActionLoading}
                        >
                          {expandedLogId === log.id ? (
                            <ChevronUp size={16} />
                          ) : (
                            <ChevronDown size={16} />
                          )}
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
  const location = useLocation();
  const metadataFilePath = location.state?.metadataFilePath;
  const [activeTab, setActiveTab] = useState("execution");
  const [isLoading, setIsLoading] = useState(true);
  const [flowsData, setFlowsData] = useState([]);
  const [logsData, setLogsData] = useState([]);
  const [isUpdatingFlows, setIsUpdatingFlows] = useState(false);

  // Stati per filtri e interazioni
  const [selectedFlows, setSelectedFlows] = useState(new Set());
  const [searchTerm, setSearchTerm] = useState("");
  const [packageFilter, setpackageFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortConfig, setSortConfig] = useState({
    key: "id",
    direction: "ascending",
  });

  const [generalParams, setGeneralParams] = useState({
    selectedWeek: "1",
    selectedYear: currentYear.toString(),
  });
  const [logSearchTerm, setLogSearchTerm] = useState("");
  const [logLevelFilter, setLogLevelFilter] = useState("all");

  const [isExecutingFlows, setIsExecutingFlows] = useState(false);
  const [isRefreshingLogs, setIsRefreshingLogs] = useState(false);
  const [isClearingLogs, setIsClearingLogs] = useState(false);
  const [isDownloadingLogs, setIsDownloadingLogs] = useState(false);

  // Funzione per caricare i dati iniziali
  const fetchInitialData = async () => {
    setIsLoading(true);
    try {
      console.log("-> Avvio aggiornamento automatico flussi da Excel...");
      console.log("Invio file_path al backend:", metadataFilePath);

      await apiClient.post("/tasks/update-flows-from-excel", {
        file_path: metadataFilePath,
      });
      console.log("-> Aggiornamento da Excel completato sul backend.");
      toast.info("Fonte dati aggiornata dall'Excel.");

      console.log("-> Caricamento flussi e storico...");
      const [flowsResponse, historyResponse] = await Promise.all([
        apiClient.get("/flows"),
        apiClient.get("/flows/history"), // Usa FlowExecutionDetail per lo storico
      ]);

      const staticFlows = flowsResponse.data;
      const historyMap = historyResponse.data;

      // DEBUG: Vediamo cosa restituisce il backend
      console.log("🔍 DEBUG - staticFlows:", staticFlows?.slice(0, 2));
      console.log("🔍 DEBUG - historyMap:", historyMap);
      console.log("🔍 DEBUG - historyMap keys:", Object.keys(historyMap));
      console.log("🔍 DEBUG - historyMap length:", Object.keys(historyMap).length);
      
      if (!Array.isArray(staticFlows)) {
        throw new Error("La risposta dei flussi non è valida.");
      }

      console.log("-> Unione dati per la visualizzazione...");
      const combinedFlows = staticFlows.map((flow) => {
        const flowId = flow.ID; // Usa solo la prima parte dell'ID
        const executionHistory = historyMap[flowId] || {};

        return {
          id: `${flow.ID}-${flow.SEQ || "0"}`,
          originalId: flow.ID,
          originalSeq: flow.SEQ || "0",
          name: flow["Filename out"],
          package: flow["Package"],
          year: new Date().getFullYear(),
          lastRun: executionHistory.timestamp || null,
          result: executionHistory.result || "N/A",
          detail: executionHistory.error_lines || "",
          duration: executionHistory.duration || null,
        };
      });

      console.log("Dati combinati pronti:", combinedFlows);
      setFlowsData(combinedFlows);
      toast.success("Dati caricati e pronti.");
    } catch (error) {
      console.error(
        "Errore nel processo di caricamento e aggiornamento:",
        error
      );
      toast.error(
        error.response?.data?.detail ||
          "Un'operazione è fallita durante il caricamento."
      );
    } finally {
      setIsLoading(false);
    }
  };

  // Funzione per caricare i log dal backend (usa FlowExecutionHistory)
  const fetchLogs = async () => {
    try {
      const response = await apiClient.get("/flows/logs");
      const backendLogs = response.data;

      if (!Array.isArray(backendLogs)) throw new Error("Logs non validi");

      const frontendLogs = backendLogs.map((log) =>
        mapBackendLogToFrontend(log, flowsData)
      );

      setLogsData(frontendLogs);
    } catch (error) {
      console.error("Errore nel caricamento dei log:", error);
      toast.error("Errore nel caricamento dei log di esecuzione");
      setLogsData([]);
    }
  };

  useEffect(() => {
    fetchInitialData();
  }, []);

  // Carica i log quando cambia activeTab o quando i flussi sono caricati
  useEffect(() => {
    if (activeTab === "logs" && flowsData.length > 0) {
      fetchLogs();
    }
  }, [activeTab, flowsData]);

  const flowPackages = useMemo(
    () => ["all", ...new Set(flowsData.map((f) => f.package).filter(Boolean))],
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
    console.log("Stato attuale dei filtri:", {
      searchTerm,
      packageFilter,
      statusFilter,
    });
    console.log("Dati di input (flowsData):", flowsData);
    return flowsData.filter(
      (flow) =>
        (flow.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
          flow.package?.toLowerCase().includes(searchTerm.toLowerCase())) &&
        (packageFilter === "all" || flow.package === packageFilter) &&
        (statusFilter === "all" || (flow.result || "N/A") === statusFilter)
    );
  }, [flowsData, searchTerm, packageFilter, statusFilter]);

  const filteredAndSortedFlows = useMemo(() => {
    let sortableFlows = [...filteredFlows];

    if (sortConfig.key) {
      sortableFlows.sort((a, b) => {
        const aValue = a[sortConfig.key];
        const bValue = b[sortConfig.key];

        if (sortConfig.key === "id") {
          const numA = parseInt(a.originalId, 10) || 0;
          const numB = parseInt(b.originalId, 10) || 0;

          if (numA !== numB) {
            return numA - numB;
          }

          const seqA = parseInt(a.originalSeq, 10) || 0;
          const seqB = parseInt(b.originalSeq, 10) || 0;
          return seqA - seqB;
        }

        if (sortConfig.key === "lastRun") {
          const dateA = aValue ? new Date(aValue).getTime() : 0;
          const dateB = bValue ? new Date(bValue).getTime() : 0;
          return dateA - dateB;
        }

        const strA = (aValue || "").toString().toLowerCase();
        const strB = (bValue || "").toString().toLowerCase();
        return strA.localeCompare(strB);
      });

      if (sortConfig.direction === "descending") {
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

  const handleExecuteSelectedFlows = async () => {
    if (selectedFlows.size === 0) {
      toast.warn("Nessun flusso selezionato per l'esecuzione.");
      return;
    }

    setIsExecutingFlows(true);

    try {
      const flowsToRun = flowsData.filter((f) => selectedFlows.has(f.id));

      if (flowsToRun.length === 0) {
        toast.warn("I flussi selezionati non sono presenti nei dati.");
        return;
      }

      const executionPayload = {
        flows: flowsToRun.map((f) => {
          const mainId = f.id.split("-")[0];
          return {
            id: mainId,
            name: f.name,
          };
        }),
        params: generalParams,
      };

      console.log("Payload inviato al backend:", executionPayload);

      const response = await apiClient.post(
        "/tasks/execute-flows",
        executionPayload
      );

      toast.success(response.data.message || "Esecuzione completata!");

      // Ricarica i dati dopo l'esecuzione
      await fetchInitialData();

      // Se siamo nel tab logs, ricarica anche i log
      if (activeTab === "logs") {
        await fetchLogs();
      }
    } catch (error) {
      console.error("Errore durante l'esecuzione:", error);
      toast.error(
        error.response?.data?.detail || "L'esecuzione dei flussi è fallita."
      );
    } finally {
      setSelectedFlows(new Set());
      setIsExecutingFlows(false);
    }
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
          ? flowsData.find((f) => f.originalId === log.flowId)
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
    try {
      await fetchLogs();
      toast.success("Log aggiornati con successo.");
    } catch (error) {
      toast.error("Errore nell'aggiornamento dei log.");
    } finally {
      setIsRefreshingLogs(false);
    }
  };

  const handleClearLogs = async () => {
    if (
      window.confirm("Sei sicuro di voler pulire tutti i log di esecuzione?")
    ) {
      setIsClearingLogs(true);
      try {
        // Chiamata API per pulire i log dal backend
        await apiClient.delete("/flows/logs");
        setLogsData([]);
        toast.success("Log puliti con successo.");
      } catch (error) {
        console.error("Errore nella pulizia dei log:", error);
        toast.error("Errore nella pulizia dei log.");
      } finally {
        setIsClearingLogs(false);
      }
    }
  };

  const handleDownloadLogs = async () => {
    setIsDownloadingLogs(true);
    try {
      toast.info("Preparazione download log...");

      const logData = filteredLogs
        .map(
          (log) =>
            `${new Date(log.timestamp).toLocaleString("it-IT")} [${
              log.level?.toUpperCase() || "N/D"
            }] ${log.flowId || "N/A"}: ${log.message || ""}`
        )
        .join("\n");

      const blob = new Blob([logData], { type: "text/plain;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute(
        "download",
        `ingest_logs_${new Date().toISOString().split("T")[0]}.txt`
      );
      link.style.visibility = "hidden";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      toast.success("Download completato.");
    } catch (error) {
      console.error("Errore nel download dei log:", error);
      toast.error("Errore nel download dei log.");
    } finally {
      setIsDownloadingLogs(false);
    }
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
    if (isLoading) {
      return (
        <div className="tab-content-padding loading-container">
          <RefreshCw className="animate-spin-css" />
          <p>Caricamento flussi dal backend...</p>
        </div>
      );
    }

    switch (activeTab) {
      case "execution":
        return (
          <ExecutionTabContent
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
        return (
          <LogsTabContent
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
                <h1 className="ingest-header-title">Ingestion</h1>
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
                  className={`tab-button ${
                    activeTab === tab.id ? "active" : ""
                  }`}
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

        {!isLoading && activeTab === "execution" && (
          <div className="ingest-filters-bar">
            <select
              id="week-select"
              className="form-select form-select-sm"
              value={generalParams.selectedWeek}
              onChange={(e) =>
                handleGeneralParamChange("selectedWeek", e.target.value)
              }
            >
              {weekOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <select
              className="form-select"
              value={packageFilter}
              onChange={(e) => setpackageFilter(e.target.value)}
              disabled={isExecutingFlows}
            >
              <option value="all">Tutti i Package</option>
              {flowPackages
                .filter((pkg) => pkg !== "all")
                .map((pkg) => (
                  <option key={pkg} value={pkg}>
                    {pkg}
                  </option>
                ))}
            </select>
            <select
              id="year-select"
              className="form-select form-select-sm"
              value={generalParams.selectedYear}
              onChange={(e) =>
                handleGeneralParamChange("selectedYear", e.target.value)
              }
            >
              {yearOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <select
              className="form-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              disabled={isExecutingFlows}
            >
              <option value="all">Tutti i Risultati</option>
              {flowStatuses
                .filter((status) => status !== "all")
                .map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
            </select>
          </div>
        )}

        <main className="tab-content-main">{renderActiveTabContent()}</main>
      </div>
    </div>
  );
}

export default Ingest;