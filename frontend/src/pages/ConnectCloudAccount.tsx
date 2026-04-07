import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Typography,
  Steps,
  Card,
  Row,
  Col,
  Button,
  Form,
  Input,
  Select,
  Result,
  Space,
  Alert,
  message,
} from 'antd';
import {
  CloudOutlined,
  CheckCircleFilled,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  LinkOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { CLOUD_TYPE_LABELS, CLOUD_TYPE_COLORS } from '@/utils/constants';
import { cloudAccountsApi } from '@/api/cloudAccounts';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface ProviderOption {
  key: string;
  name: string;
  description: string;
  color: string;
}

const providers: ProviderOption[] = [
  {
    key: 'aws_cnr',
    name: 'Amazon Web Services',
    description: 'Connect your AWS account using IAM access keys to import cost and usage data.',
    color: CLOUD_TYPE_COLORS.aws_cnr,
  },
  {
    key: 'azure_cnr',
    name: 'Microsoft Azure',
    description: 'Connect via Azure service principal with Tenant ID and Client credentials.',
    color: CLOUD_TYPE_COLORS.azure_cnr,
  },
  {
    key: 'gcp_cnr',
    name: 'Google Cloud Platform',
    description: 'Connect with a GCP service account key to import billing data.',
    color: CLOUD_TYPE_COLORS.gcp_cnr,
  },
  {
    key: 'alibaba_cnr',
    name: 'Alibaba Cloud',
    description: 'Connect your Alibaba Cloud account to track resource costs.',
    color: CLOUD_TYPE_COLORS.alibaba_cnr,
  },
  {
    key: 'kubernetes_cnr',
    name: 'Kubernetes',
    description: 'Connect a Kubernetes cluster to monitor pod and namespace costs.',
    color: CLOUD_TYPE_COLORS.kubernetes_cnr,
  },
  {
    key: 'nebius',
    name: 'Nebius',
    description: 'Connect your Nebius cloud account for cost tracking and optimization.',
    color: CLOUD_TYPE_COLORS.nebius,
  },
];

const awsRegions = [
  'us-east-1',
  'us-east-2',
  'us-west-1',
  'us-west-2',
  'eu-west-1',
  'eu-central-1',
  'ap-southeast-1',
  'ap-northeast-1',
];

const buildConfig = (provider: string, values: Record<string, string>): Record<string, string> => {
  switch (provider) {
    case 'aws_cnr':
      return {
        access_key_id: values.accessKeyId,
        secret_access_key: values.secretAccessKey,
        region: values.region,
      };
    case 'azure_cnr':
      return {
        tenant_id: values.tenantId,
        client_id: values.clientId,
        client_secret: values.clientSecret,
        subscription_id: values.subscriptionId,
      };
    case 'gcp_cnr':
      return {
        project_id: values.projectId,
        service_account_key: values.serviceAccountKey,
      };
    default:
      try {
        return JSON.parse(values.config);
      } catch {
        return { raw: values.config };
      }
  }
};

const ConnectCloudAccount: React.FC = () => {
  const navigate = useNavigate();
  const orgId = useCurrentOrgId();
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [form] = Form.useForm();

  const handleProviderSelect = (key: string) => {
    setSelectedProvider(key);
    setCurrentStep(1);
    setSubmitError(null);
  };

  const handleNext = async () => {
    if (currentStep === 1) {
      try {
        const values = await form.validateFields();
        setSubmitting(true);
        setSubmitError(null);

        const config = buildConfig(selectedProvider!, values);
        const accountName = values.accountName || `${CLOUD_TYPE_LABELS[selectedProvider!] || selectedProvider} Account`;

        await cloudAccountsApi.create(orgId, {
          name: accountName,
          type: selectedProvider!,
          config,
        });

        message.success('Cloud account connected successfully');
        setCurrentStep(2);
      } catch (err: unknown) {
        const errorMsg = err instanceof Error ? err.message
          : (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
            || 'Failed to connect cloud account. Please check your credentials and try again.';
        setSubmitError(errorMsg);
      } finally {
        setSubmitting(false);
      }
    }
  };

  const handleBack = () => {
    if (currentStep === 1) {
      setSelectedProvider(null);
      setCurrentStep(0);
      setSubmitError(null);
    } else if (currentStep === 2) {
      setCurrentStep(1);
    }
  };

  const renderProviderForm = () => {
    switch (selectedProvider) {
      case 'aws_cnr':
        return (
          <>
            <Form.Item
              name="accessKeyId"
              label="Access Key ID"
              rules={[{ required: true, message: 'Access Key ID is required' }]}
            >
              <Input placeholder="AKIAIOSFODNN7EXAMPLE" />
            </Form.Item>
            <Form.Item
              name="secretAccessKey"
              label="Secret Access Key"
              rules={[{ required: true, message: 'Secret Access Key is required' }]}
            >
              <Input.Password placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" />
            </Form.Item>
            <Form.Item
              name="region"
              label="Default Region"
              rules={[{ required: true, message: 'Region is required' }]}
            >
              <Select placeholder="Select a region">
                {awsRegions.map((r) => (
                  <Select.Option key={r} value={r}>{r}</Select.Option>
                ))}
              </Select>
            </Form.Item>
          </>
        );
      case 'azure_cnr':
        return (
          <>
            <Form.Item
              name="tenantId"
              label="Tenant ID"
              rules={[{ required: true, message: 'Tenant ID is required' }]}
            >
              <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
            </Form.Item>
            <Form.Item
              name="clientId"
              label="Client ID"
              rules={[{ required: true, message: 'Client ID is required' }]}
            >
              <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
            </Form.Item>
            <Form.Item
              name="clientSecret"
              label="Client Secret"
              rules={[{ required: true, message: 'Client Secret is required' }]}
            >
              <Input.Password placeholder="Client secret value" />
            </Form.Item>
            <Form.Item
              name="subscriptionId"
              label="Subscription ID"
              rules={[{ required: true, message: 'Subscription ID is required' }]}
            >
              <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
            </Form.Item>
          </>
        );
      case 'gcp_cnr':
        return (
          <>
            <Form.Item
              name="projectId"
              label="Project ID"
              rules={[{ required: true, message: 'Project ID is required' }]}
            >
              <Input placeholder="my-project-123456" />
            </Form.Item>
            <Form.Item
              name="serviceAccountKey"
              label="Service Account Key (JSON)"
              rules={[{ required: true, message: 'Service account key is required' }]}
            >
              <Input.Password
                placeholder='Paste your service account JSON key here'
                visibilityToggle
                style={{ fontFamily: 'monospace', fontSize: 12 }}
              />
            </Form.Item>
          </>
        );
      default:
        return (
          <>
            <Form.Item
              name="name"
              label="Account Name"
              rules={[{ required: true, message: 'Account name is required' }]}
            >
              <Input placeholder="My cloud account" />
            </Form.Item>
            <Form.Item
              name="config"
              label="Configuration (JSON)"
              rules={[{ required: true, message: 'Configuration is required' }]}
            >
              <TextArea
                rows={6}
                placeholder='{\n  "key": "value"\n}'
                style={{ fontFamily: 'monospace', fontSize: 12 }}
              />
            </Form.Item>
          </>
        );
    }
  };

  const selectedProviderName = selectedProvider
    ? CLOUD_TYPE_LABELS[selectedProvider] || selectedProvider
    : '';

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <Title level={3} style={{ marginBottom: 24 }}>
        <LinkOutlined style={{ marginRight: 8 }} />
        Connect Cloud Account
      </Title>

      <Steps
        current={currentStep}
        style={{ marginBottom: 32 }}
        items={[
          { title: 'Select Provider' },
          { title: 'Enter Credentials' },
          { title: 'Verify & Connect' },
        ]}
      />

      {currentStep === 0 && (
        <Row gutter={[16, 16]}>
          {providers.map((provider) => (
            <Col xs={24} sm={12} md={8} key={provider.key}>
              <Card
                hoverable
                onClick={() => handleProviderSelect(provider.key)}
                style={{
                  height: '100%',
                  textAlign: 'center',
                  borderColor: selectedProvider === provider.key ? provider.color : undefined,
                }}
              >
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: 12,
                      backgroundColor: `${provider.color}15`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      margin: '0 auto',
                    }}
                  >
                    <CloudOutlined style={{ fontSize: 24, color: provider.color }} />
                  </div>
                  <Text strong style={{ fontSize: 15 }}>{provider.name}</Text>
                  <Paragraph
                    type="secondary"
                    style={{ fontSize: 12, marginBottom: 0 }}
                    ellipsis={{ rows: 3 }}
                  >
                    {provider.description}
                  </Paragraph>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {currentStep === 1 && (
        <Card
          title={
            <Space>
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  backgroundColor: CLOUD_TYPE_COLORS[selectedProvider || ''] || '#999',
                }}
              />
              <span>{selectedProviderName} Credentials</span>
            </Space>
          }
        >
          <Form form={form} layout="vertical" style={{ maxWidth: 500 }}>
            <Form.Item
              name="accountName"
              label="Account Name"
              rules={[{ required: true, message: 'Account name is required' }]}
            >
              <Input placeholder={`My ${selectedProviderName} account`} />
            </Form.Item>
            {renderProviderForm()}
          </Form>
          {submitError && (
            <Alert
              type="error"
              message="Connection Failed"
              description={submitError}
              closable
              onClose={() => setSubmitError(null)}
              style={{ marginTop: 16 }}
            />
          )}
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 24 }}>
            <Button icon={<ArrowLeftOutlined />} onClick={handleBack} disabled={submitting}>
              Back
            </Button>
            <Button
              type="primary"
              icon={submitting ? <LoadingOutlined /> : <ArrowRightOutlined />}
              onClick={handleNext}
              loading={submitting}
            >
              {submitting ? 'Connecting...' : 'Connect'}
            </Button>
          </div>
        </Card>
      )}

      {currentStep === 2 && (
        <Card>
          <Result
            icon={<CheckCircleFilled style={{ color: '#52c41a' }} />}
            status="success"
            title={`Successfully connected ${selectedProviderName}!`}
            subTitle="Your cloud account has been linked and the initial data import will begin shortly. Cost data will appear within a few hours."
            extra={[
              <Button
                type="primary"
                key="datasources"
                onClick={() => navigate('/cloud-accounts')}
              >
                Go to Data Sources
              </Button>,
              <Button key="another" onClick={() => {
                setCurrentStep(0);
                setSelectedProvider(null);
                form.resetFields();
              }}>
                Connect Another Account
              </Button>,
            ]}
          />
        </Card>
      )}
    </div>
  );
};

export default ConnectCloudAccount;
