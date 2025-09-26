// src/components/Ingest/Ingest.jsx
import React, { useState, useEffect, useMemo } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "react-toastify";
import { Layers, PlayCircle, TerminalSquare, RefreshCw } from "lucide-react";

import ExecutionTabContent from "./ExecutionTab";
import LogsTabContent from "./LogsTab";
import { useIngestData } from "../hooks/useIngestData";
import { useIngestFlows } from "../hooks/useIngestFlows";
import "./Ingest.css";

const TABS = [
  { id: "execution", label: "Esecuzione", icon: PlayCircle, description: "Seleziona ed esegui flussi" },
  { id: "logs", label: "Log", icon: TerminalSquare, description: "Visualizza log di esecuzione" },
];

const currentYear = new Date().getFullYear();
const weekOptions = Array.from({ length: 52 }, (_, i) => ({ value: (i + 1).toString(), label: `Settimana ${i + 1}` }));
const yearOptions = Array.from({ length: 2 }, (_, i) => currentYear - i).map(year => ({ value: year.toString(), label: year.toString() }));

function Ingest() {
  const navigate = useNavigate();
  const location = useLocation();
  const metadataFilePath = location.state?.metadataFilePath;

  const [logSearchTerm, setLogSearchTerm] = useState("");
  const [logLevelFilter, setLogLevelFilter] = useState("all");
  const [activeTab, setActiveTab] = useState("execution");
  const [flowSearchTerm, setFlowSearchTerm] = useState("");

  // 🔹 Persistenza filtri di esecuzione
  const [executionFilters, setExecutionFilters] = useState(() => {
    const saved = localStorage.getItem("executionTabFilters");
    return saved ? JSON.parse(saved) : { name: "", package: "", result: "" };
  });

  const [executionSortConfig, setExecutionSortConfig] = useState(() => {
    const saved = localStorage.getItem("executionTabSortConfig");
    return saved ? JSON.parse(saved) : { key: "name", direction: "asc" };
  });

  // 🔹 Persistenza generalParams (week, year)
  const [generalParams, setGeneralParams] = useState(() => {
    const saved = localStorage.getItem("generalParams");
    return saved ? JSON.parse(saved) : { selectedWeek: "1", selectedYear: currentYear.toString() };
  });

  // 🔹 Persistenza package e status filter
  const [packageFilter, setPackageFilter] = useState(() => {
    return localStorage.getItem("packageFilter") || "all";
  });
  const [statusFilter, setStatusFilter] = useState(() => {
    return localStorage.getItem("statusFilter") || "all";
  });

  // 🔹 Gestione dati
  const { flowsData, logsData, historyData, isLoading, fetchInitialData, fetchLogs } = useIngestData(metadataFilePath);

  const {
    selectedFlows,
    flowPackages,
    flowStatuses,
    isExecutingFlows,
    handleSelectFlow,
    handleSelectAllFlows,
    handleExecuteSelectedFlows,
    requestSort,
    getSortIcon,
  } = useIngestFlows(flowsData, generalParams, setGeneralParams, fetchInitialData, fetchLogs, activeTab);

  // 🔹 Trasformazione logsData in headers e dettagli
  const [executionHeaders, setExecutionHeaders] = useState([]);
  const [executionDetails, setExecutionDetails] = useState([]);

  useEffect(() => {
    if (!logsData.length) return;

    const headersMap = {};
    const detailsArr = [];

    logsData.forEach(log => {
      if (!headersMap[log.logKey]) {
        headersMap[log.logKey] = { logKey: log.logKey, executed_by: log.executed_by || "N/A", status: log.status, timestamp: log.timestamp };
      }
      detailsArr.push({ id: log.id, executionId: log.logKey, flowId: log.flowId, step: log.step, status: log.status, message: log.message, timestamp: log.timestamp });
    });

    setExecutionHeaders(Object.values(headersMap));
    setExecutionDetails(detailsArr);
  }, [logsData]);

  // 🔹 Caricamento iniziale dati
  useEffect(() => {
    if (!metadataFilePath) {
      toast.error("Nessun file Excel selezionato. Torna alla home e seleziona un file.");
      navigate("/home");
      return;
    }
    fetchInitialData();
  }, [metadataFilePath, fetchInitialData, navigate]);

  // 🔹 Sincronizzazione filtri/ordinamento tra finestre/tab
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === "executionTabFilters" && e.newValue) setExecutionFilters(JSON.parse(e.newValue));
      if (e.key === "executionTabSortConfig" && e.newValue) setExecutionSortConfig(JSON.parse(e.newValue));
      if (e.key === "generalParams" && e.newValue) setGeneralParams(JSON.parse(e.newValue));
      if (e.key === "packageFilter" && e.newValue) setPackageFilter(e.newValue);
      if (e.key === "statusFilter" && e.newValue) setStatusFilter(e.newValue);
    };
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  // 🔹 Filtraggio locale per ricerca flussi
  const displayedFlows = useMemo(() => {
    if (!flowsData) return [];
    if (!flowSearchTerm) return flowsData;

    const query = flowSearchTerm.toLowerCase();
    return flowsData.filter(
      flow =>
        (flow.name && flow.name.toLowerCase().includes(query)) ||
        flow.id.toLowerCase().includes(query)
    );
  }, [flowsData, flowSearchTerm]);

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
            filteredAndSortedFlows={displayedFlows}
            isExecuting={isExecutingFlows}
            handleExecuteSelectedFlows={handleExecuteSelectedFlows}
            generalParams={generalParams}
            handleGeneralParamChange={(key, value) => {
              const updated = { ...generalParams, [key]: value };
              setGeneralParams(updated);
              localStorage.setItem("generalParams", JSON.stringify(updated));
            }}
            sortConfig={executionSortConfig}
            requestSort={(key) => {
              let direction = "asc";
              if (executionSortConfig.key === key && executionSortConfig.direction === "asc") direction = "desc";
              const newSort = { key, direction };
              setExecutionSortConfig(newSort);
              localStorage.setItem("executionTabSortConfig", JSON.stringify(newSort));
            }}
            getSortIcon={getSortIcon}
            filters={executionFilters}
            setFilters={(newFilters) => {
              setExecutionFilters(newFilters);
              localStorage.setItem("executionTabFilters", JSON.stringify(newFilters));
            }}
            packageFilter={packageFilter}
            setPackageFilter={(value) => {
              setPackageFilter(value);
              localStorage.setItem("packageFilter", value);
            }}
            statusFilter={statusFilter}
            setStatusFilter={(value) => {
              setStatusFilter(value);
              localStorage.setItem("statusFilter", value);
            }}
          />
        );
      case "logs":
        return (
          <LogsTabContent
            logsData={logsData}
            historyData={historyData}
            logSearchTerm={logSearchTerm}
            setLogSearchTerm={setLogSearchTerm}
            logLevelFilter={logLevelFilter}
            setLogLevelFilter={setLogLevelFilter}
            handleRefreshLogs={fetchLogs}
            isRefreshingLogs={isLoading}
          />
        );
      default:
        return null;
    }
  };

  const isAnyCriticalLoadingOverall = isExecutingFlows;

  return (
    <div className="ingest-container">
      <div className="ingest-content-wrapper">
        <header className="ingest-header-container">
          <div className="ingest-header">
            <div className="ingest-header-title-group">
              <div className="ingest-header-icon-bg"><Layers className="ingest-header-icon" /></div>
              <div>
                <h1 className="ingest-header-title">Ingestion</h1>
                <p className="ingest-header-subtitle">Esegui flussi e monitora i log di ingestione.</p>
              </div>
            </div>
            <div className="ingest-header-actions-group">
              <button onClick={() => navigate("/home")} className="btn btn-outline ingest-header-back-button" disabled={isAnyCriticalLoadingOverall}>← Indietro</button>
            </div>
          </div>
        </header>

        <nav className="tab-nav-container">
          <div className="tab-nav-grid">
            {TABS.map(tab => {
              const Icon = tab.icon;
              return (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`tab-button ${activeTab === tab.id ? "active" : ""}`} disabled={isAnyCriticalLoadingOverall && activeTab !== tab.id}>
                  <div className="tab-button-header"><Icon className="tab-button-icon" /><span className="tab-button-label">{tab.label}</span></div>
                  <p className="tab-button-description">{tab.description}</p>
                </button>
              );
            })}
          </div>
        </nav>

        {!isLoading && activeTab === "execution" && (
          <div className="ingest-filters-bar">
            <input
              type="text"
              className="form-input ingest-filter-input"
              placeholder="Cerca per nome o ID..."
              value={flowSearchTerm}
              onChange={(e) => setFlowSearchTerm(e.target.value)}
              disabled={isExecutingFlows}
            />

            <select id="week-select" className="form-select form-select-sm" value={generalParams.selectedWeek} onChange={(e) => {
              const updated = { ...generalParams, selectedWeek: e.target.value };
              setGeneralParams(updated);
              localStorage.setItem("generalParams", JSON.stringify(updated));
            }}>
              {weekOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>

            <select id="year-select" className="form-select form-select-sm" value={generalParams.selectedYear} onChange={(e) => {
              const updated = { ...generalParams, selectedYear: e.target.value };
              setGeneralParams(updated);
              localStorage.setItem("generalParams", JSON.stringify(updated));
            }}>
              {yearOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>

            <select className="form-select" value={packageFilter} onChange={(e) => {
              setPackageFilter(e.target.value);
              localStorage.setItem("packageFilter", e.target.value);
            }} disabled={isExecutingFlows}>
              <option value="all">Tutti i Package</option>
              {flowPackages.filter(pkg => pkg !== "all").map(pkg => <option key={pkg} value={pkg}>{pkg}</option>)}
            </select>

            <select className="form-select" value={statusFilter} onChange={(e) => {
              setStatusFilter(e.target.value);
              localStorage.setItem("statusFilter", e.target.value);
            }} disabled={isExecutingFlows}>
              <option value="all">Tutti i Risultati</option>
              {flowStatuses.filter(status => status !== "all").map(status => <option key={status} value={status}>{status}</option>)}
            </select>
          </div>
        )}

        <main className="tab-content-main">{renderActiveTabContent()}</main>
      </div>
    </div>
  );
}

export default Ingest;
