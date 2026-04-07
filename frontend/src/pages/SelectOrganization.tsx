import React, { useEffect, useState } from 'react';
import { Card, Typography, Button, Form, Input, Select, Spin, Row, Col, Space, Tag, message } from 'antd';
import { PlusOutlined, BankOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { organizationsApi } from '@/api/organizations';
import { useOrgStore, type OrgWithRole } from '@/store/orgStore';

const { Title, Text } = Typography;

const SelectOrganization: React.FC = () => {
  const { setCurrentOrg, setOrganizations } = useOrgStore();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [form] = Form.useForm();
  const queryClient = useQueryClient();

  const { data: orgs, isLoading } = useQuery({
    queryKey: ['organizations'],
    queryFn: async () => {
      const res = await organizationsApi.list();
      return res.data as OrgWithRole[];
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: { name: string; currency?: string }) =>
      organizationsApi.create(data),
    onSuccess: async (createdOrgResponse) => {
      const res = await organizationsApi.list();
      const nextOrgs = res.data as OrgWithRole[];
      setOrganizations(nextOrgs);
      const createdOrg = nextOrgs.find((org) => org.id === createdOrgResponse.data.id);
      if (createdOrg) {
        setCurrentOrg(createdOrg);
      }
      queryClient.setQueryData(['organizations'], nextOrgs);
      form.resetFields();
      setShowCreateForm(false);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || 'Failed to create organization';
      message.error(detail);
    },
  });

  // Auto-select if user has exactly 1 org
  useEffect(() => {
    if (orgs && orgs.length === 1) {
      setOrganizations(orgs);
      setCurrentOrg(orgs[0]);
    }
  }, [orgs, setCurrentOrg, setOrganizations]);

  const handleSelectOrg = (org: OrgWithRole) => {
    if (orgs) {
      setOrganizations(orgs);
    }
    setCurrentOrg(org);
  };

  const handleCreate = async (values: { name: string; currency: string }) => {
    await createMutation.mutateAsync(values);
  };

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  // If auto-selected (1 org), show loading while redirect happens
  if (orgs && orgs.length === 1) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: '#f5f5f5',
      padding: 24,
    }}>
      <div style={{ maxWidth: 700, width: '100%' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Title level={2}>
            {orgs && orgs.length > 0 ? 'Select an Organization' : 'Create Your Organization'}
          </Title>
          <Text type="secondary">
            {orgs && orgs.length > 0
              ? 'Choose an organization to continue'
              : 'Get started by creating your first organization'}
          </Text>
        </div>

        {orgs && orgs.length > 0 && (
          <Row gutter={[16, 16]}>
            {orgs.map((org) => (
              <Col xs={24} sm={12} key={org.id}>
                <Card
                  hoverable
                  onClick={() => handleSelectOrg(org)}
                  style={{ cursor: 'pointer' }}
                >
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Space>
                      <BankOutlined style={{ fontSize: 20, color: '#1677ff' }} />
                      <Text strong style={{ fontSize: 16 }}>{org.name}</Text>
                    </Space>
                    <Space>
                      <Tag color="blue">{org.currency}</Tag>
                      <Tag>{org.role.replace('optscale_', '')}</Tag>
                    </Space>
                  </Space>
                </Card>
              </Col>
            ))}
            <Col xs={24} sm={12}>
              <Card
                hoverable
                onClick={() => setShowCreateForm(true)}
                style={{
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minHeight: 88,
                  borderStyle: 'dashed',
                }}
              >
                <Space>
                  <PlusOutlined />
                  <Text>Create new organization</Text>
                </Space>
              </Card>
            </Col>
          </Row>
        )}

        {(showCreateForm || !orgs || orgs.length === 0) && (
          <Card style={{ marginTop: orgs && orgs.length > 0 ? 24 : 0 }}>
            <Title level={4}>Create Organization</Title>
            <Form
              form={form}
              layout="vertical"
              onFinish={handleCreate}
              initialValues={{ currency: 'USD' }}
            >
              <Form.Item
                name="name"
                label="Organization Name"
                rules={[{ required: true, message: 'Please enter an organization name' }]}
              >
                <Input placeholder="My Company" maxLength={256} />
              </Form.Item>
              <Form.Item name="currency" label="Currency">
                <Select>
                  <Select.Option value="USD">USD</Select.Option>
                  <Select.Option value="EUR">EUR</Select.Option>
                  <Select.Option value="GBP">GBP</Select.Option>
                  <Select.Option value="JPY">JPY</Select.Option>
                </Select>
              </Form.Item>
              <Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
                    Create
                  </Button>
                  {orgs && orgs.length > 0 && (
                    <Button onClick={() => setShowCreateForm(false)}>Cancel</Button>
                  )}
                </Space>
              </Form.Item>
            </Form>
          </Card>
        )}
      </div>
    </div>
  );
};

export default SelectOrganization;
