import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Form, Input, Button, message, Typography } from 'antd';
import { MailOutlined, LockOutlined } from '@ant-design/icons';
import { authApi, type LoginData } from '@/api/auth';
import { useAuthStore } from '@/store/authStore';

const { Text } = Typography;

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const onFinish = async (values: LoginData) => {
    setLoading(true);
    try {
      const { data } = await authApi.login(values);
      setAuth(data.access_token, data.user);
      navigate('/');
    } catch (err: any) {
      const detail =
        err?.response?.data?.detail || 'Login failed. Please try again.';
      message.error(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form
      name="login"
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

      <Form.Item
        name="password"
        rules={[{ required: true, message: 'Please enter your password' }]}
      >
        <Input.Password prefix={<LockOutlined />} placeholder="Password" />
      </Form.Item>

      <Form.Item>
        <Button
          type="primary"
          htmlType="submit"
          block
          size="large"
          loading={loading}
        >
          Sign in
        </Button>
      </Form.Item>

      <div style={{ textAlign: 'center' }}>
        <Text>
          Don't have an account? <Link to="/register">Sign up</Link>
        </Text>
      </div>
    </Form>
  );
};

export default Login;
