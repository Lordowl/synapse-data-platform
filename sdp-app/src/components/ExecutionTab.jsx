// src/components/Ingest/ExecutionTab.jsx
import React from "react";
import {
  Play,
  Filter,
  RefreshCw,
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
}) {
  // 🔹 Filtraggio locale basato su week, year, package e status
  const displayedFlows = filteredAndSortedFlows.filter(flow => {
    const matchesPackage = packageFilter === "all" || flow.package === packageFilter;
    const matchesStatus = statusFilter === "all" || flow.result?.toLowerCase() === statusFilter.toLowerCase();

    // Qui puoi aggiungere eventuale logica per week/year se il flusso contiene proprietà tipo flow.week, flow.year
    // const matchesWeek = flow.week === generalParams.selectedWeek;
    // const matchesYear = flow.year === generalParams.selectedYear;

    return matchesPackage && matchesStatus; // && matchesWeek && matchesYear;
  });

  return (
    <div className="tab-content-padding">
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
                  checked={displayedFlows.length > 0 && selectedFlows.size === displayedFlows.length}
                  ref={(el) => {
                    if (el) {
                      el.indeterminate = selectedFlows.size > 0 && selectedFlows.size < displayedFlows.length;
                    }
                  }}
                  disabled={displayedFlows.length === 0 || isExecuting}
                />
              </th>
              <th onClick={() => !isExecuting && requestSort("id")}>ID -SEQ {getSortIcon("id")}</th>
              <th onClick={() => !isExecuting && requestSort("anno")}>Anno {getSortIcon("anno")}</th>
              <th onClick={() => !isExecuting && requestSort("settimana")}>Settimana {getSortIcon("settimana")}</th>
              <th onClick={() => !isExecuting && requestSort("name")}>Nome Flusso {getSortIcon("name")}</th>
              <th onClick={() => !isExecuting && requestSort("lastRun")}>Ultima Esecuzione {getSortIcon("lastRun")}</th>
              <th onClick={() => !isExecuting && requestSort("result")}>Risultato {getSortIcon("result")}</th>
              <th>Dettagli</th>
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
                <td data-label="ID Univoco"><span className="muted-text">{flow.id}</span></td>
                <td data-label="Anno">{flow.anno || "N/A"}</td>
                <td data-label="Settimana">{flow.settimana || "N/A"}</td>
                <td data-label="Flusso">{flow.name || <span className="muted-text italic">{flow.id}</span>}</td>
                <td data-label="Ultima Esecuzione">{flow.lastRun ? new Date(flow.lastRun).toLocaleString("it-IT") : "N/A"}</td>
                <td data-label="Risultato"><span className={`status-badge ${getStatusBadgeColor(flow.result)}`}>{flow.result || "N/A"}</span></td>
                <td data-label="Dettagli">{flow.detail ? <pre className="flow-detail-content">{flow.detail}</pre> : <span className="muted-text italic">Nessun dettaglio</span>}</td>
              </tr>
            ))}
            {displayedFlows.length === 0 && (
              <tr>
                <td colSpan="8" className="text-center muted-text">
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