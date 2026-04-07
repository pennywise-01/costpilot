import { useState, useEffect, useCallback } from 'react';
import {
  Typography,
  Card,
  Tabs,
  Table,
  Tag,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Switch,
  Space,
  Statistic,
  Row,
  Col,
  message,
  Popconfirm,
  Tooltip,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  SafetyCertificateOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  KeyOutlined,
  AuditOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { rbacApi } from '@/api/rbac';
import type {
  Role,
  ABACPolicy,
  AccessReview,
  UserRoleAssignment,
  SSOConfig,
  RBACOverview,
} from '@/api/rbac';
import { userManagementApi } from '@/api/userManagement';
import type { User as OrganizationUser } from '@/api/userManagement';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';

const { Title, Text } = Typography;

const RESOURCE_TYPES = [
  'organization', 'cloud_account', 'pool', 'expense',
  'resource', 'recommendation', 'rule', 'user', 'notification', 'enterprise',
];

const ACTIONS = ['read', 'create', 'update', 'delete', 'manage'];

const OPERATORS = ['equals', 'not_equals', 'in', 'not_in', 'contains', 'starts_with'];

const SYSTEM_ROLE_LABEL = 'System';

const RBAC: React.FC = () => {
  const orgId = useCurrentOrgId();
  const [overview, setOverview] = useState<RBACOverview | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [assignments, setAssignments] = useState<UserRoleAssignment[]>([]);
  const [orgUsers, setOrgUsers] = useState<OrganizationUser[]>([]);
  const [policies, setPolicies] = useState<ABACPolicy[]>([]);
  const [reviews, setReviews] = useState<AccessReview[]>([]);
  const [ssoConfigs, setSSOConfigs] = useState<SSOConfig[]>([]);
  const [loading, setLoading] = useState(false);

  // Modals
  const [roleModalOpen, setRoleModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [policyModalOpen, setPolicyModalOpen] = useState(false);
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [ssoModalOpen, setSSOModalOpen] = useState(false);

  const [roleForm] = Form.useForm();
  const [policyForm] = Form.useForm();
  const [assignForm] = Form.useForm();
  const [ssoForm] = Form.useForm();

  const fetchAll = useCallback(async () => {
    if (!orgId) {
      return;
    }

    setLoading(true);
    try {
      const [overviewRes, rolesRes, assignRes, policiesRes, reviewsRes, ssoRes, usersRes] = await Promise.all([
        rbacApi.getOverview(orgId).catch(() => null),
        rbacApi.listRoles(orgId).catch(() => null),
        rbacApi.listAssignments(orgId).catch(() => null),
        rbacApi.listPolicies(orgId).catch(() => null),
        rbacApi.listReviews(orgId).catch(() => null),
        rbacApi.listSSOConfigs(orgId).catch(() => null),
        userManagementApi
          .listUsers(orgId, { page: 1, limit: 100 })
          .catch((error) => {
            console.error('Failed to load organization users for role assignment', error);
            return null;
          }),
      ]);
      if (overviewRes) setOverview(overviewRes.data);
      // Extract items from paginated responses (fallback to plain array for backward compat)
      if (rolesRes) {
        const rolesData = rolesRes.data;
        setRoles(Array.isArray(rolesData) ? rolesData : (rolesData as { items?: Role[] })?.items ?? []);
      }
      if (assignRes) {
        const assignData = assignRes.data;
        setAssignments(Array.isArray(assignData) ? assignData : (assignData as { items?: UserRoleAssignment[] })?.items ?? []);
      }
      if (policiesRes) {
        const policiesData = policiesRes.data;
        setPolicies(Array.isArray(policiesData) ? policiesData : (policiesData as { items?: ABACPolicy[] })?.items ?? []);
      }
      if (reviewsRes) setReviews(reviewsRes.data);
      if (ssoRes) setSSOConfigs(ssoRes.data);
      if (usersRes) setOrgUsers(usersRes.data.items);
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ---- Role CRUD ----
  const handleRoleSave = async () => {
    const values = await roleForm.validateFields();
    const permissions = (values.permissions || []).map((p: string) => {
      const [action, resource_type] = p.split(':');
      return { action, resource_type };
    });
    const payload = {
      name: values.name,
      description: values.description,
      permissions,
    };

    try {
      if (editingRole) {
        await rbacApi.updateRole(orgId, editingRole.id, payload);
        message.success('Role updated');
      } else {
        await rbacApi.createRole(orgId, payload);
        message.success('Role created');
      }
      setRoleModalOpen(false);
      setEditingRole(null);
      roleForm.resetFields();
      fetchAll();
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Failed to save role');
    }
  };

  const handleDeleteRole = async (roleId: string) => {
    try {
      await rbacApi.deleteRole(orgId, roleId);
      message.success('Role deleted');
      fetchAll();
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Failed to delete role');
    }
  };

  const getUserDisplay = (userId: string): string => {
    const user = orgUsers.find((item) => item.id === userId);
    if (!user) {
      return userId;
    }

    return `${user.display_name} (${user.email})`;
  };

  // ---- Assignments ----
  const handleAssign = async () => {
    const values = await assignForm.validateFields();
    try {
      await rbacApi.assignRole(orgId, values);
      message.success('Role assigned');
      setAssignModalOpen(false);
      assignForm.resetFields();
      fetchAll();
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Failed to assign role');
    }
  };

  const handleRevoke = async (id: string) => {
    try {
      await rbacApi.revokeAssignment(orgId, id);
      message.success('Assignment revoked');
      fetchAll();
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Failed to revoke');
    }
  };

  // ---- Policies ----
  const handlePolicySave = async () => {
    const values = await policyForm.validateFields();
    try {
      await rbacApi.createPolicy(orgId, values);
      message.success('Policy created');
      setPolicyModalOpen(false);
      policyForm.resetFields();
      fetchAll();
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Failed to create policy');
    }
  };

  const handleDeletePolicy = async (id: string) => {
    try {
      await rbacApi.deletePolicy(orgId, id);
      message.success('Policy deleted');
      fetchAll();
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Failed to delete policy');
    }
  };

  // ---- Reviews ----
  const handleDecideReview = async (reviewId: string, decision: 'approved' | 'revoked') => {
    try {
      await rbacApi.decideReview(orgId, reviewId, { status: decision });
      message.success(`Review ${decision}`);
      fetchAll();
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Failed to decide review');
    }
  };

  // ---- SSO ----
  const handleSSOSave = async () => {
    const values = await ssoForm.validateFields();
    try {
      await rbacApi.createSSOConfig(orgId, values);
      message.success('SSO config created');
      setSSOModalOpen(false);
      ssoForm.resetFields();
      fetchAll();
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Failed to create SSO config');
    }
  };

  const handleDeleteSSO = async (id: string) => {
    try {
      await rbacApi.deleteSSOConfig(orgId, id);
      message.success('SSO config deleted');
      fetchAll();
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Failed to delete SSO config');
    }
  };

  // ---- Permission options for select ----
  const permissionOptions = ACTIONS.flatMap((action) =>
    RESOURCE_TYPES.map((rt) => ({
      label: `${action}:${rt}`,
      value: `${action}:${rt}`,
    }))
  );

  // ---- Columns ----
  const roleColumns: ColumnsType<Role> = [
    { title: 'Name', dataIndex: 'name', key: 'name', render: (n: string) => <Text strong>{n}</Text> },
    { title: 'Description', dataIndex: 'description', key: 'desc', ellipsis: true },
    {
      title: 'Type',
      dataIndex: 'is_default',
      key: 'default',
      width: 100,
      render: (isDefault: boolean) => (
        <Tag color={isDefault ? 'purple' : 'blue'}>
          {isDefault ? SYSTEM_ROLE_LABEL : 'Custom'}
        </Tag>
      ),
    },
    {
      title: 'Permissions', dataIndex: 'permissions', key: 'perms', width: 120,
      render: (perms: Role['permissions']) => <Tag>{perms.length} permissions</Tag>,
    },
    {
      title: 'Actions', key: 'actions', width: 120,
      render: (_: unknown, record: Role) => (
        record.is_default ? (
          <Text type="secondary">Locked</Text>
        ) : (
        <Space>
          <Tooltip title="Edit">
            <Button type="text" icon={<EditOutlined />} size="small" onClick={() => {
              setEditingRole(record);
              roleForm.setFieldsValue({
                name: record.name,
                description: record.description,
                permissions: record.permissions.map((p) => `${p.action}:${p.resource_type}`),
              });
              setRoleModalOpen(true);
            }} />
          </Tooltip>
          <Popconfirm title="Delete this role?" onConfirm={() => handleDeleteRole(record.id)}>
            <Button type="text" danger icon={<DeleteOutlined />} size="small" />
          </Popconfirm>
        </Space>
        )
      ),
    },
  ];

  const assignColumns: ColumnsType<UserRoleAssignment> = [
    {
      title: 'User',
      dataIndex: 'user_id',
      key: 'uid',
      ellipsis: true,
      render: (userId: string) => getUserDisplay(userId),
    },
    { title: 'Role', key: 'role', render: (_: unknown, r: UserRoleAssignment) => <Tag color="blue">{r.role.name}</Tag> },
    { title: 'Assigned', dataIndex: 'created_at', key: 'at', render: (d: string) => new Date(d).toLocaleDateString() },
    {
      title: 'Actions', key: 'actions', width: 80,
      render: (_: unknown, r: UserRoleAssignment) => (
        <Popconfirm title="Revoke this assignment?" onConfirm={() => handleRevoke(r.id)}>
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  const policyColumns: ColumnsType<ABACPolicy> = [
    { title: 'Name', dataIndex: 'name', key: 'name', render: (n: string) => <Text strong>{n}</Text> },
    { title: 'Resource', dataIndex: 'resource_type', key: 'rt' },
    { title: 'Action', dataIndex: 'action', key: 'action' },
    { title: 'Condition', key: 'cond', render: (_: unknown, r: ABACPolicy) => `${r.attribute_key} ${r.operator} ${r.attribute_value}` },
    { title: 'Effect', key: 'effect', render: (_: unknown, r: ABACPolicy) => <Tag color={r.effect_allow ? 'green' : 'red'}>{r.effect_allow ? 'Allow' : 'Deny'}</Tag> },
    { title: 'Active', dataIndex: 'active', key: 'active', width: 80, render: (v: boolean) => v ? <Tag color="green">Yes</Tag> : <Tag>No</Tag> },
    {
      title: 'Actions', key: 'actions', width: 80,
      render: (_: unknown, r: ABACPolicy) => (
        <Popconfirm title="Delete this policy?" onConfirm={() => handleDeletePolicy(r.id)}>
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  const reviewColumns: ColumnsType<AccessReview> = [
    { title: 'User ID', dataIndex: 'user_id', key: 'uid', ellipsis: true },
    { title: 'Role', key: 'role', render: (_: unknown, r: AccessReview) => <Tag color="blue">{r.role.name}</Tag> },
    {
      title: 'Status', dataIndex: 'status', key: 'status',
      render: (s: string) => (
        <Tag color={s === 'approved' ? 'green' : s === 'revoked' ? 'red' : 'orange'}>{s}</Tag>
      ),
    },
    { title: 'Notes', dataIndex: 'notes', key: 'notes', ellipsis: true },
    {
      title: 'Actions', key: 'actions', width: 160,
      render: (_: unknown, r: AccessReview) =>
        r.status === 'pending' ? (
          <Space>
            <Button type="primary" size="small" icon={<CheckCircleOutlined />} onClick={() => handleDecideReview(r.id, 'approved')}>Approve</Button>
            <Button danger size="small" icon={<CloseCircleOutlined />} onClick={() => handleDecideReview(r.id, 'revoked')}>Revoke</Button>
          </Space>
        ) : '-',
    },
  ];

  const ssoColumns: ColumnsType<SSOConfig> = [
    { title: 'Provider', dataIndex: 'provider', key: 'prov', render: (p: string) => <Tag color="purple">{p.toUpperCase()}</Tag> },
    { title: 'Issuer URL', dataIndex: 'issuer_url', key: 'url', ellipsis: true },
    { title: 'Enabled', dataIndex: 'enabled', key: 'en', width: 80, render: (v: boolean) => v ? <Tag color="green">Yes</Tag> : <Tag>No</Tag> },
    { title: 'Auto-Provision', dataIndex: 'auto_provision_roles', key: 'ap', width: 120, render: (v: boolean) => v ? 'Yes' : 'No' },
    {
      title: 'Actions', key: 'actions', width: 80,
      render: (_: unknown, r: SSOConfig) => (
        <Popconfirm title="Delete this SSO config?" onConfirm={() => handleDeleteSSO(r.id)}>
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>Advanced RBAC</Title>
        <Text type="secondary">Fine-grained role-based access control with custom roles, ABAC policies, and SSO integration</Text>
      </div>

      {/* Stats */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}><Card><Statistic title="Roles" value={overview?.total_roles ?? roles.length} prefix={<KeyOutlined />} /></Card></Col>
        <Col span={6}><Card><Statistic title="Assignments" value={overview?.total_assignments ?? assignments.length} prefix={<SafetyCertificateOutlined />} /></Card></Col>
        <Col span={6}><Card><Statistic title="ABAC Policies" value={overview?.total_abac_policies ?? policies.length} prefix={<AuditOutlined />} /></Card></Col>
        <Col span={6}><Card><Statistic title="Pending Reviews" value={overview?.pending_reviews ?? 0} prefix={<ApiOutlined />} valueStyle={overview && overview.pending_reviews > 0 ? { color: '#faad14' } : undefined} /></Card></Col>
      </Row>

      <Card>
        <Tabs
          defaultActiveKey="roles"
          items={[
            {
              key: 'roles',
              label: 'Roles',
              children: (
                <>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
                    <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingRole(null); roleForm.resetFields(); setRoleModalOpen(true); }}>
                      Create Role
                    </Button>
                  </div>
                  <Table<Role> columns={roleColumns} dataSource={roles} rowKey="id" loading={loading} pagination={false} />
                </>
              ),
            },
            {
              key: 'assignments',
              label: 'Assignments',
              children: (
                <>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
                    <Button type="primary" icon={<PlusOutlined />} onClick={() => { assignForm.resetFields(); setAssignModalOpen(true); }}>
                      Assign Role
                    </Button>
                  </div>
                  <Table<UserRoleAssignment> columns={assignColumns} dataSource={assignments} rowKey="id" loading={loading} pagination={false} />
                </>
              ),
            },
            {
              key: 'policies',
              label: 'ABAC Policies',
              children: (
                <>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
                    <Button type="primary" icon={<PlusOutlined />} onClick={() => { policyForm.resetFields(); setPolicyModalOpen(true); }}>
                      Create Policy
                    </Button>
                  </div>
                  <Table<ABACPolicy> columns={policyColumns} dataSource={policies} rowKey="id" loading={loading} pagination={false} />
                </>
              ),
            },
            {
              key: 'reviews',
              label: 'Access Reviews',
              children: (
                <Table<AccessReview> columns={reviewColumns} dataSource={reviews} rowKey="id" loading={loading} pagination={false} />
              ),
            },
            {
              key: 'sso',
              label: 'SSO / Identity Providers',
              children: (
                <>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
                    <Button type="primary" icon={<PlusOutlined />} onClick={() => { ssoForm.resetFields(); setSSOModalOpen(true); }}>
                      Add SSO Config
                    </Button>
                  </div>
                  <Table<SSOConfig> columns={ssoColumns} dataSource={ssoConfigs} rowKey="id" loading={loading} pagination={false} />
                </>
              ),
            },
          ]}
        />
      </Card>

      {/* Role Modal */}
      <Modal
        title={editingRole ? 'Edit Role' : 'Create Role'}
        open={roleModalOpen}
        onCancel={() => { setRoleModalOpen(false); setEditingRole(null); roleForm.resetFields(); }}
        onOk={handleRoleSave}
        okText={editingRole ? 'Update' : 'Create'}
        width={600}
      >
        <Form form={roleForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="Role Name" rules={[{ required: true, message: 'Required' }]}>
            <Input placeholder="e.g. Viewer, Cost Admin" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} placeholder="What this role provides access to" />
          </Form.Item>
          <Form.Item name="permissions" label="Permissions">
            <Select
              mode="multiple"
              placeholder="Select permissions"
              options={permissionOptions}
              maxTagCount={5}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Assign Modal */}
      <Modal
        title="Assign Role to User"
        open={assignModalOpen}
        onCancel={() => { setAssignModalOpen(false); assignForm.resetFields(); }}
        onOk={handleAssign}
        okText="Assign"
      >
        <Form form={assignForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="user_id" label="User" rules={[{ required: true, message: 'Required' }]}>
            <Select
              showSearch
              placeholder="Select user"
              optionFilterProp="label"
              options={orgUsers.map((user) => ({
                label: `${user.display_name} (${user.email})`,
                value: user.id,
              }))}
            />
          </Form.Item>
          <Form.Item name="role_id" label="Role" rules={[{ required: true, message: 'Required' }]}>
            <Select
              placeholder="Select role"
              options={roles.map((role) => ({
                label: `${role.name}${role.is_default ? ' (System)' : ''}`,
                value: role.id,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Policy Modal */}
      <Modal
        title="Create ABAC Policy"
        open={policyModalOpen}
        onCancel={() => { setPolicyModalOpen(false); policyForm.resetFields(); }}
        onOk={handlePolicySave}
        okText="Create"
        width={600}
      >
        <Form form={policyForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="Policy Name" rules={[{ required: true, message: 'Required' }]}>
            <Input placeholder="e.g. Deny non-prod deletes" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="resource_type" label="Resource Type" rules={[{ required: true }]}>
                <Select options={RESOURCE_TYPES.map((r) => ({ label: r, value: r }))} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="action" label="Action" rules={[{ required: true }]}>
                <Select options={ACTIONS.map((a) => ({ label: a, value: a }))} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="attribute_key" label="Attribute Key" rules={[{ required: true }]}>
                <Input placeholder="e.g. environment" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="operator" label="Operator" rules={[{ required: true }]}>
                <Select options={OPERATORS.map((o) => ({ label: o, value: o }))} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="attribute_value" label="Value" rules={[{ required: true }]}>
                <Input placeholder="e.g. production" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="effect_allow" label="Effect" initialValue={true}>
                <Select options={[{ label: 'Allow', value: true }, { label: 'Deny', value: false }]} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="active" label="Active" valuePropName="checked" initialValue={true}>
                <Switch />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* SSO Modal */}
      <Modal
        title="Add SSO Configuration"
        open={ssoModalOpen}
        onCancel={() => { setSSOModalOpen(false); ssoForm.resetFields(); }}
        onOk={handleSSOSave}
        okText="Create"
        width={600}
      >
        <Form form={ssoForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="provider" label="Provider" rules={[{ required: true }]}>
            <Select placeholder="Select provider" options={[
              { label: 'SAML', value: 'saml' },
              { label: 'OIDC', value: 'oidc' },
            ]} />
          </Form.Item>
          <Form.Item name="issuer_url" label="Issuer URL" rules={[{ required: true }]}>
            <Input placeholder="https://idp.example.com" />
          </Form.Item>
          <Form.Item name="client_id" label="Client ID">
            <Input placeholder="Client ID (for OIDC)" />
          </Form.Item>
          <Form.Item name="metadata_url" label="Metadata URL">
            <Input placeholder="https://idp.example.com/.well-known/..." />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="enabled" label="Enabled" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="auto_provision_roles" label="Auto-Provision Roles" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="default_role_id" label="Default Role">
            <Select placeholder="Select default role" allowClear options={roles.map((r) => ({ label: r.name, value: r.id }))} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default RBAC;
