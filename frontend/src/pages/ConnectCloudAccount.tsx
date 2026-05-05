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
  Radio,
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
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { CLOUD_TYPE_LABELS, CLOUD_TYPE_COLORS } from '@/utils/constants';
import { cloudAccountsApi } from '@/api/cloudAccounts';
import { useCurrentOrgId } from '@/hooks/useCurrentOrgId';
import IamPolicyModal from '@/components/cloud-accounts/IamPolicyModal';

type AwsAuthMode = 'keys' | 'role';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface ProviderOption {
  key: string;
  name: string;
  description: string;
  color: string;
}

const providers: ProviderOption[] = [
  // Cloud Service Providers (direct API)
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
  // Big Data Analytics Platforms (query normalized tables)
  {
    key: 'bigquery',
    name: 'GCP BigQuery',
    description: 'Query normalized billing data from GCP BigQuery tables instead of calling APIs.',
    color: '#4285F4',
  },
  {
    key: 'redshift',
    name: 'AWS Redshift',
    description: 'Query normalized billing data from AWS Redshift tables via Data API.',
    color: '#FF9900',
  },
  {
    key: 'athena',
    name: 'AWS Athena',
    description: 'Query normalized billing data from AWS Athena tables (CUR export to S3).',
    color: '#527FFF',
  },
  {
    key: 'synapse',
    name: 'Azure Synapse Analytics',
    description: 'Query normalized billing data from Azure Synapse Analytics tables.',
    color: '#0078D4',
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
    case 'aws_cnr': {
      // Role-based auth (recommended) — assume-role with optional ExternalId.
      // Static keys remain supported for self-hosted users without an
      // sts:AssumeRole-capable identity.
      if (values.awsAuthMode === 'role') {
        return {
          role_arn: values.roleArn,
          external_id: values.externalId || '',
          region: values.region,
        };
      }
      return {
        access_key_id: values.accessKeyId,
        secret_access_key: values.secretAccessKey,
        region: values.region,
      };
    }
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
    // Analytics connectors
    case 'bigquery':
      return {
        project_id: values.projectId,
        dataset_id: values.datasetId,
        table_name: values.tableName,
        service_account_key: values.serviceAccountKey,
        location: values.location || 'US',
      };
    case 'redshift':
      return {
        cluster_id: values.clusterId,
        database: values.database || 'dev',
        table_name: values.tableName,
        host: values.host,
        port: values.port || '5439',
        region: values.region || 'us-east-1',
        iam_access_key_id: values.iamAccessKeyId,
        iam_secret_access_key: values.iamSecretAccessKey,
      };
    case 'athena':
      return {
        database: values.database,
        table_name: values.tableName,
        s3_output_location: values.s3OutputLocation,
        region: values.region || 'us-east-1',
        workgroup: values.workgroup || 'primary',
        iam_access_key_id: values.iamAccessKeyId,
        iam_secret_access_key: values.iamSecretAccessKey,
      };
    case 'synapse':
      return {
        server: values.server,
        database: values.database,
        table_name: values.tableName,
        tenant_id: values.tenantId,
        client_id: values.clientId,
        client_secret: values.clientSecret,
        port: values.port || '1433',
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
  const [iamModalOpen, setIamModalOpen] = useState(false);
  const [awsAuthMode, setAwsAuthMode] = useState<AwsAuthMode>('role');
  // External ID used to scope the trust policy to this organization.
  // Stable per org so the user only has to set it up once.
  const trustExternalId = orgId ? `costpilot-${orgId}` : '';

  // The principal CostPilot trusts. In a real deployment this comes from
  // process.env or a /config endpoint; we read from Vite env if present
  // and fall back to an empty string (which disables the CFN button and
  // shows a "switch to role auth" hint instead).
  const trustPrincipal = (
    import.meta.env.VITE_COSTPILOT_AWS_PRINCIPAL_ARN as string | undefined
  ) || '';

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

        // Inject auth-mode state for AWS so buildConfig can branch on it
        // without making the form aware of it.
        const enrichedValues = {
          ...values,
          awsAuthMode,
        };
        const config = buildConfig(selectedProvider!, enrichedValues);
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
            <Alert
              type="info"
              showIcon
              icon={<SafetyCertificateOutlined />}
              style={{ marginBottom: 16 }}
              message="Recommended: connect via IAM Role"
              description={
                <Space direction="vertical" size={4}>
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    Role-based auth uses temporary credentials and an external ID
                    instead of long-lived access keys. Click below to see the
                    exact IAM policy CostPilot needs.
                  </Text>
                  <Button
                    size="small"
                    icon={<SafetyCertificateOutlined />}
                    onClick={() => setIamModalOpen(true)}
                  >
                    View required IAM policy
                  </Button>
                </Space>
              }
            />
            <Form.Item label="Authentication mode">
              <Radio.Group
                value={awsAuthMode}
                onChange={(e) =>
                  setAwsAuthMode(e.target.value as AwsAuthMode)
                }
                optionType="button"
                buttonStyle="solid"
              >
                <Radio.Button value="role">Role ARN (recommended)</Radio.Button>
                <Radio.Button value="keys">Access keys (legacy)</Radio.Button>
              </Radio.Group>
            </Form.Item>

            {awsAuthMode === 'role' ? (
              <>
                <Form.Item
                  name="roleArn"
                  label="Role ARN"
                  rules={[
                    { required: true, message: 'Role ARN is required' },
                    {
                      pattern: /^arn:aws:iam::\d{12}:role\/.+$/,
                      message: 'Must look like arn:aws:iam::123456789012:role/RoleName',
                    },
                  ]}
                  extra="Created by the CloudFormation stack — see the IAM policy modal."
                >
                  <Input placeholder="arn:aws:iam::123456789012:role/CostPilotReadOnly" />
                </Form.Item>
                <Form.Item
                  name="externalId"
                  label="External ID"
                  initialValue={trustExternalId}
                  extra="Required by the trust policy to prevent the confused-deputy attack."
                >
                  <Input placeholder={trustExternalId} />
                </Form.Item>
              </>
            ) : (
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
              </>
            )}

            <Form.Item
              name="region"
              label="Default Region"
              rules={[{ required: true, message: 'Region is required' }]}
              extra="Compute Optimizer will be scanned across all enabled regions; this is the bootstrap region."
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
      // Analytics connectors
      case 'bigquery':
        return (
          <>
            <Form.Item
              name="projectId"
              label="GCP Project ID"
              rules={[{ required: true, message: 'Project ID is required' }]}
            >
              <Input placeholder="my-gcp-project" />
            </Form.Item>
            <Form.Item
              name="datasetId"
              label="BigQuery Dataset ID"
              rules={[{ required: true, message: 'Dataset ID is required' }]}
            >
              <Input placeholder="cloud_billing" />
            </Form.Item>
            <Form.Item
              name="tableName"
              label="Billing Table Name"
              rules={[{ required: true, message: 'Table name is required' }]}
            >
              <Input placeholder="gcp_billing_export" />
            </Form.Item>
            <Form.Item
              name="serviceAccountKey"
              label="Service Account Key (JSON)"
              rules={[{ required: true, message: 'Service account key is required' }]}
            >
              <Input.Password
                placeholder='Paste your BigQuery service account JSON key here'
                visibilityToggle
                style={{ fontFamily: 'monospace', fontSize: 12 }}
              />
            </Form.Item>
            <Form.Item
              name="location"
              label="Dataset Location"
              initialValue="US"
            >
              <Input placeholder="US" />
            </Form.Item>
          </>
        );
      case 'redshift':
        return (
          <>
            <Form.Item
              name="host"
              label="Redshift Host"
              rules={[{ required: true, message: 'Redshift host is required' }]}
            >
              <Input placeholder="my-cluster.xxxxxx.region.redshift.amazonaws.com" />
            </Form.Item>
            <Form.Item
              name="database"
              label="Database Name"
              initialValue="dev"
            >
              <Input placeholder="dev" />
            </Form.Item>
            <Form.Item
              name="tableName"
              label="Billing Table Name"
              rules={[{ required: true, message: 'Table name is required' }]}
            >
              <Input placeholder="aws_billing" />
            </Form.Item>
            <Form.Item
              name="iamAccessKeyId"
              label="IAM Access Key ID"
              rules={[{ required: true, message: 'IAM Access Key ID is required' }]}
            >
              <Input placeholder="AKIAIOSFODNN7EXAMPLE" />
            </Form.Item>
            <Form.Item
              name="iamSecretAccessKey"
              label="IAM Secret Access Key"
              rules={[{ required: true, message: 'IAM Secret Access Key is required' }]}
            >
              <Input.Password placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" />
            </Form.Item>
            <Form.Item
              name="region"
              label="AWS Region"
              initialValue="us-east-1"
            >
              <Input placeholder="us-east-1" />
            </Form.Item>
          </>
        );
      case 'athena':
        return (
          <>
            <Form.Item
              name="database"
              label="Athena Database"
              rules={[{ required: true, message: 'Database is required' }]}
            >
              <Input placeholder="athena_billing" />
            </Form.Item>
            <Form.Item
              name="tableName"
              label="Billing Table Name"
              rules={[{ required: true, message: 'Table name is required' }]}
            >
              <Input placeholder="aws_billing_cur" />
            </Form.Item>
            <Form.Item
              name="s3OutputLocation"
              label="S3 Output Location"
              rules={[{ required: true, message: 'S3 output location is required' }]}
            >
              <Input placeholder="s3://my-bucket/athena-results/" />
            </Form.Item>
            <Form.Item
              name="iamAccessKeyId"
              label="IAM Access Key ID"
              rules={[{ required: true, message: 'IAM Access Key ID is required' }]}
            >
              <Input placeholder="AKIAIOSFODNN7EXAMPLE" />
            </Form.Item>
            <Form.Item
              name="iamSecretAccessKey"
              label="IAM Secret Access Key"
              rules={[{ required: true, message: 'IAM Secret Access Key is required' }]}
            >
              <Input.Password placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" />
            </Form.Item>
            <Form.Item
              name="region"
              label="AWS Region"
              initialValue="us-east-1"
            >
              <Input placeholder="us-east-1" />
            </Form.Item>
          </>
        );
      case 'synapse':
        return (
          <>
            <Form.Item
              name="server"
              label="Synapse Server"
              rules={[{ required: true, message: 'Synapse server is required' }]}
            >
              <Input placeholder="my-synapse.sql.azuresynapse.net" />
            </Form.Item>
            <Form.Item
              name="database"
              label="Database Name"
              rules={[{ required: true, message: 'Database is required' }]}
            >
              <Input placeholder="CloudCosts" />
            </Form.Item>
            <Form.Item
              name="tableName"
              label="Billing Table Name"
              rules={[{ required: true, message: 'Table name is required' }]}
            >
              <Input placeholder="azure_billing" />
            </Form.Item>
            <Form.Item
              name="tenantId"
              label="Azure Tenant ID"
              rules={[{ required: true, message: 'Tenant ID is required' }]}
            >
              <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
            </Form.Item>
            <Form.Item
              name="clientId"
              label="Service Principal Client ID"
              rules={[{ required: true, message: 'Client ID is required' }]}
            >
              <Input placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
            </Form.Item>
            <Form.Item
              name="clientSecret"
              label="Service Principal Client Secret"
              rules={[{ required: true, message: 'Client Secret is required' }]}
            >
              <Input.Password placeholder="Service principal secret" />
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

      {/* Mounted at the wizard root so it persists across re-renders of
          renderProviderForm. Only meaningful for AWS today; Azure/GCP
          forms can opt in later. */}
      <IamPolicyModal
        open={iamModalOpen}
        onClose={() => setIamModalOpen(false)}
        cloud="aws"
        trustPrincipal={trustPrincipal}
        externalId={trustExternalId}
      />
    </div>
  );
};

export default ConnectCloudAccount;
