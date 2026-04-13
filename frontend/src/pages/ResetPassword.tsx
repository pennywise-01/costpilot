import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Form, Input, Button, message, Typography, Result } from 'antd';
import { LockOutlined } from '@ant-design/icons';
import { authApi } from '@/api/auth';

const ResetPassword: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();

  const onFinish = async (values: { password: string; confirmPassword: string }) => {
    if (!token) {
      setError('Invalid reset link. Please request a new one.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await authApi.resetPassword(token, values.password);
      setSuccess(true);
      message.success('Password reset successfully!');
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Failed to reset password. The link may have expired.';
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <Result
        status="success"
        title="Password Reset Successful"
        subTitle="You can now sign in with your new password."
        extra={
          <Button type="primary" onClick={() => navigate('/login')}>
            Sign In
          </Button>
        }
      />
    );
  }

  if (error && !loading) {
    return (
      <Result
        status="error"
        title="Reset Failed"
        subTitle={error}
        extra={[
          <Button type="primary" key="retry" onClick={() => navigate('/forgot-password')}>
            Request New Link
          </Button>,
          <Button key="login" onClick={() => navigate('/login')}>
            Back to Login
          </Button>,
        ]}
      />
    );
  }

  if (!token) {
    return (
      <Result
        status="error"
        title="Invalid Reset Link"
        subTitle="This reset link is invalid or has expired."
        extra={
          <Button type="primary" onClick={() => navigate('/forgot-password')}>
            Request New Link
          </Button>
        }
      />
    );
  }

  return (
    <>
      <Typography.Title level={4} style={{ marginBottom: 8, textAlign: 'center' }}>
        Set new password
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ textAlign: 'center', marginBottom: 24 }}>
        Choose a strong password with at least 8 characters.
      </Typography.Paragraph>
      <Form
        name="reset-password"
        layout="vertical"
        onFinish={onFinish}
        autoComplete="off"
        size="large"
      >
        <Form.Item
          name="password"
          rules={[
            { required: true, message: 'Please enter a new password' },
            { min: 8, message: 'Password must be at least 8 characters' },
          ]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="New password" />
        </Form.Item>

        <Form.Item
          name="confirmPassword"
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
          <Input.Password prefix={<LockOutlined />} placeholder="Confirm new password" />
        </Form.Item>

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            block
            loading={loading}
          >
            Reset Password
          </Button>
        </Form.Item>
      </Form>

      <div style={{ textAlign: 'center' }}>
        <Link to="/login">Back to Login</Link>
      </div>
    </>
  );
};

export default ResetPassword;
