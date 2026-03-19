"""Email service using Resend API."""
import structlog
from app.config import settings

log = structlog.get_logger()


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """Send password reset email via Resend. Returns True on success."""
    if not settings.resend_api_key:
        log.warning("resend_not_configured")
        return False
    try:
        import resend
        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": f"Institutional Edge Brain <{settings.from_email}>",
            "to": [to_email],
            "subject": "Reset your password — Institutional Edge Brain",
            "html": f"""
<!DOCTYPE html>
<html>
<body style="background:#06060f;color:#e2e8f0;font-family:monospace;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#0d0d1a;border:1px solid #1a1a2e;border-radius:12px;padding:32px;">
    <div style="color:#2563ff;font-size:18px;font-weight:700;letter-spacing:2px;margin-bottom:8px;">
      INSTITUTIONAL EDGE BRAIN
    </div>
    <div style="color:#64748b;font-size:12px;margin-bottom:32px;">Password Reset Request</div>
    <p style="color:#e2e8f0;font-size:14px;line-height:1.6;">
      We received a request to reset your password. Click the button below to set a new one.
      This link expires in <strong style="color:#f59e0b;">15 minutes</strong>.
    </p>
    <a href="{reset_url}"
       style="display:inline-block;background:#2563ff;color:#fff;text-decoration:none;
              padding:12px 28px;border-radius:8px;font-size:13px;font-weight:600;
              letter-spacing:1px;margin:24px 0;">
      RESET PASSWORD
    </a>
    <p style="color:#475569;font-size:11px;margin-top:24px;line-height:1.6;">
      If you didn't request this, you can safely ignore this email.<br>
      This link will expire in 15 minutes for your security.
    </p>
    <hr style="border:none;border-top:1px solid #1a1a2e;margin:24px 0;">
    <div style="color:#334155;font-size:10px;">
      Institutional Edge Brain · quantneuraledge.com
    </div>
  </div>
</body>
</html>
""",
        })
        log.info("reset_email_sent", to=to_email)
        return True
    except Exception as e:
        log.error("reset_email_failed", error=str(e))
        return False


def send_magic_link_email(to_email: str, magic_url: str) -> bool:
    """Send magic link login email via Resend. Returns True on success."""
    if not settings.resend_api_key:
        log.warning("resend_not_configured")
        return False
    try:
        import resend
        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": f"Institutional Edge Brain <{settings.from_email}>",
            "to": [to_email],
            "subject": "Your login link — Institutional Edge Brain",
            "html": f"""
<!DOCTYPE html>
<html>
<body style="background:#06060f;color:#e2e8f0;font-family:monospace;padding:40px;">
  <div style="max-width:480px;margin:0 auto;background:#0d0d1a;border:1px solid #1a1a2e;border-radius:12px;padding:32px;">
    <div style="color:#2563ff;font-size:18px;font-weight:700;letter-spacing:2px;margin-bottom:8px;">
      INSTITUTIONAL EDGE BRAIN
    </div>
    <div style="color:#64748b;font-size:12px;margin-bottom:32px;">Passwordless Login</div>
    <p style="color:#e2e8f0;font-size:14px;line-height:1.6;">
      Click the button below to log in instantly. No password needed.<br>
      This link expires in <strong style="color:#f59e0b;">15 minutes</strong> and can only be used once.
    </p>
    <a href="{magic_url}"
       style="display:inline-block;background:#2563ff;color:#fff;text-decoration:none;
              padding:12px 28px;border-radius:8px;font-size:13px;font-weight:600;
              letter-spacing:1px;margin:24px 0;">
      LOG IN NOW
    </a>
    <p style="color:#475569;font-size:11px;margin-top:24px;line-height:1.6;">
      If you didn't request this, you can safely ignore this email.<br>
      This link will expire in 15 minutes for your security.
    </p>
    <hr style="border:none;border-top:1px solid #1a1a2e;margin:24px 0;">
    <div style="color:#334155;font-size:10px;">
      Institutional Edge Brain · quantneuraledge.com
    </div>
  </div>
</body>
</html>
""",
        })
        log.info("magic_link_sent", to=to_email)
        return True
    except Exception as e:
        log.error("magic_link_failed", error=str(e))
        return False
