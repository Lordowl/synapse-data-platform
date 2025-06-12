import { useNavigate } from "react-router-dom";

function LogoutButton({ setIsAuthenticated }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("authToken"); // Cancella il token salvato
    setIsAuthenticated(false);
    navigate("/"); // Torna alla pagina di login
  };

  return <button onClick={handleLogout}>Logout</button>;
}

export default LogoutButton;