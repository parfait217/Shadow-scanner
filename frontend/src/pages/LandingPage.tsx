import { Link } from 'react-router-dom';
import Navbar from '../components/common/Navbar';
import { Shield, Target, Globe, Lock, Eye, Zap, ChevronRight, Search, Server, AlertTriangle, ArrowRight, CheckCircle, Layers, BarChart3, Users, Mail, Phone, MapPin } from 'lucide-react';
import './LandingPage.css';

const LandingPage = () => {
  return (
    <div className="landing-wrapper">
      <Navbar />

      {/* ===== HERO SECTION ===== */}
      <header className="hero-section">
        <img src="/hero-banner.png" alt="Shadow Scanner Banner" className="hero-image" />
        <div className="hero-grid-bg"></div>
        <div className="hero-glow glow-1"></div>
        <div className="hero-glow glow-2"></div>
        <div className="hero-overlay"></div>

        <div className="hero-content">
          <div className="hero-badge">
            <span className="badge-dot"></span>
            <span>Plateforme OSINT & Attack Surface Management</span>
          </div>

          <h1 className="hero-title">
            Expert en <span className="text-gradient">Cybersécurité</span> <br />
            et Reconnaissance Automatisée
          </h1>
          <p className="hero-subtitle">
            Shadow Scanner cartographie, analyse et sécurise votre surface d'attaque
            grâce à une reconnaissance OSINT automatisée. Identifiez vos failles avant les attaquants.
          </p>

          <div className="hero-actions">
            <Link to="/register" className="btn btn-primary btn-lg btn-gradient">
              Commencer l'Audit
              <ArrowRight size={18} />
            </Link>
            <Link to="/login" className="btn btn-outline btn-lg">
              Accéder au Dashboard
            </Link>
          </div>

          <div className="hero-stats">
            <div className="stat-item">
              <span className="stat-number">10K+</span>
              <span className="stat-label">ACTIFS DÉCOUVERTS</span>
            </div>
            <div className="stat-divider"></div>
            <div className="stat-item">
              <span className="stat-number">500+</span>
              <span className="stat-label">CVE SURVEILLÉES</span>
            </div>
            <div className="stat-divider"></div>
            <div className="stat-item">
              <span className="stat-number">99.9%</span>
              <span className="stat-label">DISPONIBILITÉ</span>
            </div>
          </div>
        </div>
      </header>

      {/* ===== NOS EXPERTISES (Inspiré NalaSecurity "3 pôles") ===== */}
      <section className="expertise-section" id="services">
        <div className="section-container">
          <div className="section-header">
            <span className="section-tag">Nos Expertises</span>
            <h2 className="section-title-main">Trois piliers pour votre sécurité</h2>
            <p className="section-description">
              Shadow Scanner structure son offre autour de trois pôles complémentaires pour
              répondre à tous vos besoins en matière de sécurité informatique.
            </p>
          </div>

          <div className="expertise-grid">
            <div className="expertise-card">
              <div className="expertise-icon-wrapper">
                <Search size={32} />
              </div>
              <h3>Reconnaissance OSINT</h3>
              <p>
                Découverte automatisée de sous-domaines, résolution DNS, et cartographie
                complète de votre empreinte numérique externe grâce à CRT.sh et nos algorithmes propriétaires.
              </p>
              <Link to="/register" className="card-link">
                En savoir plus <ArrowRight size={16} />
              </Link>
            </div>

            <div className="expertise-card featured">
              <div className="expertise-icon-wrapper">
                <Target size={32} />
              </div>
              <h3>Scan de Vulnérabilités</h3>
              <p>
                Détection précise des services exposés, identification des ports ouverts
                et corrélation automatique avec la base CVE pour évaluer votre niveau de risque.
              </p>
              <Link to="/register" className="card-link">
                En savoir plus <ArrowRight size={16} />
              </Link>
            </div>

            <div className="expertise-card">
              <div className="expertise-icon-wrapper">
                <BarChart3 size={32} />
              </div>
              <h3>Monitoring Continu</h3>
              <p>
                Surveillance en temps réel de votre surface d'attaque avec alertes
                intelligentes et rapports détaillés pour une posture de sécurité proactive.
              </p>
              <Link to="/register" className="card-link">
                En savoir plus <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ===== COMMENT ÇA MARCHE ===== */}
      <section className="how-it-works-section">
        <div className="section-container">
          <div className="section-header">
            <span className="section-tag">Comment ça marche</span>
            <h2 className="section-title-main">En 3 étapes simples</h2>
          </div>

          <div className="steps-grid">
            <div className="step-card">
              <div className="step-number">01</div>
              <Layers size={28} color="var(--accent-primary)" />
              <h3>Ajoutez votre domaine</h3>
              <p>Renseignez le nom de domaine à auditer. Notre moteur prend le relais immédiatement.</p>
            </div>

            <div className="step-connector">
              <ChevronRight size={24} />
            </div>

            <div className="step-card">
              <div className="step-number">02</div>
              <Server size={28} color="var(--accent-primary)" />
              <h3>Scan automatisé</h3>
              <p>DNS, ports, services, CVE — tout est analysé en parallèle par nos workers asynchrones.</p>
            </div>

            <div className="step-connector">
              <ChevronRight size={24} />
            </div>

            <div className="step-card">
              <div className="step-number">03</div>
              <AlertTriangle size={28} color="var(--accent-primary)" />
              <h3>Rapport de risques</h3>
              <p>Recevez un tableau de bord avec le score de risque, les actifs et les vulnérabilités détectées.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== FONCTIONNALITÉS DÉTAILLÉES ===== */}
      <section className="features-section" id="features">
        <div className="section-container">
          <div className="section-header">
            <span className="section-tag">Fonctionnalités</span>
            <h2 className="section-title-main">Capacités OSINT Avancées</h2>
            <p className="section-description">
              Une suite complète d'outils pour cartographier et protéger votre infrastructure.
            </p>
          </div>

          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon">
                <Globe size={24} />
              </div>
              <h3>Intelligence DNS</h3>
              <p>Énumération complète de sous-domaines et résolution IP furtive. Cartographiez toute votre empreinte externe.</p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">
                <Target size={24} />
              </div>
              <h3>Fingerprinting de Services</h3>
              <p>Détection précise des services et gestion des ports ouverts. Identifiez les applications en exécution.</p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">
                <Eye size={24} />
              </div>
              <h3>Monitoring CVE</h3>
              <p>Corrélation instantanée des vulnérabilités connues sur vos actifs. Alertes en temps réel.</p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">
                <Shield size={24} />
              </div>
              <h3>Détection de Fuites</h3>
              <p>Surveillance des identifiants exposés et des fuites de données. Protégez votre identité numérique.</p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">
                <Lock size={24} />
              </div>
              <h3>Scan de Secrets</h3>
              <p>Détectez les clés API, tokens et données sensibles exposées dans vos dépôts et configurations.</p>
            </div>

            <div className="feature-card">
              <div className="feature-icon">
                <Zap size={24} />
              </div>
              <h3>Score de Risque</h3>
              <p>Évaluation automatisée avec scoring basé sur le CVSS. Priorisez vos actions de remédiation.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ===== À PROPOS ===== */}
      <section className="about-section" id="about">
        <div className="section-container">
          <div className="about-grid">
            <div className="about-content">
              <span className="section-tag">À propos</span>
              <h2 className="section-title-main">Pourquoi Shadow Scanner ?</h2>
              <p>
                Dans un monde où les cybermenaces évoluent à une vitesse fulgurante,
                connaître sa surface d'attaque est devenu un impératif stratégique.
                Shadow Scanner est né de cette nécessité.
              </p>
              <ul className="about-checklist">
                <li>
                  <CheckCircle size={20} color="var(--success)" />
                  <span>Reconnaissance automatisée et non-intrusive</span>
                </li>
                <li>
                  <CheckCircle size={20} color="var(--success)" />
                  <span>Intelligence multi-sources (CRT.sh, Shodan, NVD)</span>
                </li>
                <li>
                  <CheckCircle size={20} color="var(--success)" />
                  <span>Dashboard temps réel avec scoring de risque</span>
                </li>
                <li>
                  <CheckCircle size={20} color="var(--success)" />
                  <span>Architecture asynchrone haute performance</span>
                </li>
                <li>
                  <CheckCircle size={20} color="var(--success)" />
                  <span>API RESTful pour intégration dans vos workflows</span>
                </li>
              </ul>
            </div>

            <div className="about-visual">
              <div className="about-stats-card glass">
                <div className="about-stat">
                  <span className="about-stat-number">90%</span>
                  <span className="about-stat-label">Précision de Détection</span>
                </div>
                <div className="about-stat-divider"></div>
                <div className="about-stat">
                  <span className="about-stat-number">95%</span>
                  <span className="about-stat-label">Couverture OSINT</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== CTA FINAL ===== */}
      <section className="cta-section">
        <div className="cta-content">
          <h2>Prêt à sécuriser votre surface d'attaque ?</h2>
          <p>Lancez votre premier audit en quelques minutes. Aucune carte bancaire requise.</p>
          <div className="cta-actions">
            <Link to="/register" className="btn btn-primary btn-lg btn-gradient">
              Démarrer Gratuitement
              <ArrowRight size={18} />
            </Link>
            <Link to="/login" className="btn btn-outline btn-lg">
              Se Connecter
            </Link>
          </div>
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="landing-footer">
        <div className="footer-container">
          <div className="footer-grid">
            <div className="footer-brand">
              <div className="footer-logo">
                <Shield size={28} color="var(--accent-primary)" />
                <span>Shadow Scanner</span>
              </div>
              <p>Plateforme OSINT automatisée pour la gestion de surface d'attaque et la cybersécurité proactive.</p>
            </div>

            <div className="footer-links">
              <h4>Plateforme</h4>
              <ul>
                <li><Link to="/register">Commencer</Link></li>
                <li><Link to="/login">Connexion</Link></li>
                <li><a href="#features">Fonctionnalités</a></li>
                <li><a href="#services">Services</a></li>
              </ul>
            </div>

            <div className="footer-links">
              <h4>Ressources</h4>
              <ul>
                <li><a href="#about">À propos</a></li>
                <li><a href="#">Documentation</a></li>
                <li><a href="#">API Reference</a></li>
                <li><a href="#">Blog</a></li>
              </ul>
            </div>

            <div className="footer-contact">
              <h4>Contact</h4>
              <ul>
                <li><Mail size={16} /> <span>contact@shadow-scanner.io</span></li>
                <li><MapPin size={16} /> <span>Douala, Cameroun</span></li>
              </ul>
            </div>
          </div>

          <div className="footer-bottom">
            <p>© 2026 Shadow Scanner. Tous droits réservés. Construit pour les professionnels de la sécurité.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
