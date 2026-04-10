import { useCallback, useEffect, useState, type FC } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Alert, Button, Form, Input, Typography, App, Spin } from 'antd';
import { LockOutlined, UserOutlined, CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { userManagementApi, type InvitationDetail } from '@/api/userManagement';
import { ROUTES } from '@/utils/routes';

const { Title, Text, Paragraph } = Typography;

const AcceptInvitation: FC = () => {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();

  const [invitation, setInvitation] = useState<InvitationDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [form] = Form.useForm();
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchInvitation = useCallback(async () => {
    if (!token) {
      setError('Invalid invitation link.');
      setFetching(false);
      return;
    }
    try {
      const response = await userManagementApi.getInvitation(token);
      setInvitation(response.data);
      if (!response.data.is_valid) {
        setError('This invitation has expired or is no longer valid.');
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Failed to load invitation details.';
      setError(detail);
    } finally {
      setFetching(false);
    }
  }, [token]);

  useEffect(() => {
    fetchInvitation();
  }, [fetchInvitation]);

  const handleAccept = async () => {
    const values = await form.validateFields();
    if (!token) return;

    setLoading(true);
    try {
      await userManagementApi.acceptInvitation(token, {
        display_name: values.display_name,
        password: values.password,
      });
      setAccepted(true);
      message.success('Account created successfully! You can now log in.');
      setTimeout(() => {
        navigate(ROUTES.LOGIN, { replace: true });
      }, 2000);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Failed to accept invitation.';
      message.error(detail);
    } finally {
      setLoading(false);
    }
  };

  if (fetching) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 0' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (accepted) {
    return (
      <div style={{ textAlign: 'center', padding: '16px 0' }}>
        <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a', marginBottom: 16 }} />
        <Title level={4} style={{ marginBottom: 8 }}>Welcome Aboard!</Title>
        <Text type="secondary">Your account has been created. Redirecting to login...</Text>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '16px 0' }}>
        <WarningOutlined style={{ fontSize: 48, color: '#ff4d4f', marginBottom: 16 }} />
        <Title level={4} style={{ marginBottom: 8 }}>Invitation Error</Title>
        <Text type="danger">{error}</Text>
        <div style={{ marginTop: 24 }}>
          <Button type="primary" onClick={() => navigate(ROUTES.LOGIN)}>
            Go to Login
          </Button>
        </div>
      </div>
    );
  }

  if (!invitation) {
    return null;
  }

  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ marginBottom: 4 }}>Accept Invitation</Title>
        <Text type="secondary">
          You've been invited to join <strong>{invitation.organization_name}</strong>
        </Text>
      </div>

      <Alert
        type="info"
        showIcon
        icon={<UserOutlined />}
        message="Invitation Details"
        description={
          <div>
            <Paragraph style={{ marginBottom: 4 }}>
              <Text strong>Email:</Text> {invitation.email}
            </Paragraph>
            {invitation.role_name && (
              <Paragraph style={{ marginBottom: 4 }}>
                <Text strong>Role:</Text> {invitation.role_name}
              </Paragraph>
            )}
            {invitation.invited_by_name && (
              <Paragraph style={{ marginBottom: 4 }}>
                <Text strong>Invited by:</Text> {invitation.invited_by_name}
              </Paragraph>
            )}
            <Paragraph style={{ marginBottom: 0 }}>
              <Text strong>Expires:</Text>{' '}
              {new Date(invitation.expires_at).toLocaleString()}
            </Paragraph>
          </div>
        }
        style={{ marginBottom: 24 }}
      />

      <Form form={form} layout="vertical" onFinish={handleAccept}>
        <Form.Item
          name="display_name"
          label="Display Name"
          rules={[
            { required: true, message: 'Please enter your display name' },
            { min: 1, max: 256, message: 'Name must be 1-256 characters' },
          ]}
        >
          <Input
            prefix={<UserOutlined />}
            placeholder="e.g. John Doe"
            size="large"
          />
        </Form.Item>

        <Form.Item
          name="password"
          label="Password"
          rules={[
            { required: true, message: 'Please enter a password' },
            { min: 8, message: 'Password must be at least 8 characters' },
            { max: 128, message: 'Password must be at most 128 characters' },
          ]}
        >
          <Input.Password
            prefix={<LockOutlined />}
            placeholder="Create a secure password"
            size="large"
          />
        </Form.Item>

        <Form.Item
          name="confirmPassword"
          label="Confirm Password"
          dependencies={['password']}
          rules={[
            { required: true, message: 'Please confirm your password' },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue('password') === value) {
                  return Promise.resolve();
                }
                return Promise.reject(new Error('Passwords do not match'));
              },
            }),
          ]}
        >
          <Input.Password
            prefix={<LockOutlined />}
            placeholder="Confirm your password"
            size="large"
          />
        </Form.Item>

        <Form.Item style={{ marginBottom: 0 }}>
          <Button
            type="primary"
            htmlType="submit"
            block
            size="large"
            loading={loading}
            disabled={!invitation.is_valid}
          >
            {invitation.is_valid ? 'Accept & Create Account' : 'Invitation Expired'}
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
};

export default AcceptInvitation;
