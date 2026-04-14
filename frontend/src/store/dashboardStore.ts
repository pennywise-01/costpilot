import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface DashboardState {
  activeDashboardId: string | null;
  editMode: boolean;
  isDirty: boolean;
  selectedWidgetId: string | null;
  setActiveDashboard: (id: string) => void;
  toggleEditMode: () => void;
  setEditMode: (mode: boolean) => void;
  markDirty: () => void;
  markClean: () => void;
  setSelectedWidget: (id: string | null) => void;
}

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set) => ({
      activeDashboardId: null,
      editMode: false,
      isDirty: false,
      selectedWidgetId: null,
      setActiveDashboard: (id) => set({ activeDashboardId: id }),
      toggleEditMode: () => set((s) => ({ editMode: !s.editMode })),
      setEditMode: (mode) => set({ editMode: mode }),
      markDirty: () => set({ isDirty: true }),
      markClean: () => set({ isDirty: false }),
      setSelectedWidget: (id) => set({ selectedWidgetId: id }),
    }),
    {
      name: 'costpilot-dashboard',
      partialize: (state) => ({
        activeDashboardId: state.activeDashboardId,
      }),
    }
  )
);
