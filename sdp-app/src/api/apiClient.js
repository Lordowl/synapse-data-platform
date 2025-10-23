// src/api/apiClient.js
import axios from 'axios';


const apiClient = axios.create({
    baseURL: sessionStorage.getItem('apiBaseURL') || 'http://127.0.0.1:9123/api/v1', // URL di fallback
    headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use(
    (config) => {
        const token = sessionStorage.getItem('accessToken');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        config.baseURL = sessionStorage.getItem('apiBaseURL') || 'http://127.0.0.1:9123/api/v1';  //assicura che baseURL sia sempre aggiornato
        return config;
    },
    (error) => Promise.reject(error)
);

// Funzione helper per ottenere il token
apiClient.getToken = () => {
    return sessionStorage.getItem('accessToken');
};

export default apiClient;