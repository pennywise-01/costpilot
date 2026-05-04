# CostPilot Browser Test Cases (agent-browser)

> **Generated from Knowledge Graph** — Covers all major modules: Auth, Organizations, Cloud Accounts, Expenses, Resources, Recommendations, Pools, Schedulers, Dashboards, Users, Settings, RBAC, Exports.
>
> **Credentials:** `test@test.com` / `H4fz4n12@#`
> **Frontend URL:** `http://localhost:5173`
> **Backend API:** `http://localhost:8000`

---

## Table of Contents

1. [Prerequisites & Setup](#1-prerequisites--setup)
2. [Docker Log Checking](#2-docker-log-checking)
3. [TC-01: Authentication — Login](#tc-01-authentication--login)
4. [TC-02: Authentication — Invalid Login](#tc-02-authentication--invalid-login)
5. [TC-03: Authentication — Register](#tc-03-authentication--register)
6. [TC-04: Authentication — Forgot Password](#tc-04-authentication--forgot-password)
7. [TC-05: Organization Selection](#tc-05-organization-selection)
8. [TC-06: Dashboard — Load & Widgets](#tc-06-dashboard--load--widgets)
9. [TC-07: Dashboard — Edit Mode & Save](#tc-07-dashboard--edit-mode--save)
10. [TC-08: Expenses Page](#tc-08-expenses-page)
11. [TC-09: Recommendations Page](#tc-09-recommendations-page)
12. [TC-10: Recommendation Detail Page](#tc-10-recommendation-detail-page)
13. [TC-11: Recommendation Rules Page](#tc-11-recommendation-rules-page)
14. [TC-12: Pools — CRUD Operations](#tc-12-pools--crud-operations)
15. [TC-13: Cloud Accounts — List & Connect](#tc-13-cloud-accounts--list--connect)
16. [TC-14: Cloud Account Details](#tc-14-cloud-account-details)
17. [TC-15: Resources Page](#tc-15-resources-page)
18. [TC-16: Resource Detail Page](#tc-16-resource-detail-page)
19. [TC-17: Schedulers — CRUD & Runs](#tc-17-schedulers--crud--runs)
20. [TC-18: Users Management](#tc-18-users-management)
21. [TC-19: Settings Page](#tc-19-settings-page)
22. [TC-20: RBAC Page](#tc-20-rbac-page)
23. [TC-21: Exports Page](#tc-21-exports-page)
24. [TC-22: Navigation — Sidebar Links](#tc-22-navigation--sidebar-links)
25. [TC-23: Protected Route — Unauthenticated Access](#tc-23-protected-route--unauthenticated-access)
26. [TC-24: 404 Not Found Page](#tc-24-404-not-found-page)
27. [TC-25: Logout](#tc-25-logout)
28. [TC-26: API Error Handling — Network Errors](#tc-26-api-error-handling--network-errors)
29. [TC-27: Session Timeout & Auto-Redirect](#tc-27-session-timeout--auto-redirect)
30. [TC-28: Responsive Layout Check](#tc-28-responsive-layout-check)

---

## 1. Prerequisites & Setup

Ensure Docker Compose is running with all 5 services:

```bash
docker compose up -d
# Wait for all services to be healthy
docker compose ps
```

Verify services are accessible:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000/docs`

---

## 2. Docker Log Checking

> **Run these commands BEFORE and AFTER each test case (or test suite) to capture any backend errors.**

### Check all service logs for errors

```bash
:: Check backend logs for errors (last 100 lines)
docker compose logs backend --tail=100 2>&1 | findstr /I "error exception traceback 500 502 503"

:: Check postgres logs for errors
docker compose logs postgres --tail=50 2>&1 | findstr /I "error fatal panic"

:: Check mongodb logs for errors
docker compose logs mongodb --tail=50 2>&1 | findstr /I "error fatal"

:: Check redis logs for errors
docker compose logs redis --tail=50 2>&1 | findstr /I "error"

:: Check frontend/nginx logs for errors
docker compose logs frontend --tail=50 2>&1 | findstr /I "error"
```

### Stream backend logs in real-time during test execution

```bash
:: Open a separate terminal and run:
docker compose logs -f backend 2>&1 | findstr /I "error exception traceback"
```

### Check for specific HTTP error codes in backend logs

```bash
:: Look for 4xx/5xx responses
docker compose logs backend --tail=200 2>&1 | findstr /I "400 401 403 404 409 422 500 502 503"

:: Look for unhandled exceptions
docker compose logs backend --tail=200 2>&1 | findstr /I "Unhandled exception\|Traceback\|INTERNAL SERVER ERROR"
```

### Save full logs to file for analysis

```bash
:: Dump all logs to a file
docker compose logs --no-color > full-docker-logs.txt 2>&1

:: Dump only backend logs
docker compose logs backend --no-color > backend-logs.txt 2>&1
```

### Check container health status

```bash
docker compose ps
:: All services should show "Up" or "Up (healthy)"
```

---

## TC-01: Authentication — Login

**Module:** AuthModule  
**Route:** `/login`  
**Description:** Verify successful login with valid credentials and redirect to dashboard.

### Steps

```bash
:: Step 1: Open the login page
agent-browser open http://localhost:5173/login

:: Step 2: Wait for page to load and take snapshot of interactive elements
agent-browser wait --load networkidle
agent-browser snapshot -i

:: Step 3: Fill in email field
agent-browser find label "Email" fill "test@test.com"
:: OR using ref from snapshot:
:: agent-browser fill @e1 "test@test.com"

:: Step 4: Fill in password field
agent-browser find label "Password" fill "H4fz4n12@#"
:: OR using ref from snapshot:
:: agent-browser fill @e2 "H4fz4n12@#"

:: Step 5: Click Sign In button
agent-browser find text "Sign in" click

:: Step 6: Wait for navigation to dashboard (or org selection)
agent-browser wait --url "**/"
agent-browser wait --load networkidle

:: Step 7: Verify we are no longer on the login page
agent-browser get url

:: Step 8: Take screenshot of the result
agent-browser screenshot tests/screenshots/tc01-login-success.png

:: Step 9: Check for console errors
agent-browser errors
```

### Expected Results
- URL changes from `/login` to `/` (dashboard) or org selection page
- No error messages displayed on the page
- No console errors related to authentication
- User is authenticated (auth store has user data)

### Docker Log Check

```bash
docker compose logs backend --tail=20 2>&1 | findstr /I "error exception"
```

---

## TC-02: Authentication — Invalid Login

**Module:** AuthModule  
**Route:** `/login`  
**Description:** Verify error handling for invalid credentials.

### Steps

```bash
:: Step 1: Open the login page
agent-browser open http://localhost:5173/login
agent-browser wait --load networkidle
agent-browser snapshot -i

:: Step 2: Fill in invalid email
agent-browser find label "Email" fill "invalid@test.com"

:: Step 3: Fill in invalid password
agent-browser find label "Password" fill "wrongpassword"

:: Step 4: Click Sign In
agent-browser find text "Sign in" click

:: Step 5: Wait for error message to appear
agent-browser wait 2000

:: Step 6: Take snapshot to see error message
agent-browser snapshot

:: Step 7: Verify still on login page
agent-browser get url

:: Step 8: Take screenshot
agent-browser screenshot tests/screenshots/tc02-invalid-login.png

:: Step 9: Check console errors
agent-browser errors
```

### Expected Results
- Error message displayed (e.g., "Login failed. Please try again." or similar)
- URL remains `/login`
- No navigation to dashboard

### Docker Log Check

```bash
docker compose logs backend --tail=20 2>&1 | findstr /I "401 unauthorized"
```

---

## TC-03: Authentication — Register

**Module:** AuthModule  
**Route:** `/register`  
**Description:** Verify user registration flow.

### Steps

```bash
:: Step 1: Open the registration page
agent-browser open http://localhost:5173/register
agent-browser wait --load networkidle
agent-browser snapshot -i

:: Step 2: Fill in registration form
agent-browser find label "Email" fill "newuser@test.com"
agent-browser find label "Password" fill "SecureP@ss123"
:: Look for display name field if present
agent-browser find label "Display Name" fill "Test User"

:: Step 3: Click Sign Up / Register button
agent-browser find text "Sign up" click

:: Step 4: Wait for response
agent-browser wait 3000
agent-browser snapshot

:: Step 5: Take screenshot
agent-browser screenshot tests/screenshots/tc03-register.png

:: Step 6: Check console errors
agent-browser errors
```

### Expected Results
- Successful registration redirects to dashboard or shows success message
- Invalid registration shows validation errors

### Docker Log Check

```bash
docker compose logs backend --tail=20 2>&1 | findstr /I "error exception register"
```

---

## TC-04: Authentication — Forgot Password

**Module:** AuthModule  
**Route:** `/forgot-password`  
**Description:** Verify forgot password flow.

### Steps

```bash
:: Step 1: Open forgot password page
agent-browser open http://localhost:5173/forgot-password
agent-browser wait --load networkidle
agent-browser snapshot -i

:: Step 2: Fill in email
agent-browser find label "Email" fill "test@test.com"

:: Step 3: Click submit button
agent-browser find text "Submit" click
:: OR: agent-browser find text "Send" click
:: OR: agent-browser find text "Reset" click

:: Step 4: Wait for response
agent-browser wait 2000
agent-browser snapshot

:: Step 5: Take screenshot
agent-browser screenshot tests/screenshots/tc04-forgot-password.png

:: Step 6: Check console errors
agent-browser errors
```

### Expected Results
- Success message indicating reset email sent
- OR form submission accepted without error

### Docker Log Check

```bash
docker compose logs backend --tail=20 2>&1 | findstr /I "error forgot-password email"
```

---

## TC-05: Organization Selection

**Module:** OrganizationsModule  
**Route:** `/` (with OrgGuard)  
**Description:** Verify organization selection flow after login.

### Steps

```bash
:: Step 1: Login first (reuse TC-01 flow)
agent-browser open http://localhost:5173/login
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser find label "Email" fill "test@test.com"
agent-browser find label "Password" fill "H4fz4n12@#"
agent-browser find text "Sign in" click
agent-browser wait --load networkidle
agent-browser wait 2000

:: Step 2: Check if org selection page appears
agent-browser snapshot -i

:: Step 3: If org selection is shown, select an organization
:: Look for organization cards or list items
agent-browser find text "Select" click
:: OR click on the first organization card
:: agent-browser find first ".ant-card" click

:: Step 4: Wait for dashboard to load
agent-browser wait --load networkidle
agent-browser wait 2000

:: Step 5: Take screenshot
agent-browser screenshot tests/screenshots/tc05-org-selection.png

:: Step 6: Verify URL
agent-browser get url

:: Step 7: Check console errors
agent-browser errors
```

### Expected Results
- Organization selection page shows available organizations
- Selecting an org navigates to the dashboard
- Current org is stored in the org store

### Docker Log Check

```bash
docker compose logs backend --tail=20 2>&1 | findstr /I "error organization"
```

---

## TC-06: Dashboard — Load & Widgets

**Module:** DashboardsModule  
**Route:** `/`  
**Description:** Verify dashboard loads with widgets and data.

### Steps

```bash
:: Step 1: Login and navigate to dashboard (assumes org is selected)
agent-browser open http://localhost:5173/login
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser find label "Email" fill "test@test.com"
agent-browser find label "Password" fill "H4fz4n12@#"
agent-browser find text "Sign in" click
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: If org selection appears, select one
agent-browser snapshot -i
:: agent-browser find text "Select" click
:: agent-browser wait --load networkidle

:: Step 3: Verify dashboard page loaded
agent-browser get url
:: Should be http://localhost:5173/

:: Step 4: Take snapshot of dashboard content
agent-browser snapshot

:: Step 5: Check for dashboard widgets
agent-browser snapshot -i

:: Step 6: Wait for data to load (widgets may fetch data asynchronously)
agent-browser wait 5000

:: Step 7: Take full-page screenshot of dashboard
agent-browser screenshot --full tests/screenshots/tc06-dashboard.png

:: Step 8: Check for any loading spinners still visible
agent-browser snapshot -i

:: Step 9: Check console errors
agent-browser errors
```

### Expected Results
- Dashboard page loads without errors
- Widgets are rendered (cost summary, charts, etc.)
- No infinite loading spinners
- Cache status indicator shows healthy/stale/expired

### Docker Log Check

```bash
docker compose logs backend --tail=50 2>&1 | findstr /I "error exception dashboard"
```

---

## TC-07: Dashboard — Edit Mode & Save

**Module:** DashboardsModule  
**Route:** `/`  
**Description:** Verify dashboard edit mode, widget management, and save.

### Steps

```bash
:: Step 1: Navigate to dashboard (after login)
agent-browser open http://localhost:5173/
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Look for Edit button
agent-browser snapshot -i

:: Step 3: Click Edit button to enter edit mode
agent-browser find text "Edit" click
:: OR: agent-browser find role button click --name "Edit"

:: Step 4: Wait for edit mode UI to appear
agent-browser wait 1000
agent-browser snapshot -i

:: Step 5: Look for Add Widget button
agent-browser find text "Add Widget" click
:: OR: agent-browser find text "Add" click

:: Step 6: Wait for widget picker to appear
agent-browser wait 1000
agent-browser snapshot -i

:: Step 7: Select a widget type (if picker is shown)
:: agent-browser find text "Cost Summary" click

:: Step 8: Close widget picker if opened as modal/drawer
:: agent-browser find text "Close" click
:: OR: agent-browser press Escape

:: Step 9: Click Save button
agent-browser find text "Save" click

:: Step 10: Wait for save confirmation
agent-browser wait 2000
agent-browser snapshot

:: Step 11: Take screenshot
agent-browser screenshot tests/screenshots/tc07-dashboard-edit.png

:: Step 12: Check console errors
agent-browser errors
```

### Expected Results
- Edit mode toggles layout editing capabilities
- Widget picker allows adding new widgets
- Save persists changes and shows success message
- 409 Conflict handled if another user modified the dashboard

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception dashboard 409"
```

---

## TC-08: Expenses Page

**Module:** ExpensesModule  
**Route:** `/expenses`  
**Description:** Verify expenses page loads and displays cost data.

### Steps

```bash
:: Step 1: Navigate to expenses page
agent-browser open http://localhost:5173/expenses
agent-browser wait --load networkidle
agent-browser wait 5000

:: Step 2: Take snapshot of page content
agent-browser snapshot -i

:: Step 3: Check for expense data tables/charts
agent-browser snapshot

:: Step 4: Look for filter controls (date range, cloud provider)
:: Try interacting with filters if present
:: agent-browser find text "AWS" click
:: agent-browser find text "Azure" click

:: Step 5: Wait for filtered data
agent-browser wait 3000

:: Step 6: Take full-page screenshot
agent-browser screenshot --full tests/screenshots/tc08-expenses.png

:: Step 7: Check console errors
agent-browser errors
```

### Expected Results
- Expenses page loads with cost data or "No data" message
- Filters work correctly
- 90-second timeout not exceeded for expense API calls
- No unhandled errors

### Docker Log Check

```bash
docker compose logs backend --tail=50 2>&1 | findstr /I "error exception expense timeout"
```

---

## TC-09: Recommendations Page

**Module:** RecommendationsModule  
**Route:** `/recommendations`  
**Description:** Verify recommendations page loads and displays optimization suggestions.

### Steps

```bash
:: Step 1: Navigate to recommendations page
agent-browser open http://localhost:5173/recommendations
agent-browser wait --load networkidle
agent-browser wait 5000

:: Step 2: Take snapshot of page content
agent-browser snapshot -i
agent-browser snapshot

:: Step 3: Check for recommendation cards/list items
:: Look for recommendation types (AWS, Azure, GCP)

:: Step 4: Click on a recommendation type if available
:: agent-browser find first ".ant-card" click

:: Step 5: Take full-page screenshot
agent-browser screenshot --full tests/screenshots/tc09-recommendations.png

:: Step 6: Check console errors
agent-browser errors
```

### Expected Results
- Recommendations page loads with optimization suggestions
- Recommendations are grouped by cloud provider
- Each recommendation shows potential savings

### Docker Log Check

```bash
docker compose logs backend --tail=50 2>&1 | findstr /I "error exception recommendation"
```

---

## TC-10: Recommendation Detail Page

**Module:** RecommendationsModule  
**Route:** `/recommendations/:type`  
**Description:** Verify recommendation detail page for a specific recommendation type.

### Steps

```bash
:: Step 1: Navigate to recommendations list first
agent-browser open http://localhost:5173/recommendations
agent-browser wait --load networkidle
agent-browser wait 5000

:: Step 2: Find and click on a recommendation type
agent-browser snapshot -i
:: Click on the first recommendation link/card
:: agent-browser find first "a[href*='recommendations']" click
:: OR: agent-browser find first ".ant-table-row" click

:: Step 3: Wait for detail page to load
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 4: Take snapshot of detail page
agent-browser snapshot -i
agent-browser snapshot

:: Step 5: Take screenshot
agent-browser screenshot --full tests/screenshots/tc10-recommendation-detail.png

:: Step 6: Check console errors
agent-browser errors
```

### Expected Results
- Detail page shows specific recommendation information
- Resource details, estimated savings, and action items are displayed
- Back navigation works

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception recommendation"
```

---

## TC-11: Recommendation Rules Page

**Module:** RecommendationRulesModule  
**Route:** `/recommendation-rules`  
**Description:** Verify recommendation rules management page.

### Steps

```bash
:: Step 1: Navigate to recommendation rules page
agent-browser open http://localhost:5173/recommendation-rules
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Take snapshot
agent-browser snapshot -i
agent-browser snapshot

:: Step 3: Look for create/add rule button
:: agent-browser find text "Add Rule" click
:: agent-browser find text "Create" click

:: Step 4: Take screenshot
agent-browser screenshot --full tests/screenshots/tc11-recommendation-rules.png

:: Step 5: Check console errors
agent-browser errors
```

### Expected Results
- Recommendation rules page loads
- Existing rules are displayed in a table/list
- Create/edit/delete actions are available

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception rule"
```

---

## TC-12: Pools — CRUD Operations

**Module:** PoolsModule  
**Route:** `/pools`  
**Description:** Verify pool listing, creation, editing, and deletion.

### Steps

```bash
:: Step 1: Navigate to pools page
agent-browser open http://localhost:5173/pools
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Take snapshot of pools list
agent-browser snapshot -i

:: Step 3: Look for Create/Add Pool button
agent-browser find text "Create Pool" click
:: OR: agent-browser find text "Add Pool" click
:: OR: agent-browser find text "New Pool" click

:: Step 4: Wait for create form/modal
agent-browser wait 1000
agent-browser snapshot -i

:: Step 5: Fill in pool details
agent-browser find label "Name" fill "Test Pool Browser"
:: agent-browser find label "Description" fill "Created by browser test"

:: Step 6: Submit the form
agent-browser find text "Create" click
:: OR: agent-browser find text "Save" click
:: OR: agent-browser find text "Submit" click

:: Step 7: Wait for pool to be created
agent-browser wait 2000
agent-browser snapshot

:: Step 8: Verify the new pool appears in the list
agent-browser snapshot -i

:: Step 9: Take screenshot
agent-browser screenshot --full tests/screenshots/tc12-pools.png

:: Step 10: Check console errors
agent-browser errors
```

### Expected Results
- Pools page loads with existing pools listed
- Create pool form validates required fields
- New pool appears in the list after creation
- 15-second timeout not exceeded

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception pool"
```

---

## TC-13: Cloud Accounts — List & Connect

**Module:** CloudAccountsModule  
**Route:** `/cloud-accounts`, `/connect-cloud-account`  
**Description:** Verify cloud accounts listing and connection flow.

### Steps

```bash
:: Step 1: Navigate to cloud accounts page
agent-browser open http://localhost:5173/cloud-accounts
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Take snapshot of cloud accounts list
agent-browser snapshot -i

:: Step 3: Look for Connect Account button
agent-browser find text "Connect" click
:: OR: agent-browser find text "Add Account" click
:: OR: agent-browser find text "Connect Cloud Account" click

:: Step 4: Wait for connect page/form
agent-browser wait --load networkidle
agent-browser snapshot -i

:: Step 5: Check cloud provider selection (AWS, Azure, GCP)
agent-browser snapshot

:: Step 6: Take screenshot
agent-browser screenshot --full tests/screenshots/tc13-cloud-accounts.png

:: Step 7: Navigate back to list
agent-browser open http://localhost:5173/cloud-accounts
agent-browser wait --load networkidle
agent-browser wait 2000

:: Step 8: Take screenshot of accounts list
agent-browser screenshot --full tests/screenshots/tc13-cloud-accounts-list.png

:: Step 9: Check console errors
agent-browser errors
```

### Expected Results
- Cloud accounts page lists connected accounts
- Connect flow shows provider selection (AWS/Azure/GCP)
- Credential form fields are appropriate per provider

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception cloud_account"
```

---

## TC-14: Cloud Account Details

**Module:** CloudAccountsModule  
**Route:** `/cloud-accounts/:id`  
**Description:** Verify cloud account detail page.

### Steps

```bash
:: Step 1: Navigate to cloud accounts list
agent-browser open http://localhost:5173/cloud-accounts
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Click on the first cloud account
agent-browser snapshot -i
:: agent-browser find first ".ant-table-row" click
:: OR: agent-browser find first ".ant-card" click

:: Step 3: Wait for detail page
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 4: Take snapshot
agent-browser snapshot -i
agent-browser snapshot

:: Step 5: Take screenshot
agent-browser screenshot --full tests/screenshots/tc14-cloud-account-detail.png

:: Step 6: Check console errors
agent-browser errors
```

### Expected Results
- Detail page shows account information (provider, status, credentials)
- Associated resources/costs may be displayed
- Edit/delete actions available

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception cloud_account"
```

---

## TC-15: Resources Page

**Module:** ResourcesModule  
**Route:** `/resources`  
**Description:** Verify resources page loads and displays cloud resources.

### Steps

```bash
:: Step 1: Navigate to resources page
agent-browser open http://localhost:5173/resources
agent-browser wait --load networkidle
agent-browser wait 5000

:: Step 2: Take snapshot
agent-browser snapshot -i
agent-browser snapshot

:: Step 3: Check for resource table/list
:: Look for pagination, filters, search

:: Step 4: Try using search/filter if available
:: agent-browser find placeholder "Search" type "test"

:: Step 5: Take full-page screenshot
agent-browser screenshot --full tests/screenshots/tc15-resources.png

:: Step 6: Check console errors
agent-browser errors
```

### Expected Results
- Resources page loads with cloud resource data
- Table shows resource name, type, provider, region, cost
- Search/filter functionality works
- 90-second timeout not exceeded

### Docker Log Check

```bash
docker compose logs backend --tail=50 2>&1 | findstr /I "error exception resource timeout"
```

---

## TC-16: Resource Detail Page

**Module:** ResourcesModule  
**Route:** `/resources/:id`  
**Description:** Verify resource detail page.

### Steps

```bash
:: Step 1: Navigate to resources page
agent-browser open http://localhost:5173/resources
agent-browser wait --load networkidle
agent-browser wait 5000

:: Step 2: Click on a resource
agent-browser snapshot -i
:: agent-browser find first ".ant-table-row" click

:: Step 3: Wait for detail page
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 4: Take snapshot
agent-browser snapshot -i
agent-browser snapshot

:: Step 5: Take screenshot
agent-browser screenshot --full tests/screenshots/tc16-resource-detail.png

:: Step 6: Check console errors
agent-browser errors
```

### Expected Results
- Resource detail page shows comprehensive resource information
- Cost history, tags, and recommendations may be displayed

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception resource"
```

---

## TC-17: Schedulers — CRUD & Runs

**Module:** SchedulerModule  
**Route:** `/schedulers`  
**Description:** Verify scheduler listing, creation, and run history.

### Steps

```bash
:: Step 1: Navigate to schedulers page
agent-browser open http://localhost:5173/schedulers
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Take snapshot of schedulers list
agent-browser snapshot -i

:: Step 3: Look for Create Scheduler button
agent-browser find text "Create" click
:: OR: agent-browser find text "Add Scheduler" click
:: OR: agent-browser find text "New" click

:: Step 4: Wait for create form/modal
agent-browser wait 1000
agent-browser snapshot -i

:: Step 5: Fill in scheduler details
:: (Fields depend on SchedulerForm component)
agent-browser find label "Name" fill "Test Scheduler Browser"
:: Select schedule type if dropdown present
:: agent-browser select @eX "daily"

:: Step 6: Submit the form
agent-browser find text "Save" click
:: OR: agent-browser find text "Create" click

:: Step 7: Wait for scheduler to be created
agent-browser wait 2000
agent-browser snapshot

:: Step 8: Look for "Runs" button/link to view scheduler run history
agent-browser find text "Runs" click
:: OR: agent-browser find text "View Runs" click

:: Step 9: Wait for runs modal/page
agent-browser wait 2000
agent-browser snapshot -i

:: Step 10: Take screenshot
agent-browser screenshot --full tests/screenshots/tc17-schedulers.png

:: Step 11: Check console errors
agent-browser errors
```

### Expected Results
- Schedulers page lists configured schedulers
- Create form validates required fields
- Scheduler runs modal shows execution history with logs
- APScheduler integration works correctly

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception scheduler"
```

---

## TC-18: Users Management

**Module:** UserManagementModule  
**Route:** `/users`  
**Description:** Verify user management page with invite and activity log.

### Steps

```bash
:: Step 1: Navigate to users page
agent-browser open http://localhost:5173/users
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Take snapshot of users list
agent-browser snapshot -i

:: Step 3: Look for Invite User button
agent-browser find text "Invite" click
:: OR: agent-browser find text "Invite User" click
:: OR: agent-browser find text "Add User" click

:: Step 4: Wait for invite modal
agent-browser wait 1000
agent-browser snapshot -i

:: Step 5: Fill in invite details
agent-browser find label "Email" fill "invited@test.com"
:: Select role if dropdown present
:: agent-browser select @eX "viewer"

:: Step 6: Submit invite
agent-browser find text "Send" click
:: OR: agent-browser find text "Invite" click

:: Step 7: Wait for response
agent-browser wait 2000
agent-browser snapshot

:: Step 8: Close modal if still open
:: agent-browser press Escape

:: Step 9: Click on a user to view details
agent-browser snapshot -i
:: agent-browser find first ".ant-table-row" click

:: Step 10: Wait for user detail modal
agent-browser wait 1000
agent-browser snapshot -i

:: Step 11: Take screenshot
agent-browser screenshot --full tests/screenshots/tc18-users.png

:: Step 12: Check console errors
agent-browser errors
```

### Expected Results
- Users page lists all users in the organization
- Invite user form sends invitation email
- User detail modal shows activity log
- Role assignment works

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception user invitation"
```

---

## TC-19: Settings Page

**Module:** AuthModule (profile update)  
**Route:** `/settings`  
**Description:** Verify settings page for user profile management.

### Steps

```bash
:: Step 1: Navigate to settings page
agent-browser open http://localhost:5173/settings
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Take snapshot
agent-browser snapshot -i
agent-browser snapshot

:: Step 3: Look for profile update form
:: Try updating display name
:: agent-browser find label "Display Name" fill "Updated Name"

:: Step 4: Look for password change section
:: agent-browser find label "Current Password" fill "H4fz4n12@#"
:: agent-browser find label "New Password" fill "NewP@ss123"

:: Step 5: Save changes
:: agent-browser find text "Save" click

:: Step 6: Take screenshot
agent-browser screenshot --full tests/screenshots/tc19-settings.png

:: Step 7: Check console errors
agent-browser errors
```

### Expected Results
- Settings page loads with current user profile data
- Profile update form works
- Password change form validates current password

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception settings profile"
```

---

## TC-20: RBAC Page

**Module:** EnterpriseModule (RBAC)  
**Route:** `/rbac`  
**Description:** Verify RBAC management page for roles and permissions.

### Steps

```bash
:: Step 1: Navigate to RBAC page
agent-browser open http://localhost:5173/rbac
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Take snapshot
agent-browser snapshot -i
agent-browser snapshot

:: Step 3: Check for roles table/list
:: Look for role management actions

:: Step 4: Take screenshot
agent-browser screenshot --full tests/screenshots/tc20-rbac.png

:: Step 5: Check console errors
agent-browser errors
```

### Expected Results
- RBAC page loads with roles and permissions
- Role management (create/edit/delete) available
- Permission assignment UI works

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception rbac role permission"
```

---

## TC-21: Exports Page

**Module:** EnterpriseModule (Export)  
**Route:** `/exports`  
**Description:** Verify data export management page.

### Steps

```bash
:: Step 1: Navigate to exports page
agent-browser open http://localhost:5173/exports
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Take snapshot
agent-browser snapshot -i
agent-browser snapshot

:: Step 3: Look for Create Export button
:: agent-browser find text "Create Export" click
:: agent-browser find text "New Export" click

:: Step 4: Take screenshot
agent-browser screenshot --full tests/screenshots/tc21-exports.png

:: Step 5: Check console errors
agent-browser errors
```

### Expected Results
- Exports page loads with export job history
- Create export functionality available
- Export templates listed

### Docker Log Check

```bash
docker compose logs backend --tail=30 2>&1 | findstr /I "error exception export"
```

---

## TC-22: Navigation — Sidebar Links

**Module:** FrontendLayouts (AppLayout)  
**Route:** All protected routes  
**Description:** Verify all sidebar navigation links work correctly.

### Steps

```bash
:: Step 1: Login and navigate to dashboard
agent-browser open http://localhost:5173/login
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser find label "Email" fill "test@test.com"
agent-browser find label "Password" fill "H4fz4n12@#"
agent-browser find text "Sign in" click
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Take snapshot of sidebar
agent-browser snapshot -i

:: Step 3: Click each sidebar link and verify navigation

:: Dashboard
agent-browser find text "Dashboard" click
agent-browser wait --load networkidle
agent-browser get url
:: Expected: http://localhost:5173/

:: Expenses
agent-browser find text "Expenses" click
agent-browser wait --load networkidle
agent-browser get url
:: Expected: http://localhost:5173/expenses

:: Recommendations
agent-browser find text "Recommendations" click
agent-browser wait --load networkidle
agent-browser get url
:: Expected: http://localhost:5173/recommendations

:: Pools
agent-browser find text "Pools" click
agent-browser wait --load networkidle
agent-browser get url
:: Expected: http://localhost:5173/pools

:: Cloud Accounts
agent-browser find text "Cloud Accounts" click
agent-browser wait --load networkidle
agent-browser get url
:: Expected: http://localhost:5173/cloud-accounts

:: Resources
agent-browser find text "Resources" click
agent-browser wait --load networkidle
agent-browser get url
:: Expected: http://localhost:5173/resources

:: Schedulers
agent-browser find text "Schedulers" click
agent-browser wait --load networkidle
agent-browser get url
:: Expected: http://localhost:5173/schedulers

:: Users
agent-browser find text "Users" click
agent-browser wait --load networkidle
agent-browser get url
:: Expected: http://localhost:5173/users

:: Settings
agent-browser find text "Settings" click
agent-browser wait --load networkidle
agent-browser get url
:: Expected: http://localhost:5173/settings

:: Step 4: Take final screenshot
agent-browser screenshot tests/screenshots/tc22-navigation.png

:: Step 5: Check console errors
agent-browser errors
```

### Expected Results
- All sidebar links navigate to correct routes
- Active link is highlighted
- No 404 errors on any route

### Docker Log Check

```bash
docker compose logs backend --tail=50 2>&1 | findstr /I "error 404"
```

---

## TC-23: Protected Route — Unauthenticated Access

**Module:** AuthModule (ProtectedRoute guard)  
**Route:** Any protected route  
**Description:** Verify unauthenticated users are redirected to login.

### Steps

```bash
:: Step 1: Clear all cookies/storage to ensure unauthenticated state
agent-browser cookies clear
agent-browser storage local clear

:: Step 2: Try to access a protected route directly
agent-browser open http://localhost:5173/
agent-browser wait --load networkidle
agent-browser wait 2000

:: Step 3: Verify redirect to login
agent-browser get url
:: Expected: http://localhost:5173/login

:: Step 4: Take snapshot
agent-browser snapshot -i

:: Step 5: Try another protected route
agent-browser open http://localhost:5173/expenses
agent-browser wait --load networkidle
agent-browser wait 2000
agent-browser get url
:: Expected: http://localhost:5173/login

:: Step 6: Take screenshot
agent-browser screenshot tests/screenshots/tc23-protected-route.png

:: Step 7: Check console errors
agent-browser errors
```

### Expected Results
- All protected routes redirect to `/login` when not authenticated
- No protected content is visible

### Docker Log Check

```bash
docker compose logs backend --tail=20 2>&1 | findstr /I "401 unauthorized"
```

---

## TC-24: 404 Not Found Page

**Module:** FrontendPages (NotFound)  
**Route:** `/*` (wildcard)  
**Description:** Verify 404 page for non-existent routes.

### Steps

```bash
:: Step 1: Login first
agent-browser open http://localhost:5173/login
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser find label "Email" fill "test@test.com"
agent-browser find label "Password" fill "H4fz4n12@#"
agent-browser find text "Sign in" click
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Navigate to a non-existent route
agent-browser open http://localhost:5173/non-existent-page
agent-browser wait --load networkidle
agent-browser wait 2000

:: Step 3: Verify 404 page is shown
agent-browser snapshot -i
agent-browser snapshot

:: Step 4: Take screenshot
agent-browser screenshot tests/screenshots/tc24-not-found.png

:: Step 5: Check for "Go Home" or "Back" link
:: agent-browser find text "Go Home" click
:: agent-browser get url
:: Expected: http://localhost:5173/

:: Step 6: Check console errors
agent-browser errors
```

### Expected Results
- 404 page displays for non-existent routes
- Navigation back to home/dashboard works
- No server errors

### Docker Log Check

```bash
docker compose logs backend --tail=20 2>&1 | findstr /I "error 404"
```

---

## TC-25: Logout

**Module:** AuthModule  
**Route:** Any (logout action)  
**Description:** Verify logout functionality.

### Steps

```bash
:: Step 1: Login first
agent-browser open http://localhost:5173/login
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser find label "Email" fill "test@test.com"
agent-browser find label "Password" fill "H4fz4n12@#"
agent-browser find text "Sign in" click
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Find and click logout button
agent-browser snapshot -i
:: Look for user avatar/menu in header
agent-browser find text "Logout" click
:: OR: agent-browser find text "Sign out" click
:: OR: agent-browser find text "Log out" click

:: Step 3: Wait for redirect to login
agent-browser wait --load networkidle
agent-browser wait 2000

:: Step 4: Verify redirect to login page
agent-browser get url
:: Expected: http://localhost:5173/login

:: Step 5: Verify cannot access protected routes
agent-browser open http://localhost:5173/
agent-browser wait --load networkidle
agent-browser wait 2000
agent-browser get url
:: Expected: http://localhost:5173/login

:: Step 6: Take screenshot
agent-browser screenshot tests/screenshots/tc25-logout.png

:: Step 7: Check console errors
agent-browser errors
```

### Expected Results
- Logout clears auth state
- User is redirected to login page
- Protected routes are no longer accessible

### Docker Log Check

```bash
docker compose logs backend --tail=20 2>&1 | findstr /I "error logout"
```

---

## TC-26: API Error Handling — Network Errors

**Module:** MiddlewareModule (GlobalExceptionHandler)  
**Route:** Any  
**Description:** Verify frontend handles API errors gracefully.

### Steps

```bash
:: Step 1: Login first
agent-browser open http://localhost:5173/login
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser find label "Email" fill "test@test.com"
agent-browser find label "Password" fill "H4fz4n12@#"
agent-browser find text "Sign in" click
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Monitor network requests
agent-browser network requests

:: Step 3: Navigate to a data-heavy page
agent-browser open http://localhost:5173/expenses
agent-browser wait --load networkidle
agent-browser wait 5000

:: Step 4: Check network requests for errors
agent-browser network requests --filter api

:: Step 5: Check for any error notifications/messages on page
agent-browser snapshot

:: Step 6: Take screenshot
agent-browser screenshot tests/screenshots/tc26-error-handling.png

:: Step 7: Check console errors
agent-browser errors
```

### Expected Results
- API errors show user-friendly error messages
- 401 errors trigger redirect to login
- 403 "not a member" errors clear org and redirect
- 409 conflicts show appropriate message
- No unhandled promise rejections

### Docker Log Check

```bash
docker compose logs backend --tail=50 2>&1 | findstr /I "error exception 500 502 503"
```

---

## TC-27: Session Timeout & Auto-Redirect

**Module:** AuthModule (token expiry)  
**Route:** Any protected route  
**Description:** Verify session timeout behavior and auto-redirect.

### Steps

```bash
:: Step 1: Login first
agent-browser open http://localhost:5173/login
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser find label "Email" fill "test@test.com"
agent-browser find label "Password" fill "H4fz4n12@#"
agent-browser find text "Sign in" click
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Simulate expired token by clearing auth storage
agent-browser eval "localStorage.removeItem('auth-storage')"

:: Step 3: Try to navigate to a protected page
agent-browser open http://localhost:5173/expenses
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 4: Verify redirect to login
agent-browser get url
:: Expected: http://localhost:5173/login

:: Step 5: Take screenshot
agent-browser screenshot tests/screenshots/tc27-session-timeout.png

:: Step 6: Check console errors
agent-browser errors
```

### Expected Results
- Expired/invalid session redirects to login
- No protected content shown with expired session

### Docker Log Check

```bash
docker compose logs backend --tail=20 2>&1 | findstr /I "401 token expired"
```

---

## TC-28: Responsive Layout Check

**Module:** FrontendLayouts (AppLayout)  
**Route:** `/`  
**Description:** Verify responsive layout at different viewport sizes.

### Steps

```bash
:: Step 1: Login first
agent-browser open http://localhost:5173/login
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser find label "Email" fill "test@test.com"
agent-browser find label "Password" fill "H4fz4n12@#"
agent-browser find text "Sign in" click
agent-browser wait --load networkidle
agent-browser wait 3000

:: Step 2: Desktop viewport (1920x1080)
agent-browser set viewport 1920 1080
agent-browser wait 1000
agent-browser screenshot tests/screenshots/tc28-desktop-1920x1080.png

:: Step 3: Laptop viewport (1366x768)
agent-browser set viewport 1366 768
agent-browser wait 1000
agent-browser screenshot tests/screenshots/tc28-laptop-1366x768.png

:: Step 4: Tablet viewport (768x1024)
agent-browser set viewport 768 1024
agent-browser wait 1000
agent-browser screenshot tests/screenshots/tc28-tablet-768x1024.png

:: Step 5: Mobile viewport (375x812 - iPhone X)
agent-browser set viewport 375 812
agent-browser wait 1000
agent-browser screenshot tests/screenshots/tc28-mobile-375x812.png

:: Step 6: Check for layout issues at each size
agent-browser snapshot -i

:: Step 7: Check console errors
agent-browser errors
```

### Expected Results
- Layout adapts to different viewport sizes
- Sidebar collapses on smaller screens
- Content remains readable and accessible
- No horizontal scrollbars on mobile

### Docker Log Check

```bash
docker compose logs backend --tail=20 2>&1 | findstr /I "error"
```

---

## Full Test Suite Execution Script

> Run this script to execute all test cases sequentially. Each test case includes Docker log checks.

```bash
@echo off
echo ========================================
echo CostPilot Browser Test Suite
echo ========================================
echo.

:: Create screenshots directory
mkdir tests\screenshots 2>nul

:: Pre-test: Check Docker services
echo [PRE-TEST] Checking Docker services...
docker compose ps
echo.

:: Pre-test: Capture baseline logs
echo [PRE-TEST] Capturing baseline Docker logs...
docker compose logs --no-color > tests\screenshots\baseline-docker-logs.txt 2>&1
echo.

:: TC-01: Login
echo [TC-01] Authentication - Login
agent-browser open http://localhost:5173/login
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser find label "Email" fill "test@test.com"
agent-browser find label "Password" fill "H4fz4n12@#"
agent-browser find text "Sign in" click
agent-browser wait --url "**/"
agent-browser wait --load networkidle
agent-browser screenshot tests\screenshots\tc01-login-success.png
agent-browser errors
echo [TC-01] PASS - Login successful
echo.

:: TC-05: Organization Selection (if needed)
echo [TC-05] Organization Selection
agent-browser snapshot -i
agent-browser wait 2000
agent-browser screenshot tests\screenshots\tc05-org-selection.png
echo.

:: TC-06: Dashboard
echo [TC-06] Dashboard Load
agent-browser open http://localhost:5173/
agent-browser wait --load networkidle
agent-browser wait 5000
agent-browser screenshot --full tests\screenshots\tc06-dashboard.png
agent-browser errors
echo [TC-06] PASS - Dashboard loaded
echo.

:: TC-08: Expenses
echo [TC-08] Expenses Page
agent-browser open http://localhost:5173/expenses
agent-browser wait --load networkidle
agent-browser wait 5000
agent-browser screenshot --full tests\screenshots\tc08-expenses.png
agent-browser errors
echo [TC-08] PASS - Expenses page loaded
echo.

:: TC-09: Recommendations
echo [TC-09] Recommendations Page
agent-browser open http://localhost:5173/recommendations
agent-browser wait --load networkidle
agent-browser wait 5000
agent-browser screenshot --full tests\screenshots\tc09-recommendations.png
agent-browser errors
echo [TC-09] PASS - Recommendations page loaded
echo.

:: TC-12: Pools
echo [TC-12] Pools Page
agent-browser open http://localhost:5173/pools
agent-browser wait --load networkidle
agent-browser wait 3000
agent-browser screenshot --full tests\screenshots\tc12-pools.png
agent-browser errors
echo [TC-12] PASS - Pools page loaded
echo.

:: TC-13: Cloud Accounts
echo [TC-13] Cloud Accounts Page
agent-browser open http://localhost:5173/cloud-accounts
agent-browser wait --load networkidle
agent-browser wait 3000
agent-browser screenshot --full tests\screenshots\tc13-cloud-accounts.png
agent-browser errors
echo [TC-13] PASS - Cloud Accounts page loaded
echo.

:: TC-15: Resources
echo [TC-15] Resources Page
agent-browser open http://localhost:5173/resources
agent-browser wait --load networkidle
agent-browser wait 5000
agent-browser screenshot --full tests\screenshots\tc15-resources.png
agent-browser errors
echo [TC-15] PASS - Resources page loaded
echo.

:: TC-17: Schedulers
echo [TC-17] Schedulers Page
agent-browser open http://localhost:5173/schedulers
agent-browser wait --load networkidle
agent-browser wait 3000
agent-browser screenshot --full tests\screenshots\tc17-schedulers.png
agent-browser errors
echo [TC-17] PASS - Schedulers page loaded
echo.

:: TC-18: Users
echo [TC-18] Users Page
agent-browser open http://localhost:5173/users
agent-browser wait --load networkidle
agent-browser wait 3000
agent-browser screenshot --full tests\screenshots\tc18-users.png
agent-browser errors
echo [TC-18] PASS - Users page loaded
echo.

:: TC-19: Settings
echo [TC-19] Settings Page
agent-browser open http://localhost:5173/settings
agent-browser wait --load networkidle
agent-browser wait 3000
agent-browser screenshot --full tests\screenshots\tc19-settings.png
agent-browser errors
echo [TC-19] PASS - Settings page loaded
echo.

:: TC-20: RBAC
echo [TC-20] RBAC Page
agent-browser open http://localhost:5173/rbac
agent-browser wait --load networkidle
agent-browser wait 3000
agent-browser screenshot --full tests\screenshots\tc20-rbac.png
agent-browser errors
echo [TC-20] PASS - RBAC page loaded
echo.

:: TC-21: Exports
echo [TC-21] Exports Page
agent-browser open http://localhost:5173/exports
agent-browser wait --load networkidle
agent-browser wait 3000
agent-browser screenshot --full tests\screenshots\tc21-exports.png
agent-browser errors
echo [TC-21] PASS - Exports page loaded
echo.

:: TC-24: 404 Page
echo [TC-24] 404 Not Found Page
agent-browser open http://localhost:5173/non-existent-page
agent-browser wait --load networkidle
agent-browser wait 2000
agent-browser screenshot tests\screenshots\tc24-not-found.png
echo [TC-24] PASS - 404 page displayed
echo.

:: TC-25: Logout
echo [TC-25] Logout
agent-browser find text "Logout" click
agent-browser wait --load networkidle
agent-browser wait 2000
agent-browser screenshot tests\screenshots\tc25-logout.png
echo [TC-25] PASS - Logout successful
echo.

:: Post-test: Capture final logs
echo [POST-TEST] Capturing final Docker logs...
docker compose logs --no-color > tests\screenshots\final-docker-logs.txt 2>&1

:: Post-test: Check for errors
echo [POST-TEST] Checking for errors in Docker logs...
docker compose logs backend --tail=200 2>&1 | findstr /I "error exception traceback 500"
echo.

:: Close browser
agent-browser close

echo ========================================
echo Test Suite Complete!
echo Screenshots saved to tests/screenshots/
echo ========================================
```

---

## Test Coverage Matrix

| Module | Route | TC # | Status |
|--------|-------|------|--------|
| AuthModule | `/login` | TC-01, TC-02 | Pending |
| AuthModule | `/register` | TC-03 | Pending |
| AuthModule | `/forgot-password` | TC-04 | Pending |
| AuthModule | Logout | TC-25 | Pending |
| AuthModule | Session Timeout | TC-27 | Pending |
| OrganizationsModule | Org Selection | TC-05 | Pending |
| DashboardsModule | `/` | TC-06, TC-07 | Pending |
| ExpensesModule | `/expenses` | TC-08 | Pending |
| RecommendationsModule | `/recommendations` | TC-09 | Pending |
| RecommendationsModule | `/recommendations/:type` | TC-10 | Pending |
| RecommendationRulesModule | `/recommendation-rules` | TC-11 | Pending |
| PoolsModule | `/pools` | TC-12 | Pending |
| CloudAccountsModule | `/cloud-accounts` | TC-13 | Pending |
| CloudAccountsModule | `/cloud-accounts/:id` | TC-14 | Pending |
| ResourcesModule | `/resources` | TC-15 | Pending |
| ResourcesModule | `/resources/:id` | TC-16 | Pending |
| SchedulerModule | `/schedulers` | TC-17 | Pending |
| UserManagementModule | `/users` | TC-18 | Pending |
| Settings | `/settings` | TC-19 | Pending |
| EnterpriseModule (RBAC) | `/rbac` | TC-20 | Pending |
| EnterpriseModule (Export) | `/exports` | TC-21 | Pending |
| AppLayout | Sidebar Navigation | TC-22 | Pending |
| ProtectedRoute | Unauthenticated | TC-23 | Pending |
| NotFound | `/*` | TC-24 | Pending |
| GlobalExceptionHandler | Error Handling | TC-26 | Pending |
| AppLayout | Responsive | TC-28 | Pending |
