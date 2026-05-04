import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Typography, Button, Space, Modal, Input, message, Alert, Badge, Tooltip, Spin } from 'antd';
import {
  ReloadOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import dayjs from 'dayjs';

import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';
import { useDashboardData } from '@/hooks/useDashboardData';
import { useDashboardStore } from '@/store/dashboardStore';
import { dashboardsApi, type DashboardDetail, type LayoutItem, type WidgetConfigEntry } from '@/api/dashboards';
import apiClient from '@/api/client';
import { WIDGET_REGISTRY } from '@/components/dashboard/widgetRegistry';

import DashboardGrid from '@/components/dashboard/DashboardGrid';
import DashboardToolbar from '@/components/dashboard/DashboardToolbar';
import WidgetPicker from '@/components/dashboard/WidgetPicker';
import WidgetConfigDrawer from '@/components/dashboard/WidgetConfigDrawer';

const { Title, Text } = Typography;

// --- Helpers ---

const getCacheStatusColor = (status?: string) => {
  switch (status) {
    case 'healthy': return 'success';
    case 'stale': return 'warning';
    case 'expired':
    case 'error': return 'error';
    default: return 'default';
  }
};

const getCacheStatusIcon = (status?: string) => {
  switch (status) {
    case 'healthy': return <CheckCircleOutlined />;
    case 'stale':
    case 'expired': return <ClockCircleOutlined />;
    case 'error': return <ExclamationCircleOutlined />;
    default: return <ClockCircleOutlined />;
  }
};

const getRelativeTime = (dateStr: string | null) => {
  if (!dateStr) return 'Never';
  const date = dayjs(dateStr);
  const now = dayjs();
  const hours = now.diff(date, 'hours');
  if (hours < 1) return 'Just now';
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
};

const normalizeDashboardLayout = (
  layout: LayoutItem[],
  widgets: Record<string, WidgetConfigEntry>,
): LayoutItem[] => layout.filter((item) => widgets[item.i]).map((item) => {
  const widgetConfig = widgets[item.i];
  const definition = widgetConfig ? WIDGET_REGISTRY[widgetConfig.type] : null;
  const minW = definition?.minW ?? item.minW ?? 1;
  const minH = definition?.minH ?? item.minH ?? 1;
  const w = Math.min(12, Math.max(item.w, minW));
  const h = Math.max(item.h, minH);
  return {
    ...item,
    x: Math.min(Math.max(item.x, 0), 12 - w),
    y: Math.max(item.y, 0),
    w,
    h,
    minW,
    minH,
    maxW: 12,
    maxH: Math.max(item.maxH ?? 20, h),
  };
});

// --- Main Component ---

const Dashboard: React.FC = () => {
  const orgId = useCurrentOrgId();
  const queryClient = useQueryClient();
  const {
    activeDashboardId,
    editMode,
    isDirty,
    selectedWidgetId,
    setActiveDashboard,
    setEditMode,
    markDirty,
    markClean,
    setSelectedWidget,
  } = useDashboardStore();

  // --- State ---
  const [widgetPickerOpen, setWidgetPickerOpen] = useState(false);
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false);
  const [configWidgetId, setConfigWidgetId] = useState<string | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newDashboardName, setNewDashboardName] = useState('');
  const [duplicateModalOpen, setDuplicateModalOpen] = useState(false);
  const [duplicateName, setDuplicateName] = useState('');

  // Local layout state for optimistic edits
  const [localLayout, setLocalLayout] = useState<LayoutItem[] | null>(null);
  const [localWidgets, setLocalWidgets] = useState<Record<string, WidgetConfigEntry> | null>(null);

  // --- Data fetching ---

  const { data: dashboardList, isLoading: listLoading } = useQuery({
    queryKey: ['dashboards', orgId],
    queryFn: () => dashboardsApi.list(orgId).then((r) => r.data),
  });

  // Auto-select default dashboard or first available
  const effectiveDashboardId = activeDashboardId ?? dashboardList?.[0]?.id ?? null;

  const { data: dashboardDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['dashboard', orgId, effectiveDashboardId],
    queryFn: () => dashboardsApi.get(orgId, effectiveDashboardId!).then((r) => r.data),
    enabled: !!effectiveDashboardId,
  });

  // Batch widget data
  const widgetDataQuery = useDashboardData(dashboardDetail ?? null);

  // Cache status
  const { data: cacheStatus } = useQuery({
    queryKey: ['cache-status', orgId],
    queryFn: () => apiClient.get(`/organizations/${orgId}/expenses/cache-status`).then((r) => r.data),
    staleTime: 60_000,
  });

  const refreshMutation = useMutation({
    mutationFn: () => apiClient.post(`/organizations/${orgId}/expenses/refresh`, { force: false }).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['dashboard-data'] }),
  });

  // --- Sync local state with server data ---

  useEffect(() => {
    if (dashboardDetail && !isDirty) {
      setLocalWidgets(dashboardDetail.widget_config);
      setLocalLayout(normalizeDashboardLayout(dashboardDetail.layout_config, dashboardDetail.widget_config));
    }
  }, [dashboardDetail, isDirty]);

  // Reset edit mode on dashboard change
  useEffect(() => {
    setEditMode(false);
    markClean();
    setLocalLayout(null);
    setLocalWidgets(null);
  }, [effectiveDashboardId]);

  // --- Handlers ---

  const handleLayoutChange = useCallback((newLayout: LayoutItem[]) => {
    setLocalLayout(newLayout);
    markDirty();
  }, [markDirty]);

  const handleSave = useCallback(async () => {
    if (!dashboardDetail || !localLayout || !localWidgets) return;
    try {
      await dashboardsApi.update(orgId, dashboardDetail.id, {
        layout_config: normalizeDashboardLayout(localLayout, localWidgets),
        widget_config: localWidgets,
        version: dashboardDetail.version,
      });
      markClean();
      setEditMode(false);
      queryClient.invalidateQueries({ queryKey: ['dashboard', orgId, effectiveDashboardId] });
      message.success('Dashboard saved');
    } catch (err: any) {
      if (err?.response?.status === 409) {
        message.error('Dashboard was modified by another user. Refresh to see the latest.');
      } else {
        message.error('Failed to save dashboard');
      }
    }
  }, [orgId, dashboardDetail, localLayout, localWidgets, markClean, setEditMode, queryClient, effectiveDashboardId]);

  const handleRevert = useCallback(async () => {
    if (!dashboardDetail) return;
    try {
      await dashboardsApi.revert(orgId, dashboardDetail.id);
      markClean();
      queryClient.invalidateQueries({ queryKey: ['dashboard', orgId, effectiveDashboardId] });
      message.success('Reverted to previous layout');
    } catch {
      message.error('Failed to revert');
    }
  }, [orgId, dashboardDetail, markClean, queryClient, effectiveDashboardId]);

  const handleAddWidget = useCallback((type: string) => {
    const definition = WIDGET_REGISTRY[type];
    if (!definition || !localWidgets || !localLayout) return;

    const id = `${type}-${Date.now()}`;
    const maxY = localLayout.reduce((max, item) => Math.max(max, item.y + item.h), 0);

    setLocalWidgets({
      ...localWidgets,
      [id]: { ...definition.defaultConfig, type: definition.type } as WidgetConfigEntry,
    });
    setLocalLayout([
      ...localLayout,
      { i: id, x: 0, y: maxY, w: definition.defaultW, h: definition.defaultH, minW: definition.minW, minH: definition.minH },
    ]);
    markDirty();
  }, [localWidgets, localLayout, markDirty]);

  const handleRemoveWidget = useCallback((widgetId: string) => {
    if (!localWidgets || !localLayout) return;
    const { [widgetId]: _, ...restWidgets } = localWidgets;
    setLocalWidgets(restWidgets);
    setLocalLayout(localLayout.filter((item) => item.i !== widgetId));
    markDirty();
  }, [localWidgets, localLayout, markDirty]);

  const handleConfigureWidget = useCallback((widgetId: string) => {
    setConfigWidgetId(widgetId);
    setConfigDrawerOpen(true);
  }, []);

  const handleConfigSave = useCallback((widgetId: string, config: WidgetConfigEntry) => {
    if (!localWidgets) return;
    setLocalWidgets({ ...localWidgets, [widgetId]: config });
    markDirty();
  }, [localWidgets, markDirty]);

  const handleCreateDashboard = useCallback(async () => {
    if (!newDashboardName.trim()) return;
    try {
      const result = await dashboardsApi.create(orgId, { name: newDashboardName.trim() });
      setActiveDashboard(result.data.id);
      setCreateModalOpen(false);
      setNewDashboardName('');
      queryClient.invalidateQueries({ queryKey: ['dashboards', orgId] });
      message.success('Dashboard created');
    } catch {
      message.error('Failed to create dashboard');
    }
  }, [orgId, newDashboardName, setActiveDashboard, queryClient]);

  const handleDeleteDashboard = useCallback(async () => {
    if (!effectiveDashboardId) return;
    try {
      await dashboardsApi.delete(orgId, effectiveDashboardId);
      setActiveDashboard('');
      queryClient.invalidateQueries({ queryKey: ['dashboards', orgId] });
      message.success('Dashboard deleted');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to delete dashboard');
    }
  }, [orgId, effectiveDashboardId, setActiveDashboard, queryClient]);

  const handleDuplicateDashboard = useCallback(async () => {
    if (!effectiveDashboardId || !duplicateName.trim()) return;
    try {
      const result = await dashboardsApi.duplicate(orgId, effectiveDashboardId, duplicateName.trim());
      setActiveDashboard(result.data.id);
      setDuplicateModalOpen(false);
      setDuplicateName('');
      queryClient.invalidateQueries({ queryKey: ['dashboards', orgId] });
      message.success('Dashboard duplicated');
    } catch {
      message.error('Failed to duplicate dashboard');
    }
  }, [orgId, effectiveDashboardId, duplicateName, setActiveDashboard, queryClient]);

  const handleSetDefault = useCallback(async () => {
    if (!effectiveDashboardId) return;
    try {
      await dashboardsApi.setDefault(orgId, effectiveDashboardId);
      queryClient.invalidateQueries({ queryKey: ['dashboards', orgId] });
      message.success('Set as default dashboard');
    } catch {
      message.error('Failed to set default');
    }
  }, [orgId, effectiveDashboardId, queryClient]);

  // --- Render ---

  const currentLayout = localLayout ?? dashboardDetail?.layout_config ?? [];
  const currentWidgets = localWidgets ?? dashboardDetail?.widget_config ?? {};
  const configWidget = configWidgetId ? currentWidgets[configWidgetId] ?? null : null;

  if (listLoading) {
    return <div style={{ padding: 40, textAlign: 'center' }}><Spin size="large" /></div>;
  }

  return (
    <div style={{ padding: 0 }}>
      {/* Header */}
      <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>Dashboard</Title>
          <Text type="secondary">Overview of your cloud spend across all accounts</Text>
        </div>
        <Space>
          {cacheStatus && (
            <Tooltip title={`Last updated: ${getRelativeTime(cacheStatus.last_updated)}`}>
              <Badge
                status={getCacheStatusColor(cacheStatus.status) as any}
                text={
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {cacheStatus.status === 'healthy' && `Updated ${getRelativeTime(cacheStatus.last_updated)}`}
                    {cacheStatus.status === 'stale' && `Stale (${getRelativeTime(cacheStatus.last_updated)})`}
                    {cacheStatus.status === 'expired' && `Expired`}
                    {cacheStatus.status === 'error' && 'Update failed'}
                    {cacheStatus.status === 'uninitialized' && 'Not initialized'}
                  </Text>
                }
              />
            </Tooltip>
          )}
          <Button
            icon={<ReloadOutlined spin={refreshMutation.isPending} />}
            onClick={() => refreshMutation.mutate()}
            loading={refreshMutation.isPending}
            size="small"
          >
            Refresh
          </Button>
        </Space>
      </div>

      {/* Cache alerts */}
      {cacheStatus?.status === 'expired' && (
        <Alert message="Cost data is out of date" type="warning" showIcon style={{ marginBottom: 16 }} closable />
      )}

      {/* Toolbar */}
      <DashboardToolbar
        dashboards={dashboardList ?? []}
        activeDashboardId={effectiveDashboardId}
        editMode={editMode}
        isDirty={isDirty}
        onDashboardSelect={setActiveDashboard}
        onToggleEdit={() => setEditMode(!editMode)}
        onSave={handleSave}
        onRevert={handleRevert}
        onCreate={() => setCreateModalOpen(true)}
        onDelete={handleDeleteDashboard}
        onDuplicate={() => {
          setDuplicateName(`${dashboardDetail?.name ?? 'Dashboard'} Copy`);
          setDuplicateModalOpen(true);
        }}
        onSetDefault={handleSetDefault}
        onAddWidget={() => setWidgetPickerOpen(true)}
      />

      {/* Grid */}
      {detailLoading ? (
        <div style={{ padding: 40, textAlign: 'center' }}><Spin size="large" /></div>
      ) : (
        <DashboardGrid
          layout={currentLayout}
          widgets={currentWidgets}
          data={widgetDataQuery.data?.data}
          errors={widgetDataQuery.data?.errors}
          loading={widgetDataQuery.isLoading}
          editMode={editMode}
          onLayoutChange={handleLayoutChange}
          onRemoveWidget={editMode ? handleRemoveWidget : undefined}
          onConfigureWidget={editMode ? handleConfigureWidget : undefined}
        />
      )}

      {/* Widget Picker Modal */}
      <WidgetPicker
        open={widgetPickerOpen}
        onSelect={handleAddWidget}
        onCancel={() => setWidgetPickerOpen(false)}
      />

      {/* Widget Config Drawer */}
      <WidgetConfigDrawer
        open={configDrawerOpen}
        widgetId={configWidgetId}
        config={configWidget}
        onSave={handleConfigSave}
        onClose={() => {
          setConfigDrawerOpen(false);
          setConfigWidgetId(null);
        }}
      />

      {/* Create Dashboard Modal */}
      <Modal
        title="Create Dashboard"
        open={createModalOpen}
        onOk={handleCreateDashboard}
        onCancel={() => { setCreateModalOpen(false); setNewDashboardName(''); }}
        okButtonProps={{ disabled: !newDashboardName.trim() }}
      >
        <Input
          placeholder="Dashboard name"
          value={newDashboardName}
          onChange={(e) => setNewDashboardName(e.target.value)}
          onPressEnter={handleCreateDashboard}
          autoFocus
        />
      </Modal>

      {/* Duplicate Dashboard Modal */}
      <Modal
        title="Duplicate Dashboard"
        open={duplicateModalOpen}
        onOk={handleDuplicateDashboard}
        onCancel={() => { setDuplicateModalOpen(false); setDuplicateName(''); }}
        okButtonProps={{ disabled: !duplicateName.trim() }}
      >
        <Input
          placeholder="New dashboard name"
          value={duplicateName}
          onChange={(e) => setDuplicateName(e.target.value)}
          onPressEnter={handleDuplicateDashboard}
          autoFocus
        />
      </Modal>
    </div>
  );
};

export default Dashboard;
