// src/utils/sessionTimeout.js

let inactivityTimer = null;
let lastActivityTime = Date.now();

// Timeout di inattività: 1 giorno (24 ore)
const INACTIVITY_TIMEOUT = 24 * 60 * 60 * 1000; // 24 ore in millisecondi

/**
 * Resetta il timer di inattività
 * Chiamato ad ogni interazione utente
 */
export function resetInactivityTimer() {
  lastActivityTime = Date.now();

  // Cancella timer precedente
  if (inactivityTimer) {
    clearTimeout(inactivityTimer);
  }

  // Avvia nuovo timer
  inactivityTimer = setTimeout(() => {
    console.log('Session expired due to inactivity');

    // Logout automatico dopo 24 ore di inattività
    sessionStorage.removeItem('accessToken');
    sessionStorage.removeItem('apiBaseURL');
    sessionStorage.removeItem('selectedBank');

    // Reindirizza al login con messaggio
    window.location.href = '/login?reason=inactivity';
  }, INACTIVITY_TIMEOUT);
}

/**
 * Avvia il tracking dell'inattività utente
 * Monitora eventi mouse, tastiera, touch, scroll
 */
export function startInactivityTracking() {
  console.log('Starting inactivity tracking (24 hour timeout)');

  // Eventi da monitorare per attività utente
  const events = [
    'mousedown',
    'mousemove',
    'keydown',
    'scroll',
    'touchstart',
    'click',
    'wheel'
  ];

  // Aggiungi listener per ogni evento
  events.forEach(event => {
    document.addEventListener(event, resetInactivityTimer, true);
  });

  // Avvia timer iniziale
  resetInactivityTimer();
}

/**
 * Ferma il tracking dell'inattività
 * Chiamato al logout
 */
export function stopInactivityTracking() {
  console.log('Stopping inactivity tracking');

  if (inactivityTimer) {
    clearTimeout(inactivityTimer);
    inactivityTimer = null;
  }

  // Rimuovi tutti i listener
  const events = [
    'mousedown',
    'mousemove',
    'keydown',
    'scroll',
    'touchstart',
    'click',
    'wheel'
  ];

  events.forEach(event => {
    document.removeEventListener(event, resetInactivityTimer, true);
  });
}

/**
 * Ottieni il tempo rimanente prima del timeout
 * @returns {number} Millisecondi rimanenti
 */
export function getTimeUntilTimeout() {
  const elapsed = Date.now() - lastActivityTime;
  const remaining = INACTIVITY_TIMEOUT - elapsed;
  return remaining > 0 ? remaining : 0;
}

/**
 * Ottieni il timeout configurato in ore
 * @returns {number} Ore di timeout
 */
export function getTimeoutInHours() {
  return INACTIVITY_TIMEOUT / (60 * 60 * 1000);
}
