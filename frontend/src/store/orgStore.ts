import { create } from 'zustand';
import { persist } from 'zustand/middleware';

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
