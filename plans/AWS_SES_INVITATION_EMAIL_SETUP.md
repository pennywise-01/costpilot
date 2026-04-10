# AWS SES Integration for Invitation Emails

## Overview

This document describes how to configure AWS Simple Email Service (SES) for sending user invitation emails in CostPilot. The invitation email system is already fully functional — it just needs an email delivery provider. Currently it uses SMTP (defaulting to `localhost:1025` which doesn't exist), and this plan adds AWS SES as an alternative provider.

---

## Current Architecture

### How Invitation Emails Work Today

1. **Admin invites user** via frontend modal (`UserInviteModal.tsx`)
2. **Backend creates** a `UserInvitation` record with a cryptographically random token (`secrets.token_urlsafe(48)`)
3. **Backend sends email** via `_send_invitation_email()` in `backend/app/user_management/router.py`
4. **Email delivered** via `aiosmtplib` (SMTP library) → `send_email()` in `backend/app/notifications/email_service.py`
5. **User clicks link** → goes to `/accept-invitation/{token}` → creates account → auto-login

### Current Problem

- SMTP defaults to `localhost:1025` (MailHog port)
- No SMTP server configured in `docker-compose.yml`
- Email sending **fails silently** (`except Exception: pass` in router)
- Invitation is created regardless of email success

### Email Templates

All templates are inline HTML strings (no separate template files):

| Template | Location | Purpose |
|---|---|---|
| `_send_invitation_email()` | `backend/app/user_management/router.py` | User invitations |
| `render_budget_alert` | `backend/app/notifications/email_service.py` | Budget threshold alerts |
| `render_recommendation_updates` | `backend/app/notifications/email_service.py` | New savings recommendations |
| `render_daily_cost_summary` | `backend/app/notifications/email_service.py` | Daily cost digest |
| `render_weekly_report` | `backend/app/notifications/email_service.py` | Weekly cost report |
| `render_anomaly_alert` | `backend/app/notifications/email_service.py` | Spending anomaly detection |
| `render_new_user_joined` | `backend/app/notifications/email_service.py` | New user notification |

---

## Part 1: AWS SES Console Setup

### Step 1: Verify Sender Identity

You must verify the email address or domain that will send emails.

#### Option A: Verify Individual Email (Quick, for testing)

1. Go to **AWS Console** → **Amazon SES** → **Verified identities**
2. Click **Create identity**
3. Select **Email address**
4. Enter the sender email (e.g., `noreply@costpilot.io`)
5. AWS sends a verification email to that address
6. Click the verification link in the email
7. Status changes to **Verified**

#### Option B: Verify Domain (Recommended for production)

1. Go to **AWS Console** → **Amazon SES** → **Verified identities**
2. Click **Create identity**
3. Select **Domain**
4. Enter your domain (e.g., `costpilot.io`)
5. AWS provides DNS records (TXT, optionally MX/CNAME)
6. Add these records to your DNS provider (Route 53, Cloudflare, etc.)
7. Wait for DNS propagation (minutes to 48 hours)
8. Status changes to **Verified**

**Why domain verification is better:**
- Verify once, send from any address @yourdomain
- Required for production use
- Enables DKIM signing for better deliverability
- Required for higher sending limits

---

### Step 2: Request SES Production Access

By default, SES starts in **Sandbox Mode** with these restrictions:

| Restriction | Sandbox Mode | Production Mode |
|---|---|---|
| Recipients | Only verified emails | Any email address |
| Sending limit | 200 emails/24h | Up to 50,000+/day |
| Rate limit | 1 email/second | 14+ emails/second |

#### To Request Production Access:

1. Go to **AWS Console** → **Amazon SES** → **Account dashboard**
2. Click **Request production access** (or **Edit your account details**)
3. Fill out the form:
   - **Use case description**: "CostPilot is a cloud cost optimization platform. We use SES to send user invitation emails, budget alerts, and cost reports to organization members. Emails are transactional and only sent to users who have been explicitly invited by administrators."
   - **Types of emails**: Transactional
   - **Frequency**: Low volume (< 1,000/month initially)
   - **How you handle bounces/complaints**: "We use SNS notifications to track bounces and complaints. Failed emails are logged and administrators are notified."
4. Submit the request
5. Approval typically takes **24-48 hours**

**You can test in sandbox mode while waiting** — just verify recipient email addresses too.

---

### Step 3: Create IAM User for SES

Create a dedicated IAM user with least-privilege SES permissions.

#### Create the IAM User:

1. Go to **AWS Console** → **IAM** → **Users** → **Create user**
2. User name: `costpilot-ses-sender`
3. **Do NOT** check "Provide user access to the AWS Management Console"
4. Click **Next** → **Create user**

#### Attach Policy:

1. Select the newly created user
2. Go to **Permissions** tab → **Add permissions** → **Create inline policy**
3. Switch to **JSON** tab
4. Paste this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

5. Click **Next** → Name the policy `CostPilotSESSendPolicy` → **Create policy**

**Why only these permissions:**
- `ses:SendEmail` — Required for sending simple emails
- `ses:SendRawEmail` — Required for HTML emails with attachments/multipart (which we use)
- No other SES permissions needed (no template management, no configuration set management)

---

### Step 4: Generate IAM Credentials

1. Go to **IAM** → **Users** → `costpilot-ses-sender`
2. Go to **Security credentials** tab
3. Under **Access keys**, click **Create access key**
4. Select **Other** as use case
5. Click **Next** → **Create access key**
6. **Save these immediately** (you can't see the secret key again):
   - **Access Key ID**: `AKIA...` (looks like this)
   - **Secret Access Key**: `...` (long string)
7. Download the `.csv` file or copy to password manager

---

### Step 5: Note Your AWS Region

SES is region-specific. You verified your identity in a specific region — make sure to use the **same region** in your code.

Common regions:
- `us-east-1` — US East (N. Virginia)
- `us-west-2` — US West (Oregon)
- `eu-west-1` — Europe (Ireland)
- `ap-south-1` — Asia Pacific (Mumbai)

**Check your region**: In the AWS Console, look at the top-right corner of the page. It shows your current region.

---

## Part 2: Code Changes

### File 1: `backend/app/config.py`

**Purpose**: Add SES configuration settings to the Pydantic Settings class.

**Location**: Add after the existing SMTP settings (around line 52).

**Changes**:

```python
# Add these new fields to the Settings class:

# Email Provider Selection
EMAIL_PROVIDER: str = "smtp"  # "smtp" or "ses"

# AWS SES Configuration
AWS_REGION: str = "us-east-1"  # AWS region for SES (must match where identity is verified)
AWS_ACCESS_KEY_ID: str = ""  # IAM user access key for SES
AWS_SECRET_ACCESS_KEY: str = ""  # IAM user secret access key for SES
SES_FROM_EMAIL: str = "noreply@costpilot.io"  # Verified SES sender email
```

**Why these fields:**
- `EMAIL_PROVIDER` — Allows switching between SMTP and SES without code changes
- `AWS_REGION` — SES is region-specific; must match where you verified your identity
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — IAM credentials for authentication
- `SES_FROM_EMAIL` — The verified email address that appears as the sender

---

### File 2: `backend/pyproject.toml`

**Purpose**: Add the AWS SDK for Python (boto3) as a dependency.

**Check first**: Run `pip list | grep boto3` to see if it's already installed.

**If not installed**, add to the `dependencies` list:

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "boto3>=1.34.0",  # AWS SDK for SES email sending
]
```

**Why boto3:**
- Official AWS SDK for Python
- Provides `boto3.client("ses")` for sending emails via SES
- Handles authentication, retries, and error handling automatically

---

### File 3: `backend/app/notifications/email_service.py`

**Purpose**: Add SES email sending function and refactor `send_email()` to support both providers.

**Changes**:

#### Add new function `send_email_ses()`:

```python
import boto3
from botocore.exceptions import ClientError

async def send_email_ses(to: str, subject: str, html_body: str) -> None:
    """Send an email via AWS SES. Raises on failure."""
    ses_client = boto3.client(
        "ses",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    
    try:
        response = ses_client.send_email(
            Source=settings.SES_FROM_EMAIL,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
            },
        )
        logger.info(
            "SES email sent to %s: %s (MessageId: %s)",
            to,
            subject,
            response.get("MessageId"),
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error("SES email failed: %s - %s", error_code, error_message)
        raise
```

**Why this code:**
- `boto3.client("ses")` — Creates SES client with credentials
- `send_email()` — SES API call for sending HTML emails
- `Source` — Verified sender email address
- `Destination` — Recipient email address
- `Message` — Subject and HTML body with UTF-8 charset
- Logs `MessageId` for tracking/delivery confirmation
- Catches `ClientError` and logs detailed error info

#### Refactor existing `send_email()`:

**Current code (line ~228):**
```python
async def send_email(to: str, subject: str, html_body: str) -> None:
    """Send an email via SMTP. Raises on failure."""
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        start_tls=settings.SMTP_TLS,
        username=settings.SMTP_USER or None,
        password=settings.SMTP_PASSWORD or None,
    )
    logger.info("Email sent to %s: %s", to, subject)
```

**Replace with:**
```python
async def send_email(to: str, subject: str, html_body: str) -> None:
    """Send an email via configured provider (SMTP or SES). Raises on failure."""
    if settings.EMAIL_PROVIDER == "ses":
        await send_email_ses(to, subject, html_body)
    else:
        await send_email_smtp(to, subject, html_body)


async def send_email_smtp(to: str, subject: str, html_body: str) -> None:
    """Send an email via SMTP. Raises on failure."""
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        start_tls=settings.SMTP_TLS,
        username=settings.SMTP_USER or None,
        password=settings.SMTP_PASSWORD or None,
    )
    logger.info("SMTP email sent to %s: %s", to, subject)
```

**Why this refactor:**
- `send_email()` becomes a router that delegates to the configured provider
- `send_email_smtp()` extracted to keep SMTP logic separate
- Easy to add more providers later (e.g., SendGrid, Postmark)
- No changes needed to calling code (`_send_invitation_email()` in router.py)

---

### File 4: `docker-compose.yml`

**Purpose**: Pass SES configuration to the backend container.

**Changes**: Add SES environment variables to the `backend` service.

```yaml
services:
  backend:
    # ... existing configuration ...
    environment:
      # ... existing environment variables ...
      
      # Email Configuration
      - EMAIL_PROVIDER=ses
      - AWS_REGION=us-east-1  # Change to your SES region
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - SES_FROM_EMAIL=noreply@costpilot.io
```

**Why these env vars:**
- `EMAIL_PROVIDER=ses` — Switches from SMTP to SES
- `${AWS_ACCESS_KEY_ID}` — Reads from host's `.env` file (not hardcoded)
- All other vars configure the SES client

---

### File 5: `.env` (Create if doesn't exist)

**Purpose**: Store SES credentials locally (never commit to Git).

**Location**: `backend/.env` or project root `.env`

**Contents**:

```env
# ============================================
# AWS SES Configuration
# ============================================

# Email provider: "smtp" or "ses"
EMAIL_PROVIDER=ses

# AWS region where SES identity is verified
AWS_REGION=us-east-1

# IAM user credentials for SES
AWS_ACCESS_KEY_ID=AKIA_YOUR_ACCESS_KEY_HERE
AWS_SECRET_ACCESS_KEY=YourSecretAccessKeyHere

# Verified sender email address in SES
SES_FROM_EMAIL=noreply@costpilot.io
```

**Security notes:**
- **NEVER commit this file** — ensure it's in `.gitignore`
- Use AWS Secrets Manager or SSM Parameter Store in production
- Rotate access keys regularly (every 90 days recommended)

---

### File 6: `.gitignore` (Verify)

**Purpose**: Ensure `.env` files are not committed to Git.

**Check that these lines exist:**
```
.env
.env.*
!.env.example
```

**Create `.env.example`** (safe to commit) for documentation:
```env
# AWS SES Configuration (copy to .env and fill in values)
EMAIL_PROVIDER=ses
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
SES_FROM_EMAIL=noreply@costpilot.io
```

---

## Part 3: Testing

### Phase 1: Sandbox Mode Testing (Before Production Access)

#### Prerequisites
1. Complete Part 1 steps (verify sender identity, create IAM user)
2. **Verify your personal email** in SES Console (since sandbox mode only allows verified recipients)

#### Local Testing (Without Docker)

```bash
# Navigate to backend directory
cd backend

# Set environment variables (PowerShell on Windows)
$env:EMAIL_PROVIDER="ses"
$env:AWS_REGION="us-east-1"
$env:AWS_ACCESS_KEY_ID="AKIA_YOUR_KEY_HERE"
$env:AWS_SECRET_ACCESS_KEY="YourSecretKeyHere"
$env:SES_FROM_EMAIL="your-verified-email@example.com"

# Install dependencies (if boto3 not installed)
pip install -e .

# Run backend server
uvicorn app.main:app --reload

# Backend starts on http://localhost:8000
```

#### Docker Testing

```bash
# Ensure .env file exists with SES credentials
# Then start services
docker-compose up -d

# Check backend logs for startup
docker-compose logs -f backend

# Look for successful connection on startup
```

#### Test Invitation Email Flow

1. **Login as admin** to CostPilot frontend
2. Navigate to **Settings** → **Users** → Click **Invite User**
3. Enter:
   - Email: Your verified email (sandbox mode only)
   - Role: Select a role (e.g., Member)
   - Department: (optional)
   - Job title: (optional)
4. Click **Send Invitation**
5. **Check backend logs** for confirmation:
   ```
   INFO: SES email sent to you@example.com: Invitation to join... (MessageId: 010101...)
   ```
6. **Check your email inbox** (and spam folder)
7. You should receive an email with:
   - Subject: `Invitation to join {Organization} on CostPilot`
   - Body: Organization name, your email, "Accept Invitation" button
   - Footer: Invitation expiry date

#### Test Acceptance Flow

1. Click **Accept Invitation** button in email
2. Should redirect to: `http://localhost:5173/accept-invitation/{token}`
3. Page shows:
   - Organization name
   - Your email address
   - Role you'll be assigned
   - Inviter's name
   - Expiration date
4. Fill in:
   - Display name
   - Password
   - Confirm password
5. Click **Accept & Create Account**
6. Should redirect to login page
7. Login with your new credentials
8. Verify you can access the organization dashboard

---

### Phase 2: Production Mode Testing (After Production Access Approval)

#### Test with Unverified Recipients

1. Invite a colleague's email address (not verified in SES)
2. Verify they receive the invitation email
3. Verify they can accept and create an account
4. Test with multiple email providers (Gmail, Outlook, corporate email)

#### Test Edge Cases

| Test Case | Expected Result |
|---|---|
| Invite invalid email format | Frontend validation rejects |
| Invite already registered user | Backend returns error |
| Invite expired token (7+ days old) | Backend returns 400, shows expired message |
| SES credentials incorrect | Backend logs error, invitation still created |
| SES quota exceeded | Backend logs error, retry after quota reset |
| Send to verified email in sandbox | Email delivered successfully |

---

### Phase 3: Monitoring & Logging

#### Check SES Sending Statistics

1. Go to **AWS Console** → **Amazon SES** → **Account dashboard**
2. View:
   - Emails sent (last 24 hours)
   - Bounce rate
   - Complaint rate
   - Reputation score (must stay above 90%)

#### Set Up CloudWatch Logs (Optional but Recommended)

1. Go to **AWS Console** → **CloudWatch** → **Logs**
2. Create a log group for SES: `/aws/ses/costpilot`
3. Configure SES to publish delivery notifications to CloudWatch
4. Set up alarms for:
   - Bounce rate > 5%
   - Complaint rate > 0.1%
   - Sending quota utilization > 80%

#### Add SES Configuration Set (Optional)

1. Go to **Amazon SES** → **Configuration sets** → **Create configuration set**
2. Name: `costpilot-invitations`
3. Add event destination:
   - Type: CloudWatch Logs
   - Events: Send, Reject, Bounce, Complaint
4. Update `send_email_ses()` to include configuration set:

```python
response = ses_client.send_email(
    Source=settings.SES_FROM_EMAIL,
    Destination={"ToAddresses": [to]},
    Message={...},
    ConfigurationSetName="costpilot-invitations",  # Add this line
)
```

---

## Part 4: Optional Enhancements

### Enhancement 1: SES Email Templates

Instead of sending raw HTML in each API call, store templates in SES:

#### Create Template in SES Console

1. Go to **Amazon SES** → **Email templates** → **Create template**
2. Template name: `costpilot-invitation`
3. Subject: `Invitation to join {{organization_name}} on CostPilot`
4. HTML body:
```html
<h2>You've been invited to join {{organization_name}}</h2>
<p>Hi {{invitee_name}},</p>
<p>You have been invited to join <strong>{{organization_name}}</strong> on CostPilot.</p>
<p><a href="{{accept_url}}" class="btn">Accept Invitation</a></p>
<p style="color:#999;font-size:13px;">
  Invitation expires on {{expires_at}}.<br>
  If you didn't expect this invitation, ignore this email.
</p>
```

#### Update Code to Use Template

```python
response = ses_client.send_templated_email(
    Source=settings.SES_FROM_EMAIL,
    Destination={"ToAddresses": [to]},
    Template="costpilot-invitation",
    TemplateData=json.dumps({
        "organization_name": org_name,
        "invitee_name": invitee_name,
        "accept_url": accept_url,
        "expires_at": invitation.expires_at.strftime("%B %d, %Y"),
    }),
)
```

**Benefits:**
- Templates managed in AWS Console (not code)
- Easy to update without deploying code
- Supports personalization with variables
- Better for branding consistency

---

### Enhancement 2: Add INVITATION to NotificationType Enum

**File**: `backend/app/shared/enums.py`

**Current state**: The `NotificationType` enum has 6 types but no `INVITATION`:

```python
class NotificationType(str, Enum):
    BUDGET_ALERTS = "budget_alerts"
    RECOMMENDATION_UPDATES = "recommendation_updates"
    DAILY_COST_SUMMARY = "daily_cost_summary"
    WEEKLY_REPORT = "weekly_report"
    ANOMALY_ALERTS = "anomaly_alerts"
    NEW_USER_JOINED = "new_user_joined"
```

**Add**:
```python
class NotificationType(str, Enum):
    # ... existing types ...
    INVITATION = "invitation"  # Add this
```

**Why:**
- Allows invitation emails to go through the notification preference system
- Users can opt in/out of invitation notifications
- Consistent with other notification types
- Enables notification history logging

---

### Enhancement 3: Improve Error Handling for Email Failures

**File**: `backend/app/user_management/router.py`

**Current code (line ~250)**:
```python
try:
    await _send_invitation_email(db, org_id, current_user.id, data.email, result)
except Exception:
    pass  # Do not fail the invitation if email sending fails
```

**Better approach**:
```python
try:
    await _send_invitation_email(db, org_id, current_user.id, data.email, result)
except Exception as e:
    logger.warning(
        "Failed to send invitation email to %s: %s. Invitation still created.",
        data.email,
        e,
    )
    # Optionally: add a flag to the response indicating email failed
    # response["email_sent"] = False
```

**Why:**
- Logs failures for debugging
- Administrators can check logs to see which emails failed
- Can add UI indicator to re-send invitation email

---

### Enhancement 4: Email Verification for Invited Users

**File**: `backend/app/user_management/service.py`

**Current state**: Users created via invitation have `verified=False` (from SEC-05 fix), but there's no email verification flow yet.

**Implementation**:
1. After account creation, send verification email with token
2. User clicks verification link
3. Update `User.verified = True`
4. Restrict certain features until email verified

**Why:**
- Ensures email address is valid and owned by user
- Prevents fake account creation
- Required for production email sending (reduces bounce rate)

---

## Cost Estimate

| Item | Cost | Notes |
|---|---|---|
| SES emails (from EC2) | Free (first 62,000/month) | If backend runs on EC2 |
| SES emails (from Docker/local) | $0.10 per 1,000 emails | If sending from non-EC2 |
| IAM user | Free | No charge for IAM users |
| CloudWatch logs | Free (within free tier) | 5 GB ingestion/month free |
| **Estimated monthly cost** | **~$0** | For invitation emails (~10-100/month) |

**Example calculation:**
- 100 invitations/month × $0.10/1,000 = **$0.01/month**
- Even at 10,000 invitations/month = **$1.00/month**

---

## Troubleshooting

### Common Issues

#### 1. "Email address not verified" Error

**Problem**: Trying to send to an unverified email in sandbox mode.

**Solution**:
- Verify the recipient email in SES Console, OR
- Request production access

#### 2. "Access denied" or "Invalid credentials" Error

**Problem**: IAM access key or secret key is incorrect.

**Solution**:
- Double-check credentials in `.env` file
- Ensure IAM user has `ses:SendEmail` and `ses:SendRawEmail` permissions
- Regenerate access keys if necessary

#### 3. "SES sending quota exceeded" Error

**Problem**: You've hit the daily sending limit.

**Solution**:
- Check quota in SES Console → Account dashboard
- Request quota increase if needed
- Implement retry logic with exponential backoff

#### 4. Email Goes to Spam

**Problem**: SES emails landing in spam folder.

**Solution**:
- Verify your domain (not just email)
- Enable DKIM signing in SES Console
- Set up SPF, DKIM, DMARC DNS records
- Maintain low bounce/complaint rates

#### 5. "Region mismatch" Error

**Problem**: Code uses different region than where identity was verified.

**Solution**:
- Check `AWS_REGION` in `.env` matches SES Console region
- Identities are region-specific — verify in the correct region

#### 6. Email Not Received

**Problem**: Invitation email not arriving.

**Debug steps**:
1. Check backend logs for `SES email sent` message
2. Check SES Console → Sending statistics
3. Check CloudWatch logs (if configured)
4. Check recipient's spam folder
5. Check if email address is on SES suppression list

---

## Migration Checklist

### Before Starting

- [ ] AWS account created and accessible
- [ ] Domain or email address ready for verification
- [ ] DNS access (if verifying domain)

### AWS Console Setup

- [ ] Verified sender identity (email or domain) in SES
- [ ] Requested production access (if needed)
- [ ] Created IAM user `costpilot-ses-sender`
- [ ] Attached inline policy with `ses:SendEmail` and `ses:SendRawEmail`
- [ ] Generated access key ID and secret access key
- [ ] Noted AWS region

### Code Changes

- [ ] Added SES config fields to `backend/app/config.py`
- [ ] Added `boto3` to `backend/pyproject.toml` (if not present)
- [ ] Added `send_email_ses()` to `backend/app/notifications/email_service.py`
- [ ] Refactored `send_email()` to route between SMTP/SES
- [ ] Updated `docker-compose.yml` with SES environment variables
- [ ] Created `.env` file with SES credentials
- [ ] Verified `.env` is in `.gitignore`
- [ ] Created `.env.example` for documentation

### Testing

- [ ] Installed dependencies (`pip install boto3`)
- [ ] Started backend server
- [ ] Sent test invitation email in sandbox mode
- [ ] Received invitation email in inbox
- [ ] Clicked acceptance link
- [ ] Created account and logged in
- [ ] Verified email content (subject, body, links)
- [ ] Tested with production access (unverified recipients)
- [ ] Tested edge cases (invalid email, expired token, etc.)

### Monitoring

- [ ] Checked SES sending statistics in AWS Console
- [ ] Set up CloudWatch logs (optional)
- [ ] Created SES configuration set (optional)
- [ ] Set up bounce/complaint alarms (optional)

### Production Readiness

- [ ] Domain verified in SES
- [ ] DKIM signing enabled
- [ ] SPF/DKIM/DMARC DNS records configured
- [ ] Production access approved by AWS
- [ ] Error handling improved (no silent failures)
- [ ] Email verification flow implemented (optional)
- [ ] Credentials moved to AWS Secrets Manager (production)

---

## Security Considerations

### Credential Management

| Environment | Recommendation |
|---|---|
| Local development | `.env` file (in `.gitignore`) |
| Docker Compose | `.env` file + environment variables |
| Production (EC2/ECS) | IAM instance profile (no credentials needed) |
| Production (Lambda) | Lambda execution role |
| Production (Kubernetes) | AWS Secrets Manager + IAM roles for service accounts |

### Best Practices

1. **Never commit credentials** — Always use `.env` files or secret managers
2. **Rotate access keys** — Every 90 days minimum
3. **Least privilege IAM** — Only `ses:SendEmail` and `ses:SendRawEmail`
4. **Monitor usage** — Set up CloudWatch alarms for unusual sending patterns
5. **Encrypt in transit** — SES uses HTTPS by default (no extra config needed)
6. **Log all sends** — Keep `MessageId` in application logs for auditing

---

## References

- [AWS SES Documentation](https://docs.aws.amazon.com/ses/)
- [SES Sandbox Limits](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html)
- [boto3 SES Client](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ses.html)
- [Email Deliverability Best Practices](https://docs.aws.amazon.com/ses/latest/dg/best-practices.html)
- [SES Pricing](https://aws.amazon.com/ses/pricing/)

---

## Appendix: Current Known Issues

These are documented in `BACKLOG.md` and `AUDIT.md`:

| Issue | Status | Priority |
|---|---|---|
| No SMTP server in docker-compose | Known | Low (SES replaces need) |
| Email errors silently swallowed | Known | Medium (Enhancement 3 addresses this) |
| Invitation email bypasses notification preferences | Known | Low |
| `INVITATION` missing from `NotificationType` enum | Known | Low (Enhancement 2 addresses this) |
| No email verification for invited users | Known | Medium (Enhancement 4 addresses this) |

---

**Last updated**: April 8, 2026  
**Author**: CostPilot Development Team  
**Status**: Ready for implementation
