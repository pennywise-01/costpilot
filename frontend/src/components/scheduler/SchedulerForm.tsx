import React, { useEffect } from 'react';
import {
  Form,
  Input,
  Select,
  Checkbox,
  Button,
  Space,
  Divider,
  Radio,
  InputNumber,
  DatePicker,
  message,
} from 'antd';
import type { FormInstance } from 'antd/es/form';
import { useCurrentOrgId } from '../../hooks/useCurrentOrgId';
import { schedulerApi } from '../../api/scheduler';
import type { SchedulerConfig, SchedulerConfigCreate } from '../../types/scheduler';
import {
  SCHEDULE_TYPE_OPTIONS,
  COMMON_INTERVALS,
  COMMON_CRON_EXPRESSIONS,
  TIMEZONE_OPTIONS,
} from '../../types/scheduler';
import dayjs from 'dayjs';

const { TextArea } = Input;
const { Option } = Select;

interface SchedulerFormProps {
  scheduler?: SchedulerConfig | null;
  onSuccess: () => void;
  onCancel: () => void;
}

const SchedulerForm: React.FC<SchedulerFormProps> = ({
  scheduler,
  onSuccess,
  onCancel,
}) => {
  const [form] = Form.useForm();
  const orgId = useCurrentOrgId();
  const isEditing = !!scheduler;

  useEffect(() => {
    if (scheduler) {
      form.setFieldsValue({
        name: scheduler.name,
        description: scheduler.description,
        collect_expenses: scheduler.collect_expenses,
        collect_resources: scheduler.collect_resources,
        collect_recommendations: scheduler.collect_recommendations,
        schedule_type: scheduler.schedule_type,
        interval_minutes: scheduler.interval_minutes,
        cron_expression: scheduler.cron_expression,
        timezone: scheduler.timezone,
        start_date: scheduler.start_date ? dayjs(scheduler.start_date) : null,
        end_date: scheduler.end_date ? dayjs(scheduler.end_date) : null,
        max_consecutive_failures: scheduler.max_consecutive_failures,
      });
    } else {
      form.resetFields();
      form.setFieldsValue({
        schedule_type: 'interval',
        interval_minutes: 60,
        timezone: 'UTC',
        max_consecutive_failures: 3,
        collect_expenses: true,
        collect_resources: true,
        collect_recommendations: true,
      });
    }
  }, [scheduler, form]);

  const handleSubmit = async (values: any) => {
    if (!orgId) {
      message.error('No organization selected');
      return;
    }

    try {
      const data: SchedulerConfigCreate = {
        name: values.name,
        description: values.description,
        collect_expenses: values.collect_expenses,
        collect_resources: values.collect_resources,
        collect_recommendations: values.collect_recommendations,
        schedule_type: values.schedule_type,
        interval_minutes: values.interval_minutes,
        cron_expression: values.cron_expression,
        timezone: values.timezone,
        start_date: values.start_date?.toISOString(),
        end_date: values.end_date?.toISOString(),
        max_consecutive_failures: values.max_consecutive_failures,
      };

      if (isEditing && scheduler) {
        await schedulerApi.updateScheduler(orgId, scheduler.id, data);
        message.success('Scheduler updated successfully');
      } else {
        await schedulerApi.createScheduler(orgId, data);
        message.success('Scheduler created successfully');
      }

      onSuccess();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to save scheduler');
    }
  };

  const scheduleType = Form.useWatch('schedule_type', form);

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleSubmit}
      initialValues={{
        schedule_type: 'interval',
        interval_minutes: 60,
        timezone: 'UTC',
        max_consecutive_failures: 3,
      }}
    >
      <Form.Item
        name="name"
        label="Name"
        rules={[{ required: true, message: 'Please enter a name' }]}
      >
        <Input placeholder="e.g., Hourly Data Collection" />
      </Form.Item>

      <Form.Item name="description" label="Description">
        <TextArea
          rows={2}
          placeholder="Optional description of this scheduler"
        />
      </Form.Item>

      <Divider>Data Types to Collect</Divider>

      <Form.Item label="Select data types to collect">
        <Space direction="vertical">
          <Form.Item
            name="collect_expenses"
            valuePropName="checked"
            noStyle
          >
            <Checkbox>Expenses (Cost data from CSP billing APIs)</Checkbox>
          </Form.Item>
          <Form.Item
            name="collect_resources"
            valuePropName="checked"
            noStyle
          >
            <Checkbox>Resources (Cloud resource inventory)</Checkbox>
          </Form.Item>
          <Form.Item
            name="collect_recommendations"
            valuePropName="checked"
            noStyle
          >
            <Checkbox>Recommendations (Cost optimization recommendations)</Checkbox>
          </Form.Item>
        </Space>
      </Form.Item>

      <Divider>Schedule Configuration</Divider>

      <Form.Item
        name="schedule_type"
        label="Schedule Type"
        rules={[{ required: true }]}
      >
        <Radio.Group>
          <Space direction="vertical">
            {SCHEDULE_TYPE_OPTIONS.map((option) => (
              <Radio key={option.value} value={option.value}>
                <Space direction="vertical" size={0}>
                  <span>{option.label}</span>
                  <span style={{ fontSize: 12, color: '#666' }}>
                    {option.description}
                  </span>
                </Space>
              </Radio>
            ))}
          </Space>
        </Radio.Group>
      </Form.Item>

      {scheduleType === 'interval' && (
        <Form.Item
          name="interval_minutes"
          label="Interval"
          rules={[{ required: true, message: 'Please select an interval' }]}
        >
          <Select placeholder="Select interval">
            {COMMON_INTERVALS.map((interval) => (
              <Option key={interval.value} value={interval.value}>
                {interval.label}
              </Option>
            ))}
          </Select>
        </Form.Item>
      )}

      {scheduleType === 'cron' && (
        <Form.Item
          name="cron_expression"
          label="Cron Expression"
          rules={[{ required: true, message: 'Please enter a cron expression' }]}
          extra={
            <div style={{ marginTop: 8 }}>
              <div style={{ marginBottom: 8 }}>Common expressions:</div>
              <Select
                style={{ width: '100%' }}
                placeholder="Select a common expression"
                onChange={(value) => form.setFieldValue('cron_expression', value)}
                allowClear
              >
                {COMMON_CRON_EXPRESSIONS.map((expr) => (
                  <Option key={expr.value} value={expr.value}>
                    {expr.label} ({expr.value})
                  </Option>
                ))}
              </Select>
            </div>
          }
        >
          <Input placeholder="e.g., 0 */6 * * *" />
        </Form.Item>
      )}

      {scheduleType === 'once' && (
        <Form.Item
          name="start_date"
          label="Run Date/Time"
          rules={[{ required: true, message: 'Please select a date and time' }]}
        >
          <DatePicker
            showTime
            style={{ width: '100%' }}
            placeholder="Select date and time"
          />
        </Form.Item>
      )}

      <Form.Item
        name="timezone"
        label="Timezone"
        rules={[{ required: true }]}
      >
        <Select placeholder="Select timezone">
          {TIMEZONE_OPTIONS.map((tz) => (
            <Option key={tz} value={tz}>
              {tz}
            </Option>
          ))}
        </Select>
      </Form.Item>

      {scheduleType !== 'once' && (
        <>
          <Form.Item name="start_date" label="Start Date (Optional)">
            <DatePicker
              showTime
              style={{ width: '100%' }}
              placeholder="When to start scheduling"
            />
          </Form.Item>

          <Form.Item name="end_date" label="End Date (Optional)">
            <DatePicker
              showTime
              style={{ width: '100%' }}
              placeholder="When to stop scheduling"
            />
          </Form.Item>
        </>
      )}

      <Form.Item
        name="max_consecutive_failures"
        label="Max Consecutive Failures"
        extra="Automatically disable scheduler after this many consecutive failures"
        rules={[{ required: true, message: 'Please enter max consecutive failures' }]}
      >
        <InputNumber min={1} max={10} style={{ width: '100%' }} />
      </Form.Item>

      <Form.Item>
        <Space>
          <Button type="primary" htmlType="submit">
            {isEditing ? 'Update Scheduler' : 'Create Scheduler'}
          </Button>
          <Button onClick={onCancel}>Cancel</Button>
        </Space>
      </Form.Item>
    </Form>
  );
};

export default SchedulerForm;
