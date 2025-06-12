// src/components/Report/Report.jsx
import { useState, useMemo, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  BarChart3, Filter, Play, FileText, PlusSquare, Copy, UploadCloud, Send,
  RefreshCw, CheckCircle, XCircle, AlertTriangle, ListChecks, Eye, AlertCircle,
  Calendar, Clock
} from "lucide-react";
import "./Report.css";

// --- Configurazione per periodicità ---
const PERIODICITY_CONFIG = {
  settimanale: {
    label: "Settimanale",
    icon: Clock,
    timeUnit: "settimana",
    timeLabel: "Settimana",
    dateFormat: "S{week}",
    defaultFilters: {
      settimana: "29",
      mese: null
    }
  },
  mensile: {
    label: "Mensile", 
    icon: Calendar,
    timeUnit: "mese",
    timeLabel: "Mese",
    dateFormat: "M{month}",
    defaultFilters: {
      settimana: null,
      mese: "06"
    }
  }
};

// --- Dati di Esempio Unificati ---
const initialReportTasks = [
  { 
    id: "file1_ERP_clienti", 
    periodicity: "settimanale",
    fileName: "Clienti_ERP_S27.xlsx", 
    description: "Anagrafica Clienti da ERP", 
    package: "Anagrafiche Core",
    serverStatus: "presente",
    serverCheckDetails: "OK - Aggiornato alla settimana corretta, record presenti.",
    sharepointStatus: "non_copiato",
    sharepointCopyDate: null,
    sharepointMessage: "",
    powerBIStatus: "non_importato",
    selected: false,
  },
  { 
    id: "file2_SP_inventario", 
    periodicity: "settimanale",
    fileName: "Inventario_S27.csv", 
    description: "Dati Inventario da SharePoint", 
    package: "Logistica",
    serverStatus: "presente",
    serverCheckDetails: "ATTENZIONE: Campo settimana mancante nel file!",
    sharepointStatus: "non_copiato",
    sharepointCopyDate: null,
    sharepointMessage: "",
    powerBIStatus: "non_importato",
    selected: false,
  },
  { 
    id: "file3_Vendite_mensili", 
    periodicity: "mensile",
    fileName: "Report_Vendite_M06.xlsx", 
    description: "Aggregato Vendite Mensili", 
    package: "Commerciale",
    serverStatus: "mancante_no_dati_irion",
    serverCheckDetails: "File non prodotto da IRION per il mese corrente.",
    sharepointStatus: "non_copiato",
    sharepointCopyDate: null,
    sharepointMessage: "",
    powerBIStatus: "non_importato",
    selected: false,
  },
  {
    id: "file4_Budget_mensile",
    periodicity: "mensile", 
    fileName: "Budget_Analisi_M06.xlsx",
    description: "Analisi Budget Mensile",
    package: "Controllo Gestione",
    serverStatus: "presente",
    serverCheckDetails: "File aggiornato correttamente per il mese.",
    sharepointStatus: "copiato_ok",
    sharepointCopyDate: "2024-06-15T10:30:00Z",
    sharepointMessage: "",
    powerBIStatus: "importato_precheck",
    selected: false,
  }
];

// --- Funzioni Helper (identiche a prima) ---
const getTaskStatusBadge = (statusKey, statusValue) => {
  if (!statusValue) return 'status-badge-muted';
  switch (statusValue.toLowerCase()) {
    case 'presente': case 'copiato_ok': case 'importato_precheck': case 'completed':
      return 'status-badge-success';
    case 'mancante_errore_salvataggio': case 'copia_fallita': case 'import_fallito': case 'failed':
      return 'status-badge-danger';
    case 'mancante_no_dati_irion': case 'pending':
      return 'status-badge-warning';
    case 'in_copia': case 'in_importazione': case 'inprogress':
      return 'status-badge-info';
    default:
      return 'status-badge-muted';
  }
};

// --- Componente Principale Report Unificato ---
function Report() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  
  // Leggi la periodicità dai parametri URL o default a 'settimanale'
  const currentPeriodicity = searchParams.get('type') || 'settimanale';
  const periodicityConfig = PERIODICITY_CONFIG[currentPeriodicity] || PERIODICITY_CONFIG.settimanale;

  const [filters, setFilters] = useState({
    istituto: "Sparkasse", 
    package: "Tutti", 
    finalita: "Reportistica Commerciale",
    anno: new Date().getFullYear().toString(),
    // Filtri dinamici basati sulla periodicità
    ...periodicityConfig.defaultFilters,
    periodicity: currentPeriodicity // Mantieni per retrocompatibilità
  });

  const [reportTasks, setReportTasks] = useState(initialReportTasks);
  const [selectedTaskIds, setSelectedTaskIds] = useState(new Set());

  // Aggiorna i filtri quando cambia la periodicità
  useEffect(() => {
    setFilters(prev => ({
      ...prev,
      ...periodicityConfig.defaultFilters,
      periodicity: currentPeriodicity
    }));
    setSelectedTaskIds(new Set()); // Reset selezione
  }, [currentPeriodicity]);

  // Calcola status complessivo solo per i task della periodicità corrente
  const overallStatus = useMemo(() => {
    const relevantTasks = reportTasks.filter(task => task.periodicity === currentPeriodicity);
    
    if (relevantTasks.every(task => 
      task.powerBIStatus === 'importato_precheck' || 
      task.serverStatus === 'mancante_no_dati_irion'
    )) {
      return 'completed';
    }
    if (relevantTasks.some(task => 
      task.sharepointStatus === 'copia_fallita' || 
      task.serverStatus === 'mancante_errore_salvataggio' || 
      task.powerBIStatus === 'import_fallito'
    )) {
      return 'error';
    }
    if (relevantTasks.some(task => 
      task.serverStatus === 'presente' && 
      task.sharepointStatus !== 'copiato_ok'
    )) {
      return 'pending';
    }
    return 'pending';
  }, [reportTasks, currentPeriodicity]);

  const [loadingActions, setLoadingActions] = useState({
    global: null,
    taskAction: null,
  });

  // Stati e funzioni per i Toast (identici)
  const [toast, setToast] = useState({ message: '', type: 'info', visible: false });
  useEffect(() => {
    if (toast.visible) {
      const timer = setTimeout(() => {
        setToast(prev => ({ ...prev, visible: false }));
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [toast.visible]);
  
  const showToast = (message, type = 'info') => {
    setToast({ message, type, visible: true });
  };

  const getToastIcon = (type) => {
    switch (type) {
      case 'success': return <CheckCircle size={20} />;
      case 'error': return <XCircle size={20} />;
      case 'warning': return <AlertTriangle size={20} />;
      default: return <AlertCircle size={20} />;
    }
  };

  // Funzione per cambiare periodicità
  const handlePeriodicityChange = (newPeriodicity) => {
    setSearchParams({ type: newPeriodicity });
  };

  const handleFilterChange = (filterName, value) => {
    setFilters(prev => ({ ...prev, [filterName]: value }));
  };

  // Filtra task per periodicità corrente + altri filtri
  const filteredReportTasks = useMemo(() => {
    return reportTasks.filter(task => {
      const matchesPeriodicity = task.periodicity === currentPeriodicity;
      // Altri filtri qui se necessario
      return matchesPeriodicity;
    });
  }, [reportTasks, currentPeriodicity, filters]);

  const handleTaskSelection = (taskId) => {
    setSelectedTaskIds(prev => {
      const newSelection = new Set(prev);
      if (newSelection.has(taskId)) {
        newSelection.delete(taskId);
      } else {
        newSelection.add(taskId);
      }
      return newSelection;
    });
  };

  const handleSelectAllTasks = (e) => {
    if (e.target.checked) {
      setSelectedTaskIds(new Set(filteredReportTasks.map(t => t.id)));
    } else {
      setSelectedTaskIds(new Set());
    }
  };
  
  const simulateApiCall = (duration = 1500) => 
    new Promise(resolve => setTimeout(resolve, duration));

  const getActionLabelAndIcon = (task) => {
    if (task.powerBIStatus === 'importato_precheck') 
      return { label: "Pubblica?", Icon: Send, action: "publish_single" };
    if (task.sharepointStatus === 'copiato_ok' && task.powerBIStatus !== 'importato_precheck') 
      return { label: "Importa PBI", Icon: UploadCloud, action: "import_pbi_single" };
    if (task.serverStatus === 'presente' && task.sharepointStatus !== 'copiato_ok') 
      return { label: "Copia su SP", Icon: Copy, action: "copy_to_sp_single" };
    if (task.serverStatus === 'mancante_no_dati_irion') 
      return { 
        label: `Crea ${periodicityConfig.timeLabel}`, 
        Icon: PlusSquare, 
        action: "create_period_single" 
      };
    if (task.serverStatus === 'mancante_errore_salvataggio' || 
        task.sharepointStatus === 'copia_fallita' || 
        task.powerBIStatus === 'import_fallito') 
      return { label: "Riesegui Check", Icon: RefreshCw, action: "recheck_single" };
    return { label: "Verifica Dati", Icon: Eye, action: "check_data_single" };
  };

  const handleTaskAction = async (taskId) => {
    const task = reportTasks.find(t => t.id === taskId);
    if (!task) return;
    const { action, label } = getActionLabelAndIcon(task);

    setLoadingActions(prev => ({ ...prev, taskAction: taskId }));
    showToast(`Avvio azione '${label}' per "${task.fileName}"...`, 'info');
    await simulateApiCall(2000 + Math.random() * 1000);

    // Aggiornamento stato con logica specifica per periodicità
    setReportTasks(prevTasks => prevTasks.map(t => {
      if (t.id === taskId) {
        if (action === "check_data_single" || action === "recheck_single") 
          return { 
            ...t, 
            serverStatus: 'presente', 
            serverCheckDetails: 'Verifica OK', 
            sharepointStatus: 'non_copiato'
          };
        if (action === "create_period_single") 
          return { 
            ...t, 
            serverStatus: 'presente', 
            serverCheckDetails: `${periodicityConfig.timeLabel} creata manualmente`, 
            sharepointStatus: 'non_copiato'
          };
        if (action === "copy_to_sp_single") 
          return { 
            ...t, 
            sharepointStatus: 'copiato_ok', 
            sharepointCopyDate: new Date().toISOString() 
          };
        if (action === "import_pbi_single") 
          return { ...t, powerBIStatus: 'importato_precheck' };
        if (action === "publish_single") {
          // Logica pubblicazione
        }
      }
      return t;
    }));

    showToast(`Azione '${label}' per "${task.fileName}" completata.`, 'success');
    setLoadingActions(prev => ({ ...prev, taskAction: null }));
  };
  
  const handleGlobalAction = async (actionName) => {
    if (actionName === 'esegui' && selectedTaskIds.size === 0) {
      showToast("Nessun task selezionato per l'esecuzione.", "warning");
      return;
    }
    
    setLoadingActions(prev => ({ ...prev, global: actionName }));
    showToast(`Avvio azione globale '${actionName}'...`, "info");
    await simulateApiCall(2500 + Math.random() * 2000);

    if (actionName === 'esegui') {
      setReportTasks(prevTasks => prevTasks.map(t => {
        if (selectedTaskIds.has(t.id)) {
          if (t.serverStatus !== 'presente' && t.serverStatus !== 'mancante_no_dati_irion') 
            return {...t, serverStatus: 'presente', serverCheckDetails: 'Verifica OK tramite ESEGUI'};
          if (t.sharepointStatus !== 'copiato_ok') 
            return {...t, sharepointStatus: 'copiato_ok', sharepointCopyDate: new Date().toISOString()};
          if (t.powerBIStatus !== 'importato_precheck') 
            return {...t, powerBIStatus: 'importato_precheck'};
        }
        return t;
      }));
      showToast(`Esecuzione ${selectedTaskIds.size} task completata.`, "success");
      setSelectedTaskIds(new Set());
    } else if (actionName === 'creaPeriodo') {
      setReportTasks(prevTasks => prevTasks.map(t => 
        (selectedTaskIds.has(t.id) && t.serverStatus === 'mancante_no_dati_irion') ? 
        {...t, serverStatus: 'presente', serverCheckDetails: `${periodicityConfig.timeLabel} creata per file mancante`} : t
      ));
      showToast(`Azione 'Crea ${periodicityConfig.timeLabel}' applicata ai task selezionati.`, "success");
    } else {
      showToast(`Azione globale '${actionName}' completata (simulazione).`, "success");
    }
    setLoadingActions(prev => ({ ...prev, global: null }));
  };

  const allTasksSelected = filteredReportTasks.length > 0 && selectedTaskIds.size === filteredReportTasks.length;
  const isAnyTaskSelected = selectedTaskIds.size > 0;
  const canImportPBI = filteredReportTasks.length > 0 && filteredReportTasks.every(task => 
    task.sharepointStatus === 'copiato_ok' || task.serverStatus === 'mancante_no_dati_irion'
  );

  // Icona dinamica per il tipo di report
  const ReportIcon = periodicityConfig.icon;

  return (
    <div className="report-container">

      
      <div className="report-content-wrapper">
        <header className="report-header-container">
          <div className="report-header">
            <div className="report-header-title-group">
              <div className="report-header-icon-bg">
                <ReportIcon className="report-header-icon" /> {/* Icona dinamica */}
              </div>
              <div>
                <h1 className="report-header-title">
                  Cruscotto Reportistica
                </h1>
                <p className="report-header-subtitle">
                  Elaborazione e monitoraggio report.
                </p>
              </div>
            </div>
            {/* Pulsante Indietro rimane qui, i pulsanti di periodicità sono stati spostati */}
            <button 
              onClick={() => navigate("/home")} 
              className="btn btn-outline report-header-back-button" 
              disabled={loadingActions.global !== null || loadingActions.taskAction !== null}
            >
              ← Indietro
            </button>
          </div>
        </header>


        <section className="periodicity-selector-section">
          <div className="periodicity-toggle">
            <button 
              className={`btn ${currentPeriodicity === 'settimanale' ? 'btn-primary-action' : 'btn-outline'} periodicity-toggle-btn`}
              onClick={() => handlePeriodicityChange('settimanale')}
              disabled={loadingActions.global !== null || loadingActions.taskAction !== null} // Aggiunto disabled
            >
              <Clock size={16} className="btn-icon-sm"/> Report Settimanali
            </button>
            <button 
              className={`btn ${currentPeriodicity === 'mensile' ? 'btn-primary-action' : 'btn-outline'} periodicity-toggle-btn`}
              onClick={() => handlePeriodicityChange('mensile')}
              disabled={loadingActions.global !== null || loadingActions.taskAction !== null} // Aggiunto disabled
            >
              <Calendar size={16} className="btn-icon-sm"/> Report Mensili
            </button>
          </div>
        </section>


        <section className="report-filters-section">
          <div className="filter-row">
            <div className="filter-group">
              <label htmlFor="istituto-filter" className="form-label">Istituto</label>
              <select 
                id="istituto-filter" 
                className="form-select" 
                value={filters.istituto} 
                onChange={e => handleFilterChange('istituto', e.target.value)} 
                disabled={loadingActions.global !== null}
              >
                <option value="Sparkasse">Sparkasse</option>
                <option value="CiviBank">CiviBank</option>
                <option value="Tutti">Tutti</option>
              </select>
            </div>
            <div className="filter-group">
              <label htmlFor="finalita-filter" className="form-label">Finalità</label>
              <select 
                id="finalita-filter" 
                className="form-select" 
                value={filters.finalita} 
                onChange={e => handleFilterChange('finalita', e.target.value)} 
                disabled={loadingActions.global !== null}
              >
                <option value="Reportistica Commerciale">Reportistica Commerciale</option>
                <option value="Reportistica Vigilanza">Reportistica Vigilanza</option>
                <option value="Altro">Altro</option>
              </select>
            </div>
            <div className="filter-group">
              <label htmlFor="anno-filter" className="form-label">Anno</label>
              <select 
                id="anno-filter" 
                className="form-select" 
                value={filters.anno} 
                onChange={e => handleFilterChange('anno', e.target.value)} 
                disabled={loadingActions.global !== null}
              >
                <option value="2024">2024</option>
                <option value="2023">2023</option>
                <option value="2022">2022</option>
              </select>
            </div>
          </div>
          <div className="filter-row">
            <div className="filter-group">
              <label htmlFor="package-filter" className="form-label">Package</label>
              <select 
                id="package-filter" 
                className="form-select" 
                value={filters.package} 
                onChange={e => handleFilterChange('package', e.target.value)} 
                disabled={loadingActions.global !== null}
              >
                <option value="Tutti">Tutti</option>
                <option value="Package A">Package A</option>
                <option value="Package B">Package B</option>
              </select>
            </div>
            
            {/* Campo dinamico: Settimana o Mese */}
            {currentPeriodicity === 'settimanale' && (
              <div className="filter-group">
                <label htmlFor="settimana-filter" className="form-label">Settimana</label>
                <select 
                  id="settimana-filter" 
                  className="form-select" 
                  value={filters.settimana || ''} 
                  onChange={e => handleFilterChange('settimana', e.target.value)} 
                  disabled={loadingActions.global !== null}
                >
                  <option value="01">Settimana 1</option>
                  <option value="02">Settimana 2</option>
                  <option value="03">Settimana 3</option>
                  <option value="04">Settimana 4</option>
                  <option value="05">Settimana 5</option>
                  <option value="06">Settimana 6</option>
                  <option value="07">Settimana 7</option>
                  <option value="08">Settimana 8</option>
                  <option value="09">Settimana 9</option>
                  <option value="10">Settimana 10</option>
                  <option value="11">Settimana 11</option>
                  <option value="12">Settimana 12</option>
                  <option value="13">Settimana 13</option>
                  <option value="14">Settimana 14</option>
                  <option value="15">Settimana 15</option>
                  <option value="16">Settimana 16</option>
                  <option value="17">Settimana 17</option>
                  <option value="18">Settimana 18</option>
                  <option value="19">Settimana 19</option>
                  <option value="20">Settimana 20</option>
                  <option value="21">Settimana 21</option>
                  <option value="22">Settimana 22</option>
                  <option value="23">Settimana 23</option>
                  <option value="24">Settimana 24</option>
                  <option value="25">Settimana 25</option>
                  <option value="26">Settimana 26</option>
                  <option value="27">Settimana 27</option>
                  <option value="28">Settimana 28</option>
                  <option value="29">Settimana 29</option>
                  <option value="30">Settimana 30</option>
                  <option value="31">Settimana 31</option>
                  <option value="32">Settimana 32</option>
                  <option value="33">Settimana 33</option>
                  <option value="34">Settimana 34</option>
                  <option value="35">Settimana 35</option>
                  <option value="36">Settimana 36</option>
                  <option value="37">Settimana 37</option>
                  <option value="38">Settimana 38</option>
                  <option value="39">Settimana 39</option>
                  <option value="40">Settimana 40</option>
                  <option value="41">Settimana 41</option>
                  <option value="42">Settimana 42</option>
                  <option value="43">Settimana 43</option>
                  <option value="44">Settimana 44</option>
                  <option value="45">Settimana 45</option>
                  <option value="46">Settimana 46</option>
                  <option value="47">Settimana 47</option>
                  <option value="48">Settimana 48</option>
                  <option value="49">Settimana 49</option>
                  <option value="50">Settimana 50</option>
                  <option value="51">Settimana 51</option>
                  <option value="52">Settimana 52</option>
                  <option value="53">Settimana 53</option>
                </select>
              </div>
            )}
            
            {currentPeriodicity === 'mensile' && (
              <div className="filter-group">
                <label htmlFor="mese-filter" className="form-label">Mese</label>
                <select 
                  id="mese-filter" 
                  className="form-select" 
                  value={filters.mese || ''} 
                  onChange={e => handleFilterChange('mese', e.target.value)} 
                  disabled={loadingActions.global !== null}
                >
                  <option value="01">Gennaio</option>
                  <option value="02">Febbraio</option>
                  <option value="03">Marzo</option>
                  <option value="04">Aprile</option>
                  <option value="05">Maggio</option>
                  <option value="06">Giugno</option>
                  <option value="07">Luglio</option>
                  <option value="08">Agosto</option>
                  <option value="09">Settembre</option>
                  <option value="10">Ottobre</option>
                  <option value="11">Novembre</option>
                  <option value="12">Dicembre</option>
                </select>
              </div>
            )}
            
            <div className="filter-group overall-status-group">
              <label className="form-label">Status Complessivo</label>
              <div className="status-indicators">
                <span 
                  className={`status-dot ${overallStatus === 'completed' ? 'active-success' : ''}`} 
                  title="Completato"
                ></span>
                <span 
                  className={`status-dot ${overallStatus === 'pending' ? 'active-warning' : ''}`} 
                  title="In Attesa / Warning"
                ></span>
                <span 
                  className={`status-dot ${overallStatus === 'error' ? 'active-danger' : ''}`} 
                  title="Errore"
                ></span>
              </div>
            </div>
          </div>
        </section>

        <section className="report-tasks-section">
          <div className="report-table-wrapper">
            <table className="report-table">
              <thead>
                <tr>
                  <th>
                    <input 
                      type="checkbox" 
                      className="form-checkbox" 
                      onChange={handleSelectAllTasks} 
                      checked={allTasksSelected} 
                      disabled={filteredReportTasks.length === 0 || loadingActions.global !== null}
                    />
                  </th>
                  <th>File / Descrizione</th>
                  <th>Package</th>
                  <th>Stato Server</th>
                  <th>Dettagli Server</th>
                  <th>Stato SP</th>
                  <th>Data Copia SP</th>
                  <th>Stato PBI</th>
                  <th>Azione</th>
                </tr>
              </thead>
              <tbody>
                {filteredReportTasks.map(task => {
                  const {Icon: ActionIcon, label: actionButtonLabel} = getActionLabelAndIcon(task);
                  return (
                    <tr key={task.id} className={selectedTaskIds.has(task.id) ? 'selected-row' : ''}>
                      <td>
                        <input 
                          type="checkbox" 
                          className="form-checkbox" 
                          checked={selectedTaskIds.has(task.id)} 
                          onChange={() => handleTaskSelection(task.id)} 
                          disabled={loadingActions.global !== null || loadingActions.taskAction === task.id}
                        />
                      </td>
                      <td>
                        <strong>{task.fileName}</strong><br/>
                        <span className="text-xs text-gray-500">{task.description}</span>
                      </td>
                      <td>{task.package}</td>
                      <td>
                        <span className={`status-badge ${getTaskStatusBadge('serverStatus', task.serverStatus)}`}>
                          {task.serverStatus.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="text-xs">{task.serverCheckDetails}</td>
                      <td>
                        <span className={`status-badge ${getTaskStatusBadge('sharepointStatus', task.sharepointStatus)}`}>
                          {task.sharepointStatus.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td>
                        {task.sharepointCopyDate ? new Date(task.sharepointCopyDate).toLocaleDateString() : 'N/D'}
                      </td>
                      <td>
                        <span className={`status-badge ${getTaskStatusBadge('powerBIStatus', task.powerBIStatus)}`}>
                          {task.powerBIStatus.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td>
                        <button 
                          className="btn btn-outline btn-sm" 
                          onClick={() => handleTaskAction(task.id)} 
                          disabled={loadingActions.global !== null || loadingActions.taskAction === task.id}
                        >
                          {loadingActions.taskAction === task.id ? 
                            <RefreshCw className="btn-icon-sm animate-spin-css"/> : 
                            <ActionIcon size={16} className="btn-icon-sm"/>
                          }
                          {loadingActions.taskAction === task.id ? "In Corso..." : actionButtonLabel}
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {filteredReportTasks.length === 0 && (
                  <tr>
                    <td colSpan="9" className="text-center muted-text">
                      Nessuna attività di reportistica {currentPeriodicity} trovata per i filtri selezionati.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="report-global-actions">
          <button 
            className="btn btn-outline" 
            onClick={() => handleGlobalAction('log')} 
            disabled={!isAnyTaskSelected || loadingActions.global !== null}
          >
            <FileText className="btn-icon-md" /> LOG SELEZIONATI
          </button>
          <button 
            className="btn btn-primary" 
            onClick={() => handleGlobalAction('esegui')} 
            disabled={!isAnyTaskSelected || loadingActions.global !== null}
          >
            <Play className="btn-icon-md" /> ESEGUI SELEZIONATI
          </button>
          <button 
            className="btn btn-outline" 
            onClick={() => handleGlobalAction('creaPeriodo')} 
            disabled={!isAnyTaskSelected || loadingActions.global !== null}
          >
            <PlusSquare className="btn-icon-md" /> CREA {periodicityConfig.timeLabel.toUpperCase()}
          </button>
          <button 
            className="btn btn-outline" 
            onClick={() => handleGlobalAction('copiaServerSP')} 
            disabled={loadingActions.global !== null}
          >
            <Copy className="btn-icon-md" /> COPIA SU SP
          </button>
          <button 
            className="btn btn-outline" 
            onClick={() => handleGlobalAction('importPBI')} 
            disabled={!canImportPBI || loadingActions.global !== null}
          >
            <UploadCloud className="btn-icon-md" /> IMPORT PBI
          </button>
          <button 
            className="btn btn-success" 
            onClick={() => handleGlobalAction('pubblica')} 
            disabled={overallStatus !== 'completed' || loadingActions.global !== null}
          >
            <Send className="btn-icon-md" /> PUBBLICA REPORT
          </button>
        </section>
      </div>
    </div>
  );
}

export default Report;