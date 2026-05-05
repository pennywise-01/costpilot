import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Checkbox,
  Modal,
  Skeleton,
  Space,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  CopyOutlined,
  DownloadOutlined,
  RocketOutlined,
} from '@ant-design/icons';
import {
  cloudAccountsApi,
  IamPolicyResponse,
  IamTier,
  AwsPolicyBundle,
  AwsPolicyDocument,
  AzureGcpPolicy,
} from '@/api/cloudAccounts';

const { Paragraph, Text, Link } = Typography;

interface IamPolicyModalProps {
  open: boolean;
  onClose: () => void;
  cloud: 'aws' | 'azure' | 'gcp';
  /**
   * If supplied, the modal renders a "Launch CloudFormation" button
   * that pre-fills the trust policy with this principal + ExternalId.
   * Required for the assume-role onboarding flow.
   */
  trustPrincipal?: string;
  externalId?: string;
}

const ALL_TIERS: IamTier[] = ['billing', 'advisor', 'config'];

const TIER_LABELS: Record<IamTier, string> = {
  billing: 'Billing (cost & usage)',
  advisor: 'Advisor (Compute Optimizer, Trusted Advisor, COH)',
  config: 'Config (resource state, IAM, security graph) — Tier 2',
};

/**
 * Hosted CloudFormation template that creates a read-only role and
 * attaches the policy CostPilot needs. The template accepts the policy
 * action list and trust ExternalId as parameters, so it works
 * end-to-end with no manual JSON editing.
 *
 * Public template URL — same JSON the backend generates, just packaged
 * as a stack so the user gets a one-click experience.
 */
const CFN_TEMPLATE_URL =
  'https://costpilot-public-templates.s3.amazonaws.com/aws-readonly-role.yaml';

const IamPolicyModal: React.FC<IamPolicyModalProps> = ({
  open,
  onClose,
  cloud,
  trustPrincipal,
  externalId,
}) => {
  const [tiers, setTiers] = useState<IamTier[]>(['billing', 'advisor']);
  const [response, setResponse] = useState<IamPolicyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    cloudAccountsApi
      .getIamPolicy({
        cloud,
        tiers,
        trust_principal: cloud === 'aws' ? trustPrincipal : undefined,
        external_id: cloud === 'aws' ? externalId : undefined,
      })
      .then((res) => {
        if (cancelled) return;
        setResponse(res.data);
      })
      .catch((err: { response?: { data?: { detail?: string } }; message?: string }) => {
        if (cancelled) return;
        setError(
          err?.response?.data?.detail ||
            err?.message ||
            'Failed to load IAM policy.',
        );
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, cloud, tiers, trustPrincipal, externalId]);

  const policyJson = useMemo(() => {
    if (!response) return '';
    return JSON.stringify(response.policy, null, 2);
  }, [response]);

  const handleCopy = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      message.success(`${label} copied to clipboard`);
    } catch {
      message.error('Could not access clipboard. Please copy manually.');
    }
  };

  const handleDownload = (text: string, filename: string) => {
    const blob = new Blob([text], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  /**
   * AWS CloudFormation Quick-Create URL. Pre-fills the stack with the
   * ExternalId and (optional) trust-principal parameters so the user
   * just clicks Create. Region defaults to us-east-1 since IAM is
   * global; the user can change it in the console.
   */
  const cloudFormationUrl = useMemo(() => {
    if (cloud !== 'aws') return null;
    const params = new URLSearchParams({
      templateURL: CFN_TEMPLATE_URL,
      stackName: 'CostPilotReadOnlyRole',
      param_ExternalId: externalId || '',
      param_TrustPrincipal: trustPrincipal || '',
      param_Tiers: tiers.join(','),
    });
    return (
      'https://console.aws.amazon.com/cloudformation/home?#/stacks/quickcreate?' +
      params.toString()
    );
  }, [cloud, tiers, trustPrincipal, externalId]);

  const renderAwsPolicy = () => {
    if (!response) return null;
    const policy = response.policy as AwsPolicyDocument | AwsPolicyBundle;
    const isBundle = (policy as AwsPolicyBundle).Policy !== undefined;
    const inlinePolicy = isBundle
      ? (policy as AwsPolicyBundle).Policy
      : (policy as AwsPolicyDocument);
    const trustPolicy = isBundle ? (policy as AwsPolicyBundle).TrustPolicy : null;

    const inlineJson = JSON.stringify(inlinePolicy, null, 2);
    const trustJson = trustPolicy ? JSON.stringify(trustPolicy, null, 2) : '';

    const tabs = [
      {
        key: 'inline',
        label: 'Permission Policy',
        children: (
          <PolicyPane
            json={inlineJson}
            onCopy={() => handleCopy(inlineJson, 'Permission policy')}
            onDownload={() =>
              handleDownload(inlineJson, 'costpilot-permissions.json')
            }
          />
        ),
      },
    ];
    if (trustPolicy) {
      tabs.push({
        key: 'trust',
        label: 'Trust Policy',
        children: (
          <PolicyPane
            json={trustJson}
            onCopy={() => handleCopy(trustJson, 'Trust policy')}
            onDownload={() => handleDownload(trustJson, 'costpilot-trust.json')}
          />
        ),
      });
    }

    return (
      <>
        <Tabs items={tabs} />
        {cloudFormationUrl && trustPrincipal && externalId ? (
          <Alert
            type="info"
            showIcon
            style={{ marginTop: 16 }}
            message="One-click setup with CloudFormation"
            description={
              <>
                <Paragraph style={{ marginBottom: 8 }}>
                  Launches a stack that creates a read-only role trusting
                  CostPilot via <Text code>sts:ExternalId={externalId}</Text>.
                  After it finishes, copy the role ARN from the stack outputs
                  back into the wizard.
                </Paragraph>
                <Button
                  type="primary"
                  icon={<RocketOutlined />}
                  href={cloudFormationUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Launch CloudFormation
                </Button>
              </>
            }
          />
        ) : (
          <Alert
            type="warning"
            showIcon
            style={{ marginTop: 16 }}
            message="One-click setup unavailable"
            description={
              <Text type="secondary">
                Switch the wizard to <strong>Role-based</strong> auth and
                provide a trust principal + external ID to enable the
                CloudFormation launch button.
              </Text>
            }
          />
        )}
      </>
    );
  };

  const renderAzureGcpPolicy = () => {
    if (!response) return null;
    const policy = response.policy as AzureGcpPolicy;
    return (
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Paragraph>{policy.instructions}</Paragraph>
        <Space size={[8, 8]} wrap>
          {policy.roles.map((role) => (
            <Tag key={role} color={cloud === 'azure' ? 'blue' : 'green'}>
              {role}
            </Tag>
          ))}
        </Space>
        <Button
          icon={<CopyOutlined />}
          onClick={() => handleCopy(policy.roles.join('\n'), 'Role list')}
        >
          Copy role list
        </Button>
        {cloud === 'gcp' && (
          <Alert
            type="info"
            showIcon
            message="gcloud one-liner"
            description={
              <>
                <Text code copyable style={{ display: 'block' }}>
                  {policy.roles
                    .map(
                      (r) =>
                        `gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SA --role=${r}`,
                    )
                    .join(' && \\\n')}
                </Text>
              </>
            }
          />
        )}
      </Space>
    );
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={`Required IAM policy — ${cloud.toUpperCase()}`}
      width={780}
      footer={[
        <Button key="close" onClick={onClose}>
          Close
        </Button>,
      ]}
    >
      <Paragraph type="secondary">
        Grant CostPilot the read-only access it needs by applying this
        policy in your cloud provider. The actions below are scoped to
        the data tiers you select.
      </Paragraph>

      <Checkbox.Group
        value={tiers}
        onChange={(vals) => setTiers(vals as IamTier[])}
        style={{ marginBottom: 16 }}
      >
        <Space direction="vertical">
          {ALL_TIERS.map((t) => (
            <Tooltip
              key={t}
              title={
                t === 'config'
                  ? 'Tier 2 — resource state, IAM, security graph (config ingestor wired)'
                  : undefined
              }
            >
              <Checkbox value={t} disabled={t === 'billing'}>
                {TIER_LABELS[t]}
              </Checkbox>
            </Tooltip>
          ))}
        </Space>
      </Checkbox.Group>

      {error && (
        <Alert type="error" message={error} style={{ marginBottom: 16 }} />
      )}

      {loading ? (
        <Skeleton active />
      ) : cloud === 'aws' ? (
        renderAwsPolicy()
      ) : (
        renderAzureGcpPolicy()
      )}

      <Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
        <Link
          href="https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_create.html"
          target="_blank"
          rel="noopener noreferrer"
        >
          AWS docs: creating policies
        </Link>
        {' · '}
        <Link
          href="https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments-portal"
          target="_blank"
          rel="noopener noreferrer"
        >
          Azure docs: role assignment
        </Link>
        {' · '}
        <Link
          href="https://cloud.google.com/iam/docs/granting-changing-revoking-access"
          target="_blank"
          rel="noopener noreferrer"
        >
          GCP docs: granting roles
        </Link>
      </Paragraph>
    </Modal>
  );
};

interface PolicyPaneProps {
  json: string;
  onCopy: () => void;
  onDownload: () => void;
}

const PolicyPane: React.FC<PolicyPaneProps> = ({ json, onCopy, onDownload }) => (
  <Space direction="vertical" size={8} style={{ width: '100%' }}>
    <Space>
      <Button icon={<CopyOutlined />} onClick={onCopy}>
        Copy JSON
      </Button>
      <Button icon={<DownloadOutlined />} onClick={onDownload}>
        Download .json
      </Button>
    </Space>
    <pre
      style={{
        background: '#0b1020',
        color: '#e6eaf2',
        padding: 12,
        borderRadius: 6,
        maxHeight: 320,
        overflow: 'auto',
        fontSize: 12,
        margin: 0,
      }}
    >
      {json}
    </pre>
  </Space>
);

export default IamPolicyModal;
