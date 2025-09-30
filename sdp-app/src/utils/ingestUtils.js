  // src/components/Ingest/utils/ingestUtils.js

  // Funzione per mappare il colore dei badge di status
  export const getStatusBadgeColor = (status) => {
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

  // Funzione per mappare le classi CSS dei livelli di log
  export const getLogLevelClass = (level) => {
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

  // Funzione per mappare il log del backend al formato frontend
  export const mapBackendLogToFrontend = (backendLog, flows) => {
  // Cerca il flusso corrispondente
  const flow = flows.find((f) => f.originalId === backendLog.element_id);

  const logKey =
    backendLog.log_key || `${backendLog.element_id}-${backendLog.timestamp}`; // fallback se log_key non arriva

  return {
    id: backendLog.id,
    timestamp: backendLog.timestamp,
    flowId: backendLog.element_id, // conserva element_id
    flowName: flow?.name || backendLog.element_id, // nome leggibile
    message:
      backendLog.details?.message ||
      `Esecuzione flusso: ${backendLog.status || 'Unknown'}`,
    level:
      backendLog.status?.toLowerCase() === "success"
        ? "success"
        : backendLog.status?.toLowerCase() === "failed"
        ? "error"
        : "info",
    // 🔧 FIX: Gestisci details correttamente
    details: backendLog.details ? (
      // Se details è un oggetto con original_details, usa quello
      backendLog.details.original_details || backendLog.details
    ) : null,
    logKey, // <-- aggiunto logKey qui
    // 🔧 AGGIUNGI: log_key direttamente accessibile
    parsedLogKey: backendLog.details?.log_key || null,
    // 🔧 AGGIUNGI: info di stato dal backend
    status: backendLog.status,
    duration: backendLog.duration_seconds,
    // 🔧 AGGIUNGI: anno e settimana dal backend
    anno: backendLog.details?.anno || null,
    settimana: backendLog.details?.settimana || null,
  };
};
