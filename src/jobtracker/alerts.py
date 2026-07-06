"""Daily alert formatting + delivery (email / telegram / twilio / slack)."""
from __future__ import annotations
import os, smtplib, logging
from collections import defaultdict
from email.mime.text import MIMEText
import requests

log = logging.getLogger("jobtracker.alerts")

def format_alert(jobs, cfg) -> str:
    if not jobs:
        return "Quant job tracker: no new postings today." if cfg["alerts"]["zero_update"] == "short" else ""
    lines = [f"Quant job tracker — {len(jobs)} new posting(s)\n"]
    if len(jobs) > cfg["alerts"]["max_full_listings"]:
        by_cat = defaultdict(list)
        for j in jobs:
            by_cat[j["role_category"] or "other"].append(j)
        lines.append("Too many to list in full. Summary by category:\n")
        for cat, js in sorted(by_cat.items()):
            lines.append(f"== {cat.upper()} ({len(js)}) ==")
            for j in js:
                lines.append(f"- {j['company']}: {j['title']} ({j['location']}) {j['application_url']}")
            lines.append("")
    else:
        for j in jobs:
            lines += [f"• {j['company']} — {j['title']}",
                      f"  {j['location'] or 'location n/a'} | {j['role_category']} | via {j['source']}",
                      f"  why: {j['match_reason']}",
                      f"  apply: {j['application_url']}", ""]
    return "\n".join(lines)

def send(text: str, cfg: dict) -> bool:
    if not text:
        return True
    ch = cfg["alerts"]["channel"]
    if cfg["alerts"].get("preview_only") or ch == "none":
        print("---- ALERT PREVIEW ----\n" + text)
        return True
    try:
        if ch == "telegram":
            token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
            for chunk in _chunks(text, 3900):  # telegram 4096-char limit
                requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              json={"chat_id": chat, "text": chunk}, timeout=20).raise_for_status()
        elif ch == "email":
            msg = MIMEText(text)
            msg["Subject"] = text.splitlines()[0][:120]
            msg["From"], msg["To"] = os.environ["SMTP_USER"], os.environ["ALERT_EMAIL_TO"]
            with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587))) as s:
                s.starttls(); s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]); s.send_message(msg)
        elif ch == "sms":
            sid, tok = os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]
            requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                          auth=(sid, tok),
                          data={"From": os.environ["TWILIO_FROM_NUMBER"], "To": os.environ["ALERT_PHONE_TO"],
                                "Body": text[:1500]}, timeout=20).raise_for_status()
        elif ch == "slack":
            requests.post(os.environ["SLACK_WEBHOOK_URL"], json={"text": text}, timeout=20).raise_for_status()
        else:
            log.error("unknown alert channel %s", ch); return False
        return True
    except Exception as e:
        log.error("alert send failed: %s", e)
        return False

def _chunks(s: str, n: int):
    for i in range(0, len(s), n):
        yield s[i:i + n]
