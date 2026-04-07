import { useState } from 'react';
import {
  Modal,
  Form,
  Input,
  Select,
  Button,
  message,
  Space,
  Alert,
  List,
  Tag,
} from 'antd';
import { PlusOutlined, DeleteOutlined, MailOutlined } from '@ant-design/icons';
import { useUserStore } from '../../store/userStore';
import { rbacApi } from '../../api/rbac';
import { useOrgStore } from '../../store/orgStore';
import { useEffect } from 'react';
import type { Role } from '../../api/rbac';

interface UserInviteModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  orgId: string;
}

interface InvitationForm {
  email: string;
  role_id: string;
  department?: string;
  job_title?: string;
}

export const UserInviteModal: React.FC<UserInviteModalProps> = ({
  open,
  onClose,
  onSuccess,
  orgId,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [roles, setRoles] = useState<Role[]>([]);
  const [invitations, setInvitations] = useState<InvitationForm[]>([{ email: '', role_id: '' }]);
  const [bulkMode, setBulkMode] = useState(false);

  const { inviteUser, inviteBulk } = useUserStore();

  useEffect(() => {
    if (open && orgId) {
      fetchRoles();
    }
  }, [open, orgId]);

  const fetchRoles = async () => {
    try {
      const response = await rbacApi.listRoles(orgId);
      const rolesData = response.data;
      setRoles(Array.isArray(rolesData) ? rolesData : (rolesData as { items?: Role[] })?.items ?? []);
    } catch (error) {
      message.error('Failed to load roles');
    }
  };

  const handleAddInvitation = () => {
    setInvitations([...invitations, { email: '', role_id: '' }]);
  };

  const handleRemoveInvitation = (index: number) => {
    setInvitations(invitations.filter((_, i) => i !== index));
  };

  const handleInvitationChange = (index: number, field: keyof InvitationForm, value: string) => {
    const newInvitations = [...invitations];
    newInvitations[index] = { ...newInvitations[index], [field]: value };
    setInvitations(newInvitations);
  };

  const handleSubmit = async () => {
    if (!orgId) return;

    // Validate all invitations
    const validInvitations = invitations.filter((inv) => inv.email && inv.role_id);
    if (validInvitations.length === 0) {
      message.error('Please add at least one valid invitation');
      return;
    }

    setLoading(true);
    try {
      if (bulkMode && validInvitations.length > 1) {
        const result = await inviteBulk(orgId, validInvitations);
        if (result.failed > 0) {
          message.warning(`${result.successful} invitations sent, ${result.failed} failed`);
        } else {
          message.success(`${result.successful} invitations sent successfully`);
        }
      } else {
        await inviteUser(orgId, validInvitations[0]);
        message.success('Invitation sent successfully');
      }
      onSuccess();
      setInvitations([{ email: '', role_id: '' }]);
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to send invitation');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setInvitations([{ email: '', role_id: '' }]);
    setBulkMode(false);
    onClose();
  };

  return (
    <Modal
      title={
        <Space>
          <MailOutlined />
          {bulkMode ? 'Bulk Invite Users' : 'Invite User'}
        </Space>
      }
      open={open}
      onCancel={handleClose}
      width={600}
      footer={[
        <Button key="cancel" onClick={handleClose}>
          Cancel
        </Button>,
        <Button
          key="submit"
          type="primary"
          loading={loading}
          onClick={handleSubmit}
          disabled={invitations.every((inv) => !inv.email || !inv.role_id)}
        >
          Send Invitation{invitations.length > 1 ? 's' : ''}
        </Button>,
      ]}
    >
      <div style={{ marginBottom: 16 }}>
        <Button
          type="link"
          onClick={() => setBulkMode(!bulkMode)}
          style={{ padding: 0 }}
        >
          {bulkMode ? 'Switch to single invite' : 'Switch to bulk invite'}
        </Button>
      </div>

      <Space direction="vertical" style={{ width: '100%' }}>
        {invitations.map((invitation, index) => (
          <div
            key={index}
            style={{
              padding: 16,
              border: '1px solid #f0f0f0',
              borderRadius: 8,
              backgroundColor: '#fafafa',
            }}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <Tag>Invitation {index + 1}</Tag>
                {bulkMode && invitations.length > 1 && (
                  <Button
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    size="small"
                    onClick={() => handleRemoveInvitation(index)}
                  />
                )}
              </Space>

              <Input
                placeholder="Email address"
                value={invitation.email}
                onChange={(e) => handleInvitationChange(index, 'email', e.target.value)}
                style={{ width: '100%' }}
              />

              <Select
                placeholder="Select role"
                value={invitation.role_id || undefined}
                onChange={(value) => handleInvitationChange(index, 'role_id', value)}
                style={{ width: '100%' }}
              >
                {roles.map((role) => (
                  <Select.Option key={role.id} value={role.id}>
                    {role.name}
                  </Select.Option>
                ))}
              </Select>

              <Input
                placeholder="Department (optional)"
                value={invitation.department}
                onChange={(e) => handleInvitationChange(index, 'department', e.target.value)}
                style={{ width: '100%' }}
              />

              <Input
                placeholder="Job title (optional)"
                value={invitation.job_title}
                onChange={(e) => handleInvitationChange(index, 'job_title', e.target.value)}
                style={{ width: '100%' }}
              />
            </Space>
          </div>
        ))}

        {bulkMode && (
          <Button
            type="dashed"
            icon={<PlusOutlined />}
            onClick={handleAddInvitation}
            style={{ width: '100%' }}
          >
            Add Another Invitation
          </Button>
        )}
      </Space>

      <Alert
        message="Invitation Details"
        description="Invited users will receive an email with a link to join the organization. The invitation expires in 7 days."
        type="info"
        showIcon
        style={{ marginTop: 16 }}
      />
    </Modal>
  );
};
