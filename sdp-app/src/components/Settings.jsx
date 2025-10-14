// src/components/Settings/Settings.jsx
import { useState, useMemo, useEffect, useCallback } from "react";
import { toast } from "react-toastify";
import { useNavigate } from "react-router-dom";
import { useAppContext } from "../context/AppContext";
import apiClient from "../api/apiClient";
import {
  Settings as SettingsIcon,
  Users,
  Database,
  Edit,
  ExternalLink,
  Save,
  Plus,
  Trash2,
  RefreshCw,
  ListChecks,
  Search,
  Key,
} from "lucide-react";
import "./Settings.css";

// =================================================================================
// --- DEFINIZIONE DEI SOTTO-COMPONENTI PER I TAB
// =================================================================================

// --- Tab "File Metadati" ---
function MetadataFileTabContent({
  metadataPathFromIni,
  onOpenMetadataFile,
  loadingStates,
}) {
  return (
    <div className="tab-content-padding">
      <div className="tab-content-header">
        <Database className="tab-content-icon" />
        <h2 className="tab-content-title">File Metadati</h2>
      </div>
      <div className="metadata-grid">
        <div className="metadata-card">
          <div className="metadata-card-header">
            <div className="metadata-card-icon-bg metadata-card-icon-bg-green">
              <Database className="metadata-card-icon metadata-card-icon-green" />
            </div>
            <h3 className="metadata-card-title">Percorso File Metadati</h3>
          </div>
          <p className="metadata-card-description">
            Visualizza il percorso del file metadati referenziato nel file INI della banca selezionata.
          </p>
          <input
            type="text"
            value={metadataPathFromIni || ""}
            className="form-input"
            disabled
            placeholder="Nessun percorso configurato"
          />
          <div className="metadata-card-input-group">
            <button
              onClick={onOpenMetadataFile}
              className="btn btn-outline w-full"
              disabled={loadingStates?.loadingConfigFile || !metadataPathFromIni}
            >
              <ExternalLink className="btn-icon-md" /> Apri File Metadati
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Tab Log Applicativi ---
function LogsTabContent({ logEntries, onRefreshLogs }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const filteredLogs = useMemo(() => {
    if (!logEntries) return [];

    const start = startDate ? new Date(startDate) : null;
    const end = endDate ? new Date(new Date(endDate).setHours(23, 59, 59, 999)) : null;

    const lowerSearchTerm = searchTerm.toLowerCase();

    return logEntries
      .filter((log) => {
        const matchesSearch =
          log.action?.toLowerCase().includes(lowerSearchTerm) ||
          log.username?.toLowerCase().includes(lowerSearchTerm) ||
          JSON.stringify(log.details)?.toLowerCase().includes(lowerSearchTerm);

        const logDate = new Date(log.timestamp);
        const matchesStartDate = !start || logDate >= start;
        const matchesEndDate = !end || logDate <= end;

        return matchesSearch && matchesStartDate && matchesEndDate;
      })
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [logEntries, searchTerm, startDate, endDate]);

  const handleClearFilters = () => {
    setSearchTerm("");
    setStartDate("");
    setEndDate("");
  };

  return (
    <div className="tab-content-padding">
      <div className="tab-content-header">
        <ListChecks className="tab-content-icon" />
        <h2 className="tab-content-title">Registro Attività</h2>
      </div>

      <div className="logs-controls-grid">
        <input
          type="text"
          placeholder="Cerca per azione, utente, dettagli..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="form-input"
        />
        <div className="date-filter-group">
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="form-input"
            title="Data di inizio"
          />
          <span>-</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="form-input"
            title="Data di fine"
          />
        </div>
        <div className="action-buttons-group">
          <button
            onClick={handleClearFilters}
            className="btn btn-outline"
            title="Resetta tutti i filtri"
          >
            <RefreshCw className="btn-icon-sm" /> Pulisci Filtri
          </button>
          <button
            onClick={onRefreshLogs}
            className="btn btn-outline"
            title="Ricarica i dati dal server"
          >
            <RefreshCw className="btn-icon-sm" /> Aggiorna
          </button>
        </div>
      </div>

      <div className="permissions-table-wrapper">
        <table className="users-table">
          <thead>
            <tr>
              <th style={{ width: "15%" }}>Data e Ora</th>
              <th style={{ width: "15%" }}>Utente</th>
              <th style={{ width: "20%" }}>Azione</th>
              <th>Dettagli</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.length > 0 ? (
              filteredLogs.map((log) => (
                <tr key={log.id}>
                  <td data-label="Data e Ora">
                    <div className="date-primary">
                      {new Date(log.timestamp).toLocaleDateString("it-IT")}
                    </div>
                    <div className="date-secondary">
                      {new Date(log.timestamp).toLocaleTimeString("it-IT")}
                    </div>
                  </td>
                  <td data-label="Utente">{log.username || "Sistema"}</td>
                  <td data-label="Azione">
                    <span className="action-badge">{log.action}</span>
                  </td>
                  <td data-label="Dettagli">
                    {log.details ? (
                      <pre className="details-pre">
                        {JSON.stringify(log.details, null, 2)}
                      </pre>
                    ) : (
                      <span className="muted-text">Nessun dettaglio</span>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="4" className="empty-state-cell">
                  Nessun registro trovato con questi filtri.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="logs-actions">
        <p className="logs-count-info">
          Visualizzati: {filteredLogs.length} (Totali: {logEntries?.length || 0})
        </p>
      </div>
    </div>
  );
}

// --- Tab Permessi ---
// Solo Ingest e Reportistica sono controllabili - Settings è accessibile a tutti
const ALL_ACCESS_MODULES = [
  { id: "ingest", label: "Ingest" },
  { id: "reportistica", label: "Reportistica" },
];

function PermissionsTabContent({
  permissions,
  onPermissionChange,
  onAddNew,
  onRemove,
  onSave,
  isSaving,
  hasUnsavedChanges,
  loadingStates,
  searchTerm,
  setSearchTerm,
  roleFilter,
  setRoleFilter,
  accessFilter,
  setAccessFilter,
  availableRoles,
  onChangePassword,
}) {
  const [selectedPermissionIds, setSelectedPermissionIds] = useState(new Set());

  const filteredPermissions = useMemo(() => {
    const lowerSearchTerm = searchTerm.toLowerCase();

    return permissions.filter((perm) => {
      const matchesSearch = perm.user.toLowerCase().includes(lowerSearchTerm);
      const matchesRole = roleFilter === "all" || perm.role === roleFilter;
      const matchesAccess =
        accessFilter === "all" || (perm.accessTo && perm.accessTo.includes(accessFilter));

      return matchesSearch && matchesRole && matchesAccess;
    });
  }, [permissions, searchTerm, roleFilter, accessFilter]);

  const handleAccessToChange = (permId, accessType, checked) => {
    onPermissionChange(permId, "accessTo", (currentAccessTo = []) => {
      return checked
        ? [...new Set([...currentAccessTo, accessType])]
        : currentAccessTo.filter((type) => type !== accessType);
    });
  };

  const anyActionLoading = isSaving || loadingStates.removingPermissionId !== null;

  return (
    <div className="tab-content-padding">
      <div className="permissions-header">
        <div className="permissions-header-title-group">
          <Users className="tab-content-icon" />
          <h2 className="tab-content-title">Gestione Permessi Utente</h2>
        </div>
        <div className="permissions-header-actions">
          <button
            onClick={onAddNew}
            className="btn btn-outline"
            disabled={anyActionLoading}
          >
            <Plus className="btn-icon-md" /> Nuovo Utente
          </button>
        </div>
      </div>

      <div className="permissions-controls-bar">
        <input
          type="text"
          placeholder="Cerca utente per email..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="form-input"
          disabled={anyActionLoading}
        />
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="form-select"
          disabled={anyActionLoading}
        >
          <option value="all">Tutti i Ruoli</option>
          {availableRoles
            .filter((r) => r !== "all")
            .map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
        </select>
        <select
          value={accessFilter}
          onChange={(e) => setAccessFilter(e.target.value)}
          className="form-select"
          disabled={anyActionLoading}
        >
          <option value="all">Tutti gli Accessi</option>
          {ALL_ACCESS_MODULES.map((module) => (
            <option key={module.id} value={module.id}>
              {module.label}
            </option>
          ))}
        </select>
      </div>

      <div className="permissions-table-wrapper">
        <table className="permissions-table">
          <thead>
            <tr>
              <th>Utente</th>
              <th>Ruolo</th>
              <th>Accesso Moduli</th>
              <th>Azioni</th>
            </tr>
          </thead>
          <tbody>
            {filteredPermissions.map((perm) => (
              <tr
                key={perm.id}
                className={selectedPermissionIds.has(perm.id) ? "selected-row" : ""}
              >
                <td>
                  <input
                    type="email"
                    value={perm.user}
                    onChange={(e) => onPermissionChange(perm.id, "user", e.target.value)}
                    className="form-input"
                    placeholder="email@company.com"
                    disabled={anyActionLoading || loadingStates.removingPermissionId === perm.id}
                  />
                </td>
                <td>
                  <select
                    value={perm.role}
                    onChange={(e) => onPermissionChange(perm.id, "role", e.target.value)}
                    className="form-select"
                    disabled={anyActionLoading || loadingStates.removingPermissionId === perm.id}
                  >
                    {availableRoles
                      .filter((r) => r !== "all")
                      .map((role) => (
                        <option key={role} value={role}>
                          {role}
                        </option>
                      ))}
                  </select>
                </td>
                <td className="permissions-access-to-cell">
                  {ALL_ACCESS_MODULES.map((module) => (
                    <label key={module.id} className="checkbox-label">
                      <input
                        type="checkbox"
                        className="form-checkbox-sm"
                        checked={perm.accessTo?.includes(module.id) || false}
                        onChange={(e) =>
                          handleAccessToChange(perm.id, module.id, e.target.checked)
                        }
                        disabled={
                          anyActionLoading || loadingStates.removingPermissionId === perm.id
                        }
                      />
                      {module.label}
                    </label>
                  ))}
                </td>
                <td>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={() => onChangePassword(perm.id, perm.user)}
                      className="btn btn-outline"
                      disabled={anyActionLoading}
                      title="Cambia password"
                    >
                      <Key className="btn-icon-sm" />
                    </button>
                    <button
                      onClick={() => onRemove(perm.id)}
                      className="btn btn-outline"
                      disabled={
                        anyActionLoading || loadingStates.removingPermissionId === perm.id
                      }
                    >
                      {loadingStates.removingPermissionId === perm.id ? (
                        <RefreshCw className="btn-icon-sm animate-spin-css" />
                      ) : (
                        <Trash2 className="btn-icon-sm" />
                      )}
                      Rimuovi
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {filteredPermissions.length === 0 && (
              <tr>
                <td colSpan="5" className="text-center muted-text">
                  Nessun utente trovato con questi filtri.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="permissions-footer">
        <p className="permissions-footer-count">
          Utenti visualizzati: {filteredPermissions.length} (Totali: {permissions.length})
        </p>

        <div className="save-actions-wrapper">
          {hasUnsavedChanges && (
            <span className="unsaved-indicator">Modifiche non salvate</span>
          )}
          <button
            onClick={onSave}
            className="btn btn-outline"
            disabled={anyActionLoading || !hasUnsavedChanges}
          >
            {isSaving ? (
              <>
                <RefreshCw className="btn-icon-md animate-spin-css" />
                Salvataggio...
              </>
            ) : (
              <>
                <Save className="btn-icon-md" />
                Salva Permessi
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// --- Tab Config File (Solo INI) ---
function ConfigFileTabContent({
  iniPath, // Riceve il percorso del file INI
  onOpenIniFile, // Funzione per aprire il file INI
  loadingStates,
}) {
  const anyConfigActionLoading = loadingStates.loadingConfigFile;

  return (
    <div className="tab-content-padding">
      <div className="tab-content-header">
        <Edit className="tab-content-icon" />
        <h2 className="tab-content-title">File Config</h2>
      </div>

      <div className="metadata-grid">
        <div className="metadata-card">
          <div className="metadata-card-header">
            <div className="metadata-card-icon-bg">
              <Edit className="metadata-card-icon" />
            </div>
            <h3 className="metadata-card-title">Percorso File INI</h3>
          </div>
          <p className="metadata-card-description">
            Visualizza il percorso del file di configurazione INI della banca selezionata.
          </p>
          <input
            type="text"
            value={iniPath || ""}
            className="form-input"
            disabled // Impedisce la modifica
          />
          <div className="metadata-card-input-group">
            <button
              onClick={onOpenIniFile}
              className="btn btn-outline w-full"
              disabled={anyConfigActionLoading || !iniPath}
            >
              <ExternalLink className="btn-icon-md" /> Apri File INI
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function CreateUserModal({
  isOpen,
  onClose,
  newUser,
  setNewUser,
  onCreate,
  error,
  isCreating,
}) {
  if (!isOpen) return null;

  const handleChange = (e) => {
    const { name, value } = e.target;
    setNewUser((prev) => ({ ...prev, [name]: value }));
  };

  const handlePermissionChange = (permissionId, checked) => {
    setNewUser((prev) => {
      const currentPermissions = prev.permissions || [];
      const newPermissions = checked
        ? [...currentPermissions, permissionId]
        : currentPermissions.filter((p) => p !== permissionId);
      return { ...prev, permissions: newPermissions };
    });
  };

  const handleGeneratePassword = () => {
    const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*";
    let password = "";
    for (let i = 0; i < 12; i++) {
      password += alphabet.charAt(Math.floor(Math.random() * alphabet.length));
    }
    setNewUser((prev) => ({ ...prev, password }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onCreate();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>Crea Nuovo Utente</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              name="username"
              value={newUser.username}
              onChange={handleChange}
              required
              disabled={isCreating}
              placeholder="es. m.rossi"
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              value={newUser.email}
              onChange={handleChange}
              required
              disabled={isCreating}
              placeholder="es. mario.rossi@azienda.it"
            />
          </div>

          <div className="form-group">
            <label htmlFor="role">Ruolo</label>
            <select
              id="role"
              name="role"
              value={newUser.role}
              onChange={handleChange}
              disabled={isCreating}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="bank">Banca</label>
            <input
              type="text"
              id="bank"
              name="bank"
              value={newUser.bank}
              onChange={handleChange}
              disabled={isCreating}
              placeholder="Banca dell'utente"
            />
          </div>

          <div className="form-group">
            <label>Permessi Accesso Moduli</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
              {ALL_ACCESS_MODULES.map((module) => (
                <label key={module.id} className="checkbox-label">
                  <input
                    type="checkbox"
                    className="form-checkbox-sm"
                    checked={newUser.permissions?.includes(module.id) || false}
                    onChange={(e) => handlePermissionChange(module.id, e.target.checked)}
                    disabled={isCreating}
                  />
                  {module.label}
                </label>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                id="password"
                name="password"
                value={newUser.password}
                onChange={handleChange}
                disabled={isCreating}
                placeholder="Lascia vuoto per generazione automatica"
                style={{ flex: 1 }}
              />
              <button
                type="button"
                onClick={handleGeneratePassword}
                className="btn btn-outline"
                disabled={isCreating}
                style={{ whiteSpace: 'nowrap' }}
              >
                <RefreshCw className="btn-icon-sm" /> Genera
              </button>
            </div>
          </div>

          {error && <p className="error-message">{error}</p>}

          <div className="modal-actions">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-outline"
              disabled={isCreating}
            >
              Annulla
            </button>
            <button type="submit" className="btn" disabled={isCreating}>
              {isCreating ? "Creazione in corso..." : "Crea Utente"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PasswordChangeModal({
  isOpen,
  onClose,
  passwordData,
  setPasswordData,
  onChange,
  error,
  isChanging,
}) {
  if (!isOpen) return null;

  const handleGeneratePassword = () => {
    const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*";
    let password = "";
    for (let i = 0; i < 12; i++) {
      password += alphabet.charAt(Math.floor(Math.random() * alphabet.length));
    }
    setPasswordData((prev) => ({ ...prev, newPassword: password }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onChange();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <h2>Cambia Password</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Utente</label>
            <input
              type="text"
              id="username"
              value={passwordData.username}
              disabled
            />
          </div>

          <div className="form-group">
            <label htmlFor="newPassword">Nuova Password</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                id="newPassword"
                value={passwordData.newPassword}
                onChange={(e) => setPasswordData((prev) => ({ ...prev, newPassword: e.target.value }))}
                required
                disabled={isChanging}
                placeholder="Inserisci la nuova password"
                style={{ flex: 1 }}
              />
              <button
                type="button"
                onClick={handleGeneratePassword}
                className="btn btn-outline"
                disabled={isChanging}
                style={{ whiteSpace: 'nowrap' }}
              >
                <RefreshCw className="btn-icon-sm" /> Genera
              </button>
            </div>
          </div>

          {error && <p className="error-message">{error}</p>}

          <div className="modal-actions">
            <button
              type="button"
              onClick={onClose}
              className="btn btn-outline"
              disabled={isChanging}
            >
              Annulla
            </button>
            <button type="submit" className="btn" disabled={isChanging}>
              {isChanging ? "Modifica in corso..." : "Cambia Password"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Settings() {
  const navigate = useNavigate();
  const { metadataFilePath, setMetadataFilePath } = useAppContext();

  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [activeTab, setActiveTab] = useState("metadata_file");
  const [permissions, setPermissions] = useState([]);
  const [iniPath, setIniPath] = useState(""); // Stato per il percorso del file INI
  const [metadataPath, setMetadataPath] = useState(""); // Stato per il percorso del file metadati
  const [logEntries, setLogEntries] = useState([]);

  const [permissionSearchTerm, setPermissionSearchTerm] = useState("");
  const [permissionRoleFilter, setPermissionRoleFilter] = useState("all");
  const [permissionAccessFilter, setPermissionAccessFilter] = useState("all");

  const AVAILABLE_ROLES_FOR_FILTER = useMemo(
    () => ["all", ...new Set(permissions.map((p) => p.role))],
    [permissions]
  );

  const [loadingStates, setLoadingStates] = useState({
    savingPermissions: false,
    removingPermissionId: null,
    loadingConfigFile: false,
    refreshingLogs: false,
  });

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newUser, setNewUser] = useState({
    username: "",
    email: "",
    password: "",
    role: "user",
    bank: "",
    permissions: []
  });
  const [createError, setCreateError] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [passwordChangeData, setPasswordChangeData] = useState({
    userId: null,
    username: "",
    newPassword: "",
  });
  const [passwordChangeError, setPasswordChangeError] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const fetchIniPath = useCallback(async () => {
    setLoadingStates(prev => ({ ...prev, loadingConfigFile: true }));
    try {
      const selectedBank = sessionStorage.getItem("selectedBank");
      if (!selectedBank) {
        toast.error("Nessuna banca selezionata.");
        return;
      }

      const response = await apiClient.get("/folder/ini-path", {
        params: { bank: selectedBank }
      });
      setIniPath(response.data.ini_path); // Salva il percorso del file INI
      setMetadataPath(response.data.metadata_path); // Salva il percorso del file metadati
    } catch (error) {
      console.error("Errore nel recupero dei percorsi dei file:", error);
      toast.error("Impossibile caricare i percorsi dei file di configurazione.");
    } finally {
      setLoadingStates(prev => ({ ...prev, loadingConfigFile: false }));
    }
  }, []);

  useEffect(() => {
    const fetchInitialData = async () => {
      setAuthLoading(true);
      try {
        const userResponse = await apiClient.get("/users/me");
        const user = userResponse.data;
        setCurrentUser(user);

        if (user && user.role === "admin") {
          const results = await Promise.allSettled([
            apiClient.get("/users/all"),
            apiClient.get("/audit/logs"),
          ]);

          const permissionsResult = results[0];
          const auditLogsResult = results[1];

          if (permissionsResult.status === "fulfilled") {
            setPermissions(permissionsResult.value.data.map((dbUser) => ({
              id: dbUser.id,
              user: dbUser.email || dbUser.username,
              role: dbUser.role,
              accessTo: dbUser.permissions || [],
            })));
          } else {
            console.error("Fallito il caricamento dei permessi:", permissionsResult.reason);
            toast.error("Impossibile caricare la lista utenti.");
          }

          if (auditLogsResult.status === "fulfilled") {
            setLogEntries(auditLogsResult.value.data);
          } else {
            console.error("Fallito il caricamento dei log di audit:", auditLogsResult.reason);
            toast.error("Impossibile caricare il registro attività.");
          }
        }
      } catch (error) {
        console.error("Errore di autenticazione:", error);
        navigate("/login");
      } finally {
        setAuthLoading(false);
      }
    };

    fetchInitialData();
  }, [navigate]);
  useEffect(() => {
    // Chiama fetchIniPath se il tab attivo è "config" o "metadata_file"
    if (activeTab === "config" || activeTab === "metadata_file") {
      fetchIniPath();
    }
  }, [activeTab, fetchIniPath]);


  const TABS = useMemo(() => {
    const baseTabs = [];

    // Mostra tab File Metadati e Config solo se l'utente ha il permesso "ingest"
    if (currentUser && currentUser.permissions && currentUser.permissions.includes("ingest")) {
      baseTabs.push(
        { id: "metadata_file", label: "File Metadati", icon: Database },
        { id: "config", label: "Config File", icon: Edit }
      );
    }

    // Mostra tab Permessi e Log solo per admin
    if (currentUser && currentUser.role === "admin") {
      baseTabs.push({
        id: "permissions",
        label: "Permessi",
        icon: Users,
      });
      baseTabs.push({
        id: "logs",
        label: "Log",
        icon: ListChecks,
      });
    }

    return baseTabs;
  }, [currentUser]);

  useEffect(() => {
    if (!currentUser) return;

    // Se l'utente non ha accesso al tab corrente, passa al primo tab disponibile
    const hasAccessToCurrentTab = TABS.some(tab => tab.id === activeTab);
    if (!hasAccessToCurrentTab && TABS.length > 0) {
      setActiveTab(TABS[0].id);
    }
  }, [currentUser, activeTab, TABS]);

  const openCreateModal = () => {
    const selectedBank = sessionStorage.getItem("selectedBank") || "";
    setNewUser({
      username: "",
      email: "",
      password: "",
      role: "user",
      bank: selectedBank,
      permissions: []
    });
    setCreateError("");
    setIsCreateModalOpen(true);
  };

  const closeCreateModal = () => {
    setIsCreateModalOpen(false);
  };

  const handleCreateUser = async () => {
    setIsCreating(true);
    setCreateError("");

    try {
      // Prepara il payload: se password è vuota, invia null
      const payload = {
        ...newUser,
        password: newUser.password?.trim() || null
      };

      const response = await apiClient.post("/users/", payload);
      const createdUser = response.data;

      setPermissions((prev) => [{
        id: createdUser.id,
        user: createdUser.email || createdUser.username,
        role: createdUser.role,
        accessTo: createdUser.permissions || [],
      }, ...prev]);

      // Mostra la password (generata dal backend o inserita dall'admin)
      const passwordToShow = createdUser.generated_password || newUser.password;
      if (passwordToShow) {
        toast.success(
          `Utente creato! Password: ${passwordToShow}`,
          { autoClose: 15000 }
        );
      } else {
        toast.success("Utente creato con successo!");
      }

      closeCreateModal();

    } catch (error) {
      console.error("Errore nella creazione dell'utente:", error);

      // Gestisci l'errore di validazione Pydantic (422)
      let errorMessage = "Impossibile creare l'utente.";

      if (error.response?.data?.detail) {
        const detail = error.response.data.detail;

        // Se è un array di errori di validazione Pydantic
        if (Array.isArray(detail)) {
          errorMessage = detail.map(err => `${err.loc.join('.')}: ${err.msg}`).join(', ');
        } else if (typeof detail === 'string') {
          errorMessage = detail;
        } else {
          errorMessage = JSON.stringify(detail);
        }
      }

      setCreateError(errorMessage);

    } finally {
      setIsCreating(false);
    }
  };

  const handlePermissionChange = async (id, field, valueOrUpdater) => {
    setHasUnsavedChanges(true);
    setPermissions((prev) =>
      prev.map((p) =>
        p.id === id
          ? { ...p, [field]: typeof valueOrUpdater === "function" ? valueOrUpdater(p[field]) : valueOrUpdater }
          : p
      )
    );
  };

  const removePermission = async (id) => {
    const userToRemove = permissions.find((p) => p.id === id);
    if (!userToRemove) return;

    if (window.confirm(`Vuoi rimuovere "${userToRemove.user}"?`)) {
      setLoadingStates((prev) => ({ ...prev, removingPermissionId: id }));
      try {
        await apiClient.delete(`/users/${id}`);
        setPermissions((prev) => prev.filter((p) => p.id !== id));
        toast.success(`Utente "${userToRemove.user}" rimosso.`);
      } catch (error) {
        console.error("Errore nella rimozione dell'utente:", error);
        toast.error("Impossibile rimuovere l'utente.");
      } finally {
        setLoadingStates((prev) => ({ ...prev, removingPermissionId: null }));
      }
    }
  };

  const handleSavePermissions = async () => {
    setHasUnsavedChanges(false);
    setLoadingStates((prev) => ({ ...prev, savingPermissions: true }));

    try {
      await Promise.all(permissions.map((perm) =>
        apiClient.put(`/users/${perm.id}`, { role: perm.role, permissions: perm.accessTo })
      ));

      toast.success("Permessi salvati!");

      // Ricarica i dati dell'utente corrente per aggiornare i permessi
      try {
        const userResponse = await apiClient.get("/users/me");
        setCurrentUser(userResponse.data);
      } catch (error) {
        console.error("Errore nel ricaricare l'utente corrente:", error);
      }
    } catch (error) {
      console.error("Errore nel salvataggio dei permessi:", error);
      toast.error(error.response?.data?.detail || "Impossibile salvare i permessi.");
    } finally {
      setLoadingStates((prev) => ({ ...prev, savingPermissions: false }));
    }
  };

  const handleOpenIniFile = async () => {
    try {
      await apiClient.post("/folder/open-file", { file_path: iniPath });
      toast.success("File INI aperto con successo!");
    } catch (error) {
      console.error("Errore nell'apertura del file INI:", error);
      toast.error(error.response?.data?.detail || "Impossibile aprire il file INI.");
    }
  };

  const handleOpenMetadataFile = async () => {
    try {
      await apiClient.post("/folder/open-file", { file_path: metadataPath });
      toast.success("File metadati aperto con successo!");
    } catch (error) {
      console.error("Errore nell'apertura del file metadati:", error);
      toast.error(error.response?.data?.detail || "Impossibile aprire il file metadati.");
    }
  };

  const handleRefreshLogs = async () => {
    setAuthLoading(true);
    try {
      const auditLogsResponse = await apiClient.get("/audit/logs");
      setLogEntries(auditLogsResponse.data);
      toast.success("Registro attività aggiornato!");
    } catch (error) {
      toast.error("Impossibile aggiornare il registro.");
    } finally {
      setAuthLoading(false);
    }
  };

  const openPasswordChangeModal = (userId, username) => {
    setPasswordChangeData({
      userId,
      username,
      newPassword: "",
    });
    setPasswordChangeError("");
    setIsPasswordModalOpen(true);
  };

  const closePasswordChangeModal = () => {
    setIsPasswordModalOpen(false);
  };

  const handleChangePassword = async () => {
    setIsChangingPassword(true);
    setPasswordChangeError("");

    try {
      await apiClient.put(`/users/${passwordChangeData.userId}/password`, {
        new_password: passwordChangeData.newPassword,
      });

      toast.success(`Password per ${passwordChangeData.username} modificata con successo!`);
      closePasswordChangeModal();
    } catch (error) {
      console.error("Errore nel cambio password:", error);
      const errorMessage = error.response?.data?.detail || "Impossibile cambiare la password.";
      setPasswordChangeError(errorMessage);
    } finally {
      setIsChangingPassword(false);
    }
  };

  const renderActiveTabContent = () => {
    if ((activeTab === "permissions" || activeTab === "logs") && (!currentUser || currentUser.role !== "admin")) {
      return (
        <div className="tab-content-padding">
          <p className="error-message">Accesso non autorizzato.</p>
        </div>
      );
    }

    switch (activeTab) {
      case "metadata_file":
        return (
          <MetadataFileTabContent
            metadataPathFromIni={metadataPath}
            onOpenMetadataFile={handleOpenMetadataFile}
            loadingStates={loadingStates}
          />
        );
      case "permissions":
        return (
          <PermissionsTabContent
            permissions={permissions}
            onPermissionChange={handlePermissionChange}
            onAddNew={openCreateModal}
            onRemove={removePermission}
            onSave={handleSavePermissions}
            isSaving={loadingStates.savingPermissions}
            hasUnsavedChanges={hasUnsavedChanges}
            loadingStates={loadingStates}
            searchTerm={permissionSearchTerm}
            setSearchTerm={setPermissionSearchTerm}
            roleFilter={permissionRoleFilter}
            setRoleFilter={setPermissionRoleFilter}
            accessFilter={permissionAccessFilter}
            setAccessFilter={setPermissionAccessFilter}
            availableRoles={AVAILABLE_ROLES_FOR_FILTER}
            onChangePassword={openPasswordChangeModal}
          />
        );
      case "config":
        return (
          <ConfigFileTabContent
            iniPath={iniPath} // Passa il percorso del file INI
            onOpenIniFile={handleOpenIniFile} // Passa la funzione per aprire il file INI
            loadingStates={loadingStates}
          />
        );
      case "logs":
        return (
          <LogsTabContent
            logEntries={logEntries}
            onRefreshLogs={handleRefreshLogs}
          />
        );
      default:
        return null;
    }
  };

  if (authLoading) {
    return (
      <div className="settings-container loading">
        <p>Caricamento impostazioni...</p>
      </div>
    );
  }

  const isAnyLoadingInProgress = Object.values(loadingStates).some(Boolean);

  return (
    <div className="settings-container">
      <div className="settings-content-wrapper">
        <header className="settings-header-container">
          <div className="settings-header">
            <div className="settings-header-title-group">
              <div className="settings-header-icon-bg">
                <SettingsIcon className="settings-header-icon" />
              </div>
              <div>
                <h1 className="settings-header-title">Impostazioni</h1>
                <p className="settings-header-subtitle">Banca: {sessionStorage.getItem("selectedBank") || "N/A"}</p>
              </div>
            </div>
            <button
              onClick={() => navigate("/home")}
              className="btn btn-outline"
              disabled={isAnyLoadingInProgress}
            >
              ← Indietro
            </button>
          </div>
        </header>

        {TABS.length === 0 ? (
          <div className="tab-content-padding">
            <p className="error-message">Non hai i permessi necessari per accedere alle impostazioni.</p>
          </div>
        ) : (
          <>
            <nav className="tab-nav-container">
              <div className={`tab-nav-grid ${TABS.length === 3 ? "three-tabs" : ""}`}>
                {TABS.map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`tab-button ${activeTab === tab.id ? "active" : ""}`}
                      disabled={isAnyLoadingInProgress && activeTab !== tab.id}
                    >
                      <div className="tab-button-header">
                        <Icon className="tab-button-icon" />
                        <span className="tab-button-label">{tab.label}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </nav>

            <main className="tab-content-main">{renderActiveTabContent()}</main>
          </>
        )}
      </div>

      <CreateUserModal
        isOpen={isCreateModalOpen}
        onClose={closeCreateModal}
        newUser={newUser}
        setNewUser={setNewUser}
        onCreate={handleCreateUser}
        error={createError}
        isCreating={isCreating}
      />

      <PasswordChangeModal
        isOpen={isPasswordModalOpen}
        onClose={closePasswordChangeModal}
        passwordData={passwordChangeData}
        setPasswordData={setPasswordChangeData}
        onChange={handleChangePassword}
        error={passwordChangeError}
        isChanging={isChangingPassword}
      />
    </div>
  );
}

export default Settings;