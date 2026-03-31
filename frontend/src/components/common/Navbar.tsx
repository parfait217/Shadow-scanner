import { Link } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import './Navbar.css';

const Navbar = () => {
  return (
    <nav className="navbar glass">
      <div className="navbar-container">
        <Link to="/" className="navbar-logo">
          <ShieldAlert size={28} color="var(--accent-primary)" />
          <span>Shadow<span className="text-secondary">Scanner</span></span>
        </Link>
        
        <div className="navbar-links">
          <a href="#services" className="nav-item">Services</a>
          <a href="#features" className="nav-item">Fonctionnalités</a>
          <a href="#about" className="nav-item">À propos</a>
          <Link to="/login" className="nav-item">Connexion</Link>
          <Link to="/register" className="btn btn-primary btn-sm">S'inscrire</Link>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
