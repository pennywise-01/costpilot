# Notifications

Configure and manage email notifications for cost events and alerts.

---

## Overview

The Notifications system provides email alerts and updates for important cost events, recommendations, and organizational changes. Users can customize their notification preferences per organization.

**URL**: Partial configuration in `/settings` (dedicated notification page may vary)

**Key Features:**
- 6 notification types with on/off toggles
- Per-user, per-organization preferences
- SMTP and AWS SES email providers
- Test notification sending
- Notification history tracking
- Configurable email templates

---

## Notification Types

| Type | Default | Description |
|------|---------|-------------|
| **Budget Alerts** | ON | Alerts when pools approach or exceed budget limits |
| **Recommendation Updates** | ON | Notifications when new recommendations are generated |
| **Daily Cost Summary** | OFF | Daily email with yesterday's costs |
| **Weekly Report** | ON | Weekly summary of costs and recommendations |
| **Anomaly Alerts** | ON | Alerts when cost anomalies are detected |
| **New User Joined** | OFF | Notification when new user joins organization |

---

## Configuring Notification Preferences

### Via UI

1. Navigate to **Settings** page
2. Click **"Notifications"** tab
3. Toggle each notification type ON or OFF
4. Changes are saved automatically

### Via API

```
PUT /api/v1/organizations/{org_id}/notifications/preferences
```

**Request Body:**
```json
{
  "budget_alerts": true,
  "recommendation_updates": true,
  "daily_cost_summary": false,
  "weekly_report": true,
  "anomaly_alerts": true,
  "new_user_joined": false
}
```

### Get Preferences

```
GET /api/v1/organizations/{org_id}/notifications/preferences
```

**Response:**
```json
{
  "user_id": "user-uuid",
  "org_id": "org-uuid",
  "budget_alerts": true,
  "recommendation_updates": true,
  "daily_cost_summary": false,
  "weekly_report": true,
  "anomaly_alerts": true,
  "new_user_joined": false
}
```

---

## Email Providers

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

**Supported SMTP Providers:**
- Gmail
- Outlook/Office 365
- SendGrid
- Mailgun
- Any SMTP server

---

### AWS SES

Configure in `.env`:

```env
EMAIL_PROVIDER=ses
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
SES_FROM_EMAIL=noreply@costpilot.io
```

**AWS SES Setup:**
1. Verify email address in SES console
2. Request production access (or use sandbox mode)
3. Create IAM user with SES permissions
4. Configure credentials in CostPilot

---

## Testing Notifications

Send a test notification to verify email configuration:

```
POST /api/v1/organizations/{org_id}/notifications/test
```

**Response:**
```json
{
  "success": true,
  "message": "Test email sent successfully"
}
```

**Check:**
1. Email inbox (and spam folder)
2. Backend logs for errors
3. SMTP/SES configuration if not received

---

## Notification History

View past notifications sent to you:

```
GET /api/v1/organizations/{org_id}/notifications/history?page=1&page_size=20
```

**Response:**
```json
{
  "notifications": [
    {
      "id": "notif-uuid",
      "type": "budget_alert",
      "subject": "Pool 'Production' exceeded 90% budget",
      "body": "Your pool 'Production' has spent $4,500 of $5,000 budget (90%)",
      "sent_at": "2026-04-09T10:00:00Z",
      "status": "sent"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

---

## Email Templates

Notifications use HTML email templates for consistent branding:

**Template Variables:**
- Organization name
- User name
- Notification type
- Message content
- Link to CostPilot
- Unsubscribe link

**Customization:**
- Templates can be customized in backend code
- Maintain consistent branding
- Ensure mobile responsiveness

---

## Notification Triggers

### Budget Alerts

**Triggered When:**
- Pool reaches 75% of budget (warning)
- Pool reaches 90% of budget (critical)
- Pool exceeds 100% of budget (over budget)

**Recipients:**
- Pool owner
- Organization Admins
- Users with Budget Alerts enabled

---

### Recommendation Updates

**Triggered When:**
- New recommendations are generated
- High-severity recommendations appear
- Significant savings opportunities identified

**Recipients:**
- Users with Recommendation Updates enabled

---

### Daily Cost Summary

**Triggered When:**
- Daily at configured time (e.g., 8 AM)
- Contains previous day's costs

**Recipients:**
- Users with Daily Cost Summary enabled

---

### Weekly Report

**Triggered When:**
- Weekly on configured day (e.g., Monday)
- Contains week's cost summary and trends

**Recipients:**
- Users with Weekly Report enabled

---

### Anomaly Alerts

**Triggered When:**
- Cost spike detected (>50% increase vs. average)
- Unexpected cost pattern
- New resource with high cost

**Recipients:**
- Organization Admins
- Users with Anomaly Alerts enabled

---

### New User Joined

**Triggered When:**
- User accepts invitation and joins organization

**Recipients:**
- Organization Admins
- Users with New User Joined enabled

---

## API Endpoints

### Get Preferences
```
GET /api/v1/organizations/{org_id}/notifications/preferences
```

### Update Preferences
```
PUT /api/v1/organizations/{org_id}/notifications/preferences
```

### Get History
```
GET /api/v1/organizations/{org_id}/notifications/history?page=1&page_size=20
```

### Send Test
```
POST /api/v1/organizations/{org_id}/notifications/test
```

---

## Best Practices

### Notification Management

1. **Enable Critical Alerts**: Always enable Budget and Anomaly alerts
2. **Avoid Overload**: Don't enable all types if email volume is high
3. **Review Preferences**: Update preferences quarterly
4. **Test Configuration**: Send test email after setup
5. **Monitor Delivery**: Check notification history for failures

### Email Configuration

1. **Use Transactional Email**: SES, SendGrid, or similar for reliability
2. **Verify Sender Email**: Ensure from-email is verified and trusted
3. **Set Up DKIM/SPF**: Improve email deliverability
4. **Monitor Bounces**: Track bounced emails and fix addresses
5. **Rate Limit**: Avoid sending too many emails in short time

---

## Troubleshooting

### Not Receiving Emails

**Check:**
1. Notification preferences are enabled
2. Email address is correct on user profile
3. Email provider (SMTP/SES) is configured correctly
4. Backend logs for email sending errors
5. Spam/junk folder

**Solutions:**
1. Send test notification to verify
2. Check SMTP/SES configuration
3. Verify email credentials
4. Review backend logs

### Emails Going to Spam

**Solutions:**
1. Verify sender domain (SPF, DKIM, DMARC)
2. Use reputable email service (SES, SendGrid)
3. Avoid spam trigger words in subject
4. Include unsubscribe link
5. Request users whitelist sender email

### Too Many Emails

**Solutions:**
1. Disable non-critical notification types
2. Reduce scheduler frequency (fewer recommendations = fewer emails)
3. Consolidate notifications (e.g., weekly instead of daily)
4. Set up email rules/filters on client side

---

## Next Steps

- **[Users](users.md)** - Manage user notification preferences
- **[Schedulers](schedulers.md)** - Configure data collection that triggers notifications
- **[Settings](settings.md)** - User settings and preferences

---

**Related Documentation:**
- [How to Configure Notifications](guides/configure-notifications.md)
- [API Reference](api-reference.md)
