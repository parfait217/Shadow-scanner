import api from './api';

export interface AuthResponse {
  tokens: {
    access_token: string;
    refresh_token: string;
    token_type: string;
  };
  user: {
    id: string;
    username: string;
    role: string;
  };
}

export const authService = {
  login: async (credentials: any): Promise<AuthResponse> => {
    // Note: l'API backend attend username/password en form-data ou JSON
    const params = new URLSearchParams();
    params.append('username', credentials.username);
    params.append('password', credentials.password);
    
    const resp = await api.post('/auth/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    return resp.data;
  },
  
  register: async (data: any) => {
    const resp = await api.post('/auth/register', data);
    return resp.data;
  },
  
  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }
};
