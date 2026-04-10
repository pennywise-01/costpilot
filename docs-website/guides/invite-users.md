# How to Invite Users

Add team members to your CostPilot organization with proper roles and permissions.

---

## Overview

User invitations allow you to add team members to your CostPilot organization. Invited users receive an email with a link to create their account and set their password.

**Time Required:** 2-5 minutes per invitation  
**Prerequisites:**
- Organization Admin or Engineer role
- User email addresses
- Decision on user roles

---

## Understanding Roles

Before inviting users, understand the available roles:

| Role | Access Level | Use For |
|------|-------------|---------|
| **Organization Admin** | Full admin access | Platform administrators |
| **Engineer** | Operational access | DevOps, developers, team leads |
| **Viewer** | Read-only access | Stakeholders, managers, auditors |
| **Billing Admin** | Cost and billing focus | Finance team, procurement |
| **Security Auditor** | Security/compliance view | Security team, compliance officers |
| **Admin View Only** | Read-only admin | Senior leadership oversight |

**Recommendation:** Start new users with Viewer or Engineer role, promote as needed.

---

## Inviting a Single User

### Step 1: Navigate to Users

1. Click **"Users"** in left sidebar
2. Click **"Invite User"** button

---

### Step 2: Enter User Details

**Email:**
- Enter user's email address
- Example: `john.doe@example.com`
- Must be valid email format

**Role:**
- Select role from dropdown
- Choose based on user's responsibilities
- Can be changed later

---

### Step 3: Send Invitation

1. Click **"Send Invitation"**
2. User receives email with invitation link
3. User appears in list with **"Invited"** status

---

### Step 4: What Happens Next

**For the Invitee:**
1. Receives email: "You've been invited to join [Organization] on CostPilot"
2. Clicks **"Accept Invitation"** link in email
3. Directed to acceptance page
4. Sets display name and password
5. Automatically logged in
6. Account status changes to **"Active"**

**For the Inviter:**
- User status updates from "Invited" to "Active"
- Can see user in list with active status
- Can manage user's roles and permissions

---

## Inviting Multiple Users (Bulk Invite)

### Step 1: Navigate to Users

1. Click **"Users"** in left sidebar
2. Click **"Bulk Invite"** button

---

### Step 2: Enter Email Addresses

Enter multiple email addresses, one per line:

```
john.doe@example.com
jane.smith@example.com
bob.johnson@example.com
alice.williams@example.com
```

**Tips:**
- Copy from spreadsheet or HR system
- Verify email addresses are correct
- Maximum: Check system limits (typically 50-100 at once)

---

### Step 3: Select Default Role

Choose a role to assign to all invited users:
- **Viewer**: Safe default for most users
- **Engineer**: For technical team members
- **Other**: Based on team responsibilities

**Note:** Roles can be changed individually after acceptance.

---

### Step 4: Send Invitations

1. Click **"Send Invitations"**
2. All emails are sent
3. All users appear in list with "Invited" status
4. Each user follows the acceptance flow individually

---

## User Acceptance Flow

When a user accepts an invitation:

### Step 1: Click Invitation Link

User clicks the link in their invitation email.

---

### Step 2: Set Display Name

- Enter first and last name
- Example: "John Doe"
- This name appears in CostPilot UI and reports

---

### Step 3: Set Password

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter (A-Z)
- At least one lowercase letter (a-z)
- At least one number (0-9)
- At least one special character (!@#$%^&* etc.)

**Example Valid Passwords:**
- `Welcome123!`
- `CostPilot@2026`
- `SecurePass#1`

---

### Step 4: Accept and Login

1. Click **"Accept Invitation"**
2. Account is created
3. User is automatically logged in
4. Redirected to dashboard
5. User can start using CostPilot immediately

---

## Managing Invitations

### Viewing Invitation Status

1. Navigate to **Users** page
2. Look for users with **"Invited"** status
3. See when invitation was sent

---

### Re-sending Invitations

If user didn't receive email or invitation expired:

1. Find user in list with "Invited" status
2. Remove the user (if invitation expired)
3. Re-invite with same email
4. New invitation email is sent

**Default Expiry:** Invitations expire after 7 days

---

### Canceling Invitations

1. Find user in list with "Invited" status
2. Click on user name
3. Click **"Remove"**
4. Invitation is canceled
5. User can no longer accept

---

## After Users Join

### Step 1: Verify Access

1. Check user status is "Active"
2. Verify assigned roles are correct
3. Ensure user can log in successfully

---

### Step 2: Assign Additional Roles (If Needed)

1. Click on user name
2. Click **"Manage Roles"**
3. Click **"Assign Role"**
4. Select additional role(s)
5. Click **"Assign"**

**Example:** User has Viewer role, also assign Billing Admin for finance responsibilities.

---

### Step 3: Assign to Pools (If Applicable)

1. Navigate to **Pools** page
2. Edit relevant pools
3. Set user as pool owner
4. User will see costs for that pool

---

### Step 4: Communicate

Send a welcome message to new users:
- Explain CostPilot's purpose in your organization
- Point to relevant documentation
- Share any internal processes (e.g., how to request access changes)
- Offer to provide training or walkthrough

---

## Best Practices

### Invitation Process

1. **Invite with Correct Role**: Assign appropriate role from the start
2. **Use Bulk for Teams**: Bulk invite when onboarding teams
3. **Verify Emails**: Double-check email addresses before sending
4. **Follow Up**: Confirm users received and accepted invitations
5. **Document**: Keep track of who has access and why

### Role Assignment

1. **Start with Minimum**: Give Viewer role initially, promote as needed
2. **Follow Least Privilege**: Don't grant more access than required
3. **Review Quarterly**: Audit user roles and adjust
4. **Remove Promptly**: Remove access when users leave team/company

### Security

1. **Monitor Invitations**: Watch for unexpected invitations
2. **Limit Admin Roles**: Few users should have Organization Admin role
3. **Audit Activity**: Review user activity logs regularly
4. **Suspend Quickly**: Suspend users immediately if security concern

---

## Troubleshooting

### User Didn't Receive Invitation Email

**Check:**
1. Email address is correct (no typos)
2. Email not in spam/junk folder
3. Email provider is configured in CostPilot
4. Backend logs show email was sent

**Solutions:**
1. Re-send invitation (remove and re-invite)
2. Ask user to check spam folder
3. Verify SMTP/SES configuration
4. Check backend logs: `docker-compose logs -f backend`

---

### Invitation Link Expired

**Default Expiry:** 7 days

**Solution:**
1. Remove the expired invitation
2. Send new invitation
3. User receives fresh link with 7-day expiry

---

### User Can't Set Password

**Check:**
1. Password meets complexity requirements
2. Password and confirm password match
3. No extra spaces in password
4. Display name is filled in

**Solution:**
1. Review password requirements
2. Use a password manager to generate strong password
3. Ensure display name is not blank

---

### User Can't Log In After Accepting

**Check:**
1. User status is "Active" (not "Suspended")
2. User is using correct email and password
3. User is on login page (not trying to accept again)
4. Account is not locked (check failed login attempts)

**Solutions:**
1. Verify user status in Users page
2. Have user reset password if forgotten
3. If account locked, admin can unlock

---

### Too Many Invitations Sent

**If you accidentally bulk invited wrong emails:**

1. Remove all incorrect invitations
2. Check if any were accepted
3. If accepted, remove users from organization
4. Verify email provider didn't flag as spam source

---

## API Reference

### Invite Single User

```
POST /api/v1/organizations/{org_id}/users/invite
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "role_id": "engineer-role-uuid"
}
```

---

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

---

### Accept Invitation

```
POST /api/v1/invitations/{token}/accept
```

**Request Body:**
```json
{
  "display_name": "John Doe",
  "password": "SecurePass123!"
}
```

**Response:**
```json
{
  "user_id": "user-uuid",
  "email": "user@example.com",
  "access_token": "jwt-token-here",
  "organization_id": "org-uuid"
}
```

---

## Next Steps

After users join your organization:

- **[RBAC & ABAC](../rbac.md)** - Manage advanced role and policy assignments
- **[Pools](../pools.md)** - Assign users as pool owners
- **[Notifications](../notifications.md)** - Users can configure their notification preferences
- **[Users](../users.md)** - Ongoing user management

---

**Need Help?**
- Check [User Management Documentation](../users.md)
- Review [RBAC Documentation](../rbac.md) for role details
- Check backend logs: `docker-compose logs -f backend`
