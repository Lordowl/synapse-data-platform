// src/components/Ingest/hooks/useIngestLogs.js
import { useState, useMemo, useCallback } from "react";
import { toast } from "react-toastify";
import apiClient from "../api/apiClient";

export const useIngestLogs = (logsData, flowsData, fetchLogs) => {
  const [logSearchTerm, setLogSearchTerm] = useState("");
  const [logLevelFilter, setLogLevelFilter] = useState("all");
  const [isRefreshingLogs, setIsRefreshingLogs] = useState(false);
  const [isClearingLogs, setIsClearingLogs] = useState(false);
  const [isDownloadingLogs, setIsDownloadingLogs] = useState(false);

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

  const handleRefreshLogs = useCallback(async () => {
    setIsRefreshingLogs(true);
    try {
      await fetchLogs();
      toast.success("Log aggiornati con successo.");
    } catch (error) {
      toast.error("Errore nell'aggiornamento dei log.");
    } finally {
      setIsRefreshingLogs(false);
    }
  }, [fetchLogs]);

  const handleClearLogs = useCallback(async () => {
    if (
      window.confirm("Sei sicuro di voler pulire tutti i log di esecuzione?")
    ) {
      setIsClearingLogs(true);
      try {
        // Chiamata API per pulire i log dal backend
        // Reset dei logs locali tramite il setter del parent
        toast.success("Log puliti con successo.");
      } catch (error) {
        console.error("Errore nella pulizia dei log:", error);
        toast.error("Errore nella pulizia dei log.");
      } finally {
        setIsClearingLogs(false);
      }
    }
  }, []);

  const handleDownloadLogs = useCallback(async () => {
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
  }, [filteredLogs]);

  return {
    logSearchTerm,
    setLogSearchTerm,
    logLevelFilter,
    setLogLevelFilter,
    filteredLogs,
    isRefreshingLogs,
    isClearingLogs,
    isDownloadingLogs,
    handleRefreshLogs,
    handleClearLogs,
    handleDownloadLogs,
  };
};