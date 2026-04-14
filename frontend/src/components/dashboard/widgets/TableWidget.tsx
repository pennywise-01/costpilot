import React, { useMemo } from 'react';
import { Table, Tag, Empty, Typography, Space } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import WidgetShell from './WidgetShell';

const { Text } = Typography;

const CLOUD_TAG_COLORS: Record<string, string> = {
  aws_cnr: 'orange',
  azure_cnr: 'blue',
  gcp_cnr: 'green',
  AWS: 'orange',
  Azure: 'blue',
  GCP: 'green',
};

const CLOUD_NAMES: Record<string, string> = {
  aws_cnr: 'AWS',
  azure_cnr: 'Azure',
  gcp_cnr: 'GCP',
};

interface TableWidgetProps {
  widgetId: string;
  config: { type: string; metric: string; title?: string; [key: string]: unknown };
  data?: Record<string, unknown>;
  loading?: boolean;
  error?: string | null;
  editMode?: boolean;
  onRemove?: () => void;
  onConfigure?: () => void;
  onRetry?: () => void;
}

const TableWidget: React.FC<TableWidgetProps> = ({
  widgetId, config, data, loading, error, editMode, onRemove, onConfigure, onRetry,
}) => {
  const metric = config.metric || 'top_resources';

  const { columns, dataSource } = useMemo(() => {
    if (metric === 'top_resources') {
      const resources = (data?.resources as any[]) ?? [];
      const cols: ColumnsType<any> = [
        {
          title: 'Resource',
          dataIndex: 'name',
          key: 'name',
          render: (name: string, record: any) => (
            <Space>
              <Tag color={CLOUD_TAG_COLORS[record.cloud_type] || 'default'} style={{ marginRight: 0, minWidth: 44, textAlign: 'center' }}>
                {CLOUD_NAMES[record.cloud_type] || record.cloud_type || '?'}
              </Tag>
              <Text strong style={{ fontSize: 13 }}>{name}</Text>
            </Space>
          ),
        },
        {
          title: 'Daily Cost',
          dataIndex: 'daily_cost',
          key: 'daily_cost',
          align: 'right',
          render: (v: number) => <Text strong style={{ color: '#1677ff' }}>${(v || 0).toFixed(2)}</Text>,
        },
      ];
      return { columns: cols, dataSource: resources.slice(0, 10).map((r, i) => ({ ...r, key: r.id || i })) };
    }

    if (metric === 'cloud_accounts') {
      const accounts = (data?.accounts as any[]) ?? [];
      const cols: ColumnsType<any> = [
        { title: 'Name', dataIndex: 'name', key: 'name', render: (n: string) => <Text strong>{n}</Text> },
        { title: 'Type', dataIndex: 'type', key: 'type', render: (t: string) => <Tag color={CLOUD_TAG_COLORS[t] || 'default'}>{CLOUD_NAMES[t] || t}</Tag> },
      ];
      return { columns: cols, dataSource: accounts.map((a, i) => ({ ...a, key: a.id || i })) };
    }

    if (metric === 'recommendations') {
      const recs = (data?.recommendations as any[]) ?? [];
      const cols: ColumnsType<any> = [
        { title: 'Name', dataIndex: 'name', key: 'name', render: (n: string) => <Text strong>{n}</Text> },
        { title: 'Count', dataIndex: 'count', key: 'count', align: 'right' },
        { title: 'Savings', dataIndex: 'saving', key: 'saving', align: 'right', render: (v: number) => <Text style={{ color: '#52c41a' }}>${(v || 0).toFixed(0)}</Text> },
      ];
      return { columns: cols, dataSource: recs.map((r, i) => ({ ...r, key: r.type || i })) };
    }

    return { columns: [], dataSource: [] };
  }, [data, metric]);

  return (
    <WidgetShell widgetId={widgetId} config={config} loading={loading} error={error} editMode={editMode} onRemove={onRemove} onConfigure={onConfigure} onRetry={onRetry}>
      {dataSource.length > 0 ? (
        <Table columns={columns} dataSource={dataSource} pagination={false} size="small" />
      ) : (
        <Empty description="No data available" style={{ padding: '20px 0' }} />
      )}
    </WidgetShell>
  );
};

export default TableWidget;
