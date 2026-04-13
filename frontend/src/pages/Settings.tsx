import { useState, useEffect, useCallback } from 'react';
import {
  Typography,
  Tabs,
  Form,
  Input,
  Button,
  Select,
  Switch,
  Card,
  Divider,
  List,
  message,
  Space,
  Spin,
} from 'antd';
import { useAuthStore } from '@/store/authStore';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';
import { authApi } from '@/api/auth';
import { notificationsApi } from '@/api/notifications';
import { organizationsApi } from '@/api/organizations';

const { Title, Text } = Typography;

const formLayout = {
  labelCol: { span: 6 },
  wrapperCol: { span: 18 },
};

const ProfileTab: React.FC = () => {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const [profileForm] = Form.useForm();
  const [passwordForm] = Form.useForm();
  const [profileLoading, setProfileLoading] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);

  const handleSaveProfile = async () => {
    try {
      const values = await profileForm.validateFields();
      setProfileLoading(true);
      const { data } = await authApi.updateMe({ display_name: values.displayName });
      setUser(data);
      message.success('Profile updated successfully');
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        message.error(err.response.data.detail);
      } else if (err?.errorFields) {
        // form validation error, ignore
      } else {
        message.error('Failed to update profile');
      }
    } finally {
      setProfileLoading(false);
    }
  };

  const handleUpdatePassword = async () => {
    try {
      const values = await passwordForm.validateFields();
      setPasswordLoading(true);
      await authApi.updateMe({
        current_password: values.currentPassword,
        password: values.newPassword,
      });
      message.success('Password updated successfully');
      passwordForm.resetFields();
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        message.error(err.response.data.detail);
      } else if (err?.errorFields) {
        // form validation error, ignore
      } else {
        message.error('Failed to update password');
      }
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <>
      <Card style={{ marginBottom: 24 }}>
        <Title level={5} style={{ marginTop: 0 }}>Profile Information</Title>
        <Form
          form={profileForm}
          {...formLayout}
          initialValues={{
            displayName: user?.display_name ?? '',
            email: user?.email ?? '',
          }}
        >
          <Form.Item
            name="displayName"
            label="Display Name"
            rules={[{ required: true, message: 'Please enter your display name' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="email" label="Email">
            <Input disabled />
          </Form.Item>
          <Form.Item wrapperCol={{ offset: 6, span: 18 }}>
            <Button type="primary" onClick={handleSaveProfile} loading={profileLoading}>
              Save Profile
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card>
        <Title level={5} style={{ marginTop: 0 }}>Change Password</Title>
        <Form form={passwordForm} {...formLayout}>
          <Form.Item
            name="currentPassword"
            label="Current Password"
            rules={[{ required: true, message: 'Please enter your current password' }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="newPassword"
            label="New Password"
            rules={[{ required: true, message: 'Please enter a new password' }]}
            help="Use at least 8 characters with a mix of letters, numbers, and symbols."
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="confirmPassword"
            label="Confirm Password"
            dependencies={['newPassword']}
            rules={[
              { required: true, message: 'Please confirm your new password' },
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
            <Input.Password />
          </Form.Item>
          <Form.Item wrapperCol={{ offset: 6, span: 18 }}>
            <Button type="primary" onClick={handleUpdatePassword} loading={passwordLoading}>
              Update Password
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </>
  );
};

const OrganizationTab: React.FC = () => {
  const orgId = useCurrentOrgId();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!orgId) return;
    
    const loadOrganization = async () => {
      try {
        const { data } = await organizationsApi.get(orgId);
        form.setFieldsValue({
          orgName: data.name,
          currency: data.currency,
        });
      } catch {
        message.error('Failed to load organization details');
      } finally {
        setLoading(false);
      }
    };

    loadOrganization();
  }, [orgId, form]);

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin />
        </div>
      </Card>
    );
  }

  return (
    <>
      <Card style={{ marginBottom: 24 }}>
        <Title level={5} style={{ marginTop: 0 }}>Organization Details</Title>
        <Form
          form={form}
          {...formLayout}
        >
          <Form.Item
            name="orgName"
            label="Organization Name"
          >
            <Input disabled />
          </Form.Item>
          <Form.Item name="currency" label="Currency">
            <Select disabled>
              <Select.Option value="USD">USD - US Dollar</Select.Option>
              <Select.Option value="EUR">EUR - Euro</Select.Option>
              <Select.Option value="GBP">GBP - British Pound</Select.Option>
              <Select.Option value="JPY">JPY - Japanese Yen</Select.Option>
              <Select.Option value="AUD">AUD - Australian Dollar</Select.Option>
              <Select.Option value="CAD">CAD - Canadian Dollar</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Card>
    </>
  );
};

interface NotificationPref {
  key: string;
  label: string;
  description: string;
  defaultChecked: boolean;
}

const notificationPrefs: NotificationPref[] = [
  { key: 'budget_alerts', label: 'Budget alerts', description: 'Get notified when spending approaches or exceeds budget limits', defaultChecked: true },
  { key: 'recommendation_updates', label: 'Recommendation updates', description: 'Receive updates when new cost-saving recommendations are available', defaultChecked: true },
  { key: 'daily_cost_summary', label: 'Daily cost summary email', description: 'Receive a daily email summarising your cloud costs', defaultChecked: false },
  { key: 'weekly_report', label: 'Weekly report email', description: 'Receive a weekly digest of cost trends and insights', defaultChecked: true },
  { key: 'anomaly_alerts', label: 'Anomaly alerts', description: 'Get notified when unusual spending patterns are detected', defaultChecked: true },
  { key: 'new_user_joined', label: 'New user joined', description: 'Get notified when a new user joins your organization', defaultChecked: false },
];

const NotificationsTab: React.FC = () => {
  const orgId = useCurrentOrgId();
  const [prefs, setPrefs] = useState<Record<string, boolean>>(
    Object.fromEntries(notificationPrefs.map((p) => [p.key, p.defaultChecked])),
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const loadPreferences = useCallback(async () => {
    try {
      const { data } = await notificationsApi.getPreferences(orgId);
      const loaded: Record<string, boolean> = {};
      for (const p of data.preferences) {
        loaded[p.notification_type] = p.enabled;
      }
      setPrefs((prev) => ({ ...prev, ...loaded }));
    } catch {
      // Use defaults on error
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    loadPreferences();
  }, [loadPreferences]);

  const handleToggle = (key: string, checked: boolean) => {
    setPrefs((prev) => ({ ...prev, [key]: checked }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const preferences = Object.entries(prefs).map(([notification_type, enabled]) => ({
        notification_type,
        enabled,
      }));
      await notificationsApi.savePreferences(orgId, preferences);
      message.success('Notification preferences saved');
    } catch {
      message.error('Failed to save notification preferences');
    } finally {
      setSaving(false);
    }
  };

  const handleSendTest = async (notificationType: string) => {
    try {
      await notificationsApi.sendTest(orgId, notificationType);
      message.success('Test email sent — check your inbox');
    } catch {
      message.error('Failed to send test email');
    }
  };

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin />
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <Title level={5} style={{ marginTop: 0 }}>Notification Preferences</Title>
      <List
        itemLayout="horizontal"
        dataSource={notificationPrefs}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Button
                key={`test-${item.key}`}
                size="small"
                onClick={() => handleSendTest(item.key)}
              >
                Test
              </Button>,
              <Switch
                key={item.key}
                checked={prefs[item.key]}
                onChange={(checked) => handleToggle(item.key, checked)}
              />,
            ]}
          >
            <List.Item.Meta title={item.label} description={item.description} />
          </List.Item>
        )}
      />
      <div style={{ marginTop: 24 }}>
        <Button type="primary" onClick={handleSave} loading={saving}>
          Save Preferences
        </Button>
      </div>
    </Card>
  );
};

const Settings: React.FC = () => {
  const tabItems = [
    { key: 'profile', label: 'Profile', children: <ProfileTab /> },
    { key: 'organization', label: 'Organization', children: <OrganizationTab /> },
    { key: 'notifications', label: 'Notifications', children: <NotificationsTab /> },
  ];

  return (
    <>
      <Title level={3} style={{ marginBottom: 24 }}>Settings</Title>
      <Tabs items={tabItems} defaultActiveKey="profile" />
    </>
  );
};

export default Settings;
