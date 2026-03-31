import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, MoreVertical, ExternalLink, Play, Globe, ShieldAlert } from 'lucide-react';
import { projectService, scanService } from '../services/api';
import './ProjectList.css';

const ProjectList = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newProject, setNewProject] = useState({ name: '', root_domain: '' });

  const fetchProjects = async () => {
    setIsLoading(true);
    try {
      const resp = await projectService.getAll();
      if (Array.isArray(resp.data)) {
        setProjects(resp.data);
      } else {
        console.error("Format de données invalide:", resp.data);
        setError("Erreur format de données.");
      }
    } catch (err: any) {
      console.error("Erreur projets:", err);
      setError("Impossible de charger les projets.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleStartScan = async (projectId: string) => {
    try {
      await scanService.start(projectId);
      alert("Scan démarré !");
      fetchProjects();
    } catch (err) {
      alert("Erreur lors du lancement du scan.");
    }
  };

  const handleCreateProject = async () => {
    if (!newProject.name || !newProject.root_domain) {
      setError("Veuillez remplir tous les champs.");
      return;
    }

    try {
      console.log("Démarrage création projet:", newProject);
      setLoading(true);
      setError('');
      const resp = await projectService.create(newProject);
      console.log("Réponse serveur:", resp.data);

      alert("Projet créé avec succès !");
      setShowAddModal(false);
      setNewProject({ name: '', root_domain: '' });
      await fetchProjects();
    } catch (err: any) {
      console.error("Crash création:", err);
      // Gestion améliorée des erreurs
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (detail.code) {
          setError(`${detail.message || detail.code}`);
        } else if (Array.isArray(detail)) {
          setError(detail.map(d => d.msg || d).join(', '));
        } else {
          setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
        }
      } else {
        setError("Erreur lors de la création du projet.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="projects-container">
      <header className="page-header flex-header">
        <div>
          <h2 className="page-title">Mes Projets</h2>
          <p className="page-subtitle">Gérez vos domaines et surveillez leur exposition.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>
          <Plus size={18} />
          Nouveau Projet
        </button>
      </header>

      <div className="search-bar card glass">
        <Search size={20} color="var(--text-muted)" />
        <input type="text" placeholder="Rechercher un domaine..." className="search-input" />
      </div>

      <div className="projects-grid">
        {isLoading ? (
          <div className="loading-state">Chargement...</div>
        ) : projects.length === 0 ? (
          <div className="empty-projects card">
            <p>Aucun projet trouvé. Commencez par ajouter un domaine à surveiller.</p>
          </div>
        ) : (
          projects.map((project) => (
            <div key={project.id} className="project-card card">
              <div className="project-card-header">
                <div className="project-icon">
                  <Globe size={24} color="var(--accent-primary)" />
                </div>
                <MoreVertical size={18} color="var(--text-muted)" />
              </div>
              <div className="project-card-body">
                <h3 className="project-name">{project.name}</h3>
                <p className="project-domain">{project.root_domain}</p>
              </div>
              <div className="project-card-footer">
                <div className="project-status">
                  <span className="status-dot success"></span>
                  <span className="status-label">Stable</span>
                </div>
                <div className="project-actions">
                  <button className="btn-icon" onClick={() => handleStartScan(project.id)} title="Lancer un scan">
                    <Play size={16} />
                  </button>
                  <button className="btn-icon" onClick={() => navigate(`/projects/${project.id}`)} title="Voir les détails">
                    <ExternalLink size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modal simplifiée pour l'ajout (pour la démo) */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal card">
            <h3>Ajouter un Projet</h3>
            <div className="form-group">
              <label>Nom du projet</label>
              <input
                type="text"
                placeholder="Ex: Mon Infrastructure"
                value={newProject.name}
                onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Domaine Racine</label>
              <input
                type="text"
                placeholder="Ex: entreprise.com"
                value={newProject.root_domain}
                onChange={(e) => setNewProject({ ...newProject, root_domain: e.target.value })}
              />
            </div>
            {error && <div className="error-banner card">{error}</div>}
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setShowAddModal(false)}>Annuler</button>
              <button className="btn btn-primary" onClick={handleCreateProject} disabled={loading}>
                {loading ? 'Création...' : 'Créer'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectList;
