import { useEffect, useState } from 'react';
import { Activity, ShieldAlert, Globe, Server, TrendingUp, Cpu, Clock } from 'lucide-react';
import { dashboardService, scanService } from '../services/api';
import './Dashboard.css';

const Dashboard = () => {
  const [stats, setStats] = useState({
    total_projects: 0,
    total_assets: 0,
    total_vulnerabilities: 0,
    risk_score: 0,
  });
  const [latestScans, setLatestScans] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsResp, scansResp] = await Promise.all([
          dashboardService.getStats(),
          scanService.getLatest(5)
        ]);
        setStats(statsResp.data);
        setLatestScans(scansResp.data.items || []);
      } catch (err) {
        console.error("Erreur Dashboard:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="dashboard-container">
      <header className="page-header">
        <h2 className="page-title">Tableau de Bord</h2>
        <p className="page-subtitle">Aperçu global de votre surface d'attaque.</p>
      </header>

      <div className="stats-grid">
        <div className="stat-card card glass">
          <div className="stat-icon-wrapper" style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)' }}>
            <Globe className="stat-icon" color="var(--accent-primary)" size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-label">Projets Actifs</span>
            <span className="stat-value">{stats.total_projects}</span>
          </div>
        </div>

        <div className="stat-card card glass">
          <div className="stat-icon-wrapper" style={{ backgroundColor: 'rgba(16, 185, 129, 0.1)' }}>
            <Server className="stat-icon" color="var(--success)" size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-label">Actifs Détectés</span>
            <span className="stat-value">{stats.total_assets}</span>
          </div>
        </div>

        <div className="stat-card card glass">
          <div className="stat-icon-wrapper" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)' }}>
            <ShieldAlert className="stat-icon" color="var(--danger)" size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-label">Vulnérabilités</span>
            <span className="stat-value">{stats.total_vulnerabilities}</span>
          </div>
        </div>

        <div className="stat-card card glass">
          <div className="stat-info">
            <span className="stat-label">Score de Risque</span>
            <div className="risk-score-wrapper">
              <span className="stat-value">{stats.risk_score.toFixed(1)}</span>
              <span className="stat-unit">/100</span>
            </div>
            <div className="progress-bar-bg">
              <div 
                className="progress-bar-fill" 
                style={{ 
                  width: `${stats.risk_score}%`, 
                  backgroundColor: stats.risk_score > 70 ? 'var(--danger)' : stats.risk_score > 30 ? 'var(--warning)' : 'var(--success)' 
                }}
              ></div>
            </div>
          </div>
        </div>
      </div>

      <div className="dashboard-sections">
        <section className="dashboard-card recent-activity card glass">
          <div className="card-header">
            <h3 className="section-title">Activité Récente</h3>
            <Activity size={18} color="var(--accent-primary)" />
          </div>
          <div className="card-body">
            {isLoading ? (
              <div className="loading-placeholder">Chargement des scans...</div>
            ) : latestScans.length === 0 ? (
              <div className="empty-state">
                <Clock size={40} color="var(--text-muted)" />
                <p>Aucun scan récent. Lancez votre premier audit dans la section Projets.</p>
              </div>
            ) : (
              <div className="scan-list">
                {latestScans.map((scan) => (
                  <div key={scan.id} className="scan-list-item">
                    <div className="scan-info">
                      <Cpu size={16} color="var(--accent-primary)" />
                      <div className="scan-details">
                        <span className="scan-project">Scan - {scan.project_name || 'Projet'}</span>
                        <span className="scan-date">{new Date(scan.started_at).toLocaleString()}</span>
                      </div>
                    </div>
                    <span className={`status-badge ${scan.status}`}>{scan.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default Dashboard;
