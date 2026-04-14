import React from 'react';
import { Modal, Card, Space, Typography, Row, Col } from 'antd';
import { WIDGET_REGISTRY } from './widgetRegistry';

const { Text } = Typography;

interface WidgetPickerProps {
  open: boolean;
  onSelect: (type: string) => void;
  onCancel: () => void;
}

const WidgetPicker: React.FC<WidgetPickerProps> = ({ open, onSelect, onCancel }) => {
  const entries = Object.values(WIDGET_REGISTRY);

  return (
    <Modal
      title="Add Widget"
      open={open}
      onCancel={onCancel}
      footer={null}
      width={720}
    >
      <Row gutter={[16, 16]}>
        {entries.map((def) => (
          <Col xs={12} sm={8} md={6} key={def.type}>
            <Card
              hoverable
              size="small"
              style={{ textAlign: 'center', borderRadius: 10 }}
              onClick={() => {
                onSelect(def.type);
                onCancel();
              }}
            >
              <div style={{ fontSize: 28, marginBottom: 8 }}>{def.icon}</div>
              <Text strong style={{ fontSize: 13 }}>{def.label}</Text>
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {def.defaultW}×{def.defaultH}
                </Text>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </Modal>
  );
};

export default WidgetPicker;
