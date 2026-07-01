import { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Server, Globe, ShieldAlert, Activity, Play, ChevronDown, ChevronUp,
  Wifi, WifiOff, MapPin, AlertTriangle, Shield, Lock, Eye, Zap, Database,
  Code, Cloud, FileText, Key, Search, RefreshCw
} from 'lucide-react';
import { projectService, scanService } from '../services/api';
import './ProjectDetails.css';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const getRiskColor = (score: number) => {
  if (score >= 80) return '#22c55e';
  if (score >= 60) return '#eab308';
  if (score >= 40) return '#f97316';
  return '#ef4444';
};

const getRiskLabel = (score: number) => {
  if (score >= 80) return 'Faible';
  if (score >= 60) return 'Modéré';
  if (score >= 40) return 'Élevé';
  return 'Critique';
};

const getSeverityColor = (sev: string) => {
  switch ((sev || '').toUpperCase()) {
    case 'CRITICAL': return { bg: 'rgba(220,38,38,0.15)', color: '#ef4444' };
    case 'HIGH':     return { bg: 'rgba(249,115,22,0.15)', color: '#f97316' };
    case 'MEDIUM':   return { bg: 'rgba(234,179,8,0.15)',  color: '#eab308' };
    case 'LOW':      return { bg: 'rgba(34,197,94,0.15)',  color: '#22c55e' };
    default:         return { bg: 'rgba(148,163,184,0.1)', color: '#94a3b8' };
  }
};

const getTechIcon = (category: string) => {
  switch (category) {
    case 'Web Server': return <Server size={10} />;
    case 'CDN':        return <Cloud size={10} />;
    case 'CMS':        return <FileText size={10} />;
    case 'Framework':  return <Code size={10} />;
    case 'JS Framework': return <Zap size={10} />;
    case 'Database Admin': return <Database size={10} />;
    case 'API Documentation': return <Eye size={10} />;
    case 'Authentication': return <Lock size={10} />;
    default:           return <Globe size={10} />;
  }
};

const getTechColor = (category: string) => {
  const map: Record<string, string> = {
    'Web Server':     '#3b82f6',
    'CDN':            '#8b5cf6',
    'CMS':            '#f97316',
    'Framework':      '#06b6d4',
    'JS Framework':   '#f59e0b',
    'Database Admin': '#ef4444',
    'API Documentation': '#10b981',
    'Authentication': '#ec4899',
    'Cloud':          '#6366f1',
    'Search Engine':  '#14b8a6',
  };
  return map[category] || '#94a3b8';
};

const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed': return 'var(--success)';
    case 'running':   return 'var(--warning)';
    case 'pending':   return 'var(--accent-primary)';
    case 'error':     return 'var(--danger)';
    default:          return 'var(--text-muted)';
  }
};

const getStatusLabel = (status: string) => {
  switch (status) {
    case 'completed': return 'Terminé';
    case 'running':   return 'En cours';
    case 'pending':   return 'En attente';
    case 'error':     return 'Erreur';
    case 'partial':   return 'Partiel';
    default:          return status;
  }
};

// ─── Component ────────────────────────────────────────────────────────────────

const ProjectDetails = () => {
  const { id } = useParams<{ id: string }>();
  const [project, setProject]           = useState<any>(null);
  const [scans, setScans]               = useState<any[]>([]);
  const [selectedScan, setSelectedScan] = useState<any>(null);
  const [assets, setAssets]             = useState<any[]>([]);
  const [employees, setEmployees]       = useState<any[]>([]);
  const [findings, setFindings]         = useState<any[]>([]);
  const [activeTab, setActiveTab]       = useState<'assets' | 'osint' | 'secrets'>('assets');
  const [isLoading, setIsLoading]       = useState(true);
  const [assetsLoading, setAssetsLoading] = useState(false);
  const [expandedAsset, setExpandedAsset]       = useState<string | null>(null);
  const [expandedEmployee, setExpandedEmployee] = useState<string | null>(null);
  const [scanningInProgress, setScanningInProgress] = useState(false);
  const [isLive, setIsLive]             = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [lastRefresh, setLastRefresh]   = useState<Date | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // ── WebSocket ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!id) return;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//localhost:8000/api/v1/ws/${id}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen  = () => setIsLive(true);
    ws.onclose = () => setIsLive(false);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === 'REFRESH') {
          setRefreshTrigger(prev => prev + 1);
          setLastRefresh(new Date());
        }
      } catch { /* ignore */ }
    };

    return () => ws.close();
  }, [id]);

  // ── Fetch projet & scans ───────────────────────────────────────────────────
  useEffect(() => {
    const fetchData = async () => {
      if (!id) return;
      try {
        const [projectResp, scansResp] = await Promise.all([
          projectService.getOne(id),
          scanService.getByProject(id),
        ]);
        setProject(projectResp.data);
        const scanList = scansResp.data.items || [];
        setScans(scanList);
        if (scanList.length > 0) setSelectedScan(scanList[0]);
      } catch (err) {
        console.error('Erreur chargement projet:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [id, refreshTrigger]);

  // ── Fetch données du scan ──────────────────────────────────────────────────
  useEffect(() => {
    const fetchScanData = async () => {
      if (!selectedScan) return;
      setAssetsLoading(true);
      try {
        const [assetsResp, empResp, findResp] = await Promise.all([
          scanService.getAssets(selectedScan.id).catch(() => ({ data: { items: [] } })),
          scanService.getEmployees(selectedScan.id).catch(() => ({ data: { items: [] } })),
          scanService.getFindings(selectedScan.id).catch(() => ({ data: { items: [] } })),
        ]);
        setAssets(assetsResp.data.items || []);
        setEmployees(empResp.data.items || []);
        setFindings(findResp.data.items || []);
      } catch (err) {
        console.error('Erreur chargement données du scan:', err);
      } finally {
        setAssetsLoading(false);
      }
    };
    fetchScanData();
  }, [selectedScan?.id, refreshTrigger]);

  // ── Actions ────────────────────────────────────────────────────────────────
  const handleStartScan = async () => {
    if (!id) return;
    setScanningInProgress(true);
    try {
      await scanService.start(id);
      setTimeout(async () => {
        const resp = await scanService.getByProject(id);
        const scanList = resp.data.items || [];
        setScans(scanList);
        if (scanList.length > 0) setSelectedScan(scanList[0]);
        setScanningInProgress(false);
      }, 2000);
    } catch (err: any) {
      setScanningInProgress(false);
      alert(err.response?.data?.detail || 'Erreur lors du lancement du scan');
    }
  };

  // ── Computed ───────────────────────────────────────────────────────────────
  const totalVulns  = assets.reduce((s: number, a: any) => s + (a.vulns_count || 0), 0);
  const criticalCount = assets.reduce((s: number, a: any) =>
    s + (a.services || []).reduce((ss: number, svc: any) =>
      ss + (svc.vulnerabilities || []).filter((v: any) =>
        ['CRITICAL', 'HIGH'].includes((v.severity || '').toUpperCase())
      ).length, 0), 0);
  const riskScore   = selectedScan?.risk_score ?? 100;
  const riskColor   = getRiskColor(riskScore);
  const aliveAssets = assets.filter((a: any) => a.is_alive).length;
  const criticalFindings = findings.filter((f: any) => f.type === 'critical').length;

  if (isLoading) return <div className="loading-state">Chargement des détails...</div>;
  if (!project)  return <div className="error-banner card">Projet introuvable.</div>;

  return (
    <div className="project-details-container">

      {/* ── Header ── */}
      <header className="details-header">
        <Link to="/projects" className="btn-back">
          <ArrowLeft size={20} /> Retour aux projets
        </Link>
        <div className="header-info">
          <div className="header-title-row">
            <div>
              <h2 className="page-title">
                {project.name}
                {isLive && (
                  <span className="live-badge">
                    <span className="live-dot" />
                    LIVE
                  </span>
                )}
              </h2>
              <p className="page-subtitle">
                <Globe size={14} /> {project.root_domain}
                {lastRefresh && (
                  <span className="last-refresh">
                    <RefreshCw size={10} /> Mis à jour {lastRefresh.toLocaleTimeString()}
                  </span>
                )}
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

      {/* ── Stats + Risk Score ── */}
      <div className="details-stats">
        {/* Risk Score Gauge */}
        <div className="mini-stat card risk-gauge-card">
          <div className="risk-gauge-wrap">
            <svg viewBox="0 0 100 60" className="risk-svg">
              <path d="M 10 55 A 40 40 0 0 1 90 55" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" strokeLinecap="round" />
              <path
                d="M 10 55 A 40 40 0 0 1 90 55"
                fill="none"
                stroke={riskColor}
                strokeWidth="10"
                strokeLinecap="round"
                strokeDasharray={`${(riskScore / 100) * 125.6} 125.6`}
                style={{ filter: `drop-shadow(0 0 6px ${riskColor})` }}
              />
              <text x="50" y="52" textAnchor="middle" fill={riskColor} fontSize="18" fontWeight="bold">{riskScore}</text>
            </svg>
          </div>
          <div>
            <span className="mini-stat-label">Score de Risque</span>
            <span className="mini-stat-value" style={{ color: riskColor, fontSize: '1rem' }}>
              {getRiskLabel(riskScore)}
            </span>
          </div>
        </div>

        <div className="mini-stat card">
          <Server size={20} color="var(--success)" />
          <div>
            <span className="mini-stat-value">{aliveAssets}<span style={{color:'var(--text-muted)',fontSize:'0.8rem'}}>/{assets.length}</span></span>
            <span className="mini-stat-label">Actifs en ligne</span>
          </div>
        </div>

        <div className="mini-stat card">
          <ShieldAlert size={20} color={criticalCount > 0 ? 'var(--danger)' : 'var(--text-muted)'} />
          <div>
            <span className="mini-stat-value" style={{ color: criticalCount > 0 ? 'var(--danger)' : undefined }}>
              {criticalCount}
              <span style={{color:'var(--text-muted)',fontSize:'0.8rem'}}>/{totalVulns}</span>
            </span>
            <span className="mini-stat-label">CVE Critiques/Total</span>
          </div>
        </div>

        <div className="mini-stat card">
          <Key size={20} color={criticalFindings > 0 ? '#f97316' : 'var(--text-muted)'} />
          <div>
            <span className="mini-stat-value" style={{ color: criticalFindings > 0 ? '#f97316' : undefined }}>
              {criticalFindings}
            </span>
            <span className="mini-stat-label">Secrets Exposés</span>
          </div>
        </div>

        <div className="mini-stat card">
          <Search size={20} color="var(--accent-primary)" />
          <div>
            <span className="mini-stat-value">{employees.length}</span>
            <span className="mini-stat-label">Emails OSINT</span>
          </div>
        </div>
      </div>

      {/* ── Historique scans ── */}
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
                <span className="scan-tab-status" style={{ backgroundColor: getStatusColor(scan.status) }} />
                <span className="scan-tab-label">{getStatusLabel(scan.status)}</span>
                {scan.risk_score != null && (
                  <span className="scan-risk-pill" style={{ color: getRiskColor(scan.risk_score), borderColor: getRiskColor(scan.risk_score) }}>
                    {scan.risk_score}/100
                  </span>
                )}
                <span className="scan-tab-date">
                  {new Date(scan.started_at || scan.created_at).toLocaleDateString()}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Onglets ── */}
      {selectedScan && (
        <div className="in-scan-tabs">
          {([
            { key: 'assets',  label: `Actifs & Services`,           count: assets.length },
            { key: 'osint',   label: `OSINT & Fuites`,              count: employees.length },
            { key: 'secrets', label: `Secrets & Fichiers Sensibles`, count: findings.length },
          ] as const).map(tab => (
            <button
              key={tab.key}
              className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
              <span className={`tab-count ${activeTab === tab.key ? 'active' : ''}`}>{tab.count}</span>
            </button>
          ))}
        </div>
      )}

      {/* ── Onglet Assets ── */}
      {activeTab === 'assets' && (
        <div className="assets-section card">
          <h3 className="section-title"><Server size={18} /> Actifs & Sous-domaines Découverts</h3>
          {assetsLoading ? (
            <div className="loading-placeholder">
              <div className="scan-spinner" />
              Analyse en cours...
            </div>
          ) : assets.length === 0 ? (
            <div className="empty-state">
              <Server size={48} color="var(--text-muted)" />
              <p>{scans.length === 0 ? "Aucun scan lancé." : "Aucun actif découvert."}</p>
            </div>
          ) : (
            <div className="assets-list">
              {assets.map((asset: any) => {
                const assetVulns = (asset.services || [])
                  .flatMap((s: any) => s.vulnerabilities || []);
                const hasCritical = assetVulns.some((v: any) =>
                  ['CRITICAL', 'HIGH'].includes((v.severity || '').toUpperCase()));
                // Collect technologies across all services
                const allTechs: any[] = [];
                (asset.services || []).forEach((svc: any) => {
                  if (svc.product && svc.product !== 'Unknown') {
                    allTechs.push({ name: svc.product, category: 'Web Server' });
                  }
                });

                return (
                  <div key={asset.id} className={`asset-item ${hasCritical ? 'asset-item-critical' : ''}`}>
                    <div className="asset-header" onClick={() => setExpandedAsset(expandedAsset === asset.id ? null : asset.id)}>
                      <div className="asset-main-info">
                        <div className="asset-status-icon">
                          {asset.is_alive
                            ? <Wifi size={16} color="var(--success)" />
                            : <WifiOff size={16} color="var(--text-muted)" />}
                        </div>
                        <div className="asset-details">
                          <span className="asset-value">{asset.value}</span>
                          <div className="asset-meta">
                            {asset.ip && <span className="asset-ip">{asset.ip}</span>}
                            {asset.country && (
                              <span className="asset-country"><MapPin size={12} /> {asset.country}</span>
                            )}
                            {asset.isp && (
                              <span className="asset-isp">{asset.isp}</span>
                            )}
                            <span className="asset-type-badge">{asset.type}</span>
                            {/* Tech badges from Shodan ASN field */}
                            {asset.asn && asset.asn.startsWith('Shodan ports:') && (
                              <span className="asset-shodan-badge">
                                <Zap size={9} /> Shodan
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="asset-right">
                        {asset.services_count > 0 && (
                          <span className="services-badge">
                            {asset.services_count} port{asset.services_count > 1 ? 's' : ''}
                          </span>
                        )}
                        {asset.vulns_count > 0 && (
                          <span className={`vulns-badge ${hasCritical ? 'danger' : 'warning'}`}>
                            <AlertTriangle size={12} /> {asset.vulns_count} CVE
                          </span>
                        )}
                        {expandedAsset === asset.id ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                      </div>
                    </div>

                    {/* Expanded Services */}
                    {expandedAsset === asset.id && asset.services && asset.services.length > 0 && (
                      <div className="asset-expanded">
                        <table className="services-table">
                          <thead>
                            <tr>
                              <th>Port</th>
                              <th>Technologie</th>
                              <th>Version / Info</th>
                              <th>Vulnérabilités CVE</th>
                            </tr>
                          </thead>
                          <tbody>
                            {asset.services.map((svc: any) => (
                              <tr key={svc.id}>
                                <td className="port-cell">{svc.port}</td>
                                <td>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <span>{svc.product || '—'}</span>
                                  </div>
                                </td>
                                <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                                  {svc.version || svc.banner || '—'}
                                </td>
                                <td>
                                  {svc.vulnerabilities && svc.vulnerabilities.length > 0 ? (
                                    <div className="cve-list">
                                      {svc.vulnerabilities.map((v: any) => {
                                        const sc = getSeverityColor(v.severity);
                                        return (
                                          <span
                                            key={v.id}
                                            className="cve-tag"
                                            style={{ background: sc.bg, color: sc.color }}
                                            title={`CVSS: ${v.cvss_score}`}
                                          >
                                            {v.cve_id}
                                            {v.cvss_score > 0 && (
                                              <span style={{ opacity: 0.7, marginLeft: '3px' }}>
                                                {v.cvss_score.toFixed(1)}
                                              </span>
                                            )}
                                          </span>
                                        );
                                      })}
                                    </div>
                                  ) : (
                                    <span className="no-cve">✓ Aucune connue</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Onglet OSINT ── */}
      {activeTab === 'osint' && (
        <div className="assets-section card">
          <h3 className="section-title">
            <Search size={18} /> Emails & Employés Découverts
            <span className="osint-source-info">via PGP · RDAP · security.txt · DuckDuckGo</span>
          </h3>
          {assetsLoading ? (
            <div className="loading-placeholder"><div className="scan-spinner" /> Collecte OSINT...</div>
          ) : employees.length === 0 ? (
            <div className="empty-state"><p>Aucun email trouvé pour ce domaine.</p></div>
          ) : (
            <div className="assets-list">
              {employees.map((emp: any) => (
                <div key={emp.id} className="asset-item">
                  <div className="asset-header" onClick={() => setExpandedEmployee(expandedEmployee === emp.id ? null : emp.id)}>
                    <div className="asset-main-info">
                      <div className="osint-avatar">
                        {emp.email.charAt(0).toUpperCase()}
                      </div>
                      <span className="asset-value">{emp.email}</span>
                    </div>
                    <div className="asset-right">
                      {emp.breach_count > 0 ? (
                        <span className="vulns-badge danger">
                          <AlertTriangle size={12} /> {emp.breach_count} fuite{emp.breach_count > 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span className="secure-badge"><Shield size={12} /> Sécurisé</span>
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
                              <td style={{ fontWeight: 600, color: 'var(--danger)' }}>{b.name}</td>
                              <td>{b.date ? new Date(b.date).toLocaleDateString() : '—'}</td>
                              <td className="cve-list">
                                {b.data_types.split(',').map((type: string, idx: number) => (
                                  <span key={idx} className="cve-tag" style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}>
                                    {type.trim()}
                                  </span>
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

      {/* ── Onglet Secrets ── */}
      {activeTab === 'secrets' && (
        <div className="assets-section card">
          <h3 className="section-title">
            <Key size={18} /> Secrets Exposés & Fichiers Sensibles
            <span className="osint-source-info">{findings.length} endpoint{findings.length > 1 ? 's' : ''} détecté{findings.length > 1 ? 's' : ''}</span>
          </h3>
          {assetsLoading ? (
            <div className="loading-placeholder"><div className="scan-spinner" /> Fuzzing 200+ endpoints...</div>
          ) : findings.length === 0 ? (
            <div className="empty-state">
              <Shield size={48} color="var(--success)" />
              <p style={{ color: 'var(--success)' }}>✓ Aucun fichier sensible ni secret détecté.</p>
            </div>
          ) : (
            <div className="assets-list">
              {findings.map((f: any) => {
                const isCritical = f.type === 'critical';
                return (
                  <div key={f.id} className={`asset-item ${isCritical ? 'asset-item-critical' : ''}`}>
                    <div className="asset-header" style={{ cursor: 'default' }}>
                      <div className="asset-main-info" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '4px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          {isCritical
                            ? <AlertTriangle size={16} color="var(--danger)" />
                            : <Eye size={16} color="var(--warning)" />}
                          <span className="asset-value" style={{ color: isCritical ? 'var(--danger)' : 'var(--warning)' }}>
                            {f.source}
                          </span>
                          <span className="cve-tag" style={getSeverityColor(isCritical ? 'CRITICAL' : 'MEDIUM')}>
                            {isCritical ? '🔑 SECRET' : '⚠ ACCÈS RESTREINT'}
                          </span>
                        </div>
                        {f.masked_value && (
                          <code className="secret-snippet">{f.masked_value}</code>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

    </div>
  );
};

export default ProjectDetails;
