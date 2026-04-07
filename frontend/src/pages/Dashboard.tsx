import React, { useMemo, useEffect, useState } from 'react';
import {
  Row,
  Col,
  Card,
  Statistic,
  Table,
  Tag,
  Typography,
  Space,
  Spin,
  Empty,
  Progress,
  Divider,
  Button,
  Tooltip,
  Badge,
  Alert,
} from 'antd';
import {
  DollarOutlined,
  FundOutlined,
  ThunderboltOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  CloudServerOutlined,
  RightOutlined,
  CalendarOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { Area } from '@ant-design/charts';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { recommendationsApi } from '@/api/recommendations';
import { expensesApi } from '@/api/expenses';
import { cloudAccountsApi, type CloudAccount, type CloudAccountWithLiveData } from '@/api/cloudAccounts';
import { resourcesApi } from '@/api/resources';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';

const { Text, Title, Link } = Typography;

/* -------------------------------------------------------------------------- */
/*                        Staggered Loading Hook                              */
/* -------------------------------------------------------------------------- */

/**
 * Custom hook to stagger dashboard data fetching.
 * This prevents overwhelming the backend with concurrent requests
 * when multiple users are accessing the dashboard simultaneously.
 */
const useStaggeredDashboard = (orgId: string | null) => {
  // Stagger phases: 0 = loading essentials, 1 = loading secondary, 2 = loading tertiary
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (!orgId) return;

    // Phase 0: Immediately load essential data (expense summary)
    // Phase 1: After 150ms, load secondary data (cloud accounts, resources)
    // Phase 2: After 300ms, load tertiary data (recommendations, breakdown)
    
    const phase1Timer = setTimeout(() => setPhase(1), 150);
    const phase2Timer = setTimeout(() => setPhase(2), 300);

    return () => {
      clearTimeout(phase1Timer);
      clearTimeout(phase2Timer);
    };
  }, [orgId]);

  return {
    // Phase 0: Essential data - load immediately
    loadExpenseSummary: !!orgId,
    
    // Phase 1: Secondary data - load after 150ms
    loadCloudAccounts: phase >= 1,
    loadResources: phase >= 1,
    
    // Phase 2: Tertiary data - load after 300ms
    loadRecommendations: phase >= 2,
    loadBreakdown: phase >= 2,
    
    currentPhase: phase,
  };
};

/* -------------------------------------------------------------------------- */
/*                               Types                                        */
/* -------------------------------------------------------------------------- */

interface ResourceRow {
  key: string;
  name: string;
  cloud: string;
  dailyCost: number;
}

const CATEGORY_COLORS: Record<string, string> = {
  cost: '#1677ff',
  security: '#fa8c16',
};

const CATEGORY_LABELS: Record<string, string> = {
  cost: 'Cost Optimization',
  security: 'Security',
};

const CLOUD_COLORS: Record<string, string> = {
  aws_cnr: '#FF9900',
  azure_cnr: '#0078D4',
  gcp_cnr: '#4285F4',
};

const CLOUD_NAMES: Record<string, string> = {
  aws_cnr: 'AWS',
  azure_cnr: 'Azure',
  gcp_cnr: 'GCP',
};

/* -------------------------------------------------------------------------- */
/*                            Helper Components                               */
/* -------------------------------------------------------------------------- */

const cloudTagColor: Record<string, string> = {
  aws_cnr: 'orange',
  azure_cnr: 'blue',
  gcp_cnr: 'green',
  AWS: 'orange',
  Azure: 'blue',
  GCP: 'green',
};

/* -------------------------------------------------------------------------- */
/*                              Dashboard Page                                */
/* -------------------------------------------------------------------------- */

const Dashboard: React.FC = () => {
  const orgId = useCurrentOrgId();
  const queryClient = useQueryClient();
  
  // Use staggered loading to prevent overwhelming the backend
  const {
    loadExpenseSummary,
    loadCloudAccounts,
    loadResources,
    loadRecommendations,
    loadBreakdown,
  } = useStaggeredDashboard(orgId);

  // Fetch cache status
  const { data: cacheStatus, refetch: refetchCacheStatus } = useQuery({
    queryKey: ['expenses-cache-status', orgId],
    queryFn: async () => {
      const res = await expensesApi.getCacheStatus(orgId);
      return res.data;
    },
    enabled: !!orgId,
    // Check cache status every minute
    refetchInterval: 60 * 1000,
  });

  // Cache refresh mutation
  const refreshMutation = useMutation({
    mutationFn: () => expensesApi.refreshCache(orgId),
    onSuccess: () => {
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: ['expenses-summary', orgId] });
      queryClient.invalidateQueries({ queryKey: ['expenses-cache-status', orgId] });
      refetchCacheStatus();
    },
  });

  // Fetch expense summary (Phase 0 - immediate)
  const { data: expenseSummary, isLoading: expensesLoading, error: expensesError } = useQuery({
    queryKey: ['expenses-summary', orgId],
    queryFn: async () => {
      console.log('[DEBUG] Fetching expense summary for orgId:', orgId);
      const res = await expensesApi.getSummary(orgId);
      console.log('[DEBUG] Expense summary response:', res.data);
      return res.data;
    },
    enabled: loadExpenseSummary,
    // Cache results for 5 minutes to reduce backend load
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  // Log any errors
  useEffect(() => {
    if (expensesError) {
      console.error('[DEBUG] Expense summary error:', expensesError);
    }
  }, [expensesError]);

  // Fetch expense breakdown for chart (Phase 2 - staggered)
  const { data: expenseBreakdown } = useQuery({
    queryKey: ['expenses-breakdown', orgId],
    queryFn: async () => {
      const endDate = dayjs().format('YYYY-MM-DD');
      const startDate = dayjs().subtract(30, 'day').format('YYYY-MM-DD');
      const res = await expensesApi.getBreakdown(orgId, {
        start_date: startDate,
        end_date: endDate,
        group_by: 'cloud',
      });
      return res.data;
    },
    enabled: loadBreakdown,
    // Cache results for 5 minutes
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  // Fetch cloud accounts (Phase 1 - staggered)
  const { data: cloudAccountsResponse, isLoading: cloudAccountsLoading } = useQuery({
    queryKey: ['cloud-accounts', orgId],
    queryFn: async () => {
      const res = await cloudAccountsApi.list(orgId);
      return res.data;
    },
    enabled: loadCloudAccounts,
    // Cache results for 10 minutes (cloud accounts change less frequently)
    staleTime: 10 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
  });

  // Extract items array from paginated response (fallback to plain array for backward compat)
  const cloudAccountsList: CloudAccount[] = Array.isArray(cloudAccountsResponse)
    ? cloudAccountsResponse
    : (cloudAccountsResponse as { items?: CloudAccount[] })?.items ?? [];

  // Fetch live data for dashboard cloud account metrics (costs/resources)
  const { data: cloudAccountsLiveData = {}, isLoading: cloudAccountsLiveLoading } = useQuery({
    queryKey: ['cloud-accounts-live-data', orgId, cloudAccountsList?.map((a: CloudAccount) => a.id).join(',')],
    queryFn: async () => {
      if (!cloudAccountsList || cloudAccountsList.length === 0) {
        return {} as Record<string, CloudAccountWithLiveData>;
      }
      const map: Record<string, CloudAccountWithLiveData> = {};

      // Fetch sequentially to avoid spiking cloud-provider calls and triggering rate limits.
      for (const account of cloudAccountsList) {
        try {
          const res = await cloudAccountsApi.getLiveData(account.id);
          let liveData = res.data;

          // Bust stale zero snapshots from previous failed refreshes.
          if (
            Number(liveData.monthly_cost ?? 0) === 0 &&
            (liveData.data_source === 'cache' || liveData.data_source === 'unavailable')
          ) {
            try {
              const freshRes = await cloudAccountsApi.getLiveData(account.id, true);
              liveData = freshRes.data;
            } catch {
              // Keep the original response if refresh fails.
            }
          }

          // If monthly summary is still zero, approximate from recent daily history
          // so the dashboard stays consistent with account details.
          if (Number(liveData.monthly_cost ?? 0) === 0) {
            try {
              const historyRes = await cloudAccountsApi.getCostHistory(account.id, 30);
              const rollingMonthlyCost = historyRes.data.reduce(
                (sum: number, point: { cost: number }) => sum + Number(point.cost || 0),
                0,
              );

              if (rollingMonthlyCost > 0) {
                liveData = {
                  ...liveData,
                  monthly_cost: Number(rollingMonthlyCost.toFixed(2)),
                };
              }
            } catch {
              // Ignore history fallback failures for this account.
            }
          }

          map[account.id] = liveData;
        } catch {
          // Keep partial results for other accounts.
        }
      }

      return map;
    },
    enabled: loadCloudAccounts && !!cloudAccountsList && cloudAccountsList.length > 0,
    // Always refresh on mount so stale zero snapshots do not linger in query cache.
    staleTime: 0,
    gcTime: 5 * 60 * 1000,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
  });

  // Fetch top resources (Phase 1 - staggered)
  const { data: resourcesData, isLoading: resourcesLoading } = useQuery({
    queryKey: ['resources', orgId],
    queryFn: async () => {
      const res = await resourcesApi.list(orgId, { limit: 5 });
      return res.data;
    },
    enabled: loadResources,
    // Cache results for 5 minutes
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  // Fetch recommendations (Phase 2 - staggered)
  const { data: recOverview } = useQuery({
    queryKey: ['recommendations', orgId],
    queryFn: async () => {
      const res = await recommendationsApi.getOverview(orgId);
      return res.data;
    },
    enabled: loadRecommendations,
    // Cache results for 10 minutes
    staleTime: 10 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
  });

  // Process cost trend data from API
  const costTrendData = useMemo(() => {
    if (!expenseBreakdown?.daily_totals) return [];
    return expenseBreakdown.daily_totals.map((d) => ({
      date: dayjs(d.date).format('MMM DD'),
      cost: d.cost,
    }));
  }, [expenseBreakdown]);

  // Process cloud accounts for display
  const cloudAccounts = useMemo(() => {
    if (!cloudAccountsList) return [];
    return cloudAccountsList.map((acc: CloudAccount) => ({
      name: acc.name,
      shortName: CLOUD_NAMES[acc.type] || acc.type,
      monthly: cloudAccountsLiveData[acc.id]?.monthly_cost || 0,
      color: CLOUD_COLORS[acc.type] || '#888',
    }));
  }, [cloudAccountsList, cloudAccountsLiveData]);

  // Process top resources for display
  const topResources: ResourceRow[] = useMemo(() => {
    if (!resourcesData?.resources) return [];
    return [...resourcesData.resources]
      .sort((a, b) => (b.daily_cost || 0) - (a.daily_cost || 0))
      .slice(0, 5)
      .map((r, idx) => ({
      key: r.id || String(idx),
      name: r.name,
      cloud: CLOUD_NAMES[r.cloud_type || ''] || r.cloud_type || 'Unknown',
      dailyCost: r.daily_cost || 0,
      }));
  }, [resourcesData]);

  const recommendations = useMemo(() => {
    if (!recOverview) return [];
    const byCategory: Record<string, { items: number; savings: number }> = {};
    for (const rec of recOverview.recommendations) {
      const cat = rec.category;
      if (!byCategory[cat]) byCategory[cat] = { items: 0, savings: 0 };
      byCategory[cat].items += rec.count;
      byCategory[cat].savings += rec.saving;
    }
    return Object.entries(byCategory).map(([cat, data]) => ({
      category: CATEGORY_LABELS[cat] || cat,
      items: data.items,
      savings: Math.round(data.savings),
      color: CATEGORY_COLORS[cat] || '#888',
    }));
  }, [recOverview]);

  const totalRecommendationSavings = recommendations.reduce(
    (sum, r) => sum + r.savings,
    0,
  );
  const totalRecommendationCount = recOverview?.total_count ?? 0;

  /* ----- Area chart config ----- */
  const areaConfig = {
    data: costTrendData,
    xField: 'date',
    yField: 'cost',
    smooth: true,
    height: 300,
    color: '#1677ff',
    areaStyle: {
      fill: 'l(270) 0:#ffffff 0.5:#d6e4ff 1:#1677ff',
    },
    line: {
      style: {
        lineWidth: 2,
      },
    },
    xAxis: {
      tickCount: 8,
      label: {
        style: { fontSize: 11 },
      },
    },
    yAxis: {
      label: {
        formatter: (v: string) => `$${v}`,
        style: { fontSize: 11 },
      },
    },
    tooltip: {
      formatter: (datum: { date: string; cost: number }) => ({
        name: 'Daily Cost',
        value: `$${datum.cost.toFixed(2)}`,
      }),
    },
    animation: {
      appear: { animation: 'wave-in', duration: 1200 },
    },
  };

  /* ----- Table columns ----- */
  const resourceColumns: ColumnsType<ResourceRow> = [
    {
      title: 'Resource Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: ResourceRow) => (
        <Space>
          <Tag
            color={cloudTagColor[record.cloud]}
            style={{ marginRight: 0, minWidth: 44, textAlign: 'center' }}
          >
            {record.cloud}
          </Tag>
          <Text strong style={{ fontSize: 13 }}>
            {name}
          </Text>
        </Space>
      ),
    },
    {
      title: 'Daily Cost',
      dataIndex: 'dailyCost',
      key: 'dailyCost',
      align: 'right' as const,
      render: (v: number) => (
        <Text strong style={{ color: '#1677ff' }}>
          ${v.toFixed(2)}
        </Text>
      ),
    },
  ];

  /* ----- Card shared style ----- */
  const cardStyle: React.CSSProperties = {
    borderRadius: 12,
    height: '100%',
  };

  // Helper to get cache status color
  const getCacheStatusColor = () => {
    switch (cacheStatus?.status) {
      case 'healthy':
        return 'success';
      case 'stale':
        return 'warning';
      case 'expired':
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  // Helper to get cache status icon
  const getCacheStatusIcon = () => {
    switch (cacheStatus?.status) {
      case 'healthy':
        return <CheckCircleOutlined />;
      case 'stale':
      case 'expired':
        return <ClockCircleOutlined />;
      case 'error':
        return <ExclamationCircleOutlined />;
      default:
        return <ClockCircleOutlined />;
    }
  };

  // Format relative time
  const getRelativeTime = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    const date = dayjs(dateStr);
    const now = dayjs();
    const hours = now.diff(date, 'hours');
    if (hours < 1) return 'Just now';
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  return (
    <div style={{ padding: 0 }}>
      {/* Page Header */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            Dashboard
          </Title>
          <Text type="secondary">
            Overview of your cloud spend across all accounts
          </Text>
        </div>
        
        {/* Cache Status & Refresh */}
        <Space>
          {cacheStatus && (
            <Tooltip title={`Last updated: ${getRelativeTime(cacheStatus.last_updated)}`}>
              <Badge
                status={getCacheStatusColor() as any}
                text={
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {cacheStatus.status === 'healthy' && `Updated ${getRelativeTime(cacheStatus.last_updated)}`}
                    {cacheStatus.status === 'stale' && `Stale (${getRelativeTime(cacheStatus.last_updated)})`}
                    {cacheStatus.status === 'expired' && `Expired (${getRelativeTime(cacheStatus.last_updated)})`}
                    {cacheStatus.status === 'error' && 'Update failed'}
                    {cacheStatus.status === 'uninitialized' && 'Not initialized'}
                    {cacheStatus.is_refreshing && ' • Refreshing...'}
                  </Text>
                }
              />
            </Tooltip>
          )}
          <Button
            icon={<ReloadOutlined spin={refreshMutation.isPending || cacheStatus?.is_refreshing} />}
            onClick={() => refreshMutation.mutate()}
            loading={refreshMutation.isPending}
            disabled={cacheStatus?.is_refreshing}
            size="small"
          >
            {cacheStatus?.is_refreshing ? 'Refreshing...' : 'Refresh'}
          </Button>
        </Space>
      </div>

      {/* Cache Alert */}
      {cacheStatus?.status === 'expired' && (
        <Alert
          message="Cost data is out of date"
          description="The dashboard is showing old data. Click Refresh to update."
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={() => refreshMutation.mutate()} loading={refreshMutation.isPending}>
              Refresh Now
            </Button>
          }
        />
      )}
      {cacheStatus?.status === 'error' && (
        <Alert
          message="Failed to update cost data"
          description={cacheStatus.last_error || "The last update failed. Please try refreshing."}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={() => refreshMutation.mutate()} loading={refreshMutation.isPending}>
              Retry
            </Button>
          }
        />
      )}

      {/* ---- Row 1: Stat Cards ---- */}
      <Row gutter={[24, 24]}>
        <Col xs={24} sm={12} lg={6}>
          <Card
            style={{
              ...cardStyle,
              borderLeft: '4px solid #1677ff',
            }}
            styles={{ body: { padding: '20px 24px' } }}
          >
            {expensesLoading ? (
              <Spin />
            ) : (
              <Statistic
                title={
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    Monthly Spend
                  </Text>
                }
                value={expenseSummary?.this_month_total || 0}
                precision={2}
                prefix={
                  <DollarOutlined
                    style={{
                      color: '#1677ff',
                      backgroundColor: '#e6f4ff',
                      padding: 8,
                      borderRadius: 8,
                      fontSize: 18,
                      marginRight: 4,
                    }}
                  />
                }
                formatter={(value) => (
                  <span>
                    ${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    {expenseSummary?.change_percent !== undefined && (
                      <span
                        style={{
                          fontSize: 13,
                          marginLeft: 8,
                          color: expenseSummary.change_percent >= 0 ? '#ff4d4f' : '#52c41a',
                          fontWeight: 500,
                        }}
                      >
                        {expenseSummary.change_percent >= 0 ? (
                          <ArrowUpOutlined style={{ fontSize: 11 }} />
                        ) : (
                          <ArrowDownOutlined style={{ fontSize: 11 }} />
                        )}{' '}
                        {Math.abs(expenseSummary.change_percent).toFixed(1)}%
                      </span>
                    )}
                  </span>
                )}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card
            style={{
              ...cardStyle,
              borderLeft: '4px solid #722ed1',
            }}
            styles={{ body: { padding: '20px 24px' } }}
          >
            {expensesLoading ? (
              <Spin />
            ) : (
              <Statistic
                title={
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    Forecast
                  </Text>
                }
                value={expenseSummary?.this_month_forecast || 0}
                precision={2}
                prefix={
                  <FundOutlined
                    style={{
                      color: '#722ed1',
                      backgroundColor: '#f9f0ff',
                      padding: 8,
                      borderRadius: 8,
                      fontSize: 18,
                      marginRight: 4,
                    }}
                  />
                }
                formatter={(value) => (
                  <span>
                    ${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    <div
                      style={{
                        fontSize: 12,
                        color: '#8c8c8c',
                        fontWeight: 400,
                        marginTop: 2,
                      }}
                    >
                      End of month estimate
                    </div>
                  </span>
                )}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card
            style={{
              ...cardStyle,
              borderLeft: '4px solid #52c41a',
            }}
            styles={{ body: { padding: '20px 24px' } }}
          >
            {expensesLoading ? (
              <Spin />
            ) : (
              <Statistic
                title={
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    Last Month
                  </Text>
                }
                value={expenseSummary?.last_month_total || 0}
                precision={2}
                prefix={
                  <CalendarOutlined
                    style={{
                      color: '#52c41a',
                      backgroundColor: '#f6ffed',
                      padding: 8,
                      borderRadius: 8,
                      fontSize: 18,
                      marginRight: 4,
                    }}
                  />
                }
                formatter={(value) => (
                  <span>${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                )}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card
            style={{
              ...cardStyle,
              borderLeft: '4px solid #fa8c16',
            }}
            styles={{ body: { padding: '20px 24px' } }}
          >
            <Statistic
              title={
                <Text type="secondary" style={{ fontSize: 13 }}>
                  Potential Savings
                </Text>
              }
              value={totalRecommendationSavings}
              precision={0}
              prefix={
                <ThunderboltOutlined
                  style={{
                    color: '#fa8c16',
                    backgroundColor: '#fff7e6',
                    padding: 8,
                    borderRadius: 8,
                    fontSize: 18,
                    marginRight: 4,
                  }}
                />
              }
              formatter={(value) => (
                <span>
                  ${Number(value).toLocaleString()}
                  <div
                    style={{
                      fontSize: 12,
                      color: '#8c8c8c',
                      fontWeight: 400,
                      marginTop: 2,
                    }}
                  >
                    From {totalRecommendationCount} recommendations
                  </div>
                </span>
              )}
            />
          </Card>
        </Col>
      </Row>

      {/* ---- Row 2: Cost Trend Chart ---- */}
      <Row gutter={[24, 24]} style={{ marginTop: 24 }}>
        <Col span={24}>
          <Card
            title="Cost Trend (Last 30 Days)"
            style={cardStyle}
            styles={{ body: { paddingTop: 12 } }}
          >
            {costTrendData.length > 0 ? (
              <Area {...areaConfig} />
            ) : (
              <Empty
                description="No cost data available. Connect a cloud account to see your spending trends."
                style={{ padding: '40px 0' }}
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* ---- Row 3: Resources + Recommendations ---- */}
      <Row gutter={[24, 24]} style={{ marginTop: 24 }}>
        {/* Top Expensive Resources */}
        <Col xs={24} lg={14}>
          <Card
            title="Top Expensive Resources"
            style={cardStyle}
            styles={{ body: { paddingBottom: 12 } }}
            extra={
              <Link href="/resources" style={{ fontSize: 13 }}>
                View all resources <RightOutlined style={{ fontSize: 10 }} />
              </Link>
            }
          >
            {resourcesLoading ? (
              <Spin style={{ display: 'block', padding: '40px 0' }} />
            ) : topResources.length > 0 ? (
              <Table<ResourceRow>
                columns={resourceColumns}
                dataSource={topResources}
                pagination={false}
                size="middle"
                showHeader
                style={{ marginTop: -8 }}
              />
            ) : (
              <Empty
                description="No resources found. Connect a cloud account to discover your resources."
                style={{ padding: '40px 0' }}
              />
            )}
          </Card>
        </Col>

        {/* Recommendations Summary */}
        <Col xs={24} lg={10}>
          <Card
            title="Recommendations Summary"
            style={cardStyle}
            extra={
              <Link href="/recommendations" style={{ fontSize: 13 }}>
                View all <RightOutlined style={{ fontSize: 10 }} />
              </Link>
            }
          >
            {/* Total savings header */}
            <div
              style={{
                textAlign: 'center',
                padding: '8px 0 20px',
              }}
            >
              <Text type="secondary" style={{ fontSize: 13 }}>
                Total Potential Savings
              </Text>
              <Title
                level={2}
                style={{
                  color: '#52c41a',
                  margin: '4px 0 0',
                  fontWeight: 700,
                }}
              >
                ${totalRecommendationSavings.toLocaleString()}/mo
              </Title>
            </div>

            <Divider style={{ margin: '0 0 16px' }} />

            {/* Recommendation categories */}
            <Space direction="vertical" style={{ width: '100%' }} size={20}>
              {recommendations.map((rec) => {
                const proportion = Math.round(
                  (rec.savings / totalRecommendationSavings) * 100,
                );
                return (
                  <div key={rec.category}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        marginBottom: 6,
                      }}
                    >
                      <Space size={8}>
                        <Text strong style={{ fontSize: 14 }}>
                          {rec.category}
                        </Text>
                        <Tag
                          style={{
                            borderRadius: 10,
                            fontSize: 11,
                            lineHeight: '18px',
                            padding: '0 8px',
                          }}
                        >
                          {rec.items} items
                        </Tag>
                      </Space>
                      <Text
                        strong
                        style={{ color: '#52c41a', fontSize: 14 }}
                      >
                        ${rec.savings.toLocaleString()}
                      </Text>
                    </div>
                    <Progress
                      percent={proportion}
                      strokeColor={rec.color}
                      trailColor="#f0f0f0"
                      showInfo={false}
                      strokeLinecap="round"
                      size={['100%', 10]}
                    />
                  </div>
                );
              })}
            </Space>
          </Card>
        </Col>
      </Row>

      {/* ---- Row 4: Pools + Cloud Accounts ---- */}
      <Row gutter={[24, 24]} style={{ marginTop: 24 }}>
        {/* Pools Requiring Attention */}
        <Col xs={24} lg={12}>
          <Card
            title="Pools Requiring Attention"
            style={cardStyle}
            extra={
              <Link href="/pools" style={{ fontSize: 13 }}>
                Manage pools <RightOutlined style={{ fontSize: 10 }} />
              </Link>
            }
          >
            <Empty
              description="No pools configured yet. Create budget pools to track spending by team or project."
              style={{ padding: '40px 0' }}
            />
          </Card>
        </Col>

        {/* Cloud Accounts */}
        <Col xs={24} lg={12}>
          <Card
            title="Cloud Accounts"
            style={cardStyle}
            extra={
              <Link href="/accounts" style={{ fontSize: 13 }}>
                Manage accounts <RightOutlined style={{ fontSize: 10 }} />
              </Link>
            }
          >
            {cloudAccountsLoading || (cloudAccountsList?.length > 0 && cloudAccountsLiveLoading) ? (
              <Spin style={{ display: 'block', padding: '40px 0' }} />
            ) : cloudAccounts.length > 0 ? (
              <Space direction="vertical" style={{ width: '100%' }} size={12}>
                {cloudAccounts.map((account, idx) => (
                  <div
                    key={account.shortName + idx}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '14px 16px',
                      borderRadius: 10,
                      border: '1px solid #f0f0f0',
                      background: '#fafafa',
                      transition: 'all 0.2s',
                    }}
                  >
                    <Space size={12}>
                      <div
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: 10,
                          backgroundColor: account.color + '18',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <CloudServerOutlined
                          style={{
                            fontSize: 20,
                            color: account.color,
                          }}
                        />
                      </div>
                      <div>
                        <Text strong style={{ fontSize: 14, display: 'block' }}>
                          {account.name}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {account.shortName}
                        </Text>
                      </div>
                    </Space>
                    <div style={{ textAlign: 'right' }}>
                      <Text
                        strong
                        style={{
                          fontSize: 16,
                          color: '#262626',
                          display: 'block',
                        }}
                      >
                        ${Number(account.monthly).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        per month
                      </Text>
                    </div>
                  </div>
                ))}
              </Space>
            ) : (
              <Empty
                description="No cloud accounts connected. Add an AWS, Azure, or GCP account to get started."
                style={{ padding: '40px 0' }}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
