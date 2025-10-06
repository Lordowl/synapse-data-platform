// src/context/AppContext.jsx
import React, { createContext, useState, useContext } from 'react';

// 1. Crea il contesto
const AppContext = createContext();

// 2. Crea il Provider (il componente che gestisce e fornisce lo stato)
export const AppProvider = ({ children }) => {
  // Stato per il percorso del file di metadati.
  // Null finché l'utente non carica un file dalle Impostazioni
  const [metadataFilePath, setMetadataFilePath] = useState(null);

  // Valori che vogliamo rendere disponibili a tutta l'app
  const value = {
    metadataFilePath,
    setMetadataFilePath,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

// 3. Crea un hook custom per usare facilmente il contesto
export const useAppContext = () => {
  return useContext(AppContext);
};