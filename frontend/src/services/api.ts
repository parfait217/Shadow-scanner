import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Intercepteur pour ajouter le token JWT si présent
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const projectService = {
  getAll: () => api.get('/projects'),
  create: (data: { name: string; root_domain: string }) => api.post('/projects', data),
  getOne: (id: string) => api.get(`/projects/${id}`),
};

export const dashboardService = {
  getStats: () => api.get('/dashboard/stats'),
};

export const scanService = {
  getLatest: (limit = 5) => api.get('/scans', { params: { limit } }),
  start: (projectId: string) => api.post(`/projects/${projectId}/scans`),
  getResults: (scanId: string) => api.get(`/scans/${scanId}/results`),
  getByProject: (projectId: string) => api.get(`/projects/${projectId}/scans`),
  getAssets: (scanId: string) => api.get(`/scans/${scanId}/assets`),
  getVulnerabilities: (scanId: string) => api.get(`/scans/${scanId}/vulnerabilities`),
};

export default api;
