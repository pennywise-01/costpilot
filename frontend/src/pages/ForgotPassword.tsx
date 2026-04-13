import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Form, Input, Button, message, Typography } from 'antd';
import { MailOutlined } from '@ant-design/icons';
import { authApi } from '@/api/auth';

const { Text } = Typography;

const ForgotPassword: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const onFinish = async (values: { email: string }) => {
    setLoading(true);
    try {
      await authApi.forgotPassword(values.email);
      setSubmitted(true);
    } catch {
      // Backend always returns success to prevent email enumeration,
      // but handle network errors gracefully
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div style={{ textAlign: 'center' }}>
        <Typography.Title level={4} style={{ marginBottom: 16 }}>
          Check your email
        </Typography.Title>
        <Typography.Paragraph>
          If an account with that email exists, we've sent a password reset link.
        </Typography.Paragraph>
        <Typography.Paragraph type="secondary" style={{ fontSize: 13 }}>
          The link expires in 15 minutes.
        </Typography.Paragraph>
        <Link to="/login">
          <Button type="primary" style={{ marginTop: 16 }}>Back to Login</Button>
        </Link>
      </div>
    );
  }

  return (
    <>
      <Typography.Title level={4} style={{ marginBottom: 8, textAlign: 'center' }}>
        Forgot your password?
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ textAlign: 'center', marginBottom: 24 }}>
        Enter your email and we'll send you a reset link.
      </Typography.Paragraph>
      <Form
        name="forgot-password"
        layout="vertical"
        onFinish={onFinish}
        autoComplete="off"
        size="large"
      >
        <Form.Item
          name="email"
          rules={[
            { required: true, message: 'Please enter your email' },
            { type: 'email', message: 'Please enter a valid email' },
          ]}
        >
          <Input prefix={<MailOutlined />} placeholder="Email" />
        </Form.Item>

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            block
            loading={loading}
          >
            Send Reset Link
          </Button>
        </Form.Item>
      </Form>

      <div style={{ textAlign: 'center' }}>
        <Text>
          Remember your password? <Link to="/login">Sign in</Link>
        </Text>
      </div>
    </>
  );
};

export default ForgotPassword;
