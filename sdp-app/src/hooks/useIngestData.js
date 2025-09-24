// src/components/Ingest/hooks/useIngestData.js
import { useState, useCallback, useRef } from "react";
import { toast } from "react-toastify";
import apiClient from "../api/apiClient";
import { mapBackendLogToFrontend } from "../utils/ingestUtils";

export const useIngestData = (metadataFilePath) => {
  const [flowsData, setFlowsData] = useState([]);
  const [logsData, setLogsData] = useState([]);
  const [historyData, setHistoryData] = useState({});
  const [isLoading, setIsLoading] = useState(true);

  // Usiamo useRef per mantenere una riferimento persistente a flowsData
  // senza innescare re-render quando flowsData cambia.
  const flowsDataRef = useRef(flowsData);
  flowsDataRef.current = flowsData;

  const fetchInitialData = useCallback(async () => {
    setIsLoading(true);
    try {
      await apiClient.post("/tasks/update-flows-from-excel", {
        file_path: metadataFilePath,
      });

      const [flowsResponse, historyResponse] = await Promise.all([
        apiClient.get("/flows"),
        apiClient.get("/flows/history"),
      ]);

      const staticFlows = flowsResponse.data;
      const historyMap = historyResponse.data || {};

      setHistoryData(historyMap);

      const combinedFlows = staticFlows
        .filter(flow => flow.ID)
        .map(flow => {
          const executionHistory = historyMap[flow.ID] || {};
          return {
            id: `${flow.ID}-${flow.SEQ || "0"}`,
            originalId: flow.ID,
            originalSeq: flow.SEQ || "0",
            name: flow["Filename out"] || `Flusso ${flow.ID}`,
            package: flow["Package"] || "",
            lastRun: executionHistory.timestamp || null,
            result: executionHistory.result || "N/A",
            detail: executionHistory.error_lines || "",
            duration: executionHistory.duration || null,
          };
        });

      setFlowsData(combinedFlows);

    } catch (error) {
      console.error(error);
      toast.error("Errore durante il caricamento dei flussi.");
    } finally {
      setIsLoading(false);
    }
  }, [metadataFilePath]);

  const fetchLogs = useCallback(async () => {
    try {
      const logsResponse = await apiClient.get("/flows/logs");
      const backendLogs = logsResponse.data;

      if (!Array.isArray(backendLogs)) throw new Error("Logs non validi");

      // Usiamo flowsDataRef.current per accedere al valore più recente
      // di flowsData senza creare una dipendenza diretta.
      const frontendLogs = backendLogs.map(log =>
        mapBackendLogToFrontend(log, flowsDataRef.current)
      );

      setLogsData(frontendLogs);

      const logMap = {};
      frontendLogs.forEach(log => {
        if (log.originalId) logMap[log.originalId] = log;
      });

      setFlowsData(prevFlows =>
        prevFlows.map(flow => {
          const logEntry = logMap[flow.originalId];
          if (logEntry) {
            return {
              ...flow,
              lastRun: logEntry.lastRun || flow.lastRun,
              result: logEntry.result || flow.result,
              detail: logEntry.detail || flow.detail,
              duration: logEntry.duration || flow.duration,
            };
          }
          return flow;
        })
      );

    } catch (error) {
      console.error(error);
      toast.error("Errore nel caricamento dei log.");
      setLogsData([]);
    }
  }, []); // Nessuna dipendenza!

  return {
    flowsData,
    logsData,
    historyData,
    isLoading,
    fetchInitialData,
    fetchLogs,
    setLogsData,
  };
};