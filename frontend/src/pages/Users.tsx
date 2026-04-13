import { useEffect, useState } from 'react';
import {
  Typography,
  Button,
  Table,
  Tag,
  Avatar,
  Dropdown,
  Modal,
  Input,
  Select,
  message,
  Card,
  Space,
  Row,
  Col,
  DatePicker,
  Tooltip,
  Badge,
  Empty,
  Spin,
  Pagination,
  Alert,
  Form,
} from 'antd';
import {
  PlusOutlined,
  MoreOutlined,
  EditOutlined,
  DeleteOutlined,
  UserOutlined,
  LockOutlined,
  UnlockOutlined,
  TeamOutlined,
  SearchOutlined,
  ReloadOutlined,
  MailOutlined,
  KeyOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useUserStore } from '../store/userStore';
import { useOrgStore } from '../store/orgStore';
import type { User, UserFilters } from '../api/userManagement';
import { UserInviteModal } from '../components/users/UserInviteModal';
import { UserDetailModal } from '../components/users/UserDetailModal';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const avatarColors = [
  '#1677ff',
  '#52c41a',
  '#fa8c16',
  '#722ed1',
  '#eb2f96',
  '#13c2c2',
  '#f5222d',
  '#faad14',
];

const statusColors: Record<string, string> = {
  active: 'success',
  pending: 'warning',
  suspended: 'error',
  deactivated: 'default',
  locked: 'error',
};

const statusLabels: Record<string, string> = {
  active: 'Active',
  pending: 'Pending',
  suspended: 'Suspended',
  deactivated: 'Deactivated',
  locked: 'Locked',
};

const Users: React.FC = () => {
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [confirmAction, setConfirmAction] = useState<{
    type: 'suspend' | 'activate' | 'remove' | 'reset-password';
    user: User;
    visible: boolean;
  } | null>(null);
  const [resetPasswordForm] = Form.useForm();

  const currentOrg = useOrgStore((state) => state.currentOrg);
  
  const {
    users,
    pagination,
    filters,
    loading,
    error,
    fetchUsers,
    setFilters,
    suspendUser,
    activateUser,
    removeUser,
    resetPassword,
  } = useUserStore();

  useEffect(() => {
    if (currentOrg?.id) {
      fetchUsers(currentOrg.id);
    }
  }, [currentOrg?.id, filters]);

  const handleInviteSuccess = () => {
    setInviteModalOpen(false);
    message.success('Invitation sent successfully');
    if (currentOrg?.id) {
      fetchUsers(currentOrg.id);
    }
  };

  const handleUserClick = (user: User) => {
    setSelectedUser(user);
    setDetailModalOpen(true);
  };

  const handleSuspend = async (user: User) => {
    if (!currentOrg?.id) return;
    try {
      await suspendUser(currentOrg.id, user.id, 'Administrative action');
      message.success(`User ${user.display_name} suspended`);
      setConfirmAction(null);
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Failed to suspend user');
    }
  };

  const handleActivate = async (user: User) => {
    if (!currentOrg?.id) return;
    try {
      await activateUser(currentOrg.id, user.id);
      message.success(`User ${user.display_name} activated`);
      setConfirmAction(null);
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Failed to activate user');
    }
  };

  const handleRemove = async (user: User) => {
    if (!currentOrg?.id) return;
    try {
      await removeUser(currentOrg.id, user.id);
      message.success(`User ${user.display_name} removed`);
      setConfirmAction(null);
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Failed to remove user');
    }
  };

  const handleResetPassword = async () => {
    if (!currentOrg?.id || !confirmAction) return;
    try {
      const values = await resetPasswordForm.validateFields();
      await resetPassword(currentOrg.id, confirmAction.user.id, values.newPassword);
      message.success(`Password reset for ${confirmAction.user.display_name}`);
      setConfirmAction(null);
      resetPasswordForm.resetFields();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err.response?.data?.detail || 'Failed to reset password');
    }
  };

  const handleConfirmAction = () => {
    if (!confirmAction) return;
    
    switch (confirmAction.type) {
      case 'suspend':
        handleSuspend(confirmAction.user);
        break;
      case 'activate':
        handleActivate(confirmAction.user);
        break;
      case 'remove':
        handleRemove(confirmAction.user);
        break;
    }
  };

  const columns: ColumnsType<User> = [
    {
      title: 'User',
      key: 'avatar',
      width: 48,
      render: (_, record, index) => (
        <Avatar
          style={{ backgroundColor: avatarColors[index % avatarColors.length] }}
          icon={<UserOutlined />}
        >
          {record.display_name.charAt(0).toUpperCase()}
        </Avatar>
      ),
    },
    {
      title: 'Name',
      dataIndex: 'display_name',
      key: 'name',
      render: (name: string, record) => (
        <a onClick={() => handleUserClick(record)}>
          <Text strong>{name}</Text>
        </a>
      ),
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: 'Roles',
      key: 'roles',
      render: (_, record) => (
        <Space size="small" wrap>
          {record.roles.map((role) => (
            <Tag key={role.id} color="blue">
              {role.name}
            </Tag>
          ))}
          {record.roles.length === 0 && (
            <Tag color="default">No roles</Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Department',
      dataIndex: 'department',
      key: 'department',
      render: (dept) => dept || '-',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Badge status={statusColors[status] as any} text={statusLabels[status]} />
      ),
    },
    {
      title: 'Last Login',
      dataIndex: 'last_login',
      key: 'last_login',
      render: (date) => (date ? dayjs(date).fromNow() : 'Never'),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 80,
      render: (_, record) => (
        <Dropdown
          menu={{
            items: [
              {
                key: 'view',
                icon: <UserOutlined />,
                label: 'View Details',
                onClick: () => handleUserClick(record),
              },
              {
                key: 'edit',
                icon: <EditOutlined />,
                label: 'Edit',
                onClick: () => handleUserClick(record),
              },
              ...(record.status === 'active'
                ? [
                    {
                      key: 'suspend',
                      icon: <LockOutlined />,
                      label: 'Suspend',
                      onClick: () =>
                        setConfirmAction({
                          type: 'suspend',
                          user: record,
                          visible: true,
                        }),
                    },
                  ]
                : []),
              ...(record.status === 'suspended' || record.status === 'locked'
                ? [
                    {
                      key: 'activate',
                      icon: <UnlockOutlined />,
                      label: 'Activate',
                      onClick: () =>
                        setConfirmAction({
                          type: 'activate',
                          user: record,
                          visible: true,
                        }),
                    },
                  ]
                : []),
              {
                key: 'remove',
                icon: <DeleteOutlined />,
                label: 'Remove',
                danger: true,
                onClick: () =>
                  setConfirmAction({
                    type: 'remove',
                    user: record,
                    visible: true,
                  }),
              },
              {
                key: 'reset-password',
                icon: <KeyOutlined />,
                label: 'Reset Password',
                onClick: () =>
                  setConfirmAction({
                    type: 'reset-password',
                    user: record,
                    visible: true,
                  }),
              },
            ],
          }}
          trigger={['click']}
        >
          <Button type="text" icon={<MoreOutlined />} />
        </Dropdown>
      ),
    },
  ];

  return (
    <>
      <div style={{ marginBottom: 24 }}>
        <Row justify="space-between" align="middle">
          <Col>
            <Title level={3} style={{ margin: 0 }}>
              Users
            </Title>
            <Text type="secondary">
              {pagination.total} total users • {users.filter((u) => u.status === 'active').length} active
            </Text>
          </Col>
          <Col>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setInviteModalOpen(true)}
            >
              Invite User
            </Button>
          </Col>
        </Row>
      </div>

      {error && (
        <Alert
          message="Error"
          description={error}
          type="error"
          closable
          onClose={() => useUserStore.getState().clearError()}
          style={{ marginBottom: 16 }}
        />
      )}

      <Card>
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={24} sm={12} md={8} lg={6}>
            <Input
              placeholder="Search by name or email"
              prefix={<SearchOutlined />}
              value={filters.search}
              onChange={(e) => setFilters({ search: e.target.value })}
              allowClear
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={6}>
            <Select
              placeholder="Filter by status"
              allowClear
              style={{ width: '100%' }}
              value={filters.status}
              onChange={(value) => setFilters({ status: value })}
            >
              <Select.Option value="active">Active</Select.Option>
              <Select.Option value="pending">Pending</Select.Option>
              <Select.Option value="suspended">Suspended</Select.Option>
              <Select.Option value="locked">Locked</Select.Option>
            </Select>
          </Col>
          <Col xs={24} sm={12} md={8} lg={6}>
            <Select
              placeholder="Filter by department"
              allowClear
              style={{ width: '100%' }}
              value={filters.department}
              onChange={(value) => setFilters({ department: value })}
            >
              <Select.Option value="Engineering">Engineering</Select.Option>
              <Select.Option value="Finance">Finance</Select.Option>
              <Select.Option value="Operations">Operations</Select.Option>
              <Select.Option value="Management">Management</Select.Option>
            </Select>
          </Col>
          <Col xs={24} sm={12} md={8} lg={6} style={{ textAlign: 'right' }}>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                setFilters({ page: 1 });
                if (currentOrg?.id) fetchUsers(currentOrg.id);
              }}
            >
              Refresh
            </Button>
          </Col>
        </Row>

        <Spin spinning={loading}>
          {users.length > 0 ? (
            <>
              <Table<User>
                columns={columns}
                dataSource={users}
                rowKey="id"
                pagination={false}
                size="middle"
              />
              <div style={{ marginTop: 16, textAlign: 'right' }}>
                <Pagination
                  current={pagination.page}
                  pageSize={pagination.limit}
                  total={pagination.total}
                  onChange={(page, pageSize) =>
                    setFilters({ page, limit: pageSize })
                  }
                  showSizeChanger
                  showTotal={(total, range) =>
                    `${range[0]}-${range[1]} of ${total} users`
                  }
                />
              </div>
            </>
          ) : (
            <Empty
              description="No users found"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </Spin>
      </Card>

      {/* Invite Modal */}
      <UserInviteModal
        open={inviteModalOpen}
        onClose={() => setInviteModalOpen(false)}
        onSuccess={handleInviteSuccess}
        orgId={currentOrg?.id || ''}
      />

      {/* User Detail Modal */}
      <UserDetailModal
        open={detailModalOpen}
        onClose={() => {
          setDetailModalOpen(false);
          setSelectedUser(null);
        }}
        user={selectedUser}
        orgId={currentOrg?.id || ''}
      />

      {/* Confirmation Modal */}
      <Modal
        title={
          confirmAction?.type === 'suspend'
            ? 'Suspend User'
            : confirmAction?.type === 'activate'
            ? 'Activate User'
            : confirmAction?.type === 'reset-password'
            ? 'Reset Password'
            : 'Remove User'
        }
        open={confirmAction?.visible || false}
        onOk={
          confirmAction?.type === 'reset-password' ? handleResetPassword : handleConfirmAction
        }
        onCancel={() => { setConfirmAction(null); resetPasswordForm.resetFields(); }}
        okText={
          confirmAction?.type === 'suspend'
            ? 'Suspend'
            : confirmAction?.type === 'activate'
            ? 'Activate'
            : confirmAction?.type === 'reset-password'
            ? 'Reset Password'
            : 'Remove'
        }
        okButtonProps={{
          danger: confirmAction?.type === 'suspend' || confirmAction?.type === 'remove',
        }}
      >
        {confirmAction?.type === 'reset-password' ? (
          <>
            <Alert
              message="This will immediately change the password for this user."
              description="The user will need to use the new password for their next login."
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
            />
            <Form form={resetPasswordForm} layout="vertical">
              <Form.Item
                name="newPassword"
                label="New Password"
                rules={[
                  { required: true, message: 'Please enter a new password' },
                  { min: 8, message: 'Password must be at least 8 characters' },
                ]}
              >
                <Input.Password placeholder="Enter new password" />
              </Form.Item>
              <Form.Item
                name="confirmPassword"
                label="Confirm Password"
                dependencies={['newPassword']}
                rules={[
                  { required: true, message: 'Please confirm the password' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('newPassword') === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error('Passwords do not match'));
                    },
                  }),
                ]}
              >
                <Input.Password placeholder="Confirm new password" />
              </Form.Item>
            </Form>
          </>
        ) : (
          <>
            <p>
              Are you sure you want to{' '}
              {confirmAction?.type === 'suspend'
                ? 'suspend'
                : confirmAction?.type === 'activate'
                ? 'activate'
                : 'remove'}{' '}
              <strong>{confirmAction?.user.display_name}</strong>?
            </p>
            {confirmAction?.type === 'remove' && (
              <p style={{ color: '#ff4d4f' }}>
                This action cannot be undone. The user will be removed from the organization.
              </p>
            )}
          </>
        )}
      </Modal>
    </>
  );
};

export default Users;
