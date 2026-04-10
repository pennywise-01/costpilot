# Troubleshooting Guide

Common issues and solutions for CostPilot.

---

## Application Won't Start

### Containers Fail to Start

**Check Status:**
```bash
docker-compose ps
```

**Check Logs:**
```bash
docker-compose logs -f
```

**Common Issues:**

**Port Already in Use:**
```bash
# Find process using port
netstat -tulpn | grep :8000  # Linux
lsof -i :8000  # macOS
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # Linux/macOS
taskkill /PID <PID> /F  # Windows
```

**Permission Denied:**
```bash
sudo chown -R $USER:$USER .
```

**Insufficient Resources:**
```bash
# Check Docker resources
docker system df
docker info

# Clean up
docker system prune -a
```

---

## Database Issues

### Migration Failures

**Check Migration Status:**
```bash
docker-compose exec backend alembic current
```

**Run Migrations:**
```bash
docker-compose exec backend alembic upgrade head
```

**Reset Database (WARNING: Deletes all data):**
```bash
docker-compose down -v
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

---

### Database Connection Errors

**Check PostgreSQL is Running:**
```bash
docker-compose ps db
```

**Test Connection:**
```bash
docker-compose exec db pg_isready -U costpilot
```

**Check Logs:**
```bash
docker-compose logs -f db
```

**Solution:**
- Ensure PostgreSQL container is healthy
- Verify `DATABASE_URL` in `.env` is correct
- Restart database: `docker-compose restart db`

---

## Redis Issues

### Redis Not Available

**Check Redis:**
```bash
docker-compose exec redis redis-cli ping
```

Should return: `PONG`

**Check Logs:**
```bash
docker-compose logs -f redis
```

**Restart Redis:**
```bash
docker-compose restart redis
```

---

## Authentication Issues

### Can't Log In

**Check:**
1. Email and password are correct
2. User account exists in database
3. User is not suspended
4. Account is not locked (too many failed attempts)

**Reset Password:**
- Use "Forgot Password" link (if configured)
- Or admin can suspend and re-invite user

**Unlock Account:**
```
POST /api/v1/auth/admin/unlock-user?user_id=<user-id>
```

---

### JWT Token Expired

**JWT Expiry:** 15 minutes

**Solution:**
- Log out and log back in
- Tokens refresh on login

---

### CSRF Token Errors

**Check:**
1. Browser cookies are enabled
2. Frontend URL matches CORS configuration
3. No ad blockers blocking cookies

**Solution:**
- Clear browser cache and cookies
- Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
- Verify `FRONTEND_URL` in `.env`

---

## Cloud Account Issues

### Credential Validation Fails

**AWS:**
- Check access key ID and secret are correct
- Verify IAM permissions are attached
- Ensure key is not expired or revoked

**Azure:**
- Verify subscription ID exists and is active
- Check service principal exists
- Ensure client secret is not expired
- Verify role assignments (Cost Management Reader, Reader)

**GCP:**
- Validate JSON format is correct
- Ensure service account exists
- Verify roles are granted (Billing Viewer, Compute Viewer)
- Check billing is enabled for project

---

### No Cost Data Appears

**Possible Causes:**
1. Cloud accounts recently connected (data collection in progress)
2. Scheduler not running
3. Cloud provider API errors
4. No actual costs incurred

**Solutions:**
1. Wait 15-30 minutes for initial collection
2. Check **Schedulers** page for expense collection status
3. Try manual refresh on account details page
4. Verify costs exist in cloud provider console
5. Check backend logs: `docker-compose logs -f backend`

---

### Rate Limiting Errors

**Azure Rate Limiting:**
- Azure Cost Management API has strict rate limits
- CostPilot implements automatic retry with exponential backoff

**Solutions:**
- Increase scheduler interval (e.g., from 60 to 120 minutes)
- Stagger scheduler times for multiple accounts
- Contact cloud provider to increase rate limits

---

## Dashboard Issues

### Dashboard Shows Zero Costs

**Check:**
1. Cloud accounts are connected and healthy
2. Schedulers have run
3. Date range is correct
4. Cache is not stale

**Solutions:**
1. Navigate to cloud account details and verify live data
2. Manually trigger expense scheduler
3. Clear dashboard cache
4. Check backend logs for errors

---

### Charts Not Rendering

**Check:**
1. Browser console for JavaScript errors
2. Data is actually present (check API responses)
3. Browser is up to date

**Solution:**
- Clear browser cache
- Try different browser
- Check browser console: `F12` > Console tab

---

## User Management Issues

### Invitation Email Not Received

**Check:**
1. Email address is correct
2. Email not in spam/junk folder
3. Email provider (SMTP/SES) is configured
4. Backend logs show email sent

**Solutions:**
1. Re-send invitation (remove and re-invite)
2. Check spam folder
3. Verify SMTP/SES configuration in `.env`
4. Check backend logs: `docker-compose logs -f backend`
5. Test email configuration:
   ```
   POST /api/v1/organizations/{org_id}/notifications/test
   ```

---

### Invitation Link Expired

**Default Expiry:** 7 days

**Solution:**
1. Remove expired invitation
2. Send new invitation

---

## Export Issues

### Export Job Fails

**Check:**
1. Date range is not too large
2. Filters are valid
3. Backend has sufficient memory
4. Cloud provider APIs are accessible

**Solutions:**
1. Reduce date range
2. Simplify filters
3. Retry job
4. Use streaming export for large datasets

---

### Download Link Expired

**Token Expiry:** 15 minutes

**Solution:**
1. Request new download URL
2. Download immediately

---

## Performance Issues

### Slow Page Loads

**Check:**
1. Browser network tab for slow API calls
2. Backend logs for slow queries
3. Database connection pool utilization
4. Redis cache hit rate

**Solutions:**
1. Increase cache TTLs
2. Optimize database queries
3. Increase connection pool size
4. Enable gzip compression

---

### High Memory Usage

**Check:**
```bash
docker stats
```

**Solutions:**
1. Reduce batch sizes in schedulers
2. Use streaming exports
3. Increase Docker memory limits
4. Restart containers to clear memory

---

## Scheduler Issues

### Scheduler Not Running

**Check:**
1. Scheduler is enabled
2. APScheduler service is running
3. Schedule configuration is correct
4. Backend logs for errors

**Solutions:**
1. Manually trigger scheduler
2. Restart backend: `docker-compose restart backend`
3. Check scheduler configuration
4. Review scheduler run logs

---

### Scheduler Runs But Collects No Data

**Check:**
1. Cloud accounts are connected and healthy
2. Cloud provider APIs return data
3. Date range has costs
4. Filters aren't too restrictive

**Solutions:**
1. Verify cloud accounts in provider consoles
2. Check scheduler run logs for errors
3. Manually fetch live data from cloud account details

---

## Notification Issues

### Emails Not Sending

**Check:**
1. Email provider configured in `.env`
2. SMTP/SES credentials are correct
3. From email is verified (for SES)
4. Backend logs for email errors

**Solutions:**
1. Verify email configuration
2. Test with test notification endpoint
3. Check spam folder
4. Review email provider dashboard (SES, SendGrid, etc.)

---

## Getting Help

### Collect Information

Before asking for help, collect:

1. **Error Messages**: Copy exact error messages
2. **Steps to Reproduce**: Document what you did
3. **Logs**: Backend and frontend logs
4. **Environment**: OS, Docker version, browser
5. **Configuration**: Relevant `.env` settings (redact secrets)

---

### Check Logs

**Backend Logs:**
```bash
docker-compose logs -f backend
```

**Frontend Logs:**
```bash
docker-compose logs -f frontend
```

**Database Logs:**
```bash
docker-compose logs -f db
```

**Last 100 Lines:**
```bash
docker-compose logs --tail=100 backend
```

---

### Health Checks

**Simple Health:**
```
http://localhost:8000/health
```

**Detailed Health:**
```
http://localhost:8000/health/detailed
```

**API Health:**
```
http://localhost:8000/api/v1/health
```

---

### Common Log Patterns

**Successful API Call:**
```
INFO: 200 GET /api/v1/...
```

**Authentication Error:**
```
401 Unauthorized: Invalid or expired token
```

**Database Error:**
```
ERROR: Database connection failed
```

**Cloud Provider Error:**
```
ERROR: AWS API error: InvalidAccessKeyId
```

---

## Emergency Procedures

### Restart All Services

```bash
docker-compose down
docker-compose up -d
```

### Reset Database (WARNING: Data Loss)

```bash
docker-compose down -v
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

### Clear Redis Cache

```bash
docker-compose exec redis redis-cli FLUSHALL
```

### Re-run All Migrations

```bash
docker-compose exec backend alembic downgrade base
docker-compose exec backend alembic upgrade head
```

---

## Additional Resources

- **[Overview](overview.md)** - Understanding CostPilot features
- **[Installation Guide](installation.md)** - Deployment instructions
- **[API Reference](api-reference.md)** - REST API documentation
- **[Security Audit Report](../AUDIT.md)** - Security findings
- **[GitHub Issues](https://github.com/your-org/costpilot/issues)** - Known issues and feature requests
