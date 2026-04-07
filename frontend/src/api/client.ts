import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import { useOrgStore } from '@/store/orgStore';
import { getFingerprintHash, verifyFingerprint } from '@/utils/fingerprint';

const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

// Add browser fingerprint to all requests for session binding
apiClient.interceptors.request.use(
  (config) => {
    // Add fingerprint header to help prevent session replay attacks
    // This is especially important for local testing where IP is always 127.0.0.1
    const fpHash = getFingerprintHash();
    if (fpHash) {
      config.headers['X-Browser-Fingerprint'] = fpHash;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = '/login';
    }

    const detail = error?.response?.data?.detail;
    if (
      error.response?.status === 403 &&
      typeof detail === 'string' &&
      detail.toLowerCase().includes('not a member of this organization')
    ) {
      useOrgStore.getState().clearOrg();
      if (window.location.pathname !== '/') {
        window.location.href = '/';
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
