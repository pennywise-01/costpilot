import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Form, Input, Button, message, Typography } from 'antd';
import { UserOutlined, MailOutlined, LockOutlined } from '@ant-design/icons';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/store/authStore';

const { Text } = Typography;

const Register: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const onFinish = async (values: {
    display_name: string;
    email: string;
    password: string;
    confirm: string;
  }) => {
    setLoading(true);
    try {
      const { data } = await authApi.register({
        display_name: values.display_name,
        email: values.email,
        password: values.password,
      });
      setAuth(data.access_token, data.user);
      navigate('/');
    } catch (err: any) {
      const detail =
        err?.response?.data?.detail ||
        'Registration failed. Please try again.';
      message.error(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form
      name="register"
      layout="vertical"
      onFinish={onFinish}
      autoComplete="off"
      size="large"
    >
      <Form.Item
        name="display_name"
        rules={[{ required: true, message: 'Please enter your name' }]}
      >
        <Input prefix={<UserOutlined />} placeholder="Display name" />
      </Form.Item>

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
        extra="At least 8 characters"
        rules={[
          { required: true, message: 'Please enter a password' },
          { min: 8, message: 'Password must be at least 8 characters' },
        ]}
      >
        <Input.Password prefix={<LockOutlined />} placeholder="Password" />
      </Form.Item>

      <Form.Item
        name="confirm"
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
          placeholder="Confirm password"
        />
      </Form.Item>

      <Form.Item>
        <Button
          type="primary"
          htmlType="submit"
          block
          size="large"
          loading={loading}
        >
          Create account
        </Button>
      </Form.Item>

      <div style={{ textAlign: 'center' }}>
        <Text>
          Already have an account? <Link to="/login">Sign in</Link>
        </Text>
      </div>
    </Form>
  );
};

export default Register;
