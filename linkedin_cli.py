#!/usr/bin/env python3
# Watermark: Living_Sin (intricos777-dot) + AI agents (Hermes, Lia, opencode) - collaborative work
"""
linkedin-cli — LinkedIn messaging CLI with API + browser fallback.

SAFETY FIRST:
- All messages require human confirmation before sending
- Rate limited: max 1 message per 5 minutes, max 20/day
- Uses OAuth2 for API (no password storage)
- Browser mode opens pre-filled page, user clicks send
- Integrates with outreach lead pipeline

Usage:
    linkedin-cli --help
    linkedin-cli send --to "Company Name" --subject "..." --body "..."
    linkedin-cli send --draft-id REV-22943a6c
    linkedin-cli queue
    linkedin-cli queue --process
    linkedin-cli status
    linkedin-cli auth
"""

import argparse
import json
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG_DIR = Path.home() / ".config" / "linkedin-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"
STATE_FILE = CONFIG_DIR / "state.json"
LOG_FILE = CONFIG_DIR / "linkedin-cli.log"

# LinkedIn API endpoints
LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
LINKEDIN_OAUTH_BASE = "https://www.linkedin.com/oauth/v2"

# Safety limits
MIN_INTERVAL_SECONDS = 300  # 5 minutes between messages
DAILY_LIMIT = 20
CONFIRMATION_REQUIRED = True


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_banner():
    print(f"""
{Colors.CYAN}{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║                    linkedin.CLI v1.0                         ║
║          LinkedIn Messaging — Safe & Compliant              ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
""")


def print_warning():
    print(f"""{Colors.YELLOW}{Colors.BOLD}⚠️  LINKEDIN TERMS OF SERVICE WARNING{Colors.RESET}
{Colors.YELLOW}Automated messaging may violate LinkedIn's User Agreement.
This tool requires human confirmation before sending any message.
Use at your own risk. The author assumes no liability for account actions.
{Colors.RESET}""")
    print()


def log(message: str):
    """Log message to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now().isoformat()} | {message}\n")


def load_config() -> dict:
    """Load configuration."""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config: dict):
    """Save configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    CONFIG_FILE.chmod(0o600)  # Only owner can read


def load_state() -> dict:
    """Load state (rate limiting, etc.)."""
    if not STATE_FILE.exists():
        return {"sent_today": [], "last_sent": None, "total_sent": 0}
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state: dict):
    """Save state."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ============================================================================
# SAFETY CHECKS
# ============================================================================

class SafetyChecker:
    """Enforces rate limits and safety rules."""
    
    def __init__(self):
        self.state = load_state()
        self._clean_old_entries()
    
    def _clean_old_entries(self):
        """Remove entries older than 24 hours."""
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        self.state["sent_today"] = [
            t for t in self.state.get("sent_today", [])
            if t > cutoff
        ]
    
    def can_send(self) -> tuple[bool, str]:
        """Check if sending is allowed."""
        self._clean_old_entries()
        
        # Check daily limit
        if len(self.state.get("sent_today", [])) >= DAILY_LIMIT:
            return False, f"Daily limit reached ({DAILY_LIMIT} messages). Try again tomorrow."
        
        # Check interval
        if self.state.get("last_sent"):
            last = datetime.fromisoformat(self.state["last_sent"])
            elapsed = (datetime.now() - last).total_seconds()
            if elapsed < MIN_INTERVAL_SECONDS:
                remaining = int(MIN_INTERVAL_SECONDS - elapsed)
                mins, secs = divmod(remaining, 60)
                return False, f"Rate limit: wait {mins}m {secs}s before next message."
        
        return True, "OK"
    
    def record_send(self):
        """Record a sent message."""
        now = datetime.now().isoformat()
        self.state.setdefault("sent_today", []).append(now)
        self.state["last_sent"] = now
        self.state["total_sent"] = self.state.get("total_sent", 0) + 1
        save_state(self.state)
    
    def status(self) -> str:
        """Get current status."""
        self._clean_old_entries()
        sent = len(self.state.get("sent_today", []))
        remaining = DAILY_LIMIT - sent
        
        last = "Never"
        if self.state.get("last_sent"):
            last = self.state["last_sent"][:19]
        
        return (
            f"Sent today: {sent}/{DAILY_LIMIT}\n"
            f"Remaining today: {remaining}\n"
            f"Last sent: {last}\n"
            f"Total sent (all time): {self.state.get('total_sent', 0)}"
        )


# ============================================================================
# BROWSER MODE (Fallback)
# ============================================================================

class BrowserSender:
    """Opens pre-filled LinkedIn message page in browser."""
    
    @staticmethod
    def send(to_name: str, subject: str, body: str) -> bool:
        """
        Open LinkedIn message compose in browser.
        User must manually select recipient and click send.
        """
        import urllib.parse
        
        # Encode for URL
        encoded_subject = urllib.parse.quote(subject)
        encoded_body = urllib.parse.quote(body)
        
        # LinkedIn message URL (compose new message)
        url = (
            f"https://www.linkedin.com/messaging/compose/"
            f"?subject={encoded_subject}"
            f"&body={encoded_body}"
        )
        
        print(f"\n{Colors.CYAN}Opening LinkedIn in browser...{Colors.RESET}")
        print(f"{Colors.BLUE}→ {url}{Colors.RESET}\n")
        
        # Try to open in default browser
        try:
            webbrowser.open(url, new=2)  # new=2 opens in new tab
            log(f"Opened browser for: {to_name}")
            return True
        except Exception as e:
            print(f"{Colors.RED}Failed to open browser: {e}{Colors.RESET}")
            print(f"{Colors.YELLOW}Open manually: {url}{Colors.RESET}")
            return False


# ============================================================================
# API Mode (OAuth2 — 1st connections only)
# ============================================================================

class APISender:
    """Uses LinkedIn API for 1st-degree connections."""
    
    def __init__(self):
        self.config = load_config()
        self.access_token = self.config.get("access_token", "")
    
    def is_configured(self) -> bool:
        """Check if API is configured."""
        return bool(self.access_token)
    
    def authenticate(self):
        """Guide user through OAuth2 setup."""
        print(f"{Colors.CYAN}{Colors.BOLD}LinkedIn API Authentication{Colors.RESET}\n")
        print("To use API mode, you need:")
        print("1. A LinkedIn Developer account")
        print("2. An app with 'Share on LinkedIn' and 'Sign In with LinkedIn using OpenID Connect' products")
        print("3. An OAuth2 access token\n")
        
        print("Setup steps:")
        print("1. Go to https://developer.linkedin.com/")
        print("2. Create an app (or use existing)")
        print("3. Under 'Products', add:")
        print("   - Share on LinkedIn")
        print("   - Sign In with LinkedIn using OpenID Connect")
        print("4. Under 'Auth', get your access token")
        print("5. Run: linkedin-cli auth --token YOUR_TOKEN\n")
        
        token = input("Enter access token (or press Enter to skip): ").strip()
        if token:
            self.config["access_token"] = token
            save_config(self.config)
            print(f"{Colors.GREEN}✅ Token saved{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}Skipped. Browser mode will be used.{Colors.RESET}")
    
    def send_message(self, recipient_urn: str, subject: str, body: str) -> bool:
        """Send message via API (requires 1st-degree connection)."""
        import urllib.request
        import urllib.error
        
        if not self.is_configured():
            print(f"{Colors.YELLOW}API not configured. Use browser mode.{Colors.RESET}")
            return False
        
        # LinkedIn URN format: urn:li:person:XXXXX
        if not recipient_urn.startswith("urn:li:person:"):
            recipient_urn = f"urn:li:person:{recipient_urn}"
        
        url = f"{LINKEDIN_API_BASE}/messages"
        
        payload = {
            "recipients": [recipient_urn],
            "subject": subject,
            "body": body,
            "messageType": "MEMBER_TO_MEMBER"
        }
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                log(f"API send OK: {recipient_urn}")
                return True
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            log(f"API send FAILED: {e.code} — {body}")
            print(f"{Colors.RED}API Error: {e.code}{Colors.RESET}")
            if e.code == 403:
                print("Recipient may not be a 1st-degree connection.")
                print("Falling back to browser mode...")
                return BrowserSender.send("Unknown", subject, body)
            return False
        except Exception as e:
            log(f"API send ERROR: {e}")
            print(f"{Colors.RED}Error: {e}{Colors.RESET}")
            return False


# ============================================================================
# CLI INTERFACE
# ============================================================================

def cmd_status(args):
    """Show current status."""
    print_banner()
    safety = SafetyChecker()
    print(f"{Colors.BOLD}Status:{Colors.RESET}\n{safety.status()}")
    
    # API status
    api = APISender()
    if api.is_configured():
        print(f"{Colors.GREEN}API: Configured{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}API: Not configured (browser mode only){Colors.RESET}")
    
    # Queue status
    queue_file = Path.home() / "Projects" / "other" / "linkedin-outreach" / "data" / "review_queue.json"
    if queue_file.exists():
        with open(queue_file) as f:
            queue = json.load(f)
        approved = sum(1 for q in queue if q.get("status") == "approved")
        pending = sum(1 for q in queue if q.get("status") == "pending")
        print(f"Queue: {approved} approved, {pending} pending review")


def cmd_auth(args):
    """Set up authentication."""
    print_banner()
    api = APISender()
    api.authenticate()


def cmd_queue(args):
    """Show or process the message queue."""
    queue_file = Path.home() / "Projects" / "other" / "linkedin-outreach" / "data" / "review_queue.json"
    if not queue_file.exists():
        print(f"{Colors.RED}No queue found.{Colors.RESET}")
        return
    
    with open(queue_file) as f:
        queue = json.load(f)
    
    if args.process:
        # Process approved messages
        approved = [q for q in queue if q.get("status") == "approved"]
        if not approved:
            print(f"{Colors.YELLOW}No approved messages to process.{Colors.RESET}")
            return
        
        print(f"{Colors.CYAN}Processing {len(approved)} approved messages...{Colors.RESET}\n")
        
        safety = SafetyChecker()
        api = APISender()
        
        for item in approved:
            can_send, reason = safety.can_send()
            if not can_send:
                print(f"{Colors.YELLOW}Skipped: {item['company_name']} — {reason}{Colors.RESET}")
                continue
            
            print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
            print(f"  {item['company_name']} ({item['industry']})")
            print(f"  Score: {item['total_score']}")
            print(f"  Subject: {item['outreach_subject']}")
            print(f"{'='*60}")
            print(f"\n{item['outreach_message']}\n")
            
            # Confirmation
            if CONFIRMATION_REQUIRED:
                response = input(f"{Colors.YELLOW}Send this message? [y/N]: {Colors.RESET}").strip().lower()
                if response != 'y':
                    print(f"{Colors.RED}Skipped.{Colors.RESET}")
                    continue
            
            # Send via browser (API only works for 1st connections)
            success = BrowserSender.send(
                item["company_name"],
                item["outreach_subject"],
                item["outreach_message"]
            )
            
            if success:
                safety.record_send()
                print(f"{Colors.GREEN}✅ Sent!{Colors.RESET}")
                
                # Update status in queue
                item["status"] = "sent"
                item["sent_at"] = datetime.now().isoformat()
            else:
                print(f"{Colors.RED}❌ Failed{Colors.RESET}")
            
            # Save updated queue
            with open(queue_file, "w") as f:
                json.dump(queue, f, indent=2)
            
            # Wait between messages
            time.sleep(2)
    else:
        # Show queue
        print(f"{Colors.BOLD}Message Queue:{Colors.RESET}\n")
        for item in queue:
            status_color = {
                "pending": Colors.YELLOW,
                "approved": Colors.GREEN,
                "rejected": Colors.RED,
                "sent": Colors.BLUE
            }.get(item.get("status", "pending"), Colors.RESET)
            
            print(f"  [{status_color}{item.get('status', 'pending').upper()}{Colors.RESET}] "
                  f"{item.get('company_name', 'Unknown')} "
                  f"(Score: {item.get('total_score', '?')}) "
                  f"— {item.get('outreach_subject', 'No subject')[:50]}")


def cmd_send(args):
    """Send a single message."""
    print_banner()
    print_warning()
    
    # Safety check
    safety = SafetyChecker()
    can_send, reason = safety.can_send()
    if not can_send:
        print(f"{Colors.RED}Cannot send: {reason}{Colors.RESET}")
        return
    
    # Get message details
    if args.draft_id:
        # Load from queue
        queue_file = Path.home() / "Projects" / "other" / "linkedin-outreach" / "data" / "review_queue.json"
        if not queue_file.exists():
            print(f"{Colors.RED}No queue found.{Colors.RESET}")
            return
        
        with open(queue_file) as f:
            queue = json.load(f)
        
        draft = next((q for q in queue if q.get("queue_id") == args.draft_id), None)
        if not draft:
            print(f"{Colors.RED}Draft {args.draft_id} not found.{Colors.RESET}")
            return
        
        to_name = draft["company_name"]
        subject = draft["outreach_subject"]
        body = draft["outreach_message"]
    else:
        to_name = args.to or "Unknown"
        subject = args.subject or ""
        body = args.body or ""
    
    if not subject or not body:
        print(f"{Colors.RED}Subject and body are required.{Colors.RESET}")
        return
    
    # Preview
    print(f"{Colors.BOLD}Message Preview:{Colors.RESET}")
    print(f"{'─'*60}")
    print(f"To: {to_name}")
    print(f"Subject: {subject}")
    print(f"{'─'*60}")
    print(body)
    print(f"{'─'*60}\n")
    
    # Confirm
    response = input(f"{Colors.YELLOW}Send this message? [y/N]: {Colors.RESET}").strip().lower()
    if response != 'y':
        print(f"{Colors.RED}Aborted.{Colors.RESET}")
        return
    
    # Send
    api = APISender()
    if api.is_configured() and args.use_api:
        success = api.send_message(args.recipient or "", subject, body)
    else:
        success = BrowserSender.send(to_name, subject, body)
    
    if success:
        safety.record_send()
        print(f"{Colors.GREEN}✅ Message sent!{Colors.RESET}")
    else:
        print(f"{Colors.RED}❌ Failed to send.{Colors.RESET}")


def main():
    print_banner()
    
    parser = argparse.ArgumentParser(
        description="linkedin.CLI — Safe LinkedIn messaging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  linkedin-cli status                    Show status and queue
  linkedin-cli queue                     Show pending messages
  linkedin-cli queue --process           Process approved messages
  linkedin-cli auth                      Set up API authentication
  linkedin-cli send --to "Company" --subject "Hi" --body "Hello"
  linkedin-cli send --draft-id REV-XXX   Send approved draft
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # status
    subparsers.add_parser("status", help="Show status")
    
    # auth
    subparsers.add_parser("auth", help="Set up authentication")
    
    # queue
    queue_parser = subparsers.add_parser("queue", help="Manage message queue")
    queue_parser.add_argument("--process", action="store_true", help="Process approved messages")
    
    # send
    send_parser = subparsers.add_parser("send", help="Send a message")
    send_parser.add_argument("--to", help="Recipient name")
    send_parser.add_argument("--subject", help="Message subject")
    send_parser.add_argument("--body", help="Message body")
    send_parser.add_argument("--draft-id", help="Draft ID from queue")
    send_parser.add_argument("--recipient", help="LinkedIn URN for API mode")
    send_parser.add_argument("--use-api", action="store_true", help="Use API mode")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    log(f"Command: {args.command}")
    
    if args.command == "status":
        cmd_status(args)
    elif args.command == "auth":
        cmd_auth(args)
    elif args.command == "queue":
        cmd_queue(args)
    elif args.command == "send":
        cmd_send(args)


if __name__ == "__main__":
    main()
