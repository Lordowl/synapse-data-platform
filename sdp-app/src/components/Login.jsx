// src/components/Login.jsx

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/apiClient";
import "./Login.css";

function Login({ setIsAuthenticated }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [apiAddress, setApiAddress] = useState("http://127.0.0.1");
  const [apiPort, setApiPort] = useState("8000");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    const baseURL = `${apiAddress}:${apiPort}/api/v1`;

    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const response = await fetch(`${baseURL}/auth/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString()
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Username o password non validi.");
      }

      const token = data.access_token;

      sessionStorage.setItem("accessToken", token);
      sessionStorage.setItem("apiBaseURL", baseURL);
      setIsAuthenticated(true);
      navigate("/");

    } catch (err) {
      console.error("Login Error:", err);
      setError(err.message || "Si è verificato un errore.");
    } finally {
      setLoading(false);
    }
  };

   return (
        <div className="login-page">
            <h2 className="title">Welcome back!</h2>
            <form onSubmit={handleSubmit}>

                {/* Sezione Connessione API */}
                <div className="api-connection">
                    <label htmlFor="apiAddress">
                        Connection
                    </label>
                    <div className="api-address-port">
                        <div className="input-group">
                            <input
                                type="text"
                                placeholder="Address"
                                id="apiAddress"
                                value={apiAddress}
                                onChange={(e) => setApiAddress(e.target.value)}
                                disabled={loading}
                            />
                        </div>
                        <div className="input-group">
                            <input
                                type="number"
                                placeholder="Port"
                                id="apiPort"
                                value={apiPort}
                                onChange={(e) => setApiPort(e.target.value)}
                                disabled={loading}
                            />
                        </div>
                    </div>
                </div>

                {/* Sezione Username/Password */}
                <label>Username</label>
                <input
                    type="text"
                    placeholder="Username"
                    id="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    disabled={loading}
                />
                <label>Password</label>
                <input
                    type="password"
                    placeholder="Password"
                    id="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={loading}
                />

                {error && <p className="error-message">{error}</p>}

                <button type="submit" disabled={loading}>
                    {loading ? 'Accesso in corso...' : 'Login'}
                </button>
            </form>
        </div>
    );
}

export default Login;