import apiClient from './client';

export interface LoginData {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  display_name: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  verified: boolean;
  role: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export const authApi = {
  login: (data: LoginData) =>
    apiClient.post<TokenResponse>('/auth/login', data),

  register: (data: RegisterData) =>
    apiClient.post<TokenResponse>('/auth/register', data),

  getMe: () =>
    apiClient.get<User>('/auth/me'),

  updateMe: (data: { display_name?: string; current_password?: string; password?: string }) =>
    apiClient.patch<User>('/auth/me', data),

  logout: () =>
    apiClient.post('/auth/logout'),
};
