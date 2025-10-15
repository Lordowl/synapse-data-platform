import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AppProvider } from './context/AppContext';
import App from "./App";
/* 
// Disabilita il menu contestuale (tasto destro) per prevenire inspect
document.addEventListener('contextmenu', (e) => {
  e.preventDefault();
  return false;
});

// Disabilita anche F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+U
document.addEventListener('keydown', (e) => {
  // F12
  if (e.key === 'F12') {
    e.preventDefault();
    return false;
  }
  // Ctrl+Shift+I (Inspect)
  if (e.ctrlKey && e.shiftKey && e.key === 'I') {
    e.preventDefault();
    return false;
  }
  // Ctrl+Shift+J (Console)
  if (e.ctrlKey && e.shiftKey && e.key === 'J') {
    e.preventDefault();
    return false;
  }
  // Ctrl+U (View Source)
  if (e.ctrlKey && e.key === 'U') {
    e.preventDefault();
    return false;
  }
});
 */
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AppProvider>
    <BrowserRouter>
      <App />
    </BrowserRouter>
    </AppProvider>
  </React.StrictMode>
);