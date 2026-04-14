import React from 'react';
import { Card, Spin, Empty, Button, Tooltip, Typography, Space } from 'antd';
import {
  SettingOutlined,
  DeleteOutlined,
  ReloadOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { WIDGET_REGISTRY } from '../widgetRegistry';

const { Text } = Typography;

interface WidgetShellProps {
  widgetId: string;
  config: {
    type: string;
    metric: string;
    title?: string;
    [key: string]: unknown;
  };
  loading?: boolean;
  error?: string | null;
  editMode?: boolean;
  onRemove?: () => void;
  onConfigure?: () => void;
  onRetry?: () => void;
  children: React.ReactNode;
}

const WidgetShell: React.FC<WidgetShellProps> = ({
  widgetId,
  config,
  loading = false,
  error = null,
  editMode = false,
  onRemove,
  onConfigure,
  onRetry,
  children,
}) => {
  const definition = WIDGET_REGISTRY[config.type];
  const title = config.title || definition?.label || config.metric;

  return (
    <Card
      title={
        <Space size={8}>
          {definition?.icon}
          <Text strong style={{ fontSize: 14 }}>{title}</Text>
        </Space>
      }
      extra={
        editMode ? (
          <Space size={4}>
            <Tooltip title="Configure">
              <Button
                type="text"
                size="small"
                icon={<SettingOutlined />}
                onClick={onConfigure}
              />
            </Tooltip>
            <Tooltip title="Remove">
              <Button
                type="text"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={onRemove}
              />
            </Tooltip>
          </Space>
        ) : null
      }
      style={{
        borderRadius: 12,
        height: '100%',
        overflow: 'hidden',
      }}
      styles={{
        body: {
          padding: '12px 16px',
          overflow: 'auto',
          height: 'calc(100% - 57px)',
        },
      }}
    >
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <Spin />
        </div>
      ) : error ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 8 }}>
          <ExclamationCircleOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
          <Text type="secondary">Data unavailable</Text>
          {onRetry && (
            <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
              Retry
            </Button>
          )}
        </div>
      ) : (
        children
      )}
    </Card>
  );
};

export default WidgetShell;
