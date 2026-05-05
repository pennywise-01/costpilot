import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/api/auth';

interface AuthState {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  setUser: (user: User) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      setAuth: (_token, user) => {
        set({ token: null, user });
      },
      setUser: (user) => {
        set({ user });
      },
      logout: () => {
        set({ token: null, user: null });
      },
      isAuthenticated: () => !!get().user,
    }),
    {
      name: 'costpilot-auth',
      // Only persist user info - the JWT lives in an httpOnly cookie
      partialize: (state) => ({ user: state.user }),
    }
  )
);
