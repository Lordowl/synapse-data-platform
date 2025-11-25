import React, { useMemo, memo, useState, useEffect } from "react";
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronRight,
  FileText,
} from "lucide-react";
import { DateTime } from "luxon";
import { toast } from "react-toastify";
import apiClient from "../api/apiClient";
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
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  useEffect(() => {
    handleRefreshLogs();
  }, [handleRefreshLogs]);

  const extractResultFromMessage = (message) => {
    if (!message) return "unknown";
    const match = message.match(/Esecuzione flusso:\s*(\w+)/i);
    return match ? match[1].toLowerCase() : "unknown";
  };

  const groupedExecutions = useMemo(() => {
    console.group("🔍 DEBUG: GroupedExecutions Processing");
    console.log("📊 Input data:");
    console.log("logsData length:", logsData.length);
    console.log("logsData sample:", logsData.slice(0, 2));
    console.log("historyData keys:", Object.keys(historyData));
    console.log("historyData sample entries:", Object.values(historyData).slice(0, 2));

    const processed = logsData.map((log, index) => {
      console.log(`\n--- Processing log ${index + 1}/${logsData.length} ---`);
      console.log("Log object:", log);

      const possibleKeys = [
        log.altroLogKey,
        log.parsedLogKey,
        log.logKey,
        log.flowId && log.timestamp ? `${log.flowId}-${log.timestamp}` : null,
      ].filter(Boolean);

      console.log("Possible keys:", possibleKeys);

      let details = [];
      let matchedKey = null;

      for (const key of possibleKeys) {
        console.log(`Checking key: "${key}"`);
        if (historyData[key] && historyData[key].length > 0) {
          details = historyData[key];
          matchedKey = key;
          console.log(`✅ Found match! Key: "${key}", Details count: ${details.length}`);
          break;
        } else {
          console.log(`❌ No match for key: "${key}"`);
        }
      }

      const result = {
        ...log,
        parsedLogKey: matchedKey || possibleKeys[0] || log.logKey,
        overallResult: extractResultFromMessage(log.message),
        details: details.sort(
          (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
        ),
      };

      console.log("Final result for this log:", {
        parsedLogKey: result.parsedLogKey,
        overallResult: result.overallResult,
        detailsCount: result.details.length
      });

      return result;
    });

    console.log("📊 Final processed executions:", processed.length);
    console.log("Executions with details:", processed.filter(e => e.details.length > 0).length);
    console.log("Executions without details:", processed.filter(e => e.details.length === 0).length);
    console.groupEnd();

    return processed;
  }, [logsData, historyData]);

  // Ricerca precisa per element_id: mostra tutta l'esecuzione se almeno un dettaglio corrisponde
  const filteredExecutions = useMemo(() => {
    console.group("🔍 DEBUG: Filtering Executions");
    console.log("Input:");
    console.log("groupedExecutions length:", groupedExecutions.length);
    console.log("logSearchTerm:", logSearchTerm);
    console.log("logLevelFilter:", logLevelFilter);
    console.log("startDate:", startDate);
    console.log("endDate:", endDate);

    const start = startDate ? new Date(startDate) : null;
    const end = endDate ? new Date(new Date(endDate).setHours(23, 59, 59, 999)) : null;

    // 🔧 FIX: Sempre filtrare per livello, anche senza termine di ricerca
    if (!logSearchTerm) {
      console.log("No search term, filtering by level and date only");

      const levelFiltered = groupedExecutions.filter((exec) => {
        const matchesLevel =
          logLevelFilter === "all" ||
          exec.overallResult === logLevelFilter.toLowerCase();

        // Filtro per data
        const execDate = exec.timestamp ? new Date(exec.timestamp) : null;
        const matchesStartDate = !start || !execDate || execDate >= start;
        const matchesEndDate = !end || !execDate || execDate <= end;

        return matchesLevel && matchesStartDate && matchesEndDate;
      });

      console.log("Level and date filtered executions:", levelFiltered.length);
      console.groupEnd();
      return levelFiltered;
    }

    const search = logSearchTerm.toString().toLowerCase();
    console.log("Searching for:", search);

    const filtered = groupedExecutions.filter((exec, index) => {
      console.log(`\n--- Filtering execution ${index + 1} ---`);
      console.log("Execution:", exec);

      const matchesLevel =
        logLevelFilter === "all" ||
        exec.overallResult === logLevelFilter.toLowerCase();

      console.log("Level match:", matchesLevel, "(level filter:", logLevelFilter, ", exec result:", exec.overallResult, ")");

      // Filtro per data
      const execDate = exec.timestamp ? new Date(exec.timestamp) : null;
      const matchesStartDate = !start || !execDate || execDate >= start;
      const matchesEndDate = !end || !execDate || execDate <= end;

      // 🔧 FIX: Cercare non solo nei dettagli, ma anche nel flowId principale e nel messaggio
      const hasMatchingDetail = exec.details.some(
        (detail) => {
          const elementIdMatch = detail.element_id &&
            detail.element_id.toString().toLowerCase() === search;
          console.log("Detail element_id:", detail.element_id, "matches search:", elementIdMatch);
          return elementIdMatch;
        }
      );

      const flowIdMatches = exec.flowId &&
        exec.flowId.toString().toLowerCase().includes(search);

      const messageMatches = exec.message &&
        exec.message.toString().toLowerCase().includes(search);

      console.log("Has matching detail:", hasMatchingDetail);
      console.log("FlowId matches:", flowIdMatches);
      console.log("Message matches:", messageMatches);

      const hasAnyMatch = hasMatchingDetail || flowIdMatches || messageMatches;
      const finalMatch = matchesLevel && hasAnyMatch && matchesStartDate && matchesEndDate;
      console.log("Final match result:", finalMatch);

      return finalMatch;
    });

    console.log("📊 Filtering results:");
    console.log("Filtered executions:", filtered.length);
    console.groupEnd();

    return filtered;
  }, [groupedExecutions, logLevelFilter, logSearchTerm, startDate, endDate]);

  const getResultIcon = (result) => {
    switch (result?.toLowerCase()) {
      case "success":
        return <CheckCircle className="result-icon success" />;
      case "warning":
        return <AlertTriangle className="result-icon warning" />;
      case "failed":
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

  const handleOpenLogFile = async (logKey) => {
    try {
      const selectedBank = sessionStorage.getItem("selectedBank");
      if (!selectedBank) {
        toast.error("Nessuna banca selezionata.");
        return;
      }

      await apiClient.post("/folder/open-log", {
        log_key: logKey,
        bank: selectedBank
      });
      toast.success("File di log aperto con successo!");
    } catch (error) {
      console.error("Errore nell'apertura del file di log:", error);
      toast.error(error.response?.data?.detail || "Impossibile aprire il file di log.");
    }
  };

  const handleClearFilters = () => {
    setLogSearchTerm("");
    setLogLevelFilter("all");
    setStartDate("");
    setEndDate("");
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
        </select>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <label htmlFor="start-date" style={{ fontWeight: '500' }}>Da:</label>
          <input
            id="start-date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="form-input"
            placeholder="Data inizio"
          />
          <label htmlFor="end-date" style={{ fontWeight: '500' }}>A:</label>
          <input
            id="end-date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="form-input"
            placeholder="Data fine"
          />
          <button
            onClick={handleClearFilters}
            className="btn btn-outline"
            style={{ whiteSpace: 'nowrap' }}
            title="Resetta tutti i filtri"
          >
            Pulisci Filtri
          </button>
        </div>
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
                    {(exec.logKey || exec.parsedLogKey) && (
                      <button
                        className="open-log-button"
                        onClick={() => handleOpenLogFile(exec.logKey || exec.parsedLogKey)}
                        title="Apri file di log"
                      >
                        <FileText size={16} />
                        <span>Apri Log</span>
                      </button>
                    )}
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
                  <div className="execution-basic-info">
                    <p><strong>Flow ID:</strong> {exec.flowId || "N/A"}</p>
                    <p><strong>Status:</strong> {exec.overallResult || "N/A"}</p>
                    <p><strong>Anno:</strong> {exec.anno || "N/A"}</p>
                    <p><strong>Settimana:</strong> {exec.settimana || "N/A"}</p>
                    <p><strong>Log Key:</strong> {exec.logKey || exec.parsedLogKey || "N/A"}</p>
                    {exec.message && (
                      <p><strong>Messaggio:</strong> {exec.message}</p>
                    )}
                  </div>
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
