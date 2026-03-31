import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ShieldAlert, UserPlus } from 'lucide-react';
import { authService } from '../services/authService';
import './LoginPage.css'; // On réutilise les styles de login

const RegisterPage = () => {
  const [formData, setFormData] = useState({ full_name: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      await authService.register(formData);
      alert("Compte créé avec succès ! Connectez-vous maintenant.");
      navigate('/login');
    } catch (err: any) {
      setError("Erreur lors de l'inscription. Vérifiez vos informations.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card card glass">
        <div className="auth-header">
          <Link to="/" className="auth-logo">
            <ShieldAlert size={40} color="var(--accent-primary)" />
          </Link>
          <h2>Créer un compte</h2>
          <p>Rejoignez Shadow-Scanner pour sécuriser votre infrastructure.</p>
        </div>

        <form onSubmit={handleRegister} className="auth-form">
          {error && <div className="auth-error">{error}</div>}
          
          <div className="form-group">
            <label>Nom complet</label>
            <input 
              type="text" 
              required
              placeholder="ex: Jérémie Sec"
              value={formData.full_name}
              onChange={(e) => setFormData({...formData, full_name: e.target.value})}
            />
          </div>

          <div className="form-group">
            <label>Email</label>
            <input 
              type="email" 
              required
              placeholder="votre@email.com"
              value={formData.email}
              onChange={(e) => setFormData({...formData, email: e.target.value})}
            />
          </div>

          <div className="form-group">
            <label>Mot de passe</label>
            <input 
              type="password" 
              required
              placeholder="••••••••"
              value={formData.password}
              onChange={(e) => setFormData({...formData, password: e.target.value})}
            />
          </div>

          <button className="btn btn-primary btn-full" disabled={loading}>
            {loading ? 'Création...' : 'S\'inscrire'}
            {!loading && <UserPlus size={18} />}
          </button>
        </form>

        <div className="auth-footer">
          <span>Déjà un compte ?</span>
          <Link to="/login">Se connecter</Link>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
