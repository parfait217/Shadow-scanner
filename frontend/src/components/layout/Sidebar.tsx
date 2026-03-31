import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Globe, ShieldAlert, Cpu, LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import './Sidebar.css';

const Sidebar = () => {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <aside className="sidebar glass">
      <div className="sidebar-header">
        <div className="logo-container">
          <ShieldAlert className="logo-icon" size={32} color="var(--accent-primary)" />
          <h1 className="logo-text">Shadow<span className="text-secondary">Scanner</span></h1>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <LayoutDashboard size={20} />
          <span>Dashboard</span>
        </NavLink>
        
        <NavLink to="/projects" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Globe size={20} />
          <span>Projets</span>
        </NavLink>

        <NavLink to="/scans" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Cpu size={20} />
          <span>Scans</span>
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-divider"></div>
        <button className="nav-link btn-logout" onClick={handleLogout}>
          <LogOut size={20} />
          <span>Déconnexion</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
