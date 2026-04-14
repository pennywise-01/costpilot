# Customizable Kibana-style Dashboard System — v2

A per-organization, multi-dashboard system with drag-to-rearrange, resize, and pick-your-panels
customization — matching Kibana-level layout flexibility for CostPilot's cost/metrics widgets.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  Frontend (React)                                   │
│  ┌─────────────┐  ┌──────────────┐                  │
│  │ Dashboard   │  │ Widget       │  react-grid-layout│
│  │ Editor Page │→ │ Registry     │  + antd Cards     │
│  └──────┬──────┘  └──────┬──────┘                   │
│         │                │                           │
│  ┌──────▼────────────────▼──────┐                   │
│  │  useDashboardData() hook     │                   │
│  │  (dedup → batch fetch,       │                   │
│  │   React Query cache)         │                   │
│  └──────────────┬───────────────┘                   │
└─────────────────┼───────────────────────────────────┘
                  │ REST API
┌─────────────────▼───────────────────────────────────┐
│  Backend (FastAPI)                                   │
│  ┌──────────────┐  ┌──────────────┐                  │
│  │ dashboards/  │  │ Widget Data  │                  │
│  │ router.py    │  │ Endpoints    │                  │
│  │ service.py   │  │ (existing +  │                  │
│  │ models.py    │  │  new batch)  │                  │
│  └──────┬───────┘  └──────┬───────┘                  │
│         │                  │                         │
│  ┌──────▼──────────────────▼───────┐                │
│  │  PostgreSQL (layout)            │                │
│  │  Redis (widget data cache)      │                │
│  │  MongoDB (raw expenses)         │                │
│  └─────────────────────────────────┘                │
└─────────────────────────────────────────────────────┘
```

**Key decisions:**
- Layout config stored in **PostgreSQL** (relational, transactional, small payload)
- Widget data served from **existing endpoints + new batch endpoint** (no per-widget backend)
- **react-grid-layout** for Kibana-level drag/resize (mature, React-native, well-tested)
- Per-org dashboards; all org members see the same layout
- **Mobile layout:** single-column collapse only — breakpoints are not stored per-device; the
  grid simply renders in a stacked order on narrow viewports (drag is disabled on mobile)
- Current fixed dashboard becomes the seeded "Default Dashboard", created **synchronously on
  org creation** (not lazily) so the dashboard list is never empty on first load
- **Slugs are immutable after creation** — renaming a dashboard changes only the display name,
  never the URL slug, so bookmarked/shared links stay valid

---

## 2. Database Schema

### New table: `dashboards`

```sql
CREATE TABLE dashboards (
    id                    VARCHAR(36) PRIMARY KEY,  -- UUID
    organization_id       VARCHAR(36) NOT NULL REFERENCES organizations(id),
    name                  VARCHAR(256) NOT NULL,
    slug                  VARCHAR(128) NOT NULL,    -- URL-friendly, immutable after creation
    is_default            BOOLEAN NOT NULL DEFAULT FALSE,
    layout_config         JSONB NOT NULL DEFAULT '[]',   -- react-grid-layout items (current)
    previous_layout_config JSONB,                        -- last explicitly-saved state (revert target)
    widget_config         JSONB NOT NULL DEFAULT '{}',   -- widget-specific settings
    version               INTEGER NOT NULL DEFAULT 1,    -- optimistic locking
    created_by            VARCHAR(36) NOT NULL REFERENCES users(id),
    updated_by            VARCHAR(36) NOT NULL REFERENCES users(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at            TIMESTAMPTZ,              -- soft delete
    UNIQUE (organization_id, slug)
);

-- Fast lookup of dashboards for an org (excludes soft-deleted)
CREATE INDEX idx_dashboards_org
    ON dashboards(organization_id)
    WHERE deleted_at IS NULL;

-- Enforce exactly one default per org at the database level,
-- preventing race conditions from dual-default writes
CREATE UNIQUE INDEX idx_one_default_per_org
    ON dashboards(organization_id)
    WHERE is_default = TRUE AND deleted_at IS NULL;
```

> **`previous_layout_config`** stores the last explicitly-saved `layout_config` snapshot.
> When a user saves a new layout, the backend copies the current `layout_config` into
> `previous_layout_config` before applying the new one, enabling a one-level "Revert to last
> saved" action without a full history table.

> **`created_by` / `updated_by`** enable "Last edited by Alice 2h ago" UI labels and provide
> an audit trail for org-shared dashboards where any MANAGE-level member can edit.

### `layout_config` JSONB structure (react-grid-layout format)

```json
[
  {
    "i": "widget-uuid-1",
    "x": 0, "y": 0,
    "w": 6, "h": 4,
    "minW": 3, "minH": 2,
    "maxW": 12, "maxH": 8,
    "static": false
  }
]
```

### `widget_config` JSONB structure

```json
{
  "widget-uuid-1": {
    "type": "stat_card",
    "metric": "monthly_spend",
    "title": "Monthly Spend",
    "color": "#1677ff",
    "icon": "DollarOutlined"
  },
  "widget-uuid-2": {
    "type": "area_chart",
    "metric": "cost_trend",
    "title": "Cost Trend",
    "dateRange": 30,
    "groupBy": "cloud",
    "smooth": true
  }
}
```

---

## 3. Widget Type Registry

### 3.1 Stat Cards (single-value metrics)

| Widget Type | Metric Key | Data Source |
|---|---|---|
| `stat_card` | `monthly_spend` | `expenses/summary` → `this_month_total` |
| `stat_card` | `last_month_spend` | `expenses/summary` → `last_month_total` |
| `stat_card` | `forecast` | `expenses/summary` → `this_month_forecast` |
| `stat_card` | `change_percent` | `expenses/summary` → `change_percent` |
| `stat_card` | `potential_savings` | `recommendations/overview` → total savings |
| `stat_card` | `recommendation_count` | `recommendations/overview` → total count |
| `stat_card` | `cloud_account_count` | `cloud-accounts` list length |
| `stat_card` | `resource_count` | `resources` total |

### 3.2 Chart Panels

| Widget Type | Metric Key | Data Source |
|---|---|---|
| `area_chart` | `cost_trend` | `expenses/breakdown` → `daily_totals` |
| `bar_chart` | `cost_by_cloud` | `expenses/breakdown` → `breakdown` (group_by=cloud) |
| `bar_chart` | `cost_by_service` | `expenses/breakdown` → `breakdown` (group_by=service) |
| `bar_chart` | `cost_by_region` | `expenses/breakdown` → `breakdown` (group_by=region) |
| `pie_chart` | `cloud_distribution` | `expenses/breakdown` → `breakdown` (group_by=cloud) |
| `pie_chart` | `service_distribution` | `expenses/breakdown` → `breakdown` (group_by=service) |
| `stacked_area_chart` | `cost_trend_by_cloud` | `expenses/breakdown` → `breakdown[].daily_breakdown` |

### 3.3 Table Panels

| Widget Type | Metric Key | Data Source |
|---|---|---|
| `table` | `top_resources` | `resources` list (sorted by daily_cost) |
| `table` | `cloud_accounts` | `cloud-accounts` list + live data |
| `table` | `recommendations` | `recommendations/overview` |

### 3.4 List / Progress Panels

| Widget Type | Metric Key | Data Source |
|---|---|---|
| `progress_list` | `recommendation_categories` | `recommendations/overview` → by category |
| `progress_list` | `pool_status` | `pools` list + budget utilization |
| `status_list` | `cloud_account_health` | `cloud-accounts` + `expenses/cache-status` |

---

## 4. Backend Implementation

### 4.1 New module: `app/dashboards/`

```
app/dashboards/
├── __init__.py
├── models.py        # Dashboard SQLAlchemy model
├── schemas.py       # Pydantic request/response schemas
├── router.py        # CRUD + layout save endpoints
├── service.py       # Business logic
└── seed.py          # Default dashboard seeder (called on org creation)
```

### 4.2 API Endpoints

```
GET    /api/v1/organizations/{org_id}/dashboards
       → List all dashboards for org (id, name, slug, is_default,
         updated_by, updated_at — for "last edited by" display)

POST   /api/v1/organizations/{org_id}/dashboards
       → Create new dashboard (name, optional template)

GET    /api/v1/organizations/{org_id}/dashboards/{dashboard_id}
       → Get full dashboard (layout_config + widget_config +
         previous_layout_config + created_by + updated_by)

PUT    /api/v1/organizations/{org_id}/dashboards/{dashboard_id}
       → Update layout + widget config (optimistic locking via version).
         On save: copy current layout_config → previous_layout_config
         before applying new values.

DELETE /api/v1/organizations/{org_id}/dashboards/{dashboard_id}
       → Soft-delete dashboard

PUT    /api/v1/organizations/{org_id}/dashboards/{dashboard_id}/set-default
       → Mark as default (DB partial unique index enforces atomicity —
         no explicit transaction lock needed)

POST   /api/v1/organizations/{org_id}/dashboards/{dashboard_id}/revert
       → Swap layout_config ← previous_layout_config, bumps version.
         Returns 409 if previous_layout_config is NULL (nothing to revert).

POST   /api/v1/organizations/{org_id}/dashboards/{dashboard_id}/duplicate
       → Clone dashboard with new name (new slug generated from new name)

POST   /api/v1/organizations/{org_id}/dashboards/widgets/data
       → Batch endpoint: accepts deduplicated list of widget types + metrics,
         returns all data in single response (reduces N requests → 1).
         NOTE: method is POST because the request carries a body payload.
```

> **Slug behaviour on rename:** `PUT` accepts a new `name` but never updates `slug`.
> Slug is written only at creation time and is permanently immutable thereafter.

### 4.3 Batch Widget Data Endpoint (Critical for Performance)

This endpoint prevents N widget requests from becoming N backend calls.

```python
# POST /api/v1/organizations/{org_id}/dashboards/widgets/data
# Request body:
{
  "widgets": [
    {"type": "stat_card", "metric": "monthly_spend"},
    {"type": "stat_card", "metric": "forecast"},
    {"type": "area_chart", "metric": "cost_trend", "params": {"days": 30}},
    {"type": "bar_chart",  "metric": "cost_by_cloud", "params": {"days": 30}},
    {"type": "table",      "metric": "top_resources",  "params": {"limit": 5}}
  ]
  // Note: the frontend deduplicates by (type, metric, params) before sending;
  // the backend also deduplicates by data source as a second safety layer.
}

# Response:
{
  "data": {
    "monthly_spend": {"value": 1234.56, "change_percent": 5.2, "data_source": "cache"},
    "forecast":      {"value": 5678.90, "data_source": "cache"},
    "cost_trend":    {"daily_totals": [...], "data_source": "cache"},
    "cost_by_cloud": {"breakdown": [...], "data_source": "cache"},
    "top_resources": {"resources": [...]}
  },
  "errors": {},   // partial failures keyed by metric name
  "meta": {
    "data_source": "cache",
    "freshness": "fresh",
    "generated_at": "2025-01-15T10:30:00Z"
  }
}
```

**Implementation strategy:**
- Group widgets by underlying data source (expenses/summary, expenses/breakdown, resources,
  recommendations)
- Fetch each data source **once** using existing cached service functions
- Map results back to individual widget responses
- Use `asyncio.gather()` with `return_exceptions=True` for parallel fetching
- Respect existing circuit breakers, retry, and degradation logic per data source
- Cap at **30 widgets per batch request** — aligned with `DASHBOARD_MAX_WIDGETS`

### 4.4 RBAC Integration

- **READ**: `PermissionAction.READ` on `RBACResourceType.EXPENSE` — view dashboard and data
- **MANAGE**: `PermissionAction.MANAGE` on `RBACResourceType.EXPENSE` — create/edit/delete dashboards
- Add `RBACResourceType.DASHBOARD` stub now for future finer-grained control (viewer vs editor
  roles within the same org)

### 4.5 Default Dashboard Seeder

The seeder is called **synchronously inside the organization creation transaction**, not on first
dashboard access. This guarantees that `GET /dashboards` always returns at least one result and
eliminates the empty-list race condition on new org onboarding.

```python
DEFAULT_LAYOUT = [
  {"i": "stat-monthly",   "x": 0, "y": 0,  "w": 3, "h": 2, "minW": 3, "minH": 2},
  {"i": "stat-forecast",  "x": 3, "y": 0,  "w": 3, "h": 2, "minW": 3, "minH": 2},
  {"i": "stat-lastmonth", "x": 6, "y": 0,  "w": 3, "h": 2, "minW": 3, "minH": 2},
  {"i": "stat-savings",   "x": 9, "y": 0,  "w": 3, "h": 2, "minW": 3, "minH": 2},
  {"i": "chart-trend",    "x": 0, "y": 2,  "w":12, "h": 6, "minW": 6, "minH": 4},
  {"i": "table-resources","x": 0, "y": 8,  "w": 7, "h": 6, "minW": 4, "minH": 4},
  {"i": "list-recs",      "x": 7, "y": 8,  "w": 5, "h": 6, "minW": 4, "minH": 4},
  {"i": "list-pools",     "x": 0, "y":14,  "w": 6, "h": 5, "minW": 4, "minH": 3},
  {"i": "list-accounts",  "x": 6, "y":14,  "w": 6, "h": 5, "minW": 4, "minH": 3},
]
```

This mirrors the current `Dashboard.tsx` layout exactly, ensuring zero visual regression on
migration.

---

## 5. Frontend Implementation

### 5.1 New Dependencies

```
react-grid-layout@^1.4.x   — drag/resize grid (Kibana uses the same concept)
```

No other new deps — we already have antd, @ant-design/charts, react-query, zustand.

### 5.2 New File Structure

```
frontend/src/
├── pages/
│   └── Dashboard.tsx                  # Rewrite: loads layout from API, renders widgets
├── components/
│   └── dashboard/
│       ├── DashboardGrid.tsx          # react-grid-layout wrapper
│       ├── DashboardToolbar.tsx       # Dashboard selector, edit toggle, save/revert buttons,
│       │                             #   "Last edited by X" label
│       ├── WidgetPicker.tsx           # Modal to add new widgets from registry
│       ├── WidgetConfigDrawer.tsx     # Drawer to edit an existing widget's settings
│       │                             #   (metric, title, color, params)
│       ├── widgets/
│       │   ├── StatCardWidget.tsx
│       │   ├── AreaChartWidget.tsx
│       │   ├── BarChartWidget.tsx
│       │   ├── PieChartWidget.tsx
│       │   ├── StackedAreaWidget.tsx
│       │   ├── TableWidget.tsx
│       │   ├── ProgressListWidget.tsx
│       │   ├── StatusListWidget.tsx
│       │   └── WidgetShell.tsx        # Shared wrapper: title bar, loading skeleton,
│       │                             #   error state, settings icon, remove button
│       └── widgetRegistry.ts          # Maps widget type → component + defaults + min size
├── hooks/
│   ├── useCurrentOrgId.ts            # (existing)
│   └── useDashboardData.ts           # Batch fetch with client-side dedup + per-widget mapping
├── api/
│   └── dashboards.ts                 # Dashboard CRUD + batch data API client
└── store/
    └── dashboardStore.ts             # Active dashboard, edit mode, dirty state,
                                      #   selected widget for config drawer
```

### 5.3 Widget Registry Pattern

```typescript
// widgetRegistry.ts
export interface WidgetDefinition {
  type: string;
  label: string;
  icon: React.ReactNode;
  component: React.LazyExoticComponent<any>;
  minW: number;
  minH: number;
  defaultW: number;
  defaultH: number;
  defaultConfig: Record<string, any>;
  dataKeys: string[];         // which metrics this widget needs
  editableFields: string[];   // fields surfaced in WidgetConfigDrawer
}

export const WIDGET_REGISTRY: Record<string, WidgetDefinition> = {
  stat_card: {
    type: 'stat_card',
    label: 'Stat Card',
    icon: <DollarOutlined />,
    component: lazy(() => import('./widgets/StatCardWidget')),
    minW: 3, minH: 2, defaultW: 3, defaultH: 2,
    defaultConfig: { metric: 'monthly_spend', color: '#1677ff' },
    dataKeys: ['monthly_spend'],
    editableFields: ['metric', 'title', 'color', 'icon'],
  },
  area_chart: {
    // ...
    editableFields: ['metric', 'title', 'dateRange', 'smooth'],
  },
  bar_chart: {
    // ...
    editableFields: ['metric', 'title', 'dateRange', 'groupBy'],
  },
  // ... etc
};
```

### 5.4 Dashboard Page Rewrite (High-Level)

```tsx
// Dashboard.tsx (simplified)
const Dashboard = () => {
  const { activeDashboardId, editMode, selectedWidgetId } = useDashboardStore();
  const { data: dashboards } = useQuery(['dashboards', orgId], fetchDashboards);

  // Derive active dashboard; if the stored ID is missing from the list
  // (e.g. deleted by another user), fall back to the org default automatically
  const activeDashboard = useMemo(() => {
    if (!dashboards) return null;
    return (
      dashboards.find(d => d.id === activeDashboardId) ??
      dashboards.find(d => d.is_default) ??
      dashboards[0]
    );
  }, [dashboards, activeDashboardId]);

  const { data: widgetData } = useDashboardData(activeDashboard);

  // Notify user if their active dashboard was deleted by someone else
  useEffect(() => {
    if (
      activeDashboardId &&
      dashboards &&
      !dashboards.find(d => d.id === activeDashboardId)
    ) {
      message.warning('Your active dashboard was deleted. Switched to the default.');
      setActiveDashboard(activeDashboard?.id ?? null);
    }
  }, [dashboards]);

  return (
    <div>
      <DashboardToolbar dashboards={dashboards} activeDashboard={activeDashboard} />
      <DashboardGrid
        layout={activeDashboard?.layout_config}
        widgets={activeDashboard?.widget_config}
        data={widgetData}
        editMode={editMode}
        onLayoutChange={handleLayoutChange}
      />
      {selectedWidgetId && (
        <WidgetConfigDrawer
          widgetId={selectedWidgetId}
          config={activeDashboard?.widget_config[selectedWidgetId]}
          onSave={handleWidgetConfigSave}
          onClose={() => setSelectedWidget(null)}
        />
      )}
    </div>
  );
};
```

### 5.5 `useDashboardData` Hook (Critical for Backend Protection)

```typescript
// useDashboardData.ts
const useDashboardData = (dashboard: Dashboard | null) => {
  const orgId = useCurrentOrgId();

  // Deduplicate by (type, metric, JSON-serialized params) before hitting the API.
  // Without this, two stat_card widgets both requesting 'monthly_spend' would send
  // two identical entries and waste the batch budget.
  const widgetRequests = useMemo(() => {
    if (!dashboard) return [];
    const seen = new Set<string>();
    return Object.values(dashboard.widget_config).reduce<WidgetRequest[]>((acc, w) => {
      const key = `${w.type}:${w.metric}:${JSON.stringify(w.params ?? {})}`;
      if (!seen.has(key)) {
        seen.add(key);
        acc.push({ type: w.type, metric: w.metric, params: w.params ?? {} });
      }
      return acc;
    }, []);
  }, [dashboard]);

  // Single batch request via React Query
  return useQuery({
    queryKey: ['dashboard-data', orgId, dashboard?.id, widgetRequests],
    queryFn: () => dashboardsApi.postWidgetData(orgId, widgetRequests),
    enabled: !!dashboard && widgetRequests.length > 0,
    staleTime: 5 * 60 * 1000,      // 5 min — matches backend cache TTL
    gcTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,    // prevent thundering herd on tab switch
  });
};
```

### 5.6 Widget Config Drawer

`WidgetConfigDrawer` opens as an antd `<Drawer>` from the right side when a user clicks the
settings icon on a `WidgetShell` in edit mode. It dynamically renders only the fields listed
in `WIDGET_REGISTRY[type].editableFields` so adding a new widget type with new config fields
requires no changes to the drawer component itself.

```tsx
// WidgetConfigDrawer.tsx (simplified)
const WidgetConfigDrawer = ({ widgetId, config, onSave, onClose }) => {
  const definition = WIDGET_REGISTRY[config.type];
  const [localConfig, setLocalConfig] = useState(config);

  return (
    <Drawer title="Widget Settings" open onClose={onClose}
            extra={<Button type="primary" onClick={() => onSave(widgetId, localConfig)}>Apply</Button>}>
      {definition.editableFields.includes('metric') && (
        <Form.Item label="Metric">
          <Select value={localConfig.metric}
                  options={METRIC_OPTIONS_BY_TYPE[config.type]}
                  onChange={v => setLocalConfig(c => ({ ...c, metric: v }))} />
        </Form.Item>
      )}
      {definition.editableFields.includes('title') && (
        <Form.Item label="Title">
          <Input value={localConfig.title}
                 onChange={e => setLocalConfig(c => ({ ...c, title: e.target.value }))} />
        </Form.Item>
      )}
      {/* color, dateRange, groupBy, smooth, etc. rendered conditionally */}
    </Drawer>
  );
};
```

### 5.7 Dashboard Store (Zustand)

```typescript
// dashboardStore.ts
interface DashboardState {
  activeDashboardId: string | null;
  editMode: boolean;
  isDirty: boolean;             // unsaved layout changes
  selectedWidgetId: string | null;  // widget whose config drawer is open
  setActiveDashboard: (id: string) => void;
  toggleEditMode: () => void;
  markDirty: () => void;
  setSelectedWidget: (id: string | null) => void;
}
```

---

## 6. Data Flow & Backend Protection Strategy

### 6.1 Request Flow

```
User opens dashboard
  → Frontend: 1 GET /dashboards/{id}            (layout + widget config, ~2KB)
  → Frontend: 1 POST /dashboards/widgets/data   (batch, all deduplicated metrics)
  → Backend: groups by data source, fetches each once
  → Backend: expenses/summary   → Redis / PG cost_cache
  → Backend: expenses/breakdown → Redis / PG cost_cache
  → Backend: resources          → Redis / PG cost_cache
  → Backend: recommendations    → Redis / PG cost_cache
  → Response: single JSON with all widget data
```

**Total: 2 HTTP requests per dashboard load** (vs. current 5–6 separate queries).

### 6.2 Deduplication Layers (Preventing Backend Overload)

| Layer | Mechanism | What It Protects |
|---|---|---|
| **Frontend** | `useDashboardData` dedup by (type, metric, params) | Duplicate widgets requesting same data |
| **Frontend** | React Query `staleTime: 5min` | Repeated tab switches, navigation |
| **Frontend** | `refetchOnWindowFocus: false` | Mass tab-focus stampede |
| **Frontend** | Single batch POST (1 request) | N widget → N API call amplification |
| **Backend** | Data source grouping in batch handler | Duplicate entries that slip through |
| **Backend** | Request coalescing (existing) | Same-org concurrent dashboard loads |
| **Backend** | Cost cache (existing) | CSP API calls on every request |
| **Backend** | Redis cache for batch responses | Repeated identical batch queries |
| **Backend** | Rate limit on batch endpoint | Max 20 req/min per org for widget data |
| **Backend** | Circuit breaker (existing) | Cascading CSP failures |

### 6.3 Batch Data Caching in Redis

```python
# Cache key: dashboard:data:{org_id}:{hash_of_widget_requests}
# TTL: 300s (5 min — matches React Query staleTime)
# Invalidation: on existing cache refresh mechanism
```

### 6.4 Layout Save Debouncing

- Frontend: debounce `onLayoutChange` by 500ms
- Explicit save triggered when user clicks "Save" in the toolbar or exits edit mode
- On save, backend copies `layout_config → previous_layout_config` before persisting new layout
- Optimistic locking via `version` field prevents lost updates

---

## 7. Reliability Considerations

### 7.1 Graceful Degradation for Widgets

- Each widget independently handles loading/error states via `WidgetShell`
- If a data source fails in the batch response, only affected widgets show an error card
- Partial data is acceptable: `errors` map in batch response keyed by metric name
- Widgets show "Data unavailable" with a retry button, not a full-page error

### 7.2 Layout Resilience

- If layout API fails on page load, fall back to last-known-good layout (localStorage cache)
- If `widget_config` references an unknown widget type, render a placeholder with "Unknown
  widget — remove and re-add" message
- Corrupted layout JSON detected by the validator → reset to the org's default dashboard

### 7.3 Concurrent Editing

- Optimistic locking via `version` field: backend rejects mismatched version with `409 Conflict`
- Frontend shows: "This dashboard was modified by another user. Refresh to see the latest."
- No real-time collaboration needed (org dashboards, not per-user)

### 7.4 Deleted Active Dashboard

If the dashboard a user is currently viewing is deleted by another org member (different
browser session), the frontend detects the missing ID on the next `GET /dashboards` poll and
automatically falls back to the org default dashboard, displaying a toast notification
explaining what happened. No broken state, no white screen.

### 7.5 Revert to Last Saved

- "Revert" button appears in the toolbar when `previous_layout_config` is non-null
- Calls `POST /dashboards/{id}/revert`; backend swaps current ↔ previous layout atomically
- Returns `409` if nothing to revert (first-ever save); frontend hides the button in this case
- One level of undo is sufficient for the use case and requires zero extra storage overhead

### 7.6 Migration Safety

- Alembic migration for `dashboards` table (including new columns `created_by`, `updated_by`,
  `previous_layout_config`)
- Default dashboard seeder is called inside org creation, not separately
- Existing `/` route continues to work during migration — it redirects to the default dashboard

---

## 8. Security Considerations

### 8.1 Input Validation

- **Dashboard name**: max 256 chars, alphanumeric + spaces + hyphens only
- **Slug**: written once at creation, validated regex `^[a-z0-9][a-z0-9-]*$`, never updated
- **Layout config**: validate each item has required fields (`i`, `x`, `y`, `w`, `h`), bounds
  check (`0 ≤ x < 12`, `0 ≤ y < 1000`, `1 ≤ w ≤ 12`, `1 ≤ h ≤ 20`)
- **Widget config**: validate `type` against whitelist enum, `metric` against per-type enum,
  reject unknown keys
- **JSONB size limit**: max 64KB per `layout_config`, 128KB per `widget_config`
- **Batch endpoint body**: max 30 widget entries (aligned with `DASHBOARD_MAX_WIDGETS`), reject
  any `metric` not in the server-side enum — client cannot request arbitrary backend data

### 8.2 Authorization

- All dashboard endpoints require org membership (`get_current_org_member`)
- READ requires `PermissionAction.READ` on EXPENSE
- WRITE requires `PermissionAction.MANAGE` on EXPENSE
- Cannot delete the last dashboard (org must always have ≥ 1)
- Cannot unset default — must set another dashboard as default first
- Soft delete only — recoverable by admin

### 8.3 Widget Data Security

- Batch endpoint returns only data the requesting user is authorized to see (org-scoped)
- No cross-org data leakage possible (all queries filtered by `org_id` in the service layer)
- Widget types and metrics are a server-side enum — clients cannot request arbitrary endpoints
  or inject custom query parameters

---

## 9. Implementation Phases

### Phase 1: Backend Foundation (3–4 days)
1. Create `dashboards` module: models (with `created_by`, `updated_by`,
   `previous_layout_config`), schemas, router, service
2. Alembic migration for `dashboards` table including the partial unique index on `is_default`
3. CRUD endpoints (list, create, get, update, delete, set-default, duplicate, revert)
4. Wire default dashboard seeder into org creation transaction
5. RBAC integration (`RBACResourceType.DASHBOARD` stub + EXPENSE permission checks)
6. Unit tests for service layer (including revert, set-default race, slug immutability)

### Phase 2: Batch Data Endpoint (2–3 days)
1. Design and implement `POST /dashboards/widgets/data`
2. Widget data resolver: map widget requests → data source calls with server-side dedup
3. Redis caching for batch responses (TTL aligned to 300s)
4. Rate limiting (20 req/min per org)
5. Integration with existing cost_cache, degradation, and coalescing logic
6. Tests: partial failures, caching, rate limiting, oversized batch rejection, unknown metric
   rejection

### Phase 3: Frontend Grid System (3–4 days)
1. Install `react-grid-layout`, create `DashboardGrid` component
2. Create `WidgetShell` (title bar, loading skeleton, error state, settings icon, remove button)
3. Create `widgetRegistry.ts` with all widget definitions and `editableFields` per type
4. Create `dashboardStore.ts` (Zustand) including `selectedWidgetId`
5. Create `dashboards.ts` API client (CRUD + `postWidgetData`)
6. Create `useDashboardData` hook with client-side deduplication
7. Rewrite `Dashboard.tsx` with active-dashboard fallback logic and deleted-dashboard guard

### Phase 4: Widget Components (3–4 days)
1. `StatCardWidget` — all 8 metric variants
2. `AreaChartWidget` + `StackedAreaWidget`
3. `BarChartWidget` + `PieChartWidget`
4. `TableWidget` — top resources, cloud accounts, recommendations
5. `ProgressListWidget` — recommendation categories, pool status
6. `StatusListWidget` — cloud account health
7. Each widget: loading skeleton, empty state, error state, resize-aware rendering

### Phase 5: Dashboard Editor UX (3–4 days)
1. `DashboardToolbar` — dashboard selector dropdown, edit toggle, save button, "Revert to last
   saved" button (hidden when `previous_layout_config` is null), "Last edited by X" label
2. `WidgetPicker` — modal with categorized widget catalog for adding new widgets
3. `WidgetConfigDrawer` — settings drawer for editing existing widget metric/title/params;
   driven by `editableFields` from the registry so no per-widget drawer code is needed
4. Edit mode: drag handles, resize handles, settings icon per widget, add/remove widgets
5. Layout save with debounce and optimistic locking; on conflict show banner with refresh prompt
6. Create new dashboard flow (blank or duplicate existing)
7. Delete dashboard with confirmation; guard against deleting the last dashboard

### Phase 6: Polish & Testing (2–3 days)
1. Responsive breakpoints (12-col desktop → 6-col tablet → 1-col mobile stacked;
   drag disabled on touch devices, replaced by up/down reorder buttons)
2. Layout persistence stress test (rapid drag/save, concurrent edit conflict simulation)
3. Batch endpoint load test (simulated 50 concurrent users)
4. E2E scenarios:
   - Create dashboard → add widgets → rearrange → save → reload → verify persisted
   - Edit widget config via drawer → confirm metric change reflected in widget data
   - Two sessions editing the same dashboard → conflict banner on second save
   - Delete active dashboard from Session B → Session A falls back to default with toast
   - Revert layout → confirm previous state restored
5. Security audit: input validation, authorization, no data leakage across orgs
6. Accessibility: keyboard navigation for grid, widget focus management, drawer focus trap

---

## 10. Configuration

### Backend `config.py`

```python
# Dashboard Settings
DASHBOARD_MAX_PER_ORG: int = 20           # Max dashboards per org
DASHBOARD_MAX_WIDGETS: int = 30            # Max widgets per dashboard
DASHBOARD_LAYOUT_MAX_SIZE_KB: int = 64     # Max layout JSON size
DASHBOARD_WIDGET_CONFIG_MAX_SIZE_KB: int = 128  # Max widget config JSON size
DASHBOARD_BATCH_MAX_WIDGETS: int = 30      # Must equal DASHBOARD_MAX_WIDGETS
DASHBOARD_BATCH_RATE_LIMIT: int = 20       # Batch requests per minute per org
DASHBOARD_BATCH_CACHE_TTL: int = 300       # Cache TTL for batch responses (seconds)
```

> `DASHBOARD_BATCH_MAX_WIDGETS` is deliberately set equal to `DASHBOARD_MAX_WIDGETS` so a
> full dashboard can always be fetched in a single batch call.

### Frontend — no new env vars needed

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| react-grid-layout bundle size (~30KB gzip) | Lazy-load the grid only when edit mode is active; view mode uses CSS grid positioning |
| Batch endpoint becomes a bottleneck | Redis cache + request coalescing + rate limit; same pattern as existing endpoints |
| Many widgets → slow batch response | Cap at 30 widgets; server-side data source dedup; parallel `asyncio.gather` |
| Concurrent layout edits | DB partial unique index for `is_default`; optimistic locking (`version`) for layout; 409 on conflict |
| Widget type proliferation | Strict server-side enum; new types require backend + frontend code deploy; `editableFields` in registry controls drawer without extra code |
| Mobile drag/resize UX | Drag disabled on touch; stacked 1-col layout; reorder via up/down buttons |
| Deleted active dashboard confusion | Frontend detects missing ID on dashboard list refresh, auto-falls back to default with toast |
| Empty dashboard on first org load | Seeder runs inside org creation transaction, never lazily, so list always has ≥ 1 result |
| Accidental layout destruction | `previous_layout_config` enables one-step revert; surfaced as "Revert to last saved" in toolbar |
| Slug collisions on high-volume org creation | Slug uniqueness enforced by `UNIQUE(organization_id, slug)` DB constraint + retry with suffix on collision |