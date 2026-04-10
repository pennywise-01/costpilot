# User Management

![Users Page](screenshots/users-page.png)

Invite, manage, and organize team members in your organization.

---

## Overview

User Management provides full lifecycle management of users within your organization, from invitation through ongoing management including role assignment, suspension, and removal.

**URL**: `/users`

**Key Features:**
- Email-based user invitations
- Bulk invite functionality
- User listing with filtering and search
- User profile management
- Suspend/activate users
- Remove users from organization
- Role assignment and management
- Activity tracking
- Effective permissions view

**As shown in the screenshot above:**
- User list with search and filter controls at the top
- "Invite User" button for adding new team members
- User table showing name, email, role, status, and actions
- Current user (Demo User / test@test.com) visible in the list

---

## Page Layout

### Invite User Button

At the top of the page:

**"Invite User"**: Invite a single user via email  
**"Bulk Invite"**: Invite multiple users at once

---

### Users Table

The main table displays all users in the organization:

**Columns:**
- **Name**: Display name (clickable to view details)
- **Email**: Email address
- **Role**: Primary role badge (Admin, Engineer, Viewer, etc.)
- **Status**: Active, Suspended, or Invited
- **Department**: Department (if set)
- **Job Title**: Job title (if set)
- **Last Active**: Last login or activity timestamp
- **Actions**: Edit, Suspend/Activate, Remove, Manage Roles

**Filters:**
- **Status**: All, Active, Suspended, Invited
- **Department**: Filter by department
- **Search**: Search by name or email
- **Sort**: Sort by name, email, last active, etc.

**Pagination:**
- 20 users per page
- Navigate with pagination controls

---

## Inviting Users

### Single User Invitation

**Step 1: Click Invite User**
- Navigate to **Users** page
- Click **"Invite User"** button

**Step 2: Fill in Details**
- **Email**: User's email address (required)
- **Role**: Select role from dropdown (e.g., Engineer, Viewer, Admin)

**Step 3: Send Invitation**
- Click **"Send Invitation"**
- Backend creates invitation token
- Email sent to invitee with acceptance link
- User appears in list with "Invited" status

**What Happens Next:**
1. User receives email with invitation link
2. User clicks link and is directed to `/accept-invitation/{token}`
3. User sets display name and password
4. Account is created and user is logged in
5. User is automatically assigned the invited role
6. User status changes from "Invited" to "Active"

**Invitation Token:**
- URL-safe, 48 bytes
- Expires in 7 days (configurable via `INVITATION_EXPIRY_DAYS`)
- Single-use token

---

### Bulk User Invitation

**Step 1: Click Bulk Invite**
- Navigate to **Users** page
- Click **"Bulk Invite"** button

**Step 2: Enter Emails**
- Enter multiple email addresses (one per line)
- Example:
  ```
  john@example.com
  jane@example.com
  bob@example.com
  ```

**Step 3: Select Default Role**
- Choose a role to assign to all invited users
- Can be changed individually later

**Step 4: Send Invitations**
- Click **"Send Invitations"**
- All emails receive invitation emails
- All users appear in list with "Invited" status

---

## Accepting an Invitation

**For the Invitee:**

1. **Receive Email**: Check inbox for invitation email
2. **Click Link**: Click the acceptance link in the email
3. **Set Details**:
   - Enter display name
   - Enter password (must meet complexity requirements)
   - Confirm password
4. **Accept**: Click **"Accept Invitation"**
5. **Logged In**: Automatically logged in and redirected to dashboard
6. **Organization**: Auto-assigned to the inviting organization with invited role

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

---

## Viewing User Details

Click on a user's name to view detailed information:

**User Profile:**
- Display name
- Email address
- Department
- Job title
- Status (Active, Suspended, Invited)
- Created date
- Last active date

**Roles:**
- List of assigned roles
- Role assignment dates
- Role expiration (if set)

**Activity Summary:**
- Recent login activity
- Recent actions
- Permission changes

**Preferences:**
- Notification preferences
- Language settings
- Timezone

**Effective Permissions:**
- Full list of permissions user has
- Derived from assigned roles
- Includes any ABAC policy effects

---

## Managing Users

### Edit User Details

1. Click on user name
2. Click **"Edit"**
3. Update fields:
   - Display name
   - Department
   - Job title
4. Click **"Save"**

---

### Suspend a User

1. Click on user name (or use actions menu)
2. Click **"Suspend"**
3. Confirm suspension

**Effects:**
- User cannot log in
- Active sessions are invalidated
- User remains in organization
- Historical data preserved
- User appears with "Suspended" status

**Use Cases:**
- Temporary leave
- Security investigation
- Offboarding process

---

### Activate a User

1. Click on suspended user name
2. Click **"Activate"**
3. User can log in again

---

### Remove a User

1. Click on user name
2. Click **"Remove"**
3. Confirm removal

**Effects:**
- User removed from organization
- User loses all organization permissions
- User can still exist in other organizations
- Historical data preserved (associated with "Former User")

**Note**: This does not delete the user account entirely if they belong to other organizations.

---

## Managing User Roles

### View User Roles

1. Click on user name
2. Click **"Manage Roles"**
3. See list of assigned roles with:
   - Role name
   - Assigned date
   - Expiration date (if set)
   - Assigned by (who made the assignment)

---

### Assign Role

1. In Manage Roles view
2. Click **"Assign Role"**
3. Select role from dropdown
4. (Optional) Set expiration date
5. Click **"Assign"**

**Notes:**
- Users can have multiple roles
- Permissions are the union of all role permissions
- Deny permissions override Allow permissions

---

### Revoke Role

1. In Manage Roles view
2. Click **"Revoke"** next to role
3. Confirm revocation
4. User loses that role's permissions

---

### Replace Roles

1. In Manage Roles view
2. Click **"Replace Roles"**
3. Select new set of roles
4. All old roles are removed, new roles assigned
5. Click **"Save"**

---

## Activity Logs

### User Activity

View individual user's recent activity:

1. Click on user name
2. Click **"Activity"** tab
3. See chronological list of:
   - Logins
   - Profile changes
   - Role changes
   - Resource modifications
   - Configuration changes

---

### Organization Activity

View organization-wide activity:

1. Navigate to **Users** page
2. Click **"Activity"** tab (or separate page)
3. See all user activity in organization
4. Filter by user, date range, action type

---

## API Endpoints

### List Users
```
GET /api/v1/organizations/{org_id}/users?page=1&limit=20&status=&department=&search=&sort_by=name&sort_order=asc
```

**Query Parameters:**
- `page` (int): Page number
- `limit` (int): Users per page
- `status` (string): Filter by status (active, suspended, invited)
- `department` (string): Filter by department
- `search` (string): Search by name or email
- `sort_by` (string): Sort field (name, email, last_active)
- `sort_order` (string): asc or desc

**Response:**
```json
{
  "users": [
    {
      "id": "user-uuid",
      "email": "john@example.com",
      "display_name": "John Doe",
      "status": "active",
      "department": "Engineering",
      "job_title": "Senior Developer",
      "last_active": "2026-04-09T12:00:00Z",
      "roles": [
        {
          "id": "role-uuid",
          "name": "Engineer"
        }
      ]
    }
  ],
  "total": 25,
  "page": 1,
  "limit": 20
}
```

### Invite User
```
POST /api/v1/organizations/{org_id}/users/invite
```

**Request Body:**
```json
{
  "email": "newuser@example.com",
  "role_id": "engineer-role-uuid"
}
```

### Bulk Invite
```
POST /api/v1/organizations/{org_id}/users/invite-bulk
```

**Request Body:**
```json
{
  "emails": [
    "user1@example.com",
    "user2@example.com",
    "user3@example.com"
  ],
  "role_id": "viewer-role-uuid"
}
```

### Get User Detail
```
GET /api/v1/organizations/{org_id}/users/{user_id}
```

### Update User
```
PATCH /api/v1/organizations/{org_id}/users/{user_id}
```

### Suspend User
```
POST /api/v1/organizations/{org_id}/users/{user_id}/suspend
```

### Activate User
```
POST /api/v1/organizations/{org_id}/users/{user_id}/activate
```

### Remove User
```
DELETE /api/v1/organizations/{org_id}/users/{user_id}
```

### Get User Roles
```
GET /api/v1/organizations/{org_id}/users/{user_id}/roles
```

### Update User Roles
```
PATCH /api/v1/organizations/{org_id}/users/{user_id}/roles
```

### Get User Permissions
```
GET /api/v1/organizations/{org_id}/users/{user_id}/permissions
```

### Get User Activity
```
GET /api/v1/organizations/{org_id}/users/{user_id}/activity
```

### Get Organization Activity
```
GET /api/v1/organizations/{org_id}/activity
```

---

## Invitation Email Configuration

### SMTP (Default)

Configure in `.env`:

```env
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@costpilot.io
```

### AWS SES

Configure in `.env`:

```env
EMAIL_PROVIDER=ses
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
SES_FROM_EMAIL=noreply@costpilot.io
```

---

## Best Practices

### User Onboarding

1. **Invite with Role**: Assign appropriate role at invitation time
2. **Start with Viewer**: New users start as Viewers, promote after training
3. **Bulk Invite Teams**: Use bulk invite for team onboarding
4. **Welcome Message**: Send a welcome message explaining CostPilot usage

### Access Management

1. **Least Privilege**: Assign minimum required permissions
2. **Regular Review**: Review user access quarterly
3. **Suspend Promptly**: Suspend immediately when user leaves
4. **Audit Activity**: Review activity logs for anomalies

### Role Assignment

1. **Use Default Roles**: Leverage built-in roles before creating custom
2. **Multi-Role**: Assign multiple roles for granular access
3. **Set Expiration**: Use role expiration for temporary access
4. **Document**: Document why users have elevated permissions

---

## Troubleshooting

### Invitation Email Not Received

**Possible Causes:**
1. Incorrect email address
2. Email in spam/junk folder
3. Email provider not configured
4. Email delivery delay

**Solutions:**
1. Verify email address is correct
2. Check spam/junk folder
3. Verify SMTP/SES configuration in backend
4. Check backend logs for email sending errors
5. Re-send invitation (delete old one first if needed)

### Invitation Link Expired

**Default Expiry**: 7 days

**Solution:**
1. Remove the expired invitation
2. Send a new invitation

### Can't Suspend Last Admin

**Restriction**: Organization must have at least one active Organization Admin

**Solution:**
1. Assign Admin role to another user first
2. Then suspend the original admin

### User Can't Log In After Activation

**Check:**
1. User status is "Active" (not "Suspended")
2. User has accepted invitation and set password
3. User is using correct email and password
4. Account is not locked (check failed login attempts)

---

## Next Steps

- **[RBAC & ABAC](rbac.md)** - Advanced role and policy management
- **[Pools](pools.md)** - Assign pool owners
- **[Notifications](notifications.md)** - Configure user notification preferences
- **[Audit Logging](audit-logging.md)** - Track user activity

---

**Related Documentation:**
- [How to Invite Users](guides/invite-users.md)
- [How to Manage User Roles](guides/manage-user-roles.md)
- [API Reference](api-reference.md)
