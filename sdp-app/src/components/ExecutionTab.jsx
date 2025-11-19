// src/components/Ingest/ExecutionTab.jsx
import React, { useState } from "react";
import {
  Play,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { getStatusBadgeColor } from "../utils/ingestUtils";

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
      return "row-color-na";
    default:
      return "row-color-default";
  }
};

function ExecutionTabContent({
  filteredAndSortedFlows,
  selectedFlows,
  handleSelectFlow,
  handleSelectAllFlows,
  isExecuting,
  handleExecuteSelectedFlows,
  generalParams,
  packageFilter,
  statusFilter,
  handleGeneralParamChange,
  sortConfig,
  requestSort,
  getSortIcon,
  metadataFilePath,
}) {
  // 🔹 Stato per tracciare quali dettagli sono espansi
  const [expandedDetails, setExpandedDetails] = useState(new Set());

  // 🔹 Filtraggio locale basato su week, year, package e status
  const displayedFlows = filteredAndSortedFlows.filter(flow => {
    const matchesPackage = packageFilter === "all" || flow.package === packageFilter;
    const matchesStatus = statusFilter === "all" || flow.result?.toLowerCase() === statusFilter.toLowerCase();

    // Qui puoi aggiungere eventuale logica per week/year se il flusso contiene proprietà tipo flow.week, flow.year
    // const matchesWeek = flow.week === generalParams.selectedWeek;
    // const matchesYear = flow.year === generalParams.selectedYear;

    return matchesPackage && matchesStatus; // && matchesWeek && matchesYear;
  });

  // Conta solo i flussi visualizzati che sono selezionati
  const selectedDisplayedCount = displayedFlows.filter(flow => selectedFlows.has(flow.id)).length;

  // 🔹 Funzione per toggle espansione dettagli
  const toggleDetailExpansion = (flowId) => {
    setExpandedDetails(prev => {
      const newSet = new Set(prev);
      if (newSet.has(flowId)) {
        newSet.delete(flowId);
      } else {
        newSet.add(flowId);
      }
      return newSet;
    });
  };

  return (
    <div className="tab-content-padding">
      <div className="ingest-section-header execution-tab-header">
        <div className="ingest-section-header-title-group">
          <Filter className="ingest-section-icon" />
          <div>
            <h2 className="ingest-section-title">Selezione Flussi</h2>
          </div>
        </div>
        <button
          onClick={handleExecuteSelectedFlows}
          className={`btn ${isExecuting ? "btn-disabled-visual" : "btn-primary"} execution-tab-run-button`}
          disabled={selectedFlows.size === 0 || isExecuting}
        >
          {isExecuting ? (
            <>
              <RefreshCw className="btn-icon-md animate-spin-css" />
              Esecuzione...
            </>
          ) : (
            <>
              <Play className="btn-icon-md" /> Esegui ({selectedDisplayedCount})
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
                  onChange={(e) => handleSelectAllFlows(e, displayedFlows)}
                  checked={displayedFlows.length > 0 && displayedFlows.every(flow => selectedFlows.has(flow.id))}
                  ref={(el) => {
                    if (el) {
                      el.indeterminate = selectedFlows.size > 0 && !displayedFlows.every(flow => selectedFlows.has(flow.id));
                    }
                  }}
                  disabled={displayedFlows.length === 0 || isExecuting}
                />
              </th>
              <th onClick={() => !isExecuting && requestSort("id")} style={{ width: '80px' }}>ID {getSortIcon("id")}</th>
              <th onClick={() => !isExecuting && requestSort("package")} style={{ width: '120px' }}>Package {getSortIcon("package")}</th>
              <th onClick={() => !isExecuting && requestSort("anno")} style={{ width: '70px' }}>Anno {getSortIcon("anno")}</th>
              <th onClick={() => !isExecuting && requestSort("settimana")} style={{ width: '70px' }}>Sett. {getSortIcon("settimana")}</th>
              <th onClick={() => !isExecuting && requestSort("name")}>Flusso {getSortIcon("name")}</th>
              <th onClick={() => !isExecuting && requestSort("lastRun")} style={{ width: '130px' }}>Ultima Esec. {getSortIcon("lastRun")}</th>
              <th onClick={() => !isExecuting && requestSort("result")} style={{ width: '100px' }}>Status {getSortIcon("result")}</th>
              <th style={{ minWidth: '200px' }}>Dettagli</th>
            </tr>
          </thead>
          <tbody>
            {displayedFlows.map(flow => (
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
                <td data-label="ID"><span className="muted-text" style={{ fontSize: '0.85rem' }}>{flow.id}</span></td>
                <td data-label="Package">{flow.package || "N/A"}</td>
                <td data-label="Anno">{flow.anno || "N/A"}</td>
                <td data-label="Sett.">{flow.settimana || "N/A"}</td>
                <td data-label="Flusso" title={flow.name || flow.id}>{flow.name || <span className="muted-text italic">{flow.id}</span>}</td>
                <td data-label="Ultima Esec." style={{ fontSize: '0.85rem' }}>
                  {flow.lastRun ? new Date(flow.lastRun).toLocaleString("it-IT", {
                    day: '2-digit',
                    month: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    timeZone: 'Europe/Rome'
                  }) : "N/A"}
                </td>
                <td data-label="Status"><span className={`status-badge ${getStatusBadgeColor(flow.result)}`}>{flow.result || "N/A"}</span></td>
                <td data-label="Dettagli" style={{ fontSize: '0.85rem', maxWidth: '300px' }}>
                  {flow.detail ? (
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <div style={{
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: expandedDetails.has(flow.id) ? 'clip' : 'ellipsis',
                        whiteSpace: expandedDetails.has(flow.id) ? 'normal' : 'nowrap',
                        wordBreak: expandedDetails.has(flow.id) ? 'break-word' : 'normal'
                      }}>
                        {flow.detail}
                      </div>
                      {flow.detail.length > 50 && (
                        <button
                          onClick={() => toggleDetailExpansion(flow.id)}
                          style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '2px',
                            display: 'flex',
                            alignItems: 'center',
                            color: 'var(--color-primary, #3b82f6)',
                            flexShrink: 0
                          }}
                          title={expandedDetails.has(flow.id) ? "Comprimi" : "Espandi"}
                        >
                          {expandedDetails.has(flow.id) ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>
                      )}
                    </div>
                  ) : (
                    <span className="muted-text italic">Nessun dettaglio</span>
                  )}
                </td>
              </tr>
            ))}
            {displayedFlows.length === 0 && (
              <tr>
                <td colSpan="9" className="text-center muted-text">
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

export default ExecutionTabContent;