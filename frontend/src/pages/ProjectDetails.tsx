import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Server, Globe, ShieldAlert, Activity, Play, ChevronDown, ChevronUp, Wifi, WifiOff, MapPin, Shield, AlertTriangle, ExternalLink } from 'lucide-react';
import { projectService, scanService } from '../services/api';
import './ProjectDetails.css';

const ProjectDetails = () => {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<any>(null);
  const [scans, setScans] = useState<any[]>([]);
  const [selectedScan, setSelectedScan] = useState<any>(null);
  const [assets, setAssets] = useState<any[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);
  const [findings, setFindings] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'assets' | 'osint' | 'secrets'>('assets');
  const [isLoading, setIsLoading] = useState(true);
  const [assetsLoading, setAssetsLoading] = useState(false);
  const [expandedAsset, setExpandedAsset] = useState<string | null>(null);
  const [expandedEmployee, setExpandedEmployee] = useState<string | null>(null);
  const [scanningInProgress, setScanningInProgress] = useState(false);

  // Charger le projet et ses scans
  useEffect(() => {
    const fetchData = async () => {
      if (!id) return;
      try {
        const [projectResp, scansResp] = await Promise.all([
          projectService.getOne(id),
          scanService.getByProject(id)
        ]);
        setProject(projectResp.data);
        const scanList = scansResp.data.items || [];
        setScans(scanList);
        
        // Sélectionner automatiquement le dernier scan
        if (scanList.length > 0) {
          setSelectedScan(scanList[0]);
        }
      } catch (err) {
        console.error("Erreur chargement projet:", err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [id]);

  // Charger les données (assets, osint, secrets) quand un scan est sélectionné
  useEffect(() => {
    const fetchScanData = async () => {
      if (!selectedScan) return;
      setAssetsLoading(true);
      try {
        const [assetsResp, empResp, findResp] = await Promise.all([
          scanService.getAssets(selectedScan.id).catch(() => ({ data: { items: [] } })),
          scanService.getEmployees(selectedScan.id).catch(() => ({ data: { items: [] } })),
          scanService.getFindings(selectedScan.id).catch(() => ({ data: { items: [] } }))
        ]);
        setAssets(assetsResp.data.items || []);
        setEmployees(empResp.data.items || []);
        setFindings(findResp.data.items || []);
      } catch (err) {
        console.error("Erreur chargement données du scan:", err);
      } finally {
        setAssetsLoading(false);
      }
    };
    fetchScanData();
  }, [selectedScan]);

  const handleStartScan = async () => {
    if (!id) return;
    setScanningInProgress(true);
    try {
      await scanService.start(id);
      // Rafraîchir la liste des scans après 2s
      setTimeout(async () => {
        const resp = await scanService.getByProject(id);
        const scanList = resp.data.items || [];
        setScans(scanList);
        if (scanList.length > 0) setSelectedScan(scanList[0]);
        setScanningInProgress(false);
      }, 2000);
    } catch (err: any) {
      console.error("Erreur lancement scan:", err);
      setScanningInProgress(false);
      alert(err.response?.data?.detail || "Erreur lors du lancement du scan");
    }
  };

  const toggleAssetExpand = (assetId: string) => {
    setExpandedAsset(expandedAsset === assetId ? null : assetId);
  };

  const toggleEmployeeExpand = (empId: string) => {
    setExpandedEmployee(expandedEmployee === empId ? null : empId);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'done': return 'var(--success)';
      case 'running': return 'var(--warning)';
      case 'pending': return 'var(--accent-primary)';
      case 'error': return 'var(--danger)';
      default: return 'var(--text-muted)';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'done': return 'Terminé';
      case 'running': return 'En cours';
      case 'pending': return 'En attente';
      case 'error': return 'Erreur';
      case 'partial': return 'Partiel';
      default: return status;
    }
  };

  if (isLoading) return <div className="loading-state">Chargement des détails...</div>;
  if (!project) return <div className="error-banner card">Projet introuvable.</div>;

  return (
    <div className="project-details-container">
      {/* Header */}
      <header className="details-header">
        <Link to="/projects" className="btn-back">
          <ArrowLeft size={20} />
          Retour aux projets
        </Link>
        <div className="header-info">
          <div className="header-title-row">
            <div>
              <h2 className="page-title">{project.name}</h2>
              <p className="page-subtitle">
                <Globe size={14} /> {project.root_domain}
              </p>
            </div>
            <button 
              className="btn btn-primary btn-gradient" 
              onClick={handleStartScan}
              disabled={scanningInProgress}
            >
              <Play size={16} />
              {scanningInProgress ? 'Scan en cours...' : 'Lancer un Scan'}
            </button>
          </div>
        </div>
      </header>

      {/* Stats rapides */}
      <div className="details-stats">
        <div className="mini-stat card">
          <Activity size={20} color="var(--accent-primary)" />
          <div>
            <span className="mini-stat-value">{scans.length}</span>
            <span className="mini-stat-label">Scans</span>
          </div>
        </div>
        <div className="mini-stat card">
          <Server size={20} color="var(--success)" />
          <div>
            <span className="mini-stat-value">{assets.length}</span>
            <span className="mini-stat-label">Actifs trouvés</span>
          </div>
        </div>
        <div className="mini-stat card">
          <ShieldAlert size={20} color="var(--danger)" />
          <div>
            <span className="mini-stat-value">{assets.reduce((sum: number, a: any) => sum + (a.vulns_count || 0), 0)}</span>
            <span className="mini-stat-label">Vulnérabilités</span>
          </div>
        </div>
      </div>

      {/* Sélecteur de scan */}
      {scans.length > 0 && (
        <div className="scan-selector card">
          <h3 className="section-title">Historique des Scans</h3>
          <div className="scan-tabs">
            {scans.map((scan: any) => (
              <button
                key={scan.id}
                className={`scan-tab ${selectedScan?.id === scan.id ? 'active' : ''}`}
                onClick={() => setSelectedScan(scan)}
              >
                <span className="scan-tab-status" style={{ backgroundColor: getStatusColor(scan.status) }}></span>
                <span className="scan-tab-label">{getStatusLabel(scan.status)}</span>
                <span className="scan-tab-date">
                  {new Date(scan.started_at || scan.created_at).toLocaleDateString()}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Navigation In-Scan (Onglets) */}
      {selectedScan && (
        <div className="in-scan-tabs" style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', borderBottom: '1px solid var(--glass-border)', paddingBottom: '0.5rem' }}>
          <button 
            className={`tab-btn ${activeTab === 'assets' ? 'active' : ''}`}
            onClick={() => setActiveTab('assets')}
            style={{ background: 'none', border: 'none', color: activeTab === 'assets' ? 'var(--accent-primary)' : 'var(--text-muted)', fontSize: '1rem', fontWeight: activeTab === 'assets' ? 600 : 400, borderBottom: activeTab === 'assets' ? '2px solid var(--accent-primary)' : '2px solid transparent', paddingBottom: '0.5rem', cursor: 'pointer' }}
          >
            Actifs & Services ({assets.length})
          </button>
          <button 
            className={`tab-btn ${activeTab === 'osint' ? 'active' : ''}`}
            onClick={() => setActiveTab('osint')}
            style={{ background: 'none', border: 'none', color: activeTab === 'osint' ? 'var(--accent-primary)' : 'var(--text-muted)', fontSize: '1rem', fontWeight: activeTab === 'osint' ? 600 : 400, borderBottom: activeTab === 'osint' ? '2px solid var(--accent-primary)' : '2px solid transparent', paddingBottom: '0.5rem', cursor: 'pointer' }}
          >
            OSINT & Fuites ({employees.length})
          </button>
          <button 
            className={`tab-btn ${activeTab === 'secrets' ? 'active' : ''}`}
            onClick={() => setActiveTab('secrets')}
            style={{ background: 'none', border: 'none', color: activeTab === 'secrets' ? 'var(--accent-primary)' : 'var(--text-muted)', fontSize: '1rem', fontWeight: activeTab === 'secrets' ? 600 : 400, borderBottom: activeTab === 'secrets' ? '2px solid var(--accent-primary)' : '2px solid transparent', paddingBottom: '0.5rem', cursor: 'pointer' }}
          >
            Secrets & Fichiers Sensibles ({findings.length})
          </button>
        </div>
      )}

      {/* Contenu principal en fonction de l'onglet actif */}
      {activeTab === 'assets' && (
      <div className="assets-section card">
        <h3 className="section-title">
          <Server size={18} />
          Actifs & Sous-domaines Découverts
        </h3>

        {assetsLoading ? (
          <div className="loading-placeholder">Chargement des actifs...</div>
        ) : assets.length === 0 ? (
          <div className="empty-state">
            <Server size={48} color="var(--text-muted)" />
            <p>
              {scans.length === 0
                ? "Aucun scan lancé. Cliquez sur 'Lancer un Scan' pour démarrer."
                : selectedScan?.status === 'running' || selectedScan?.status === 'pending'
                  ? "Le scan est en cours d'exécution. Les résultats apparaîtront bientôt."
                  : "Aucun actif découvert pour ce scan."
              }
            </p>
          </div>
        ) : (
          <div className="assets-list">
            {assets.map((asset: any) => (
              <div key={asset.id} className="asset-item">
                <div className="asset-header" onClick={() => toggleAssetExpand(asset.id)}>
                  <div className="asset-main-info">
                    <div className="asset-status-icon">
                      {asset.is_alive ? (
                        <Wifi size={16} color="var(--success)" />
                      ) : (
                        <WifiOff size={16} color="var(--text-muted)" />
                      )}
                    </div>
                    <div className="asset-details">
                      <span className="asset-value">{asset.value}</span>
                      <div className="asset-meta">
                        {asset.ip && <span className="asset-ip">{asset.ip}</span>}
                        {asset.country && (
                          <span className="asset-country">
                            <MapPin size={12} /> {asset.country}
                          </span>
                        )}
                        <span className="asset-type-badge">{asset.type}</span>
                      </div>
                    </div>
                  </div>

                  <div className="asset-right">
                    {asset.services_count > 0 && (
                      <span className="services-badge">
                        {asset.services_count} service{asset.services_count > 1 ? 's' : ''}
                      </span>
                    )}
                    {asset.vulns_count > 0 && (
                      <span className="vulns-badge danger">
                        <AlertTriangle size={12} /> {asset.vulns_count} CVE
                      </span>
                    )}
                    {expandedAsset === asset.id ? (
                      <ChevronUp size={18} />
                    ) : (
                      <ChevronDown size={18} />
                    )}
                  </div>
                </div>

                {/* Détails expandés */}
                {expandedAsset === asset.id && asset.services && asset.services.length > 0 && (
                  <div className="asset-expanded">
                    <table className="services-table">
                      <thead>
                        <tr>
                          <th>Port</th>
                          <th>Protocole</th>
                          <th>Produit</th>
                          <th>Version</th>
                          <th>CVE</th>
                        </tr>
                      </thead>
                      <tbody>
                        {asset.services.map((svc: any) => (
                          <tr key={svc.id}>
                            <td className="port-cell">{svc.port}</td>
                            <td>{svc.protocol}</td>
                            <td>{svc.product || '—'}</td>
                            <td>{svc.version || '—'}</td>
                            <td>
                              {svc.vulnerabilities && svc.vulnerabilities.length > 0 ? (
                                <div className="cve-list">
                                  {svc.vulnerabilities.map((v: any) => (
                                    <span key={v.id} className={`cve-tag ${v.severity || 'unknown'}`}>
                                      {v.cve_id}
                                      {v.cvss_score && ` (${v.cvss_score})`}
                                    </span>
                                  ))}
                                </div>
                              ) : (
                                <span className="no-cve">Aucune</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      )}

      {/* Onglet OSINT */}
      {activeTab === 'osint' && (
      <div className="assets-section card">
        <h3 className="section-title">Emails & Employés Découverts</h3>
        {assetsLoading ? (
          <div className="loading-placeholder">Recherche de données OSINT...</div>
        ) : employees.length === 0 ? (
          <div className="empty-state">
            <p>Aucun email ou employé trouvé pour ce domaine.</p>
          </div>
        ) : (
          <div className="assets-list">
            {employees.map((emp: any) => (
              <div key={emp.id} className="asset-item">
                <div className="asset-header" onClick={() => toggleEmployeeExpand(emp.id)}>
                  <div className="asset-main-info">
                    <span className="asset-value">{emp.email}</span>
                  </div>
                  <div className="asset-right">
                    {emp.breach_count > 0 ? (
                      <span className="vulns-badge danger">
                        <AlertTriangle size={12} /> {emp.breach_count} fuites de données
                      </span>
                    ) : (
                      <span className="services-badge" style={{ background: 'rgba(34, 197, 94, 0.1)', color: '#22c55e' }}>Sécurisé (Aucune fuite)</span>
                    )}
                    {expandedEmployee === emp.id ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  </div>
                </div>
                {expandedEmployee === emp.id && emp.breaches && emp.breaches.length > 0 && (
                  <div className="asset-expanded">
                    <table className="services-table">
                      <thead>
                        <tr>
                          <th>Service Compromis</th>
                          <th>Date de la Fuite</th>
                          <th>Données Exposées</th>
                        </tr>
                      </thead>
                      <tbody>
                        {emp.breaches.map((b: any) => (
                          <tr key={b.id}>
                            <td style={{ fontWeight: 600 }}>{b.name}</td>
                            <td>{b.date ? new Date(b.date).toLocaleDateString() : '—'}</td>
                            <td className="cve-list">
                              {b.data_types.split(',').map((type: string, idx: number) => (
                                <span key={idx} className="cve-tag unknown">{type.trim()}</span>
                              ))}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      )}

      {/* Onglet Secrets */}
      {activeTab === 'secrets' && (
      <div className="assets-section card">
        <h3 className="section-title">Secrets Exposés & Fichiers Sensibles</h3>
        {assetsLoading ? (
          <div className="loading-placeholder">Analyse des fichiers sensibles...</div>
        ) : findings.length === 0 ? (
          <div className="empty-state">
            <p>Aucun fichier sensible ou secret détecté.</p>
          </div>
        ) : (
          <div className="assets-list">
            <table className="services-table" style={{ marginTop: 0 }}>
              <thead>
                <tr>
                  <th>Fichier / Endpoint</th>
                  <th>Extrait du Contenu Sensible</th>
                </tr>
              </thead>
              <tbody>
                {findings.map((f: any) => (
                  <tr key={f.id}>
                    <td className="port-cell" style={{ color: 'var(--danger)' }}>{f.source}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '4px' }}>
                      {f.masked_value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      )}

    </div>
  );
};

export default ProjectDetails;
