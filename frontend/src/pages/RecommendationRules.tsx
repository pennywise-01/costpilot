import React, { useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  recommendationRulesApi,
  type RecRuleResponse,
  type RecRuleCreate,
  type RecRuleUpdate,
} from '@/api/recommendationRules';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';

const { Title } = Typography;

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'gold',
  low: 'green',
};

const CONDITION_TYPE_OPTIONS = [
  { value: 'name_is', label: 'Name is' },
  { value: 'name_starts_with', label: 'Name starts with' },
  { value: 'name_ends_with', label: 'Name ends with' },
  { value: 'name_contains', label: 'Name contains' },
  { value: 'resource_type_is', label: 'Resource type is' },
  { value: 'cloud_is', label: 'Cloud is' },
  { value: 'tag_is', label: 'Tag is' },
  { value: 'region_is', label: 'Region is' },
  { value: 'tag_exists', label: 'Tag exists' },
  { value: 'tag_value_starts_with', label: 'Tag value starts with' },
];

const RecommendationRules: React.FC = () => {
  const queryClient = useQueryClient();
  const orgId = useCurrentOrgId();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<RecRuleResponse | null>(null);
  const [form] = Form.useForm();

  const { data: rulesResponse = [], isLoading } = useQuery({
    queryKey: ['recommendation-rules', orgId],
    queryFn: async () => {
      const res = await recommendationRulesApi.list(orgId);
      return res.data;
    },
  });

  // Extract items array from paginated response (fallback to plain array for backward compat)
  const rules: RecRuleResponse[] = Array.isArray(rulesResponse)
    ? rulesResponse
    : (rulesResponse as { items?: RecRuleResponse[] })?.items ?? [];

  const createMutation = useMutation({
    mutationFn: (data: RecRuleCreate) => recommendationRulesApi.create(orgId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendation-rules'] });
      message.success('Rule created');
      closeModal();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: RecRuleUpdate }) =>
      recommendationRulesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendation-rules'] });
      message.success('Rule updated');
      closeModal();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => recommendationRulesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendation-rules'] });
      message.success('Rule deleted');
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      recommendationRulesApi.update(id, { active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendation-rules'] });
    },
  });

  const closeModal = () => {
    setModalOpen(false);
    setEditingRule(null);
    form.resetFields();
  };

  const openCreate = () => {
    setEditingRule(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (rule: RecRuleResponse) => {
    setEditingRule(rule);
    form.setFieldsValue({
      name: rule.name,
      description: rule.description,
      category: rule.category,
      severity: rule.severity,
      action_description: rule.action_description,
      saving_type: rule.saving_type,
      saving_value: rule.saving_value,
      active: rule.active,
      conditions: rule.conditions.map((c) => ({ type: c.type, meta_info: c.meta_info })),
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (editingRule) {
      updateMutation.mutate({ id: editingRule.id, data: values });
    } else {
      createMutation.mutate(values);
    }
  };

  const columns: ColumnsType<RecRuleResponse> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: 'Category',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (cat: string) => (
        <Tag color={cat === 'cost' ? 'blue' : 'red'}>
          {cat === 'cost' ? 'Cost' : 'Security'}
        </Tag>
      ),
    },
    {
      title: 'Severity',
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (sev: string) => (
        <Tag color={SEVERITY_COLORS[sev] || 'default'} style={{ textTransform: 'capitalize' }}>
          {sev}
        </Tag>
      ),
    },
    {
      title: 'Saving',
      key: 'saving',
      width: 140,
      render: (_: unknown, record: RecRuleResponse) =>
        record.saving_type === 'fixed'
          ? `$${record.saving_value.toFixed(2)}`
          : `${record.saving_value}%`,
    },
    {
      title: 'Conditions',
      key: 'conditions',
      width: 100,
      align: 'center',
      render: (_: unknown, record: RecRuleResponse) => record.conditions.length,
    },
    {
      title: 'Active',
      key: 'active',
      width: 80,
      align: 'center',
      render: (_: unknown, record: RecRuleResponse) => (
        <Switch
          size="small"
          checked={record.active}
          onChange={(checked) => toggleActiveMutation.mutate({ id: record.id, active: checked })}
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      align: 'center',
      render: (_: unknown, record: RecRuleResponse) => (
        <Space size={4}>
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm
            title="Delete this rule?"
            onConfirm={() => deleteMutation.mutate(record.id)}
            okText="Delete"
            okButtonProps={{ danger: true }}
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          <SafetyCertificateOutlined style={{ marginRight: 8 }} />
          Recommendation Rules
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Create Rule
        </Button>
      </div>

      <Card styles={{ body: { padding: 0 } }}>
        <Table<RecRuleResponse>
          dataSource={rules}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          pagination={{ pageSize: 20 }}
        />
      </Card>

      <Modal
        title={editingRule ? 'Edit Rule' : 'Create Rule'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={closeModal}
        okText={editingRule ? 'Save' : 'Create'}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
        width={640}
        destroyOnHidden
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            category: 'cost',
            severity: 'medium',
            saving_type: 'fixed',
            saving_value: 0,
            active: true,
            conditions: [],
          }}
        >
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Name is required' }]}>
            <Input placeholder="e.g. Terminate idle GPU instances" />
          </Form.Item>

          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} placeholder="What does this rule check for?" />
          </Form.Item>

          <Space size={16} style={{ width: '100%' }}>
            <Form.Item name="category" label="Category">
              <Select style={{ width: 140 }}>
                <Select.Option value="cost">Cost</Select.Option>
                <Select.Option value="security">Security</Select.Option>
              </Select>
            </Form.Item>

            <Form.Item name="severity" label="Severity">
              <Select style={{ width: 140 }}>
                <Select.Option value="critical">Critical</Select.Option>
                <Select.Option value="high">High</Select.Option>
                <Select.Option value="medium">Medium</Select.Option>
                <Select.Option value="low">Low</Select.Option>
              </Select>
            </Form.Item>
          </Space>

          <Form.Item name="action_description" label="Action Description">
            <Input.TextArea rows={2} placeholder="What action should be taken?" />
          </Form.Item>

          <Space size={16} style={{ width: '100%' }}>
            <Form.Item name="saving_type" label="Saving Type">
              <Select style={{ width: 140 }}>
                <Select.Option value="fixed">Fixed ($)</Select.Option>
                <Select.Option value="percentage">Percentage (%)</Select.Option>
              </Select>
            </Form.Item>

            <Form.Item name="saving_value" label="Saving Value">
              <InputNumber min={0} style={{ width: 140 }} />
            </Form.Item>
          </Space>

          <Form.Item name="active" label="Active" valuePropName="checked">
            <Switch />
          </Form.Item>

          <Form.List name="conditions">
            {(fields, { add, remove }) => (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <Typography.Text strong>Conditions</Typography.Text>
                  <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => add()}>
                    Add Condition
                  </Button>
                </div>
                {fields.map(({ key, name, ...restField }) => (
                  <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="start">
                    <Form.Item
                      {...restField}
                      name={[name, 'type']}
                      rules={[{ required: true, message: 'Required' }]}
                    >
                      <Select placeholder="Condition type" style={{ width: 200 }} options={CONDITION_TYPE_OPTIONS} />
                    </Form.Item>
                    <Form.Item {...restField} name={[name, 'meta_info']}>
                      <Input placeholder="Value (optional)" style={{ width: 200 }} />
                    </Form.Item>
                    <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(name)} />
                  </Space>
                ))}
              </div>
            )}
          </Form.List>
        </Form>
      </Modal>
    </div>
  );
};

export default RecommendationRules;
