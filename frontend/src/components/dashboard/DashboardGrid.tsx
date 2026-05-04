import React, { Suspense, useCallback, useMemo } from 'react';
import GridLayout, { WidthProvider } from 'react-grid-layout';
import { Spin } from 'antd';
import { WIDGET_REGISTRY } from './widgetRegistry';
import WidgetShell from './widgets/WidgetShell';
import type { LayoutItem, WidgetConfigEntry } from '@/api/dashboards';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import './dashboard.css';

const DashboardGridLayout = WidthProvider(GridLayout);

interface DashboardGridProps {
  layout: LayoutItem[];
  widgets: Record<string, WidgetConfigEntry>;
  data: Record<string, unknown> | undefined;
  errors: Record<string, string> | undefined;
  loading: boolean;
  editMode: boolean;
  onLayoutChange: (layout: LayoutItem[]) => void;
  onRemoveWidget?: (widgetId: string) => void;
  onConfigureWidget?: (widgetId: string) => void;
}

const WidgetLoadingFallback: React.FC = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: 120 }}>
    <Spin />
  </div>
);

const DashboardGrid: React.FC<DashboardGridProps> = ({
  layout,
  widgets,
  data,
  errors,
  loading,
  editMode,
  onLayoutChange,
  onRemoveWidget,
  onConfigureWidget,
}) => {
  const handleLayoutChange = useCallback(
    (currentLayout: any) => {
      const items: any[] = Array.isArray(currentLayout) ? currentLayout : [];
      const newLayout: LayoutItem[] = items.map((item: any) => ({
        ...(function () {
          const widgetConfig = widgets[item.i];
          const definition = widgetConfig ? WIDGET_REGISTRY[widgetConfig.type] : null;
          const requiredMinW = definition?.minW ?? 1;
          const requiredMinH = definition?.minH ?? 1;
          const minW = Math.max(item.minW ?? requiredMinW, requiredMinW);
          const minH = Math.max(item.minH ?? requiredMinH, requiredMinH);
          return {
            minW,
            minH,
            w: Math.max(item.w, minW),
            h: Math.max(item.h, minH),
          };
        })(),
        i: item.i,
        x: item.x,
        y: item.y,
        maxW: item.maxW,
        maxH: item.maxH,
        static: item.static,
      }));
      onLayoutChange(newLayout);
    },
    [onLayoutChange, widgets],
  );

  // Build react-grid-layout layout from stored layout_config with registry constraints
  const mergedLayout = useMemo(() => {
    return layout.map((item) => {
      const widgetConfig = widgets[item.i];
      const definition = widgetConfig ? WIDGET_REGISTRY[widgetConfig.type] : null;
      const requiredMinW = definition?.minW ?? 1;
      const requiredMinH = definition?.minH ?? 1;
      const minW = Math.max(item.minW ?? requiredMinW, requiredMinW);
      const minH = Math.max(item.minH ?? requiredMinH, requiredMinH);
      const maxW = Math.max(item.maxW ?? 12, minW);
      const maxH = Math.max(item.maxH ?? 20, minH);

      return {
        i: item.i,
        x: item.x,
        y: item.y,
        w: Math.max(item.w, minW),
        h: Math.max(item.h, minH),
        minW,
        minH,
        maxW,
        maxH,
        static: item.static ?? false,
      };
    });
  }, [layout, widgets]);

  return (
    <DashboardGridLayout
      className="dashboard-grid"
      layout={mergedLayout}
      cols={12}
      rowHeight={60}
      isDraggable={editMode}
      isResizable={editMode}
      onLayoutChange={editMode ? handleLayoutChange : undefined}
      draggableCancel=".ant-card-head-extra,.ant-btn"
      compactType={editMode ? null : 'vertical'}
      preventCollision={editMode}
      allowOverlap={false}
      margin={[16, 16] as [number, number]}
    >
      {mergedLayout.map((item) => {
        const widgetConfig = widgets[item.i];
        if (!widgetConfig) {
          return (
            <div key={item.i}>
              <WidgetShell
                widgetId={item.i}
                config={{ type: 'stat_card', metric: 'monthly_spend', title: 'Unknown widget' }}
                editMode={editMode}
                onRemove={onRemoveWidget ? () => onRemoveWidget(item.i) : undefined}
              >
                <div style={{ padding: 20, textAlign: 'center', color: '#999' }}>
                  Unknown widget — remove and re-add
                </div>
              </WidgetShell>
            </div>
          );
        }

        const definition = WIDGET_REGISTRY[widgetConfig.type];
        const metricData = data?.[widgetConfig.metric] as Record<string, unknown> | undefined;
        const metricError = errors?.[widgetConfig.metric] ?? null;
        const WidgetComponent = definition?.component;

        return (
          <div key={item.i} style={{ height: '100%', width: '100%' }}>
            {WidgetComponent ? (
              <Suspense fallback={<WidgetLoadingFallback />}>
                <WidgetComponent
                  widgetId={item.i}
                  config={widgetConfig as any}
                  data={metricData}
                  loading={loading}
                  error={metricError}
                  editMode={editMode}
                  onRemove={onRemoveWidget ? () => onRemoveWidget(item.i) : undefined}
                  onConfigure={onConfigureWidget ? () => onConfigureWidget(item.i) : undefined}
                  onRetry={() => {}}
                />
              </Suspense>
            ) : (
              <WidgetShell
                widgetId={item.i}
                config={widgetConfig as any}
                editMode={editMode}
                onRemove={onRemoveWidget ? () => onRemoveWidget(item.i) : undefined}
              >
                <div style={{ padding: 20, textAlign: 'center', color: '#999' }}>
                  Unknown widget type: {widgetConfig.type}
                </div>
              </WidgetShell>
            )}
          </div>
        );
      })}
    </DashboardGridLayout>
  );
};

export default DashboardGrid;
