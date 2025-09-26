import React, { useMemo, memo, useState, useEffect } from "react";
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { DateTime } from "luxon";
import "./LogsTab.css";

function LogsTabContent({
  logsData,
  historyData,
  logSearchTerm,
  setLogSearchTerm,
  logLevelFilter,
  setLogLevelFilter,
  handleRefreshLogs,
}) {
  const [expandedCards, setExpandedCards] = useState({});

  useEffect(() => {
    handleRefreshLogs();
  }, [handleRefreshLogs]);

  const extractResultFromMessage = (message) => {
    if (!message) return "unknown";
    const match = message.match(/Esecuzione flusso:\s*(\w+)/i);
    return match ? match[1].toLowerCase() : "unknown";
  };

  const groupedExecutions = useMemo(() => {
    return logsData.map((log) => {
      const possibleKeys = [
        log.altroLogKey,
        log.parsedLogKey,
        log.logKey,
        log.flowId && log.timestamp ? `${log.flowId}-${log.timestamp}` : null,
      ].filter(Boolean);

      let details = [];
      let matchedKey = null;

      for (const key of possibleKeys) {
        if (historyData[key] && historyData[key].length > 0) {
          details = historyData[key];
          matchedKey = key;
          break;
        }
      }

      return {
        ...log,
        parsedLogKey: matchedKey || possibleKeys[0] || log.logKey,
        overallResult: extractResultFromMessage(log.message),
        details: details.sort(
          (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
        ),
      };
    });
  }, [logsData, historyData]);

  // Ricerca precisa per element_id: mostra tutta l'esecuzione se almeno un dettaglio corrisponde
  const filteredExecutions = useMemo(() => {
    if (!logSearchTerm) return groupedExecutions;

    const search = logSearchTerm.toString().toLowerCase();

    return groupedExecutions.filter((exec) => {
      const matchesLevel =
        logLevelFilter === "all" ||
        exec.overallResult === logLevelFilter.toLowerCase();

      const hasMatchingDetail = exec.details.some(
        (detail) =>
          detail.element_id &&
          detail.element_id.toString().toLowerCase() === search
      );

      return matchesLevel && hasMatchingDetail;
    });
  }, [groupedExecutions, logLevelFilter, logSearchTerm]);

  const getResultIcon = (result) => {
    switch (result?.toLowerCase()) {
      case "success":
        return <CheckCircle className="result-icon success" />;
      case "warning":
        return <AlertTriangle className="result-icon warning" />;
      case "failed":
      case "error":
        return <XCircle className="result-icon error" />;
      default:
        return <Clock className="result-icon default" />;
    }
  };

  const getResultClass = (result) => {
    switch (result?.toLowerCase()) {
      case "success":
        return "result-success";
      case "warning":
        return "result-warning";
      case "failed":
      case "error":
        return "result-error";
      default:
        return "result-default";
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return "-";
    return DateTime.fromISO(timestamp, { zone: "utc" })
      .setZone("Europe/Rome")
      .toLocaleString(DateTime.DATETIME_MED_WITH_SECONDS);
  };

  const getDetailsSummary = (details) => {
    return details.reduce((acc, detail) => {
      const result = (detail.result || "unknown").toLowerCase();
      acc[result] = (acc[result] || 0) + 1;
      return acc;
    }, {});
  };

  const toggleExpanded = (logKey) => {
    setExpandedCards((prev) => ({
      ...prev,
      [logKey]: !prev[logKey],
    }));
  };

  return (
    <div className="logs-tab-content">
      <div className="logs-controls">
        <input
          type="text"
          placeholder="Cerca per ID elemento..."
          value={logSearchTerm}
          onChange={(e) => setLogSearchTerm(e.target.value)}
        />
        <select
          value={logLevelFilter}
          onChange={(e) => setLogLevelFilter(e.target.value)}
        >
          <option value="all">Tutti i Livelli</option>
          <option value="success">Success</option>
          <option value="warning">Warning</option>
          <option value="failed">Failed</option>
          <option value="error">Error</option>
        </select>
      </div>

      {filteredExecutions.length === 0 ? (
        <p className="no-executions">Nessuna esecuzione trovata</p>
      ) : (
        filteredExecutions.map((exec) => {
          const isExpanded =
            expandedCards[exec.parsedLogKey || exec.logKey || exec.id];
          const detailsSummary = getDetailsSummary(exec.details);

          return (
            <div
              key={exec.parsedLogKey || exec.logKey || exec.id}
              className="execution-card"
            >
              <div className="execution-header">
                <div className="execution-main-info">
                  <div className="execution-title">
                    {getResultIcon(exec.overallResult)}
                    <h3 className="log-info">Esecuzione</h3>
                    <span
                      className={`overall-result ${getResultClass(
                        exec.overallResult
                      )}`}
                    >
                      {exec.overallResult.toUpperCase()}
                    </span>
                  </div>

                  <div className="execution-meta">
                    <span className="execution-summary">
                      Esecuzione avvenuta il "{formatTimestamp(exec.timestamp)}"
                      {exec.executedBy ? ` da "${exec.executedBy}"` : ""}
                      {exec.params && Object.keys(exec.params).length > 0
                        ? ` con parametri: ${Object.entries(exec.params)
                            .map(([key, value]) => {
                              if (key === "selectedYear")
                                return `anno ${value}`;
                              if (key === "selectedWeek")
                                return `settimana ${value}`;
                              return `${key}=${value}`;
                            })
                            .join(", ")}`
                        : ""}
                    </span>
                  </div>
                </div>

                {exec.details.length > 0 && (
                  <div className="execution-summary-section">
                    <div className="details-summary">
                      {Object.entries(detailsSummary).map(([result, count]) => (
                        <span
                          key={result}
                          className={`summary-badge ${getResultClass(result)}`}
                        >
                          {result}: {count}
                        </span>
                      ))}
                    </div>
                    <button
                      className="expand-button"
                      onClick={() =>
                        toggleExpanded(
                          exec.parsedLogKey || exec.logKey || exec.id
                        )
                      }
                      aria-expanded={isExpanded}
                    >
                      {isExpanded ? <ChevronDown /> : <ChevronRight />}
                      <span>{isExpanded ? "Nascondi" : "Mostra"} dettagli</span>
                    </button>
                  </div>
                )}
              </div>

              {isExpanded && exec.details.length > 0 && (
                <div className="execution-details">
                  <h4 className="details-title">
                    Dettagli Operazioni ({exec.details.length})
                  </h4>
                  {exec.details.map((detail, index) => (
                    <div
                      key={index}
                      className={`detail-entry ${getResultClass(detail.result)}`}
                    >
                      <div className="entry-header">
                        {getResultIcon(detail.result)}
                        <div className="entry-main-info">
                          {detail.element_id && (
                            <span className="element-id">
                              ID: {detail.element_id}
                            </span>
                          )}
                          <span className="result-text">
                            {detail.result || "Unknown"}
                          </span>
                        </div>
                        <span className="entry-time">
                          {formatTimestamp(detail.timestamp)}
                        </span>
                      </div>
                      {detail.error_lines && (
                        <div className="entry-message">
                          <p>{detail.error_lines}</p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {exec.details.length === 0 && (
                <div className="no-details">
                  <p>Nessun dettaglio disponibile per questa esecuzione</p>
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

export default memo(LogsTabContent);
