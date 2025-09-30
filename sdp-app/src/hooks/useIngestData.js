// Versione modificata di useIngestData.js con debug avanzato
import { useState, useCallback, useRef } from "react";
import { toast } from "react-toastify";
import apiClient from "../api/apiClient";
import { mapBackendLogToFrontend } from "../utils/ingestUtils";

export const useIngestData = (metadataFilePath) => {
  const [flowsData, setFlowsData] = useState([]);
  const [logsData, setLogsData] = useState([]);
  const [historyData, setHistoryData] = useState({});
  const [historyLatestData, setHistoryLatestData] = useState({});
  const [isLoading, setIsLoading] = useState(true);

  const flowsDataRef = useRef(flowsData);
  flowsDataRef.current = flowsData;

  const fetchInitialData = useCallback(async () => {
    setIsLoading(true);
    try {
      await apiClient.post("/tasks/update-flows-from-excel", {
        file_path: metadataFilePath,
      });

      console.group("🔍 FETCH INITIAL DATA DEBUG");
      
      const [flowsResponse, historyLatestResponse, historyResponse] =
        await Promise.all([
          apiClient.get("/flows"),
          apiClient.get("/flows/historylatest"),
          apiClient.get("/flows/history"),
        ]);

      console.log("📊 Raw API Responses:");
      console.log("flows:", flowsResponse.data);
      console.log("historylatest:", historyLatestResponse.data);
      console.log("history:", historyResponse.data);

      const staticFlows = flowsResponse.data || [];
      const historyLatestMap = historyLatestResponse.data || {};
      const historyRows = historyResponse.data || [];

      console.log("📊 After initial processing:");
      console.log("staticFlows length:", staticFlows.length);
      console.log("historyLatestMap keys:", Object.keys(historyLatestMap));
      console.log("historyRows:", historyRows);
      console.log("historyRows type:", typeof historyRows);
      console.log("historyRows is array:", Array.isArray(historyRows));

      // Normalizza history in array
      const historyArray = Array.isArray(historyRows)
        ? historyRows
        : Object.values(historyRows);

      console.log("📊 History array after normalization:");
      console.log("historyArray length:", historyArray.length);
      console.log("historyArray sample:", historyArray.slice(0, 3));

      // Organizza per log_key
      const historyByLogKey = historyArray.reduce((acc, row) => {
        const key = row.log_key;
        console.log(`Processing history row with log_key: "${key}"`);
        if (!acc[key]) acc[key] = [];
        acc[key].push(row);
        return acc;
      }, {});

      console.log("📊 Final historyByLogKey:");
      console.log("Keys:", Object.keys(historyByLogKey));
      console.log("Total entries:", Object.values(historyByLogKey).flat().length);
      
      console.groupEnd();

      setHistoryLatestData(historyLatestMap);
      setHistoryData(historyByLogKey);

      // resto del codice per flows...
      const combinedFlows = staticFlows
        .filter((flow) => flow.ID)
        .map((flow) => {
          const executionHistory = historyLatestMap[flow.ID] || {};
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
            anno: executionHistory.anno || null,
            settimana: executionHistory.settimana || null,
          };
        });

      setFlowsData(combinedFlows);
    } catch (error) {
      console.error("❌ Error in fetchInitialData:", error);
      console.error("Error details:", error.response?.data || error.message);
      toast.error("Errore durante il caricamento dei flussi.");
    } finally {
      setIsLoading(false);
    }
  }, [metadataFilePath]);

  const fetchLogs = useCallback(async () => {
    try {
      console.group("🔍 FETCH LOGS DEBUG");
      
      const [logsResponse, historyResponse] = await Promise.all([
        apiClient.get("/flows/logs"),
        apiClient.get("/flows/history"),
      ]);

      console.log("📊 Logs fetch - Raw API Responses:");
      console.log("logs:", logsResponse.data);
      console.log("history:", historyResponse.data);

      const backendLogs = logsResponse.data || [];
      const historyRows = historyResponse.data || [];

      console.log("📊 After initial processing:");
      console.log("backendLogs length:", backendLogs.length);
      console.log("historyRows:", historyRows);
      console.log("historyRows type:", typeof historyRows);

      // Normalizza history
      const historyArray = Array.isArray(historyRows)
        ? historyRows
        : Object.values(historyRows);

      console.log("📊 History array after normalization:");
      console.log("historyArray length:", historyArray.length);
      console.log("historyArray sample:", historyArray.slice(0, 3));

      // Organizza history per log_key
      const historyByLogKey = historyArray.reduce((acc, row) => {
        const key = row.log_key;
        console.log(`Processing history row with log_key: "${key}"`);
        if (!acc[key]) acc[key] = [];
        acc[key].push(row);
        return acc;
      }, {});

      console.log("📊 Final historyByLogKey in fetchLogs:");
      console.log("Keys:", Object.keys(historyByLogKey));
      console.log("Sample entries:", Object.entries(historyByLogKey).slice(0, 2));

      setHistoryData(historyByLogKey);
      console.groupEnd();

      // Mappa i logs frontend
      const frontendLogs = backendLogs.map((log) => {
        const mapped = mapBackendLogToFrontend(log, flowsDataRef.current);

        // Estrapolo executedBy e params da original_details
        const executedBy = log.details?.original_details?.executed_by ?? null;
        const params = log.details?.original_details?.params ?? {};

        // logKey canonico
        const canonicalLogKey =
          log.details?.log_key ?? mapped.parsedLogKey ?? mapped.logKey;

        const finalLog = {
          ...mapped,
          logKey: canonicalLogKey,
          executedBy,
          params,
        };

        // rimuovo campi non necessari
        delete finalLog.parsedLogKey;
        delete finalLog.details;

        // DEBUG: log finale
        console.log("LOG PARSED:", finalLog);

        return finalLog;
      });

      console.log("📊 FINAL FRONTEND LOGS:");
      console.log("frontendLogs length:", frontendLogs.length);
      console.log("frontendLogs sample:", frontendLogs.slice(0, 2));

      setLogsData(frontendLogs);

      // aggiorna anche flowsData con ultimo stato
      const logMap = {};
      frontendLogs.forEach((log) => {
        if (log.originalId) logMap[log.originalId] = log;
      });

      setFlowsData((prevFlows) =>
        prevFlows.map((flow) => {
          const logEntry = logMap[flow.originalId];
          if (logEntry) {
            return {
              ...flow,
              lastRun: logEntry.lastRun || flow.lastRun,
              result: logEntry.result || flow.result,
              detail: logEntry.detail || flow.detail,
              duration: logEntry.duration || flow.duration,
              anno: logEntry.anno || flow.anno,
              settimana: logEntry.settimana || flow.settimana,
            };
          }
          return flow;
        })
      );
    } catch (error) {
      console.error("❌ Error in fetchLogs:", error);
      console.error("Error details:", error.response?.data || error.message);
      toast.error("Errore nel caricamento dei log.");
      setLogsData([]);
      setHistoryData({});
    }
  }, []);

  return {
    flowsData,
    logsData,
    historyData,
    historyLatestData,
    isLoading,
    fetchInitialData,
    fetchLogs,
    setLogsData,
  };
};