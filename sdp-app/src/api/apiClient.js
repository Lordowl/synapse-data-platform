// src/api/apiClient.js
import axios from 'axios';

const API_URL = 'http://127.0.0.1:8001/api/v1';

const apiClient = axios.create({
    baseURL: API_URL,
    headers: { 'Content-Type': 'application/json' },
});

// L'interceptor che aggiunge automaticamente il token JWT ad ogni richiesta
apiClient.interceptors.request.use(
    (config) => {
        const token = sessionStorage.getItem('accessToken');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Funzione helper per ottenere il token
apiClient.getToken = () => {
    return sessionStorage.getItem('accessToken');
};

export default apiClient;