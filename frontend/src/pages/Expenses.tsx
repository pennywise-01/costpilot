import React, { useState, useMemo } from 'react';
import {
  Breadcrumb,
  Card,
  Col,
  DatePicker,
  Row,
  Segmented,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import { HomeOutlined, DollarOutlined } from '@ant-design/icons';
import { Column } from '@ant-design/charts';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { formatCurrency, formatPercent } from '@/utils/formatters';
import { CLOUD_TYPE_COLORS } from '@/utils/constants';

const { Title } = Typography;
const { RangePicker } = DatePicker;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type BreakdownMode = 'Total' | 'By Cloud' | 'By Pool' | 'By Owner';

interface BreakdownRow {
  key: string;
  name: string;
  thisPeriod: number;
  prevPeriod: number;
  change: number;
  dailyAvg: number;
}

interface DailyDataPoint {
  date: string;
  value: number;
  category?: string;
}

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

const today = dayjs();
const startOfMonth = today.startOf('month');

function generateDates(count: number): string[] {
  const dates: string[] = [];
  for (let i = 0; i < count; i++) {
    dates.push(startOfMonth.add(i, 'day').format('MMM DD'));
  }
  return dates;
}

const DATES = generateDates(30);

function seededRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

function generateTotalData(): DailyDataPoint[] {
  return DATES.map((date, i) => ({
    date,
    value: Math.round(350 + seededRandom(i + 1) * 200),
  }));
}

function generateByCloudData(): DailyDataPoint[] {
  const clouds = [
    { name: 'AWS', color: CLOUD_TYPE_COLORS.aws_cnr },
    { name: 'Azure', color: CLOUD_TYPE_COLORS.azure_cnr },
    { name: 'GCP', color: CLOUD_TYPE_COLORS.gcp_cnr },
  ];
  const points: DailyDataPoint[] = [];
  DATES.forEach((date, i) => {
    clouds.forEach((cloud, ci) => {
      points.push({
        date,
        value: Math.round(80 + seededRandom(i * 3 + ci + 10) * 160),
        category: cloud.name,
      });
    });
  });
  return points;
}

function generateByPoolData(): DailyDataPoint[] {
  const pools = ['Engineering', 'Marketing', 'Data Science', 'DevOps'];
  const points: DailyDataPoint[] = [];
  DATES.forEach((date, i) => {
    pools.forEach((pool, pi) => {
      points.push({
        date,
        value: Math.round(60 + seededRandom(i * 4 + pi + 50) * 120),
        category: pool,
      });
    });
  });
  return points;
}

function generateByOwnerData(): DailyDataPoint[] {
  const owners = ['Alice Chen', 'Bob Kim', 'Carol Wu', 'Dave Patel'];
  const points: DailyDataPoint[] = [];
  DATES.forEach((date, i) => {
    owners.forEach((owner, oi) => {
      points.push({
        date,
        value: Math.round(50 + seededRandom(i * 4 + oi + 100) * 130),
        category: owner,
      });
    });
  });
  return points;
}

// ---------------------------------------------------------------------------
// Breakdown table data
// ---------------------------------------------------------------------------

const TOTAL_ROWS: BreakdownRow[] = [
  { key: '1', name: 'All Resources', thisPeriod: 12847, prevPeriod: 11520, change: 11.5, dailyAvg: 428 },
];

const BY_CLOUD_ROWS: BreakdownRow[] = [
  { key: '1', name: 'AWS Production', thisPeriod: 4850, prevPeriod: 4320, change: 12.3, dailyAvg: 162 },
  { key: '2', name: 'AWS Development', thisPeriod: 1220, prevPeriod: 1380, change: -11.6, dailyAvg: 41 },
  { key: '3', name: 'Azure Main', thisPeriod: 2980, prevPeriod: 2710, change: 10.0, dailyAvg: 99 },
  { key: '4', name: 'Azure Staging', thisPeriod: 640, prevPeriod: 590, change: 8.5, dailyAvg: 21 },
  { key: '5', name: 'GCP Analytics', thisPeriod: 1720, prevPeriod: 1350, change: 27.4, dailyAvg: 57 },
  { key: '6', name: 'GCP ML Workloads', thisPeriod: 890, prevPeriod: 750, change: 18.7, dailyAvg: 30 },
  { key: '7', name: 'AWS Sandbox', thisPeriod: 320, prevPeriod: 280, change: 14.3, dailyAvg: 11 },
  { key: '8', name: 'Azure DR', thisPeriod: 227, prevPeriod: 140, change: 62.1, dailyAvg: 8 },
];

const BY_POOL_ROWS: BreakdownRow[] = [
  { key: '1', name: 'Engineering', thisPeriod: 5120, prevPeriod: 4680, change: 9.4, dailyAvg: 171 },
  { key: '2', name: 'Marketing', thisPeriod: 1830, prevPeriod: 2010, change: -9.0, dailyAvg: 61 },
  { key: '3', name: 'Data Science', thisPeriod: 2450, prevPeriod: 1980, change: 23.7, dailyAvg: 82 },
  { key: '4', name: 'DevOps', thisPeriod: 1290, prevPeriod: 1150, change: 12.2, dailyAvg: 43 },
  { key: '5', name: 'QA / Testing', thisPeriod: 780, prevPeriod: 710, change: 9.9, dailyAvg: 26 },
  { key: '6', name: 'Sales Demos', thisPeriod: 540, prevPeriod: 490, change: 10.2, dailyAvg: 18 },
  { key: '7', name: 'Security', thisPeriod: 480, prevPeriod: 320, change: 50.0, dailyAvg: 16 },
  { key: '8', name: 'Unassigned', thisPeriod: 357, prevPeriod: 180, change: 98.3, dailyAvg: 12 },
];

const BY_OWNER_ROWS: BreakdownRow[] = [
  { key: '1', name: 'Alice Chen', thisPeriod: 3150, prevPeriod: 2870, change: 9.8, dailyAvg: 105 },
  { key: '2', name: 'Bob Kim', thisPeriod: 2640, prevPeriod: 2480, change: 6.5, dailyAvg: 88 },
  { key: '3', name: 'Carol Wu', thisPeriod: 2100, prevPeriod: 1850, change: 13.5, dailyAvg: 70 },
  { key: '4', name: 'Dave Patel', thisPeriod: 1520, prevPeriod: 1490, change: 2.0, dailyAvg: 51 },
  { key: '5', name: 'Eva Lopez', thisPeriod: 1230, prevPeriod: 1350, change: -8.9, dailyAvg: 41 },
  { key: '6', name: 'Frank Zhao', thisPeriod: 980, prevPeriod: 720, change: 36.1, dailyAvg: 33 },
  { key: '7', name: 'Grace Ito', thisPeriod: 710, prevPeriod: 530, change: 34.0, dailyAvg: 24 },
  { key: '8', name: 'Unassigned', thisPeriod: 517, prevPeriod: 230, change: 124.8, dailyAvg: 17 },
];

const BREAKDOWN_TABLE_DATA: Record<BreakdownMode, BreakdownRow[]> = {
  Total: TOTAL_ROWS,
  'By Cloud': BY_CLOUD_ROWS,
  'By Pool': BY_POOL_ROWS,
  'By Owner': BY_OWNER_ROWS,
};

const BREAKDOWN_CHART_DATA: Record<BreakdownMode, DailyDataPoint[]> = {
  Total: generateTotalData(),
  'By Cloud': generateByCloudData(),
  'By Pool': generateByPoolData(),
  'By Owner': generateByOwnerData(),
};

const CLOUD_CHART_COLOR_MAP: Record<string, string> = {
  AWS: CLOUD_TYPE_COLORS.aws_cnr,
  Azure: CLOUD_TYPE_COLORS.azure_cnr,
  GCP: CLOUD_TYPE_COLORS.gcp_cnr,
};

// ---------------------------------------------------------------------------
// Column name label
// ---------------------------------------------------------------------------

const COLUMN_LABEL: Record<BreakdownMode, string> = {
  Total: 'Name',
  'By Cloud': 'Cloud Account',
  'By Pool': 'Pool',
  'By Owner': 'Owner',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const Expenses: React.FC = () => {
  const [breakdown, setBreakdown] = useState<BreakdownMode>('Total');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    startOfMonth,
    startOfMonth.add(29, 'day'),
  ]);

  // Chart data
  const chartData = BREAKDOWN_CHART_DATA[breakdown];

  // Table data
  const tableData = BREAKDOWN_TABLE_DATA[breakdown];

  // Totals for table footer
  const totals = useMemo(() => {
    return tableData.reduce(
      (acc, row) => ({
        thisPeriod: acc.thisPeriod + row.thisPeriod,
        prevPeriod: acc.prevPeriod + row.prevPeriod,
        dailyAvg: acc.dailyAvg + row.dailyAvg,
      }),
      { thisPeriod: 0, prevPeriod: 0, dailyAvg: 0 },
    );
  }, [tableData]);

  const totalChange =
    totals.prevPeriod === 0
      ? 0
      : ((totals.thisPeriod - totals.prevPeriod) / totals.prevPeriod) * 100;

  // Chart config
  const isStacked = breakdown !== 'Total';

  const chartConfig = useMemo(
    () => ({
      data: chartData,
      xField: 'date',
      yField: 'value',
      ...(isStacked
        ? {
            colorField: 'category',
            stack: true,
            color:
              breakdown === 'By Cloud'
                ? (category: string) => CLOUD_CHART_COLOR_MAP[category] ?? '#8c8c8c'
                : undefined,
          }
        : {
            color: '#1677ff',
          }),
      height: 350,
      tooltip: {
        formatter: (datum: Record<string, unknown>) => ({
          name: (datum.category as string) ?? 'Spend',
          value: formatCurrency(datum.value as number),
        }),
      },
      axis: {
        y: {
          labelFormatter: (v: number) => `$${v}`,
        },
      },
      interaction: {
        tooltip: {
          shared: true,
        },
      },
    }),
    [chartData, isStacked, breakdown],
  );

  // Table columns
  const columns: ColumnsType<BreakdownRow> = [
    {
      title: COLUMN_LABEL[breakdown],
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: 'This Period',
      dataIndex: 'thisPeriod',
      key: 'thisPeriod',
      sorter: (a, b) => a.thisPeriod - b.thisPeriod,
      defaultSortOrder: 'descend',
      render: (v: number) => formatCurrency(v),
      align: 'right' as const,
    },
    {
      title: 'Previous Period',
      dataIndex: 'prevPeriod',
      key: 'prevPeriod',
      sorter: (a, b) => a.prevPeriod - b.prevPeriod,
      render: (v: number) => formatCurrency(v),
      align: 'right' as const,
    },
    {
      title: 'Change',
      dataIndex: 'change',
      key: 'change',
      sorter: (a, b) => a.change - b.change,
      render: (v: number) => (
        <Tag color={v <= 0 ? 'green' : 'red'}>{formatPercent(v)}</Tag>
      ),
      align: 'center' as const,
    },
    {
      title: 'Daily Average',
      dataIndex: 'dailyAvg',
      key: 'dailyAvg',
      sorter: (a, b) => a.dailyAvg - b.dailyAvg,
      render: (v: number) => formatCurrency(v),
      align: 'right' as const,
    },
  ];

  return (
    <div>
      {/* Action bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 24,
        }}
      >
        <div>
          <Breadcrumb
            items={[
              { title: <HomeOutlined />, href: '/' },
              { title: 'Expenses' },
            ]}
            style={{ marginBottom: 8 }}
          />
          <Title level={3} style={{ margin: 0 }}>
            <DollarOutlined style={{ marginRight: 8 }} />
            Cost Explorer
          </Title>
        </div>
        <RangePicker
          value={dateRange}
          onChange={(dates) => {
            if (dates && dates[0] && dates[1]) {
              setDateRange([dates[0], dates[1]]);
            }
          }}
          format="MMM D, YYYY"
          allowClear={false}
        />
      </div>

      {/* Breakdown selector */}
      <div style={{ marginBottom: 24 }}>
        <Segmented
          options={['Total', 'By Cloud', 'By Pool', 'By Owner']}
          value={breakdown}
          onChange={(val) => setBreakdown(val as BreakdownMode)}
          size="large"
        />
      </div>

      {/* Summary row */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Total Spend"
              value={12847}
              prefix="$"
              precision={0}
              valueStyle={{ fontWeight: 600 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Previous Period"
              value={11520}
              prefix="$"
              precision={0}
              valueStyle={{ color: '#8c8c8c' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Change"
              value={11.5}
              precision={1}
              suffix="%"
              prefix="+"
              valueStyle={{ color: '#cf1322' }}
            />
            <Tag color="red" style={{ marginTop: 4 }}>
              Increase
            </Tag>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="Daily Average"
              value={428}
              prefix="$"
              precision={0}
            />
          </Card>
        </Col>
      </Row>

      {/* Chart */}
      <Card
        title="Expense Trend"
        style={{ marginBottom: 24 }}
        styles={{ body: { padding: '16px 24px' } }}
      >
        <Column {...chartConfig} />
      </Card>

      {/* Breakdown table */}
      <Card title={`Breakdown - ${breakdown}`}>
        <Table<BreakdownRow>
          columns={columns}
          dataSource={tableData}
          pagination={false}
          size="middle"
          summary={() => (
            <Table.Summary fixed>
              <Table.Summary.Row>
                <Table.Summary.Cell index={0}>
                  <strong>Total</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={1} align="right">
                  <strong>{formatCurrency(totals.thisPeriod)}</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={2} align="right">
                  <strong>{formatCurrency(totals.prevPeriod)}</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={3} align="center">
                  <Tag color={totalChange <= 0 ? 'green' : 'red'}>
                    <strong>{formatPercent(totalChange)}</strong>
                  </Tag>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={4} align="right">
                  <strong>{formatCurrency(totals.dailyAvg)}</strong>
                </Table.Summary.Cell>
              </Table.Summary.Row>
            </Table.Summary>
          )}
        />
      </Card>
    </div>
  );
};

export default Expenses;
