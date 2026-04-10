# RBAC & ABAC

![RBAC Page](screenshots/rbac-page.png)

Advanced Role-Based and Attribute-Based Access Control for fine-grained permissions.

---

## Overview

CostPilot's RBAC (Role-Based Access Control) and ABAC (Attribute-Based Access Control) system provides enterprise-grade access management with custom roles, attribute-based policies, SSO integration, and access reviews.

**URL**: `/rbac`

**Key Features:**
- Custom role creation with granular permissions
- 6 pre-built system roles (as shown in screenshot)
- Attribute-based policies (ABAC)
- SSO integration (SAML/OIDC)
- Access reviews and certifications
- Permission checking API
- Role expiration support

---

## Pre-Built System Roles

As shown in the screenshot above, CostPilot comes with **6 system roles** automatically created when an organization is set up:

| Role | Description | Use Case |
|------|-------------|----------|
| **Organization Admin** | Full admin across all resources | Platform administrators |
| **Admin View Only** | Read-only across all resources | Senior leadership oversight |
| **Engineer** | Operational access (read org/user/cloud-account/pool/expense/resource/rule/notification, create/update cloud accounts, manage recommendations) | DevOps, developers, team leads |
| **Viewer** | General read-only access | Stakeholders, managers, auditors |
| **Billing Admin** | Cost and billing operations focus | Finance team, procurement |
| **Security Auditor** | Read-only for security/compliance review | Security team, compliance officers |

---

### Permission Matrix

**Resource Types:**
- Organization
- Cloud Account
- Pool
- Expense
- Resource
- Recommendation
- Rule
- User
- Notification
- Enterprise (RBAC, ABAC, SSO)

**Actions:**
- `read`: View resource data
- `create`: Create new resources
- `update`: Modify existing resources
- `delete`: Remove resources
- `manage`: Full control (includes all other actions)

---

### Creating a Custom Role

1. Navigate to **RBAC** page
2. Click **"Create Role"**
3. Fill in:
   - **Role Name**: Descriptive name
   - **Description**: What this role is for
   - **Permissions**: Check boxes for each resource/action combination
4. Click **"Create"**

**Example Role:**
```
Name: Cost Analyst
Description: Can view and export costs, manage pools
Permissions:
  - Expense: read, create
  - Pool: read, create, update
  - Resource: read
  - Recommendation: read
  - Export: read, create
```

---

### Editing a Role

1. Click on role name
2. Modify name, description, or permissions
3. Click **"Save"**

**Note**: Changes affect all users with this role immediately.

---

### Deleting a Role

1. Click on role name
2. Click **"Delete"**
3. Confirm deletion

**Warning**: All users with this role lose those permissions immediately. System roles cannot be deleted.

---

## Role Assignments

### Assigning a Role to a User

1. Navigate to **RBAC** page
2. Click **"Role Assignments"** tab
3. Click **"Assign Role"**
4. Select:
   - **User**: User to assign role to
   - **Role**: Role to assign
   - **Expiration** (Optional): Date when role expires
5. Click **"Assign"**

**Notes:**
- Users can have multiple roles
- Permissions are the union of all roles
- Deny permissions override Allow

---

### Revoking a Role

1. In Role Assignments tab
2. Find the assignment
3. Click **"Revoke"**
4. User loses that role's permissions

---

### Viewing Assignments

The Role Assignments tab shows:
- User name and email
- Role name
- Assigned date
- Expiration date (if set)
- Assigned by (who made the assignment)

---

## ABAC: Attribute-Based Access Control

ABAC policies grant or deny access based on resource attributes rather than roles.

### Creating an ABAC Policy

1. Navigate to **RBAC** page
2. Click **"ABAC Policies"** tab
3. Click **"Create Policy"**
4. Fill in:
   - **Policy Name**: Descriptive name
   - **Description**: What this policy does
   - **Effect**: Allow or Deny
   - **Resource Type**: Which resource type this applies to
   - **Attribute**: Resource attribute to check
   - **Operator**: Comparison operator
   - **Value**: Attribute value to match
   - **Active**: Enable/disable toggle
5. Click **"Create"**

---

### Operators

| Operator | Description | Example |
|----------|-------------|---------|
| **equals** | Attribute equals value | `environment equals production` |
| **not_equals** | Attribute not equals value | `environment not_equals test` |
| **in** | Attribute in list | `environment in [prod, staging]` |
| **not_in** | Attribute not in list | `environment not_in [dev, test]` |
| **contains** | Attribute contains value | `name contains prod` |
| **starts_with** | Attribute starts with value | `name starts with prod-` |

---

### Example ABAC Policies

**Policy 1: Deny Delete on Production**
```
Name: Deny delete on production cloud accounts
Effect: Deny
Resource Type: Cloud Account
Attribute: environment
Operator: equals
Value: production
```

**Result**: No user can delete cloud accounts tagged as production, regardless of role.

---

**Policy 2: Allow Team Access to Their Pools**
```
Name: Team pool access
Effect: Allow
Resource Type: Pool
Attribute: team
Operator: equals
Value: ${user.team}
```

**Result**: Users can only access pools matching their team attribute.

---

**Policy 3: Restrict Region Access**
```
Name: EU region only
Effect: Deny
Resource Type: Resource
Attribute: region
Operator: not_in
Value: [eu-west-1, eu-central-1]
```

**Result**: Users cannot access resources outside EU regions.

---

### Managing ABAC Policies

**View Policies:**
- ABAC Policies tab shows all policies
- Filter by effect (Allow/Deny), resource type, active status

**Edit Policy:**
1. Click on policy name
2. Modify fields
3. Click **"Save"**

**Delete Policy:**
1. Click on policy name
2. Click **"Delete"**
3. Confirm deletion

**Enable/Disable:**
- Toggle Active switch to enable/disable without deleting

---

## Access Reviews

Access Reviews allow periodic certification of user access to ensure compliance.

### Creating an Access Review

1. Navigate to **RBAC** page
2. Click **"Access Reviews"** tab
3. Click **"Create Review"**
4. Fill in:
   - **Review Name**: Descriptive name
   - **Description**: What this review covers
   - **Reviewer**: User responsible for reviewing
   - **Users to Review**: Select users or all users
   - **Due Date**: When review must be completed
5. Click **"Create"**

---

### Completing an Access Review

1. Reviewer navigates to Access Reviews
2. Clicks on review
3. For each user:
   - Review assigned roles and permissions
   - Decide: **Approve** (keep access) or **Revoke** (remove access)
   - Add comments if needed
4. Submit review

---

### Review Status

- **Pending**: Not yet started
- **In Progress**: Review underway
- **Completed**: All users decided
- **Overdue**: Past due date

---

## SSO Integration

Configure SAML or OIDC identity providers for single sign-on.

### Creating an SSO Configuration

1. Navigate to **RBAC** page
2. Click **"SSO"** tab
3. Click **"Create SSO Config"**
4. Select provider type:
   - **SAML**: Security Assertion Markup Language
   - **OIDC**: OpenID Connect
5. Fill in provider-specific details:
   - **SAML**:
     - Identity Provider Metadata URL
     - Entity ID
     - SSO URL
     - Certificate
   - **OIDC**:
     - Issuer URL
     - Client ID
     - Client Secret
     - Authorization URL
     - Token URL
     - User Info URL
6. Set:
   - **Default Role**: Role assigned to auto-provisioned users
   - **Auto-Provisioning**: Enable automatic user creation
7. Click **"Create"**

---

### SSO User Flow

1. User clicks **"Login with SSO"** on login page
2. User redirected to Identity Provider
3. User authenticates with IdP
4. IdP sends assertion/token back to CostPilot
5. CostPilot validates assertion
6. If auto-provisioning enabled:
   - User account created if not exists
   - Default role assigned
7. User logged in with JWT token

---

### Managing SSO Configurations

**View Configs:**
- SSO tab shows all configured identity providers

**Edit Config:**
1. Click on config name
2. Update settings
3. Click **"Save"**

**Delete Config:**
1. Click on config name
2. Click **"Delete"**
3. Users can no longer login via that IdP

---

## Permission Checking

### Check User Permission

API endpoint to check if a user has a specific permission:

```
POST /api/v1/enterprise/{org_id}/rbac/check
```

**Request Body:**
```json
{
  "user_id": "user-uuid",
  "resource_type": "cloud_account",
  "action": "create"
}
```

**Response:**
```json
{
  "allowed": true,
  "reason": "User has Engineer role which grants create permission on cloud_account"
}
```

---

## API Endpoints

### RBAC Overview
```
GET /api/v1/enterprise/{org_id}/rbac
```

### Role Management
```
POST /api/v1/enterprise/{org_id}/rbac/roles
GET /api/v1/enterprise/{org_id}/rbac/roles
GET /api/v1/enterprise/{org_id}/rbac/roles/{role_id}
PATCH /api/v1/enterprise/{org_id}/rbac/roles/{role_id}
DELETE /api/v1/enterprise/{org_id}/rbac/roles/{role_id}
```

### Role Assignments
```
POST /api/v1/enterprise/{org_id}/rbac/assignments
GET /api/v1/enterprise/{org_id}/rbac/assignments
DELETE /api/v1/enterprise/{org_id}/rbac/assignments/{assignment_id}
```

### ABAC Policies
```
POST /api/v1/enterprise/{org_id}/rbac/policies
GET /api/v1/enterprise/{org_id}/rbac/policies
PATCH /api/v1/enterprise/{org_id}/rbac/policies/{policy_id}
DELETE /api/v1/enterprise/{org_id}/rbac/policies/{policy_id}
```

### Access Reviews
```
POST /api/v1/enterprise/{org_id}/rbac/reviews
GET /api/v1/enterprise/{org_id}/rbac/reviews?status=
PATCH /api/v1/enterprise/{org_id}/rbac/reviews/{review_id}
```

### SSO Configuration
```
POST /api/v1/enterprise/{org_id}/rbac/sso
GET /api/v1/enterprise/{org_id}/rbac/sso
PATCH /api/v1/enterprise/{org_id}/rbac/sso/{config_id}
DELETE /api/v1/enterprise/{org_id}/rbac/sso/{config_id}
```

### Permission Check
```
POST /api/v1/enterprise/{org_id}/rbac/check
```

---

## Best Practices

### Role Design

1. **Start with Defaults**: Use built-in roles before creating custom
2. **Follow Least Privilege**: Grant minimum required permissions
3. **Name Clearly**: Role names should indicate purpose
4. **Document**: Describe what each role is for
5. **Review Quarterly**: Audit roles for relevance

### ABAC Policies

1. **Start Simple**: Begin with basic policies, add complexity gradually
2. **Test Thoroughly**: Verify policies work as expected
3. **Use Deny for Safety**: Deny policies override Allow for critical restrictions
4. **Monitor**: Log policy evaluations for debugging
5. **Document**: Explain why each policy exists

### Access Reviews

1. **Schedule Regularly**: Quarterly reviews minimum
2. **Assign Owners**: Team leads review their team members
3. **Track Completion**: Ensure reviews are completed on time
4. **Act on Findings**: Revoke access that's no longer needed
5. **Audit**: Keep records for compliance

### SSO

1. **Enable Auto-Provisioning**: Simplifies user onboarding
2. **Set Default Role**: Assign Viewer role by default
3. **Test IdP Integration**: Verify login flow before deploying
4. **Have Fallback**: Keep local auth as backup
5. **Monitor**: Log SSO login attempts

---

## Troubleshooting

### User Lacks Expected Permissions

**Check:**
1. User has role assigned (check Role Assignments)
2. Role has required permissions (check Role permissions)
3. No ABAC Deny policy blocking access
4. User is in correct organization

**Debug:**
- Use permission check API to see why access is denied
- Review user's effective permissions endpoint

### SSO Login Fails

**Check:**
1. SSO configuration is correct
2. Identity Provider is operational
3. Certificates/tokens are valid
4. User exists in IdP
5. Auto-provisioning is enabled (if user is new)

### Can't Delete Role

**Possible Causes:**
1. Role is a system role (cannot delete)
2. Users have this role assigned

**Solutions:**
1. System roles cannot be deleted
2. Revoke role from all users first, then delete

---

## Next Steps

- **[Users](users.md)** - Assign roles to users
- **[Authentication](authentication.md)** - Login and session management
- **[Audit Logging](audit-logging.md)** - Track permission changes
- **[Security Best Practices](security-best-practices.md)** - Security hardening

---

**Related Documentation:**
- [How to Manage User Roles](guides/manage-user-roles.md)
- [API Reference](api-reference.md)
