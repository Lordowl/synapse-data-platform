// src/components/Ingest/hooks/useIngestFlows.js
import { useState, useMemo, useCallback } from "react";
import { toast } from "react-toastify";
import apiClient from "../api/apiClient";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

export const useIngestFlows = (flowsData, generalParams, setGeneralParams, fetchInitialData, fetchLogs, activeTab) => {
  const [selectedFlows, setSelectedFlows] = useState(new Set());
  const [searchTerm, setSearchTerm] = useState("");
  const [packageFilter, setPackageFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortConfig, setSortConfig] = useState({
    key: "id",
    direction: "ascending",
  });
  const [isExecutingFlows, setIsExecutingFlows] = useState(false);

  // Memoized computed values
  const flowPackages = useMemo(
    () => ["all", ...new Set(flowsData.map((f) => f.package).filter(Boolean))],
    [flowsData]
  );

  const flowStatuses = useMemo(
    () => ["all", ...new Set(flowsData.map((f) => f.result || "N/A"))],
    [flowsData]
  );

  const filteredFlows = useMemo(() => {
    console.log("--- Ricalcolo filteredFlows ---");
    console.log("Stato attuale dei filtri:", {
      searchTerm,
      packageFilter,
      statusFilter,
    });
    //console.log("Dati di input (flowsData):", flowsData);
    return flowsData.filter(
      (flow) =>
        (flow.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
          flow.package?.toLowerCase().includes(searchTerm.toLowerCase())) &&
        (packageFilter === "all" || flow.package === packageFilter) &&
        (statusFilter === "all" || (flow.result || "N/A") === statusFilter)
    );
  }, [flowsData, searchTerm, packageFilter, statusFilter]);

  const filteredAndSortedFlows = useMemo(() => {
    let sortableFlows = [...filteredFlows];

    if (sortConfig.key) {
      sortableFlows.sort((a, b) => {
        const aValue = a[sortConfig.key];
        const bValue = b[sortConfig.key];

        if (sortConfig.key === "id") {
          const numA = parseInt(a.originalId, 10) || 0;
          const numB = parseInt(b.originalId, 10) || 0;

          if (numA !== numB) {
            return numA - numB;
          }

          const seqA = parseInt(a.originalSeq, 10) || 0;
          const seqB = parseInt(b.originalSeq, 10) || 0;
          return seqA - seqB;
        }

        if (sortConfig.key === "lastRun") {
          const dateA = aValue ? new Date(aValue).getTime() : 0;
          const dateB = bValue ? new Date(bValue).getTime() : 0;
          return dateA - dateB;
        }

        const strA = (aValue || "").toString().toLowerCase();
        const strB = (bValue || "").toString().toLowerCase();
        return strA.localeCompare(strB);
      });

      if (sortConfig.direction === "descending") {
        sortableFlows.reverse();
      }
    }

    return sortableFlows;
  }, [filteredFlows, sortConfig]);

  // Handlers
  const handleSelectFlow = useCallback((flowId) => {
    setSelectedFlows((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(flowId)) {
        newSet.delete(flowId);
      } else {
        newSet.add(flowId);
      }
      return newSet;
    });
  }, []);

  const handleSelectAllFlows = useCallback((e) => {
    if (e.target.checked) {
      setSelectedFlows(new Set(filteredAndSortedFlows.map((f) => f.id)));
    } else {
      setSelectedFlows(new Set());
    }
  }, [filteredAndSortedFlows]);

  const handleGeneralParamChange = useCallback((paramName, value) => {
    setGeneralParams((prev) => ({ ...prev, [paramName]: value }));
  }, [setGeneralParams]);

  const requestSort = useCallback((key) => {
    let direction = "ascending";
    if (sortConfig.key === key && sortConfig.direction === "ascending") {
      direction = "descending";
    }
    setSortConfig({ key, direction });
  }, [sortConfig]);

  const getSortIcon = useCallback((key) => {
  if (sortConfig.key !== key) {
    return <ChevronsUpDown className="inline-icon" />;
  }
  return sortConfig.direction === "ascending" ? (
    <ChevronUp className="inline-icon" />
  ) : (
    <ChevronDown className="inline-icon" />
  );
}, [sortConfig]);

  const handleExecuteSelectedFlows = useCallback(async () => {
    if (selectedFlows.size === 0) {
      toast.warn("Nessun flusso selezionato per l'esecuzione.");
      return;
    }

    setIsExecutingFlows(true);

    try {
      const flowsToRun = flowsData.filter((f) => selectedFlows.has(f.id));

      if (flowsToRun.length === 0) {
        toast.warn("I flussi selezionati non sono presenti nei dati.");
        return;
      }

      const executionPayload = {
        flows: flowsToRun.map((f) => {
          const mainId = f.id.split("-")[0];
          return {
            id: mainId,
            name: f.name,
          };
        }),
        params: {
          ...generalParams,
          metadataFilePath: generalParams.metadataFilePath || undefined, // Include il path del file metadati locale se disponibile
        },
      };

      console.log("Payload inviato al backend:", executionPayload);

      const response = await apiClient.post(
        "/tasks/execute-flows",
        executionPayload
      );

      toast.success(response.data.message || "Esecuzione completata!");

      // Ricarica i dati dopo l'esecuzione
      await fetchInitialData();

      // Se siamo nel tab logs, ricarica anche i log
      if (activeTab === "logs") {
        await fetchLogs();
      }
    } catch (error) {
      console.error("Errore durante l'esecuzione:", error);
      toast.error(
        error.response?.data?.detail || "L'esecuzione dei flussi è fallita."
      );
    } finally {
      setSelectedFlows(new Set());
      setIsExecutingFlows(false);
    }
  }, [selectedFlows, flowsData, generalParams, fetchInitialData, fetchLogs, activeTab]);

  return {
    selectedFlows,
    setSelectedFlows, // Esporta la funzione per resettare le selezioni
    searchTerm,
    setSearchTerm,
    packageFilter,
    setPackageFilter,
    statusFilter,
    setStatusFilter,
    sortConfig,
    setSortConfig,
    filteredAndSortedFlows,
    flowPackages,
    flowStatuses,
    isExecutingFlows,
    handleSelectFlow,
    handleSelectAllFlows,
    handleGeneralParamChange,
    handleExecuteSelectedFlows,
    requestSort,
    getSortIcon,
  };
};