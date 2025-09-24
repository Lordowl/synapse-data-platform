import React, { useMemo, memo } from "react";
import { RefreshCw } from "lucide-react";
import "./LogsTab.css";

function LogsTabContent({
  logsData,
  historyData,
  logSearchTerm,
  setLogSearchTerm,
  logLevelFilter,
  setLogLevelFilter,
  handleRefreshLogs,
  isRefreshingLogs,
}) {
  console.log("logs data dentro tab", logsData);
  console.log("history data dentro tab", historyData);
  // Filtri
  const filteredExecutions = useMemo(() => {
    return logsData.filter((exec) => {
      const matchesLevel =
        logLevelFilter === "all" ||
        (exec.level || "").toLowerCase() === logLevelFilter.toLowerCase();

      const matchesSearch =
        exec.logKey?.toLowerCase().includes(logSearchTerm.toLowerCase()) ||
        (exec.flowName || "").toLowerCase().includes(logSearchTerm.toLowerCase());

      return matchesLevel && matchesSearch;
    });
  }, [logsData, logLevelFilter, logSearchTerm]);

  return (
    <div className="logs-tab-content">
      <div className="logs-controls">
        <input
          type="text"
          placeholder="Cerca esecuzione..."
          value={logSearchTerm}
          onChange={(e) => setLogSearchTerm(e.target.value)}
          disabled={isRefreshingLogs}
        />
        <select
          value={logLevelFilter}
          onChange={(e) => setLogLevelFilter(e.target.value)}
          disabled={isRefreshingLogs}
        >
          <option value="all">Tutti i Livelli</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
          <option value="warning">Warning</option>
        </select>
        <button onClick={handleRefreshLogs} disabled={isRefreshingLogs}>
          {isRefreshingLogs ? (
            <>
              <RefreshCw className="spin" /> Aggiornando...
            </>
          ) : (
            "Aggiorna"
          )}
        </button>
      </div>

      {filteredExecutions.length === 0 ? (
        <p className="text-center">Nessuna esecuzione trovata</p>
      ) : (
        filteredExecutions.map((exec) => (
          <div key={exec.logKey} className="execution-card">
            <div className="execution-header">
              <span>{exec.timestamp || "-"}</span>
            </div>
            <div className="execution-message">
              <p>{exec.message || "-"}</p>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export default memo(LogsTabContent);
