import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Typography,
  Button,
  Card,
  Row,
  Col,
  Statistic,
  Space,
  Tag,
  Spin,
  Empty,
  Popconfirm,
  message,
  Tooltip,
  Badge,
} from 'antd';
import {
  PlusOutlined,
  CloudOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  DeleteOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatCurrency } from '@/utils/formatters';
import { CLOUD_TYPE_LABELS, CLOUD_TYPE_COLORS } from '@/utils/constants';
import { cloudAccountsApi, type CloudAccount, type CloudAccountWithLiveData } from '@/api/cloudAccounts';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';

const { Title, Text } = Typography;

/**
 * Cloud Accounts List Page
 * 
 * This page displays all connected cloud accounts with their basic info.
 * Live cost/resource data is fetched on-demand when clicking into an account.
 * 
 * The list endpoint now returns only DB data (fast, no rate limiting).
 * Individual account details (costs/resources) are fetched via getLiveData().
 */
const CloudAccounts: React.FC = () => {
  const navigate = useNavigate();
  const orgId = useCurrentOrgId();
  const queryClient = useQueryClient();
  const [refreshingAccount, setRefreshingAccount] = useState<string | null>(null);

  // Fetch list of accounts (DB data only - fast, no cloud API calls)
  const { data: accountsResponse = [], isLoading } = useQuery({
    queryKey: ['cloud-accounts', orgId],
    queryFn: async () => {
      const res = await cloudAccountsApi.list(orgId);
      return res.data;
    },
  });

  // Extract items array from paginated response (fallback to plain array for backward compat)
  const accounts: CloudAccount[] = Array.isArray(accountsResponse)
    ? accountsResponse
    : (accountsResponse as { items?: CloudAccount[] })?.items ?? [];

  // Fetch live data for all accounts (with caching on backend)
  const { data: liveDataMap, isLoading: isLoadingLiveData } = useQuery({
    queryKey: ['cloud-accounts-live-data', orgId],
    queryFn: async () => {
      console.log(`[DEBUG] Fetching live data for ${accounts.length} accounts`);
      // Fetch live data for each account in parallel
      const liveDataPromises = accounts.map(async (account) => {
        try {
          console.log(`[DEBUG] Fetching live data for account ${account.id} (${account.name}, type: ${account.type})`);
          const res = await cloudAccountsApi.getLiveData(account.id);
          console.log(`[DEBUG] Got live data for ${account.id}: resources_count=${res.data.resources_count}, data_source=${res.data.data_source}`);
          return { id: account.id, data: res.data };
        } catch (e) {
          console.error(`[DEBUG] Failed to fetch live data for account ${account.id} (${account.name}):`, e);
          return { id: account.id, data: null };
        }
      });
      
      const results = await Promise.all(liveDataPromises);
      const map: Record<string, CloudAccountWithLiveData> = {};
      results.forEach(({ id, data }) => {
        if (data) map[id] = data;
      });
      return map;
    },
    // Only fetch live data after we have the accounts list
    enabled: accounts.length > 0,
    // Cache live data for 2 minutes to prevent excessive API calls
    staleTime: 2 * 60 * 1000,
    // Don't refetch on window focus for this expensive operation
    refetchOnWindowFocus: false,
  });

  const deleteMutation = useMutation({
    mutationFn: (accountId: string) => cloudAccountsApi.delete(accountId),
    onSuccess: () => {
      message.success('Data source deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['cloud-accounts', orgId] });
      queryClient.invalidateQueries({ queryKey: ['cloud-accounts-live-data', orgId] });
    },
    onError: () => {
      message.error('Failed to delete data source');
    },
  });

  const confirmDelete = (accountId: string) => {
    deleteMutation.mutate(accountId);
  };

  const handleRefreshAccount = async (accountId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setRefreshingAccount(accountId);
    try {
      await cloudAccountsApi.getLiveData(accountId, true); // force refresh
      queryClient.invalidateQueries({ queryKey: ['cloud-accounts-live-data', orgId] });
      message.success('Account data refreshed');
    } catch (err) {
      message.error('Failed to refresh account data');
    } finally {
      setRefreshingAccount(null);
    }
  };

  // Calculate totals from live data
  const totalMonthly = accounts.reduce((sum, a) => {
    const liveData = liveDataMap?.[a.id];
    return sum + (liveData?.monthly_cost || 0);
  }, 0);

  const totalForecast = accounts.reduce((sum, a) => {
    const liveData = liveDataMap?.[a.id];
    return sum + (liveData?.forecast || 0);
  }, 0);

  const totalResources = accounts.reduce((sum, a) => {
    const liveData = liveDataMap?.[a.id];
    return sum + (liveData?.resources_count || 0);
  }, 0);

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <CloudOutlined style={{ marginRight: 8 }} />
          Data Sources
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate('/connect-cloud-account')}
        >
          Connect Cloud Account
        </Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="Total Monthly Cost"
              value={totalMonthly}
              formatter={(val) => formatCurrency(val as number)}
              valueStyle={{ color: '#1677ff' }}
              loading={isLoadingLiveData}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Forecast (This Month)"
              value={totalForecast}
              formatter={(val) => formatCurrency(val as number)}
              valueStyle={{ color: '#722ed1' }}
              loading={isLoadingLiveData}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Total Resources"
              value={totalResources}
              valueStyle={{ color: '#52c41a' }}
              loading={isLoadingLiveData}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {accounts.length === 0 ? (
          <Col span={24}>
            <Card>
              <Empty
                description="No cloud accounts connected yet"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/connect-cloud-account')}>
                  Connect Your First Account
                </Button>
              </Empty>
            </Card>
          </Col>
        ) : (
          accounts.map((account) => {
            const liveData = liveDataMap?.[account.id];
            const monthlyCost = liveData?.monthly_cost || 0;
            const lastMonthCost = liveData?.last_month_cost || 0;
            const resourcesCount = liveData?.resources_count || 0;
            const dataSource = liveData?.data_source;
            
            const trend = monthlyCost && lastMonthCost
              ? ((monthlyCost - lastMonthCost) / lastMonthCost) * 100
              : 0;
            const lastImportLabel = account.last_import_at
              ? new Date(account.last_import_at * 1000).toLocaleString()
              : 'Never';
            const importOk = account.last_import_at
              ? (Date.now() / 1000 - account.last_import_at) < 86400
              : false;

            return (
              <Col xs={24} md={12} lg={8} key={account.id}>
                <Card
                  hoverable
                  onClick={() => navigate(`/cloud-accounts/${account.id}`)}
                  style={{ height: '100%' }}
                  extra={
                    <Space>
                      <Tooltip title="Refresh data">
                        <Button
                          type="text"
                          icon={<ReloadOutlined spin={refreshingAccount === account.id} />}
                          size="small"
                          onClick={(e) => handleRefreshAccount(account.id, e)}
                          loading={refreshingAccount === account.id}
                        />
                      </Tooltip>
                      <Popconfirm
                        title="Delete Data Source"
                        description={`Are you sure you want to delete "${account.name}"? This action cannot be undone.`}
                        onConfirm={(e) => {
                          e?.stopPropagation();
                          confirmDelete(account.id);
                        }}
                        onCancel={(e) => e?.stopPropagation()}
                        okText="Delete"
                        cancelText="Cancel"
                        okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
                      >
                        <Button
                          type="text"
                          danger
                          icon={<DeleteOutlined />}
                          size="small"
                          onClick={(e) => e.stopPropagation()}
                        />
                      </Popconfirm>
                    </Space>
                  }
                >
                  <Space direction="vertical" size={12} style={{ width: '100%' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: '50%',
                          backgroundColor: CLOUD_TYPE_COLORS[account.type] || '#999',
                          flexShrink: 0,
                        }}
                      />
                      <Text strong style={{ fontSize: 16 }}>{account.name}</Text>
                    </div>

                    <Text
                      type="secondary"
                      style={{ fontFamily: 'monospace', fontSize: 12 }}
                      copyable
                    >
                      {account.account_id || account.id}
                    </Text>

                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                      <Text style={{ fontSize: 24, fontWeight: 600 }}>
                        {dataSource === 'unavailable' ? '—' : formatCurrency(monthlyCost)}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>/month</Text>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Space size={4}>
                        {importOk ? (
                          <CheckCircleOutlined style={{ color: '#52c41a' }} />
                        ) : (
                          <WarningOutlined style={{ color: '#faad14' }} />
                        )}
                        <Text type="secondary" style={{ fontSize: 13 }}>
                          {lastImportLabel}
                        </Text>
                      </Space>
                      <Space>
                        {dataSource === 'cache' && (
                          <Tooltip title="Data from cache">
                            <Badge status="processing" text="Cached" />
                          </Tooltip>
                        )}
                        {dataSource === 'unavailable' && (
                          <Tooltip title="Live data unavailable - may be due to timeout or connection issue">
                            <Badge status="warning" text="Unavailable" />
                          </Tooltip>
                        )}
                        <Tag>{dataSource === 'unavailable' ? '—' : `${resourcesCount} resources`}</Tag>
                      </Space>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {CLOUD_TYPE_LABELS[account.type] || account.type}
                      </Text>
                      {trend !== 0 && (
                        <Text
                          style={{
                            fontSize: 13,
                            color: trend >= 0 ? '#ff4d4f' : '#52c41a',
                          }}
                        >
                          {trend >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                          {' '}
                          {trend >= 0 ? '+' : ''}{trend.toFixed(1)}% vs last month
                        </Text>
                      )}
                    </div>
                  </Space>
                </Card>
              </Col>
            );
          })
        )}
      </Row>
    </div>
  );
};

export default CloudAccounts;
