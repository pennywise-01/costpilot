import { useEffect, useState } from 'react';
import {
  Modal,
  Tabs,
  Descriptions,
  Tag,
  Button,
  Space,
  Spin,
  Empty,
  Table,
  Timeline,
  Card,
  Alert,
  Select,
  message,
  Divider,
} from 'antd';
import {
  UserOutlined,
  SafetyOutlined,
  HistoryOutlined,
  TeamOutlined,
  LockOutlined,
  UnlockOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useUserStore } from '../../store/userStore';
import { rbacApi, type Role } from '../../api/rbac';
import { userManagementApi, type User, type UserDetail, type ActivityLogEntry } from '../../api/userManagement';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);

interface UserDetailModalProps {
  open: boolean;
  onClose: () => void;
  user: User | null;
  orgId: string;
}

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

export const UserDetailModal: React.FC<UserDetailModalProps> = ({
  open,
  onClose,
  user,
  orgId,
}) => {
  const [activeTab, setActiveTab] = useState('profile');
  const [userDetail, setUserDetail] = useState<UserDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [activityLog, setActivityLog] = useState<ActivityLogEntry[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);

  const { suspendUser, activateUser, removeUser, updateUserRoles } = useUserStore();

  useEffect(() => {
    if (open && user && orgId) {
      fetchUserDetail();
      fetchRoles();
      fetchActivityLog();
    }
  }, [open, user, orgId]);

  const fetchUserDetail = async () => {
    if (!user || !orgId) return;
    setLoading(true);
    try {
      const response = await userManagementApi.getUser(orgId, user.id);
      setUserDetail(response.data);
      setSelectedRoles(response.data.roles.map((r) => r.id));
    } catch (error) {
      message.error('Failed to load user details');
    } finally {
      setLoading(false);
    }
  };

  const fetchRoles = async () => {
    if (!orgId) return;
    try {
      const response = await rbacApi.listRoles(orgId);
      const rolesData = response.data;
      setRoles(Array.isArray(rolesData) ? rolesData : (rolesData as { items?: Role[] })?.items ?? []);
    } catch (error) {
      console.error('Failed to load roles');
    }
  };

  const fetchActivityLog = async () => {
    if (!user || !orgId) return;
    setActivityLoading(true);
    try {
      const response = await userManagementApi.getUserActivity(orgId, user.id, { limit: 50 });
      setActivityLog(response.data.items);
    } catch (error) {
      console.error('Failed to load activity log');
    } finally {
      setActivityLoading(false);
    }
  };

  const handleRoleChange = async (roleIds: string[]) => {
    if (!user || !orgId) return;
    try {
      await updateUserRoles(orgId, user.id, {
        role_ids: roleIds,
        action: 'replace',
      });
      message.success('Roles updated successfully');
      fetchUserDetail();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to update roles');
    }
  };

  const handleSuspend = async () => {
    if (!user || !orgId) return;
    try {
      await suspendUser(orgId, user.id, 'Administrative action');
      message.success('User suspended');
      fetchUserDetail();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to suspend user');
    }
  };

  const handleActivate = async () => {
    if (!user || !orgId) return;
    try {
      await activateUser(orgId, user.id);
      message.success('User activated');
      fetchUserDetail();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to activate user');
    }
  };

  const handleRemove = async () => {
    if (!user || !orgId) return;
    try {
      await removeUser(orgId, user.id);
      message.success('User removed');
      onClose();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to remove user');
    }
  };

  const activityColumns: ColumnsType<ActivityLogEntry> = [
    {
      title: 'Action',
      dataIndex: 'action',
      key: 'action',
      render: (action) => (
        <Tag color="blue">{action.replace(/_/g, ' ').toUpperCase()}</Tag>
      ),
    },
    {
      title: 'Resource',
      key: 'resource',
      render: (_, record) =>
        record.resource_type ? (
          <span>
            {record.resource_type}: {record.resource_id}
          </span>
        ) : (
          '-'
        ),
    },
    {
      title: 'Time',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date) => dayjs(date).fromNow(),
    },
  ];

  const items = [
    {
      key: 'profile',
      label: (
        <span>
          <UserOutlined /> Profile
        </span>
      ),
      children: userDetail ? (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Descriptions title="User Information" bordered column={2}>
            <Descriptions.Item label="Name">{userDetail.display_name}</Descriptions.Item>
            <Descriptions.Item label="Email">{userDetail.email}</Descriptions.Item>
            <Descriptions.Item label="Status">
              <Tag color={statusColors[userDetail.status]}>
                {statusLabels[userDetail.status]}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Active">
              {userDetail.is_active ? 'Yes' : 'No'}
            </Descriptions.Item>
            <Descriptions.Item label="Department">
              {userDetail.department || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="Job Title">
              {userDetail.job_title || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="Joined">
              {userDetail.joined_at ? dayjs(userDetail.joined_at).format('MMM D, YYYY') : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="Last Login">
              {userDetail.last_login ? dayjs(userDetail.last_login).fromNow() : 'Never'}
            </Descriptions.Item>
          </Descriptions>

          {userDetail.activity_summary && (
            <Card title="Activity Summary (Last 30 Days)" size="small">
              <Space size="large">
                <div>
                  <div style={{ fontSize: 24, fontWeight: 'bold' }}>
                    {userDetail.activity_summary.login_count_30d}
                  </div>
                  <div style={{ color: '#666' }}>Logins</div>
                </div>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 'bold' }}>
                    {userDetail.activity_summary.actions_count_30d}
                  </div>
                  <div style={{ color: '#666' }}>Actions</div>
                </div>
              </Space>
            </Card>
          )}
        </Space>
      ) : (
        <Empty description="No user details available" />
      ),
    },
    {
      key: 'roles',
      label: (
        <span>
          <SafetyOutlined /> Roles & Permissions
        </span>
      ),
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Card title="Role Assignment" size="small">
            <Select
              mode="multiple"
              style={{ width: '100%' }}
              placeholder="Select roles"
              value={selectedRoles}
              onChange={handleRoleChange}
              options={roles.map((role) => ({
                label: role.name,
                value: role.id,
                description: role.description,
              }))}
            />
            <div style={{ marginTop: 8, color: '#666', fontSize: 12 }}>
              Select multiple roles to assign to this user
            </div>
          </Card>

          {userDetail?.permissions && userDetail.permissions.length > 0 && (
            <Card title="Effective Permissions" size="small">
              <Space wrap>
                {userDetail.permissions.map((perm, idx) => (
                  <Tag key={idx} color="green">
                    {perm.action} {perm.resource_type}
                    {perm.granted_via_role && (
                      <small style={{ marginLeft: 4 }}>(via {perm.granted_via_role})</small>
                    )}
                  </Tag>
                ))}
              </Space>
            </Card>
          )}
        </Space>
      ),
    },
    {
      key: 'activity',
      label: (
        <span>
          <HistoryOutlined /> Activity Log
        </span>
      ),
      children: (
        <Spin spinning={activityLoading}>
          {activityLog.length > 0 ? (
            <Table
              columns={activityColumns}
              dataSource={activityLog}
              rowKey="id"
              size="small"
              pagination={{ pageSize: 10 }}
            />
          ) : (
            <Empty description="No activity recorded" />
          )}
        </Spin>
      ),
    },
  ];

  return (
    <Modal
      title={user?.display_name || 'User Details'}
      open={open}
      onCancel={onClose}
      width={800}
      footer={[
        <Button key="close" onClick={onClose}>
          Close
        </Button>,
        user?.status === 'active' && (
          <Button key="suspend" danger icon={<LockOutlined />} onClick={handleSuspend}>
            Suspend
          </Button>
        ),
        (user?.status === 'suspended' || user?.status === 'locked') && (
          <Button key="activate" type="primary" icon={<UnlockOutlined />} onClick={handleActivate}>
            Activate
          </Button>
        ),
        <Button key="remove" danger icon={<DeleteOutlined />} onClick={handleRemove}>
          Remove
        </Button>,
      ]}
    >
      <Spin spinning={loading}>
        {userDetail && (
          <Alert
            message={`${userDetail.display_name} - ${statusLabels[userDetail.status]}`}
            description={`${userDetail.email} • ${userDetail.roles.length} role(s) assigned`}
            type={userDetail.status === 'active' ? 'success' : 'warning'}
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={items} />
      </Spin>
    </Modal>
  );
};
