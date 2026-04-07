import React from 'react';
import { Card, Typography } from 'antd';
import { Outlet } from 'react-router-dom';
import {
  RocketOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;

const AuthLayout: React.FC = () => {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        padding: 24,
      }}
    >
      <Card
        style={{
          maxWidth: 440,
          width: '100%',
          borderRadius: 16,
          boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        }}
        styles={{ body: { padding: '40px 32px' } }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 56,
              height: 56,
              borderRadius: 16,
              background: 'linear-gradient(135deg, #1677ff 0%, #4096ff 100%)',
              marginBottom: 16,
            }}
          >
            <RocketOutlined style={{ fontSize: 28, color: '#fff' }} />
          </div>
          <Title level={3} style={{ margin: 0 }}>
            CostPilot
          </Title>
          <Text type="secondary">Cloud Cost Optimization Platform</Text>
        </div>
        <Outlet />
      </Card>
    </div>
  );
};

export default AuthLayout;
