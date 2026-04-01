"""Gmail CLI commands."""

import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

import click
from rich.console import Console
from rich.table import Table

from gws_cli.auth import build_service

console = Console()


def _get_service():
    return build_service("gmail", "v1")


@click.group()
def gmail():
    """Gmail operations."""


@gmail.command("inbox")
@click.option("-n", "--limit", default=10, help="Max messages to show.")
@click.option("-q", "--query", default="in:inbox", help="Gmail search query.")
def inbox(limit, query):
    """List recent messages."""
    service = _get_service()
    results = service.users().messages().list(
        userId="me", q=query, maxResults=limit
    ).execute()
    messages = results.get("messages", [])

    if not messages:
        click.echo("No messages found.")
        return

    table = Table(title="Messages")
    table.add_column("From", style="cyan", max_width=30)
    table.add_column("Subject", style="white", max_width=50)
    table.add_column("Date", style="yellow", max_width=12)
    table.add_column("ID", style="dim")

    for msg_ref in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        table.add_row(
            headers.get("From", "")[:30],
            headers.get("Subject", "(no subject)")[:50],
            headers.get("Date", "")[:12],
            msg_ref["id"],
        )
    console.print(table)


@gmail.command("read")
@click.argument("message_id")
def read_message(message_id):
    """Read a message by ID."""
    service = _get_service()
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

    click.echo(f"From:    {headers.get('From', '?')}")
    click.echo(f"To:      {headers.get('To', '?')}")
    click.echo(f"Date:    {headers.get('Date', '?')}")
    click.echo(f"Subject: {headers.get('Subject', '(no subject)')}")
    click.echo("─" * 60)

    body = _extract_body(msg["payload"])
    click.echo(body or "(no text body)")


def _extract_body(payload):
    """Recursively extract text/plain body from message payload."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result
    return None


@gmail.command("send")
@click.option("--to", required=True, help="Recipient email address.")
@click.option("--subject", required=True, help="Email subject.")
@click.option("--body", required=True, help="Email body text.")
@click.option("--attach", multiple=True, type=click.Path(exists=True), help="File attachments.")
def send(to, subject, body, attach):
    """Send an email."""
    service = _get_service()

    if attach:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body))
        for path in attach:
            part = MIMEBase("application", "octet-stream")
            with open(path, "rb") as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(path)}")
            msg.attach(part)
    else:
        msg = MIMEText(body)

    msg["to"] = to
    msg["subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    click.echo(f"Sent! Message ID: {result['id']}")


@gmail.command("labels")
def labels():
    """List Gmail labels."""
    service = _get_service()
    results = service.users().labels().list(userId="me").execute()
    labels_list = results.get("labels", [])

    table = Table(title="Labels")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("ID", style="dim")

    for label in sorted(labels_list, key=lambda l: l["name"]):
        table.add_row(label["name"], label.get("type", ""), label["id"])
    console.print(table)


@gmail.command("search")
@click.argument("query")
@click.option("-n", "--limit", default=10, help="Max results.")
def search(query, limit):
    """Search messages with Gmail query syntax."""
    service = _get_service()
    results = service.users().messages().list(
        userId="me", q=query, maxResults=limit
    ).execute()
    messages = results.get("messages", [])

    if not messages:
        click.echo("No messages found.")
        return

    table = Table(title=f"Search: {query}")
    table.add_column("From", style="cyan", max_width=30)
    table.add_column("Subject", style="white", max_width=50)
    table.add_column("Date", style="yellow")
    table.add_column("ID", style="dim")

    for msg_ref in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        table.add_row(
            headers.get("From", "")[:30],
            headers.get("Subject", "(no subject)")[:50],
            headers.get("Date", "")[:12],
            msg_ref["id"],
        )
    console.print(table)
