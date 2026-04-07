import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import { useAuthStore } from '@/store/authStore';
import { useOrgStore } from '@/store/orgStore';
import { ROUTES } from '@/utils/routes';
import AuthLayout from '@/layouts/AuthLayout';
import AppLayout from '@/layouts/AppLayout';

const Login = lazy(() => import('@/pages/Login'));
const Register = lazy(() => import('@/pages/Register'));
const SelectOrganization = lazy(() => import('@/pages/SelectOrganization'));
const Dashboard = lazy(() => import('@/pages/Dashboard'));
const Expenses = lazy(() => import('@/pages/Expenses'));
const Recommendations = lazy(() => import('@/pages/Recommendations'));
const RecommendationDetail = lazy(() => import('@/pages/RecommendationDetail'));
const RecommendationRules = lazy(() => import('@/pages/RecommendationRules'));
const Pools = lazy(() => import('@/pages/Pools'));
const CloudAccounts = lazy(() => import('@/pages/CloudAccounts'));
const CloudAccountDetails = lazy(() => import('@/pages/CloudAccountDetails'));
const ConnectCloudAccount = lazy(() => import('@/pages/ConnectCloudAccount'));
const Resources = lazy(() => import('@/pages/Resources'));
const ResourceDetail = lazy(() => import('@/pages/ResourceDetail'));
const Users = lazy(() => import('@/pages/Users'));
const Settings = lazy(() => import('@/pages/Settings'));
const RBAC = lazy(() => import('@/pages/RBAC'));
const Exports = lazy(() => import('@/pages/Exports'));
const Schedulers = lazy(() => import('@/pages/Schedulers'));
const NotFound = lazy(() => import('@/pages/NotFound'));

const Loading = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
    <Spin size="large" />
  </div>
);

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const user = useAuthStore((s) => s.user);
  if (!user) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }
  return <>{children}</>;
};

const OrgGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const currentOrg = useOrgStore((s) => s.currentOrg);
  if (!currentOrg) {
    return <SelectOrganization />;
  }
  return <>{children}</>;
};

const GuestRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const user = useAuthStore((s) => s.user);
  if (user) {
    return <Navigate to={ROUTES.DASHBOARD} replace />;
  }
  return <>{children}</>;
};

const App: React.FC = () => {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        {/* Auth routes */}
        <Route
          element={
            <GuestRoute>
              <AuthLayout />
            </GuestRoute>
          }
        >
          <Route path={ROUTES.LOGIN} element={<Login />} />
          <Route path={ROUTES.REGISTER} element={<Register />} />
        </Route>

        {/* Protected routes */}
        <Route
          element={
            <ProtectedRoute>
              <OrgGuard>
                <AppLayout />
              </OrgGuard>
            </ProtectedRoute>
          }
        >
          <Route path={ROUTES.DASHBOARD} element={<Dashboard />} />
          <Route path={ROUTES.EXPENSES} element={<Expenses />} />
          <Route path={ROUTES.RECOMMENDATIONS} element={<Recommendations />} />
          <Route path={ROUTES.RECOMMENDATION_DETAIL} element={<RecommendationDetail />} />
          <Route path={ROUTES.RECOMMENDATION_RULES} element={<RecommendationRules />} />
          <Route path={ROUTES.POOLS} element={<Pools />} />
          <Route path={ROUTES.CLOUD_ACCOUNTS} element={<CloudAccounts />} />
          <Route path={ROUTES.CLOUD_ACCOUNT_DETAIL} element={<CloudAccountDetails />} />
          <Route path={ROUTES.CONNECT_CLOUD_ACCOUNT} element={<ConnectCloudAccount />} />
          <Route path={ROUTES.RESOURCES} element={<Resources />} />
          <Route path={ROUTES.RESOURCE_DETAIL} element={<ResourceDetail />} />
          <Route path={ROUTES.USERS} element={<Users />} />
          <Route path={ROUTES.SETTINGS} element={<Settings />} />
          <Route path={ROUTES.RBAC} element={<RBAC />} />
          <Route path={ROUTES.EXPORTS} element={<Exports />} />
          <Route path={ROUTES.SCHEDULERS} element={<Schedulers />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
};

export default App;
