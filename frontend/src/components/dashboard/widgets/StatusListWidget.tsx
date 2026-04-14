import React, { useMemo } from 'react';
import { Space, Typography, Empty, Badge } from 'antd';
import { CloudServerOutlined } from '@ant-design/icons';
import WidgetShell from './WidgetShell';

const { Text } = Typography;

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

interface StatusListWidgetProps {
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

const StatusListWidget: React.FC<StatusListWidgetProps> = ({
  widgetId, config, data, loading, error, editMode, onRemove, onConfigure, onRetry,
}) => {
  const accounts = useMemo(() => {
    const raw = (data?.accounts as { id: string; name: string; type: string }[]) ?? [];
    return raw.map((a) => ({
      ...a,
      shortName: CLOUD_NAMES[a.type] || a.type,
      color: CLOUD_COLORS[a.type] || '#888',
    }));
  }, [data]);

  return (
    <WidgetShell widgetId={widgetId} config={config} loading={loading} error={error} editMode={editMode} onRemove={onRemove} onConfigure={onConfigure} onRetry={onRetry}>
      {accounts.length > 0 ? (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {accounts.map((account, idx) => (
            <div
              key={account.id || idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '14px 16px',
                borderRadius: 10,
                border: '1px solid #f0f0f0',
                background: '#fafafa',
              }}
            >
              <Space size={12}>
                <div style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  backgroundColor: account.color + '18',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <CloudServerOutlined style={{ fontSize: 20, color: account.color }} />
                </div>
                <div>
                  <Text strong style={{ fontSize: 14, display: 'block' }}>{account.name}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>{account.shortName}</Text>
                </div>
              </Space>
              <Badge status="success" text={<Text type="secondary" style={{ fontSize: 12 }}>Connected</Text>} />
            </div>
          ))}
        </Space>
      ) : (
        <Empty description="No cloud accounts connected" style={{ padding: '20px 0' }} />
      )}
    </WidgetShell>
  );
};

export default StatusListWidget;
