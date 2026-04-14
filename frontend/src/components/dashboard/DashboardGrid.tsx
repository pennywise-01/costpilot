import React, { useCallback, useMemo, useRef } from 'react';
import { Responsive, WidthProvider } from 'react-grid-layout';
import { WIDGET_REGISTRY } from './widgetRegistry';
import WidgetShell from './widgets/WidgetShell';
import type { LayoutItem, WidgetConfigEntry } from '@/api/dashboards';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import './dashboard.css';

const ResponsiveGridLayout = WidthProvider(Responsive);

interface DashboardGridProps {
  layout: LayoutItem[];
  widgets: Record<string, WidgetConfigEntry>;
  data: Record<string, unknown> | undefined;
  errors: Record<string, string> | undefined;
  editMode: boolean;
  onLayoutChange: (layout: LayoutItem[]) => void;
  onRemoveWidget?: (widgetId: string) => void;
  onConfigureWidget?: (widgetId: string) => void;
}

const DashboardGrid: React.FC<DashboardGridProps> = ({
  layout,
  widgets,
  data,
  errors,
  editMode,
  onLayoutChange,
  onRemoveWidget,
  onConfigureWidget,
}) => {
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleLayoutChange = useCallback(
    (currentLayout: any) => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      debounceTimer.current = setTimeout(() => {
        const items: any[] = Array.isArray(currentLayout) ? currentLayout : [];
        const newLayout: LayoutItem[] = items.map((item: any) => ({
          i: item.i,
          x: item.x,
          y: item.y,
          w: item.w,
          h: item.h,
          minW: item.minW,
          minH: item.minH,
          maxW: item.maxW,
          maxH: item.maxH,
          static: item.static,
        }));
        onLayoutChange(newLayout);
      }, 500);
    },
    [onLayoutChange],
  );

  // Build react-grid-layout layout from stored layout_config with registry constraints
  const mergedLayout = useMemo(() => {
    return layout.map((item) => {
      const widgetConfig = widgets[item.i];
      const definition = widgetConfig ? WIDGET_REGISTRY[widgetConfig.type] : null;
      return {
        i: item.i,
        x: item.x,
        y: item.y,
        w: item.w,
        h: item.h,
        minW: item.minW ?? definition?.minW ?? 1,
        minH: item.minH ?? definition?.minH ?? 1,
        maxW: item.maxW ?? 12,
        maxH: item.maxH ?? 20,
        static: item.static ?? false,
      };
    });
  }, [layout, widgets]);

  return (
    <ResponsiveGridLayout
      className="dashboard-grid"
      layouts={{ lg: mergedLayout, md: mergedLayout, sm: mergedLayout }}
      breakpoints={{ lg: 1200, md: 996, sm: 768 }}
      cols={{ lg: 12, md: 6, sm: 1 }}
      rowHeight={60}
      isDraggable={editMode}
      isResizable={editMode}
      onLayoutChange={handleLayoutChange}
      draggableCancel=".ant-card-head-extra,.ant-btn"
      compactType="vertical"
      margin={[16, 16] as [number, number]}
    >
      {layout.map((item) => {
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
          <div key={item.i} style={{ height: '100%' }}>
            {WidgetComponent ? (
              <WidgetComponent
                widgetId={item.i}
                config={widgetConfig as any}
                data={metricData}
                loading={false}
                error={metricError}
                editMode={editMode}
                onRemove={onRemoveWidget ? () => onRemoveWidget(item.i) : undefined}
                onConfigure={onConfigureWidget ? () => onConfigureWidget(item.i) : undefined}
                onRetry={() => {}}
              />
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
    </ResponsiveGridLayout>
  );
};

export default DashboardGrid;
