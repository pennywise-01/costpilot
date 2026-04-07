import { useOrgStore } from '@/store/orgStore';

export function useCurrentOrgId(): string {
  const orgId = useOrgStore((s) => s.currentOrg?.id);
  if (!orgId) {
    throw new Error('No organization selected');
  }
  return orgId;
}
