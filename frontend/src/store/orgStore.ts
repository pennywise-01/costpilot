import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { useAuthStore } from '@/store/authStore';

export interface OrgWithRole {
  id: string;
  name: string;
  currency: string;
  pool_id: string | null;
  is_demo: boolean;
  disabled: boolean;
  created_at: string;
  role: string;
}

interface OrgState {
  currentOrg: OrgWithRole | null;
  organizations: OrgWithRole[];
  setCurrentOrg: (org: OrgWithRole) => void;
  setOrganizations: (orgs: OrgWithRole[]) => void;
  clearOrg: () => void;
}

export const useOrgStore = create<OrgState>()(
  persist(
    (set) => ({
      currentOrg: null,
      organizations: [],
      setCurrentOrg: (org) => set({ currentOrg: org }),
      setOrganizations: (orgs) => set({ organizations: orgs }),
      clearOrg: () => set({ currentOrg: null, organizations: [] }),
    }),
    {
      name: 'costpilot-org',
    }
  )
);

// Subscribe to auth changes: clear org state when user logs out or changes.
// This replaces the direct cross-store calls that were previously in authStore.
let _lastUserId: string | null = null;
useAuthStore.subscribe((state) => {
  const currentUserId = state.user?.id ?? null;
  if (_lastUserId !== null && currentUserId !== _lastUserId) {
    useOrgStore.getState().clearOrg();
  }
  _lastUserId = currentUserId;
});
