import React from 'react';
import { Drawer, Form, Input, Select, InputNumber, Switch, Button, Space } from 'antd';
import { WIDGET_REGISTRY, METRIC_OPTIONS_BY_TYPE, COLOR_OPTIONS } from './widgetRegistry';
import type { WidgetConfigEntry } from '@/api/dashboards';

interface WidgetConfigDrawerProps {
  open: boolean;
  widgetId: string | null;
  config: WidgetConfigEntry | null;
  onSave: (widgetId: string, config: WidgetConfigEntry) => void;
  onClose: () => void;
}

const WidgetConfigDrawer: React.FC<WidgetConfigDrawerProps> = ({
  open,
  widgetId,
  config,
  onSave,
  onClose,
}) => {
  const [form] = Form.useForm();

  if (!config || !widgetId) return null;

  const definition = WIDGET_REGISTRY[config.type];
  const editableFields = definition?.editableFields ?? [];
  const metricOptions = METRIC_OPTIONS_BY_TYPE[config.type] ?? [];

  const handleSave = () => {
    const values = form.getFieldsValue();
    const updated: WidgetConfigEntry = {
      ...config,
      ...values,
    };
    onSave(widgetId, updated);
    onClose();
  };

  return (
    <Drawer
      title="Configure Widget"
      open={open}
      onClose={onClose}
      width={360}
      extra={
        <Space>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="primary" onClick={handleSave}>Save</Button>
        </Space>
      }
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={config}
      >
        {editableFields.includes('title') && (
          <Form.Item name="title" label="Title">
            <Input />
          </Form.Item>
        )}

        {editableFields.includes('metric') && (
          <Form.Item name="metric" label="Metric">
            <Select options={metricOptions} />
          </Form.Item>
        )}

        {editableFields.includes('color') && (
          <Form.Item name="color" label="Color">
            <Select
              options={COLOR_OPTIONS.map((c) => ({
                value: c.value,
                label: (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 16, height: 16, borderRadius: 4, backgroundColor: c.value, display: 'inline-block' }} />
                    {c.label}
                  </span>
                ),
              }))}
            />
          </Form.Item>
        )}

        {editableFields.includes('icon') && (
          <Form.Item name="icon" label="Icon">
            <Select
              options={[
                'DollarOutlined', 'FundOutlined', 'CalendarOutlined', 'ThunderboltOutlined',
                'CloudServerOutlined', 'HddOutlined', 'BulbOutlined',
              ].map((i) => ({ value: i, label: i }))}
            />
          </Form.Item>
        )}

        {editableFields.includes('dateRange') && (
          <Form.Item name="dateRange" label="Date Range (days)">
            <InputNumber min={1} max={365} />
          </Form.Item>
        )}

        {editableFields.includes('groupBy') && (
          <Form.Item name="groupBy" label="Group By">
            <Select options={[
              { value: 'cloud', label: 'Cloud' },
              { value: 'service', label: 'Service' },
              { value: 'region', label: 'Region' },
            ]} />
          </Form.Item>
        )}

        {editableFields.includes('smooth') && (
          <Form.Item name="smooth" label="Smooth Lines" valuePropName="checked">
            <Switch />
          </Form.Item>
        )}
      </Form>
    </Drawer>
  );
};

export default WidgetConfigDrawer;
