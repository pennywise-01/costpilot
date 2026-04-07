import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type {
  User,
  UserDetail,
  UserFilters,
  PaginatedUsers,
  UserInviteRequest,
  UserInviteResponse,
  BulkInviteResponse,
  UserUpdateRequest,
  UserStatusUpdateRequest,
  UserRoleUpdateRequest,
  ActivityLogEntry,
  ActivityLogFilter,
  EffectivePermissionsResponse,
} from '../api/userManagement';
import { userManagementApi } from '../api/userManagement';

interface UserState {
  // Data
  users: User[];
  selectedUser: UserDetail | null;
  pagination: {
    total: number;
    page: number;
    limit: number;
    pages: number;
  };
  filters: UserFilters;
  activityLog: ActivityLogEntry[];
  activityPagination: {
    total: number;
    page: number;
    limit: number;
    pages: number;
  };
  effectivePermissions: EffectivePermissionsResponse | null;
  
  // UI State
  loading: boolean;
  error: string | null;
  inviteModalOpen: boolean;
  userDetailModalOpen: boolean;
  selectedUserId: string | null;
  
  // Actions
  setFilters: (filters: Partial<UserFilters>) => void;
  fetchUsers: (orgId: string) => Promise<void>;
  fetchUserDetail: (orgId: string, userId: string) => Promise<void>;
  updateUser: (orgId: string, userId: string, data: UserUpdateRequest) => Promise<void>;
  suspendUser: (orgId: string, userId: string, reason?: string) => Promise<void>;
  activateUser: (orgId: string, userId: string) => Promise<void>;
  removeUser: (orgId: string, userId: string) => Promise<void>;
  inviteUser: (orgId: string, data: UserInviteRequest) => Promise<UserInviteResponse>;
  inviteBulk: (orgId: string, invitations: UserInviteRequest[]) => Promise<BulkInviteResponse>;
  updateUserRoles: (orgId: string, userId: string, data: UserRoleUpdateRequest) => Promise<void>;
  fetchActivityLog: (orgId: string, userId: string, filters?: ActivityLogFilter) => Promise<void>;
  fetchEffectivePermissions: (orgId: string, userId: string) => Promise<void>;
  
  // UI Actions
  setInviteModalOpen: (open: boolean) => void;
  setUserDetailModalOpen: (open: boolean) => void;
  selectUser: (userId: string | null) => void;
  clearError: () => void;
}

export const useUserStore = create<UserState>()(
  devtools(
    (set, get) => ({
      // Initial State
      users: [],
      selectedUser: null,
      pagination: {
        total: 0,
        page: 1,
        limit: 20,
        pages: 0,
      },
      filters: {
        page: 1,
        limit: 20,
        sort_by: 'created_at',
        sort_order: 'desc',
      },
      activityLog: [],
      activityPagination: {
        total: 0,
        page: 1,
        limit: 20,
        pages: 0,
      },
      effectivePermissions: null,
      loading: false,
      error: null,
      inviteModalOpen: false,
      userDetailModalOpen: false,
      selectedUserId: null,

      // Actions
      setFilters: (filters) => {
        set({ filters: { ...get().filters, ...filters, page: 1 } });
      },

      fetchUsers: async (orgId) => {
        set({ loading: true, error: null });
        try {
          const { filters } = get();
          const response = await userManagementApi.listUsers(orgId, filters);
          set({
            users: response.data.items,
            pagination: {
              total: response.data.total,
              page: response.data.page,
              limit: response.data.limit,
              pages: response.data.pages,
            },
            loading: false,
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Failed to fetch users',
            loading: false,
          });
        }
      },

      fetchUserDetail: async (orgId, userId) => {
        set({ loading: true, error: null });
        try {
          const response = await userManagementApi.getUser(orgId, userId);
          set({
            selectedUser: response.data,
            loading: false,
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Failed to fetch user details',
            loading: false,
          });
        }
      },

      updateUser: async (orgId, userId, data) => {
        set({ loading: true, error: null });
        try {
          await userManagementApi.updateUser(orgId, userId, data);
          // Refresh user list and detail
          await get().fetchUsers(orgId);
          if (get().selectedUser?.id === userId) {
            await get().fetchUserDetail(orgId, userId);
          }
          set({ loading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Failed to update user',
            loading: false,
          });
          throw error;
        }
      },

      suspendUser: async (orgId, userId, reason) => {
        set({ loading: true, error: null });
        try {
          await userManagementApi.suspendUser(orgId, userId, { status: 'suspended', reason });
          await get().fetchUsers(orgId);
          if (get().selectedUser?.id === userId) {
            await get().fetchUserDetail(orgId, userId);
          }
          set({ loading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Failed to suspend user',
            loading: false,
          });
          throw error;
        }
      },

      activateUser: async (orgId, userId) => {
        set({ loading: true, error: null });
        try {
          await userManagementApi.activateUser(orgId, userId);
          await get().fetchUsers(orgId);
          if (get().selectedUser?.id === userId) {
            await get().fetchUserDetail(orgId, userId);
          }
          set({ loading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Failed to activate user',
            loading: false,
          });
          throw error;
        }
      },

      removeUser: async (orgId, userId) => {
        set({ loading: true, error: null });
        try {
          await userManagementApi.removeUser(orgId, userId);
          await get().fetchUsers(orgId);
          set({
            selectedUser: null,
            userDetailModalOpen: false,
            loading: false,
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Failed to remove user',
            loading: false,
          });
          throw error;
        }
      },

      inviteUser: async (orgId, data) => {
        set({ loading: true, error: null });
        try {
          const response = await userManagementApi.inviteUser(orgId, data);
          await get().fetchUsers(orgId);
          set({ loading: false, inviteModalOpen: false });
          return response.data;
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Failed to send invitation',
            loading: false,
          });
          throw error;
        }
      },

      inviteBulk: async (orgId, invitations) => {
        set({ loading: true, error: null });
        try {
          const response = await userManagementApi.inviteBulk(orgId, { invitations });
          await get().fetchUsers(orgId);
          set({ loading: false, inviteModalOpen: false });
          return response.data;
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Failed to send invitations',
            loading: false,
          });
          throw error;
        }
      },

      updateUserRoles: async (orgId, userId, data) => {
        set({ loading: true, error: null });
        try {
          await userManagementApi.updateUserRoles(orgId, userId, data);
          await get().fetchUsers(orgId);
          if (get().selectedUser?.id === userId) {
            await get().fetchUserDetail(orgId, userId);
          }
          set({ loading: false });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Failed to update roles',
            loading: false,
          });
          throw error;
        }
      },

      fetchActivityLog: async (orgId, userId, filters = {}) => {
        set({ loading: true, error: null });
        try {
          const response = await userManagementApi.getUserActivity(orgId, userId, {
            ...filters,
            page: get().activityPagination.page,
            limit: get().activityPagination.limit,
          });
          set({
            activityLog: response.data.items,
            activityPagination: {
              total: response.data.total,
              page: response.data.page,
              limit: response.data.limit,
              pages: response.data.pages,
            },
            loading: false,
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Failed to fetch activity log',
            loading: false,
          });
        }
      },

      fetchEffectivePermissions: async (orgId, userId) => {
        set({ loading: true, error: null });
        try {
          const response = await userManagementApi.getUserPermissions(orgId, userId);
          set({
            effectivePermissions: response.data,
            loading: false,
          });
        } catch (error: any) {
          set({
            error: error.response?.data?.detail || 'Failed to fetch permissions',
            loading: false,
          });
        }
      },

      // UI Actions
      setInviteModalOpen: (open) => set({ inviteModalOpen: open }),
      setUserDetailModalOpen: (open) => set({ userDetailModalOpen: open }),
      selectUser: (userId) => set({ selectedUserId: userId }),
      clearError: () => set({ error: null }),
    }),
    { name: 'user-store' }
  )
);
