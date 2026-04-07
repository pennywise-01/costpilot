import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown, Typography, theme, Space, Button, Select, Spin } from 'antd';
import {
  DashboardOutlined,
  DollarOutlined,
  BulbOutlined,
  AppstoreOutlined,
  CloudOutlined,
  TeamOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  UserOutlined,
  SafetyCertificateOutlined,
  AlertOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  RocketOutlined,
  CrownOutlined,
  BankOutlined,
  ScheduleOutlined,
  ExportOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/store/authStore';
import { useOrgStore } from '@/store/orgStore';
import { authApi } from '@/api/auth';
import { ROUTES } from '@/utils/routes';
import { useSessionValidator } from '@/hooks/useSessionValidator';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

type MenuItem = Required<MenuProps>['items'][number];

const menuItems: MenuItem[] = [
  {
    key: 'home-group',
    label: 'HOME',
    type: 'group',
    children: [
      { key: ROUTES.DASHBOARD, icon: <DashboardOutlined />, label: 'Dashboard' },
      { key: ROUTES.RECOMMENDATIONS, icon: <BulbOutlined />, label: 'Recommendations' },
      { key: ROUTES.RECOMMENDATION_RULES, icon: <SafetyCertificateOutlined />, label: 'Recommendation Rules' },
      { key: ROUTES.RESOURCES, icon: <AppstoreOutlined />, label: 'Resources' },
      { key: ROUTES.POOLS, icon: <AppstoreOutlined />, label: 'Pools' },
      { key: ROUTES.SCHEDULERS, icon: <ScheduleOutlined />, label: 'Schedulers' },
    ],
  },
  {
    key: 'finops-group',
    label: 'FINOPS',
    type: 'group',
    children: [
      { key: ROUTES.EXPENSES, icon: <DollarOutlined />, label: 'Expenses' },
    ],
  },
  {
    key: 'policies-group',
    label: 'POLICIES',
    type: 'group',
    children: [
      { key: '/anomalies', icon: <AlertOutlined />, label: 'Anomalies', disabled: true },
      { key: '/quotas', icon: <FileTextOutlined />, label: 'Quotas & Budgets', disabled: true },
      { key: '/power-schedules', icon: <ThunderboltOutlined />, label: 'Power Schedules', disabled: true },
    ],
  },
  {
    key: 'enterprise-group',
    label: 'ENTERPRISE',
    type: 'group',
    children: [
      { key: ROUTES.RBAC, icon: <SafetyCertificateOutlined />, label: 'Access Control' },
      { key: ROUTES.EXPORTS, icon: <ExportOutlined />, label: 'Data Export' },
      { key: '/chargeback', icon: <CrownOutlined />, label: 'Chargeback', disabled: true },
      { key: '/forecasting', icon: <CrownOutlined />, label: 'Forecasting', disabled: true },
      { key: '/audit-logs', icon: <SafetyCertificateOutlined />, label: 'Audit Logs', disabled: true },
    ],
  },
  {
    key: 'system-group',
    label: 'SYSTEM',
    type: 'group',
    children: [
      { key: ROUTES.USERS, icon: <TeamOutlined />, label: 'Users' },
      { key: ROUTES.CLOUD_ACCOUNTS, icon: <CloudOutlined />, label: 'Data Sources' },
      { key: ROUTES.SETTINGS, icon: <SettingOutlined />, label: 'Settings' },
    ],
  },
];

const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { currentOrg, organizations, setCurrentOrg, clearOrg } = useOrgStore();
  const { token: themeToken } = theme.useToken();
  const queryClient = useQueryClient();
  
  // Validate session with server on mount - prevents session replay attacks
  const { isValidating } = useSessionValidator();

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    navigate(key);
  };

  const handleOrgSwitch = (orgId: string) => {
    const org = organizations.find((o) => o.id === orgId);
    if (org) {
      setCurrentOrg(org);
      queryClient.invalidateQueries();
    }
  };

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: 'Profile',
      onClick: () => navigate(ROUTES.SETTINGS),
    },
    {
      key: 'switch-org',
      icon: <BankOutlined />,
      label: 'Switch Organization',
      onClick: () => {
        clearOrg();
      },
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      danger: true,
      onClick: async () => {
        try { await authApi.logout(); } catch { /* ignore */ }
        logout();
        navigate(ROUTES.LOGIN);
      },
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={250}
        style={{
          background: '#fff',
          borderRight: `1px solid ${themeToken.colorBorderSecondary}`,
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 10,
        }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? '0' : '0 20px',
            borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
            gap: 10,
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: 'linear-gradient(135deg, #1677ff 0%, #4096ff 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <RocketOutlined style={{ fontSize: 18, color: '#fff' }} />
          </div>
          {!collapsed && (
            <Text strong style={{ fontSize: 18 }}>
              CostPilot
            </Text>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{
            border: 'none',
            padding: '8px 0',
          }}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 250, transition: 'margin-left 0.2s' }}>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
            position: 'sticky',
            top: 0,
            zIndex: 9,
            height: 64,
          }}
        >
          <Space>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              style={{ fontSize: 16, width: 40, height: 40 }}
            />
            {organizations.length > 1 && (
              <Select
                value={currentOrg?.id}
                onChange={handleOrgSwitch}
                style={{ minWidth: 180 }}
                suffixIcon={<BankOutlined />}
                options={organizations.map((org) => ({
                  value: org.id,
                  label: org.name,
                }))}
              />
            )}
            {organizations.length <= 1 && currentOrg && (
              <Space>
                <BankOutlined style={{ color: themeToken.colorTextSecondary }} />
                <Text strong>{currentOrg.name}</Text>
              </Space>
            )}
          </Space>
          <Space size={16}>
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" arrow>
              <Space style={{ cursor: 'pointer' }}>
                <Avatar
                  style={{ backgroundColor: themeToken.colorPrimary }}
                  icon={<UserOutlined />}
                />
                <Text>{user?.display_name || 'User'}</Text>
              </Space>
            </Dropdown>
          </Space>
        </Header>
        <Content
          style={{
            margin: 24,
            minHeight: 'calc(100vh - 112px)',
          }}
        >
          {isValidating ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
              <Spin size="large" tip="Validating session..." />
            </div>
          ) : (
            <Outlet />
          )}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
