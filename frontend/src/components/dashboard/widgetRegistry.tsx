import React, { lazy } from 'react';
import {
  DollarOutlined,
  FundOutlined,
  CalendarOutlined,
  ThunderboltOutlined,
  AreaChartOutlined,
  BarChartOutlined,
  PieChartOutlined,
  TableOutlined,
  UnorderedListOutlined,
  HeartOutlined,
  DashboardOutlined,
  SwapOutlined,
  TagsOutlined,
} from '@ant-design/icons';

export interface WidgetDefinition {
  type: string;
  label: string;
  icon: React.ReactNode;
  component: React.LazyExoticComponent<React.ComponentType<any>>;
  minW: number;
  minH: number;
  defaultW: number;
  defaultH: number;
  defaultConfig: Record<string, unknown>;
  dataKeys: string[];
  editableFields: string[];
}

export const WIDGET_REGISTRY: Record<string, WidgetDefinition> = {
  stat_card: {
    type: 'stat_card',
    label: 'Stat Card',
    icon: <DollarOutlined />,
    component: lazy(() => import('./widgets/StatCardWidget')),
    minW: 3, minH: 2, defaultW: 3, defaultH: 2,
    defaultConfig: { metric: 'monthly_spend', color: '#1677ff', icon: 'DollarOutlined' },
    dataKeys: ['monthly_spend'],
    editableFields: ['metric', 'title', 'color', 'icon'],
  },
  area_chart: {
    type: 'area_chart',
    label: 'Area Chart',
    icon: <AreaChartOutlined />,
    component: lazy(() => import('./widgets/AreaChartWidget')),
    minW: 6, minH: 4, defaultW: 12, defaultH: 6,
    defaultConfig: { metric: 'cost_trend', dateRange: 30, smooth: true },
    dataKeys: ['cost_trend'],
    editableFields: ['metric', 'title', 'dateRange', 'smooth'],
  },
  bar_chart: {
    type: 'bar_chart',
    label: 'Bar Chart',
    icon: <BarChartOutlined />,
    component: lazy(() => import('./widgets/BarChartWidget')),
    minW: 4, minH: 4, defaultW: 6, defaultH: 6,
    defaultConfig: { metric: 'cost_by_cloud', dateRange: 30, groupBy: 'cloud' },
    dataKeys: ['cost_by_cloud'],
    editableFields: ['metric', 'title', 'dateRange', 'groupBy'],
  },
  pie_chart: {
    type: 'pie_chart',
    label: 'Pie Chart',
    icon: <PieChartOutlined />,
    component: lazy(() => import('./widgets/PieChartWidget')),
    minW: 4, minH: 4, defaultW: 6, defaultH: 6,
    defaultConfig: { metric: 'cloud_distribution' },
    dataKeys: ['cloud_distribution'],
    editableFields: ['metric', 'title'],
  },
  stacked_area_chart: {
    type: 'stacked_area_chart',
    label: 'Stacked Area Chart',
    icon: <AreaChartOutlined />,
    component: lazy(() => import('./widgets/StackedAreaWidget')),
    minW: 6, minH: 4, defaultW: 12, defaultH: 6,
    defaultConfig: { metric: 'cost_trend_by_cloud', dateRange: 30 },
    dataKeys: ['cost_trend_by_cloud'],
    editableFields: ['metric', 'title', 'dateRange'],
  },
  table: {
    type: 'table',
    label: 'Table',
    icon: <TableOutlined />,
    component: lazy(() => import('./widgets/TableWidget')),
    minW: 4, minH: 4, defaultW: 7, defaultH: 6,
    defaultConfig: { metric: 'top_resources' },
    dataKeys: ['top_resources'],
    editableFields: ['metric', 'title'],
  },
  progress_list: {
    type: 'progress_list',
    label: 'Progress List',
    icon: <UnorderedListOutlined />,
    component: lazy(() => import('./widgets/ProgressListWidget')),
    minW: 4, minH: 3, defaultW: 5, defaultH: 6,
    defaultConfig: { metric: 'recommendation_categories' },
    dataKeys: ['recommendation_categories'],
    editableFields: ['metric', 'title'],
  },
  status_list: {
    type: 'status_list',
    label: 'Status List',
    icon: <HeartOutlined />,
    component: lazy(() => import('./widgets/StatusListWidget')),
    minW: 4, minH: 3, defaultW: 6, defaultH: 5,
    defaultConfig: { metric: 'cloud_account_health' },
    dataKeys: ['cloud_account_health'],
    editableFields: ['metric', 'title'],
  },
  budget_gauge: {
    type: 'budget_gauge',
    label: 'Budget Gauge',
    icon: <DashboardOutlined />,
    component: lazy(() => import('./widgets/BudgetGaugeWidget')),
    minW: 3, minH: 3, defaultW: 4, defaultH: 5,
    defaultConfig: { metric: 'budget_vs_spend' },
    dataKeys: ['budget_vs_spend'],
    editableFields: ['metric', 'title'],
  },
  trend_comparison: {
    type: 'trend_comparison',
    label: 'Trend Comparison',
    icon: <SwapOutlined />,
    component: lazy(() => import('./widgets/TrendComparisonWidget')),
    minW: 4, minH: 4, defaultW: 6, defaultH: 6,
    defaultConfig: { metric: 'cost_comparison_by_cloud', groupBy: 'cloud' },
    dataKeys: ['cost_comparison_by_cloud', 'cost_comparison_by_service'],
    editableFields: ['metric', 'title', 'groupBy'],
  },
  tag_breakdown: {
    type: 'tag_breakdown',
    label: 'Tag Breakdown',
    icon: <TagsOutlined />,
    component: lazy(() => import('./widgets/TagBreakdownWidget')),
    minW: 4, minH: 4, defaultW: 6, defaultH: 6,
    defaultConfig: { metric: 'cost_by_tag' },
    dataKeys: ['cost_by_tag'],
    editableFields: ['metric', 'title'],
  },
};

// Metric options per widget type for the config drawer
export const METRIC_OPTIONS_BY_TYPE: Record<string, { value: string; label: string }[]> = {
  stat_card: [
    { value: 'monthly_spend', label: 'Monthly Spend' },
    { value: 'last_month_spend', label: 'Last Month Spend' },
    { value: 'forecast', label: 'Forecast' },
    { value: 'change_percent', label: 'Change %' },
    { value: 'potential_savings', label: 'Potential Savings' },
    { value: 'recommendation_count', label: 'Recommendation Count' },
    { value: 'cloud_account_count', label: 'Cloud Account Count' },
    { value: 'resource_count', label: 'Resource Count' },
  ],
  area_chart: [
    { value: 'cost_trend', label: 'Cost Trend' },
  ],
  bar_chart: [
    { value: 'cost_by_cloud', label: 'Cost by Cloud' },
    { value: 'cost_by_service', label: 'Cost by Service' },
    { value: 'cost_by_region', label: 'Cost by Region' },
  ],
  pie_chart: [
    { value: 'cloud_distribution', label: 'Cloud Distribution' },
    { value: 'service_distribution', label: 'Service Distribution' },
  ],
  stacked_area_chart: [
    { value: 'cost_trend_by_cloud', label: 'Cost Trend by Cloud' },
  ],
  table: [
    { value: 'top_resources', label: 'Top Resources' },
    { value: 'cloud_accounts', label: 'Cloud Accounts' },
    { value: 'recommendations', label: 'Recommendations' },
  ],
  progress_list: [
    { value: 'recommendation_categories', label: 'Recommendation Categories' },
    { value: 'pool_status', label: 'Pool Status' },
  ],
  status_list: [
    { value: 'cloud_account_health', label: 'Cloud Account Health' },
  ],
  budget_gauge: [
    { value: 'budget_vs_spend', label: 'Budget vs Spend' },
  ],
  trend_comparison: [
    { value: 'cost_comparison_by_cloud', label: 'Cost Comparison by Cloud' },
    { value: 'cost_comparison_by_service', label: 'Cost Comparison by Service' },
  ],
  tag_breakdown: [
    { value: 'cost_by_tag', label: 'Cost by Tag' },
  ],
};

// Color options for stat cards
export const COLOR_OPTIONS = [
  { value: '#1677ff', label: 'Blue' },
  { value: '#722ed1', label: 'Purple' },
  { value: '#52c41a', label: 'Green' },
  { value: '#fa8c16', label: 'Orange' },
  { value: '#eb2f96', label: 'Magenta' },
  { value: '#13c2c2', label: 'Cyan' },
  { value: '#f5222d', label: 'Red' },
];
