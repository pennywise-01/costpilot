import React, { useState } from 'react';
import {
  Button, Space, Typography, Select, Popconfirm, Tooltip, Dropdown, Modal,
} from 'antd';
import {
  EditOutlined,
  SaveOutlined,
  UndoOutlined,
  PlusOutlined,
  DeleteOutlined,
  CopyOutlined,
  StarOutlined,
  StarFilled,
  SettingOutlined,
} from '@ant-design/icons';
import type { DashboardListItem } from '@/api/dashboards';

const { Text } = Typography;

interface DashboardToolbarProps {
  dashboards: DashboardListItem[];
  activeDashboardId: string | null;
  editMode: boolean;
  isDirty: boolean;
  onDashboardSelect: (id: string) => void;
  onToggleEdit: () => void;
  onSave: () => void;
  onRevert: () => void;
  onCreate: () => void;
  onDelete: () => void;
  onDuplicate: () => void;
  onSetDefault: () => void;
  onAddWidget: () => void;
}

const DashboardToolbar: React.FC<DashboardToolbarProps> = ({
  dashboards,
  activeDashboardId,
  editMode,
  isDirty,
  onDashboardSelect,
  onToggleEdit,
  onSave,
  onRevert,
  onCreate,
  onDelete,
  onDuplicate,
  onSetDefault,
  onAddWidget,
}) => {
  const activeDashboard = dashboards.find((d) => d.id === activeDashboardId);

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 16,
      padding: '8px 0',
    }}>
      <Space size={12}>
        <Select
          value={activeDashboardId}
          onChange={onDashboardSelect}
          style={{ width: 200 }}
          options={dashboards.map((d) => ({
            value: d.id,
            label: (
              <span>
                {d.name}
                {d.is_default && <StarFilled style={{ color: '#faad14', marginLeft: 6, fontSize: 12 }} />}
              </span>
            ),
          }))}
        />
        {activeDashboard && !activeDashboard.is_default && (
          <Tooltip title="Set as default">
            <Button size="small" icon={<StarOutlined />} onClick={onSetDefault} />
          </Tooltip>
        )}
      </Space>

      <Space size={8}>
        {editMode ? (
          <>
            <Button icon={<PlusOutlined />} onClick={onAddWidget}>
              Add Widget
            </Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={onSave}
              disabled={!isDirty}
            >
              Save
            </Button>
            <Button icon={<UndoOutlined />} onClick={onRevert} disabled={!isDirty}>
              Revert
            </Button>
            <Button onClick={onToggleEdit}>Done</Button>
          </>
        ) : (
          <>
            <Button icon={<EditOutlined />} onClick={onToggleEdit}>
              Edit
            </Button>
            <Dropdown
              menu={{
                items: [
                  { key: 'create', label: 'New Dashboard', icon: <PlusOutlined />, onClick: onCreate },
                  { key: 'duplicate', label: 'Duplicate', icon: <CopyOutlined />, onClick: onDuplicate },
                  { key: 'delete', label: 'Delete', icon: <DeleteOutlined />, danger: true, onClick: onDelete },
                ],
              }}
            >
              <Button icon={<SettingOutlined />} size="small" />
            </Dropdown>
          </>
        )}
      </Space>
    </div>
  );
};

export default DashboardToolbar;
