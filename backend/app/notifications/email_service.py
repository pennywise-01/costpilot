import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib

from app.config import settings
from app.shared.enums import NotificationType

logger = logging.getLogger(__name__)

_BASE_STYLE = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }
  .container { max-width: 600px; margin: 0 auto; background: #ffffff; }
  .header { background: #1677ff; color: #ffffff; padding: 24px 32px; }
  .header h1 { margin: 0; font-size: 20px; font-weight: 600; }
  .body { padding: 32px; color: #333333; line-height: 1.6; }
  .body h2 { margin-top: 0; font-size: 18px; color: #1a1a1a; }
  .metric { background: #f0f5ff; border-left: 4px solid #1677ff; padding: 16px; margin: 16px 0; border-radius: 4px; }
  .metric .label { font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }
  .metric .value { font-size: 24px; font-weight: 700; color: #1a1a1a; }
  .alert { background: #fff2e8; border-left: 4px solid #fa8c16; padding: 16px; margin: 16px 0; border-radius: 4px; }
  .alert-critical { background: #fff1f0; border-left-color: #ff4d4f; }
  table { width: 100%; border-collapse: collapse; margin: 16px 0; }
  th { background: #fafafa; text-align: left; padding: 10px 12px; font-size: 12px; text-transform: uppercase; color: #666; border-bottom: 2px solid #e8e8e8; }
  td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
  .btn { display: inline-block; background: #1677ff; color: #ffffff; padding: 10px 24px; border-radius: 6px; text-decoration: none; font-weight: 500; margin-top: 16px; }
  .footer { padding: 24px 32px; background: #fafafa; color: #999; font-size: 12px; text-align: center; border-top: 1px solid #f0f0f0; }
</style>
"""


def _wrap_html(title: str, body_content: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{title}</title>{_BASE_STYLE}</head>
<body>
<div class="container">
  <div class="header"><h1>CostPilot</h1></div>
  <div class="body">{body_content}</div>
  <div class="footer">
    You received this email because of your notification preferences in CostPilot.<br>
    Manage your preferences in Settings &gt; Notifications.
  </div>
</div>
</body>
</html>"""


def render_budget_alert(data: dict) -> tuple[str, str]:
    budget_name = data.get("budget_name", "Unnamed Budget")
    current_spend = data.get("current_spend", 0)
    budget_limit = data.get("budget_limit", 0)
    pct = int((current_spend / budget_limit * 100) if budget_limit else 0)
    top_drivers = data.get("top_drivers", [])
    dashboard_url = data.get("dashboard_url", "#")

    drivers_rows = "".join(
        f"<tr><td>{d['name']}</td><td>${d['cost']:,.2f}</td></tr>"
        for d in top_drivers[:5]
    )

    subject = f"[CostPilot] Budget \"{budget_name}\" is at {pct}% (${current_spend:,.2f} / ${budget_limit:,.2f})"
    body = f"""
    <h2>Budget Alert</h2>
    <p>Your budget <strong>{budget_name}</strong> has reached <strong>{pct}%</strong> of its limit.</p>
    <div class="metric{'  alert-critical' if pct >= 100 else ''}">
      <div class="label">Current Spend / Budget Limit</div>
      <div class="value">${current_spend:,.2f} / ${budget_limit:,.2f}</div>
    </div>
    {'<h3>Top Cost Drivers</h3><table><tr><th>Service</th><th>Cost</th></tr>' + drivers_rows + '</table>' if drivers_rows else ''}
    <a href="{dashboard_url}" class="btn">View Budget Details</a>
    """
    return subject, _wrap_html(subject, body)


def render_recommendation_updates(data: dict) -> tuple[str, str]:
    count = data.get("count", 0)
    total_savings = data.get("total_savings", 0)
    recommendations = data.get("recommendations", [])
    dashboard_url = data.get("dashboard_url", "#")

    rec_rows = "".join(
        f"<tr><td>{r['resource']}</td><td>{r['type']}</td><td>${r['savings']:,.2f}/mo</td></tr>"
        for r in recommendations[:10]
    )

    subject = f"[CostPilot] {count} new savings recommendation{'s' if count != 1 else ''} — potential ${total_savings:,.2f}/mo"
    body = f"""
    <h2>New Cost-Saving Recommendations</h2>
    <div class="metric">
      <div class="label">Potential Monthly Savings</div>
      <div class="value">${total_savings:,.2f}/mo</div>
    </div>
    <p>{count} new recommendation{'s have' if count != 1 else ' has'} been identified.</p>
    {'<table><tr><th>Resource</th><th>Type</th><th>Est. Savings</th></tr>' + rec_rows + '</table>' if rec_rows else ''}
    <a href="{dashboard_url}" class="btn">View Recommendations</a>
    """
    return subject, _wrap_html(subject, body)


def render_daily_cost_summary(data: dict) -> tuple[str, str]:
    date_str = data.get("date", "Today")
    total_spend = data.get("total_spend", 0)
    avg_spend = data.get("avg_spend", 0)
    delta_pct = int(((total_spend - avg_spend) / avg_spend * 100) if avg_spend else 0)
    sign = "+" if delta_pct >= 0 else ""
    by_provider = data.get("by_provider", [])
    top_services = data.get("top_services", [])
    dashboard_url = data.get("dashboard_url", "#")

    provider_rows = "".join(
        f"<tr><td>{p['name']}</td><td>${p['cost']:,.2f}</td></tr>"
        for p in by_provider[:5]
    )
    service_rows = "".join(
        f"<tr><td>{s['name']}</td><td>${s['cost']:,.2f}</td></tr>"
        for s in top_services[:5]
    )

    subject = f"[CostPilot] Daily Cost Summary — {date_str}: ${total_spend:,.2f} ({sign}{delta_pct}% vs avg)"
    body = f"""
    <h2>Daily Cost Summary — {date_str}</h2>
    <div class="metric">
      <div class="label">Today's Spend</div>
      <div class="value">${total_spend:,.2f} <span style="font-size:14px;color:{'#ff4d4f' if delta_pct > 10 else '#52c41a'}">{sign}{delta_pct}% vs 7-day avg</span></div>
    </div>
    {'<h3>Spend by Provider</h3><table><tr><th>Provider</th><th>Cost</th></tr>' + provider_rows + '</table>' if provider_rows else ''}
    {'<h3>Top Services</h3><table><tr><th>Service</th><th>Cost</th></tr>' + service_rows + '</table>' if service_rows else ''}
    <a href="{dashboard_url}" class="btn">View Dashboard</a>
    """
    return subject, _wrap_html(subject, body)


def render_weekly_report(data: dict) -> tuple[str, str]:
    week_range = data.get("week_range", "This Week")
    total_spend = data.get("total_spend", 0)
    prev_spend = data.get("prev_week_spend", 0)
    delta_pct = int(((total_spend - prev_spend) / prev_spend * 100) if prev_spend else 0)
    arrow = "\u2191" if delta_pct > 0 else "\u2193" if delta_pct < 0 else "\u2192"
    top_movers = data.get("top_movers", [])
    open_recs = data.get("open_recommendations", 0)
    potential_savings = data.get("potential_savings", 0)
    dashboard_url = data.get("dashboard_url", "#")

    mover_rows = "".join(
        f"<tr><td>{m['name']}</td><td>${m['cost']:,.2f}</td><td style='color:{'#ff4d4f' if m.get('change', 0) > 0 else '#52c41a'}'>{'+' if m.get('change', 0) > 0 else ''}{m.get('change', 0):.1f}%</td></tr>"
        for m in top_movers[:5]
    )

    subject = f"[CostPilot] Weekly Digest — {week_range}: ${total_spend:,.2f} ({arrow}{abs(delta_pct)}% WoW)"
    body = f"""
    <h2>Weekly Cost Report — {week_range}</h2>
    <div class="metric">
      <div class="label">Total Spend This Week</div>
      <div class="value">${total_spend:,.2f} <span style="font-size:14px;color:{'#ff4d4f' if delta_pct > 0 else '#52c41a'}">{arrow}{abs(delta_pct)}% vs last week</span></div>
    </div>
    {'<h3>Top Cost Movers</h3><table><tr><th>Service</th><th>Cost</th><th>Change</th></tr>' + mover_rows + '</table>' if mover_rows else ''}
    <div class="alert">
      <strong>{open_recs}</strong> open recommendation{'s' if open_recs != 1 else ''} with potential savings of <strong>${potential_savings:,.2f}/mo</strong>
    </div>
    <a href="{dashboard_url}" class="btn">View Full Report</a>
    """
    return subject, _wrap_html(subject, body)


def render_anomaly_alert(data: dict) -> tuple[str, str]:
    service = data.get("service", "Unknown Service")
    region = data.get("region", "unknown")
    expected_spend = data.get("expected_spend", 0)
    actual_spend = data.get("actual_spend", 0)
    spike_pct = int(((actual_spend - expected_spend) / expected_spend * 100) if expected_spend else 0)
    started_at = data.get("started_at", "Recently")
    possible_causes = data.get("possible_causes", [])
    dashboard_url = data.get("dashboard_url", "#")

    causes_html = "".join(f"<li>{c}</li>" for c in possible_causes[:5])

    subject = f"[CostPilot] Anomaly: {service} spend spiked {spike_pct}% in {region}"
    body = f"""
    <h2>Spending Anomaly Detected</h2>
    <div class="alert alert-critical">
      <strong>{service}</strong> in <strong>{region}</strong> shows unusual spending.
    </div>
    <div class="metric">
      <div class="label">Expected vs Actual</div>
      <div class="value">${expected_spend:,.2f} &rarr; ${actual_spend:,.2f} <span style="font-size:14px;color:#ff4d4f">+{spike_pct}%</span></div>
    </div>
    <p><strong>Anomaly started:</strong> {started_at}</p>
    {'<h3>Possible Causes</h3><ul>' + causes_html + '</ul>' if causes_html else ''}
    <a href="{dashboard_url}" class="btn">Investigate Anomaly</a>
    """
    return subject, _wrap_html(subject, body)


def render_new_user_joined(data: dict) -> tuple[str, str]:
    user_name = data.get("user_name", "Unknown User")
    user_email = data.get("user_email", "")
    role = data.get("role", "Member")
    invited_by = data.get("invited_by")
    dashboard_url = data.get("dashboard_url", "#")

    subject = f"[CostPilot] New user joined: {user_email}"
    body = f"""
    <h2>New User Joined Your Organization</h2>
    <table>
      <tr><td style="font-weight:600;width:120px">Name</td><td>{user_name}</td></tr>
      <tr><td style="font-weight:600">Email</td><td>{user_email}</td></tr>
      <tr><td style="font-weight:600">Role</td><td>{role}</td></tr>
      {'<tr><td style="font-weight:600">Invited by</td><td>' + invited_by + '</td></tr>' if invited_by else ''}
    </table>
    <a href="{dashboard_url}" class="btn">Manage Users</a>
    """
    return subject, _wrap_html(subject, body)


RENDERERS: dict[NotificationType, callable] = {
    NotificationType.BUDGET_ALERTS: render_budget_alert,
    NotificationType.RECOMMENDATION_UPDATES: render_recommendation_updates,
    NotificationType.DAILY_COST_SUMMARY: render_daily_cost_summary,
    NotificationType.WEEKLY_REPORT: render_weekly_report,
    NotificationType.ANOMALY_ALERTS: render_anomaly_alert,
    NotificationType.NEW_USER_JOINED: render_new_user_joined,
}


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
