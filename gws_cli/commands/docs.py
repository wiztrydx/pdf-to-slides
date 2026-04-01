"""Google Docs CLI commands."""

import click
from rich.console import Console
from rich.table import Table

from gws_cli.auth import build_service

console = Console()


def _get_service():
    return build_service("docs", "v1")


@click.group()
def docs():
    """Google Docs operations."""


@docs.command("create")
@click.argument("title")
def create(title):
    """Create a new Google Doc."""
    service = _get_service()
    body = {"title": title}
    doc = service.documents().create(body=body).execute()
    click.echo(f"Created: {doc['title']}")
    click.echo(f"ID: {doc['documentId']}")
    click.echo(f"URL: https://docs.google.com/document/d/{doc['documentId']}")


@docs.command("info")
@click.argument("document_id")
def info(document_id):
    """Show document info."""
    service = _get_service()
    doc = service.documents().get(documentId=document_id).execute()

    click.echo(f"Title: {doc.get('title', 'Untitled')}")
    click.echo(f"ID: {doc['documentId']}")
    click.echo(f"URL: https://docs.google.com/document/d/{doc['documentId']}")

    body = doc.get("body", {}).get("content", [])
    char_count = sum(
        len(elem.get("paragraph", {}).get("elements", [{}])[0].get("textRun", {}).get("content", ""))
        for elem in body
        if "paragraph" in elem
    )
    click.echo(f"Approximate characters: {char_count}")


@docs.command("read")
@click.argument("document_id")
def read_doc(document_id):
    """Read the text content of a document."""
    service = _get_service()
    doc = service.documents().get(documentId=document_id).execute()

    click.echo(f"# {doc.get('title', 'Untitled')}")
    click.echo("─" * 60)

    for elem in doc.get("body", {}).get("content", []):
        if "paragraph" in elem:
            for run in elem["paragraph"].get("elements", []):
                text = run.get("textRun", {}).get("content", "")
                if text:
                    click.echo(text, nl=False)


@docs.command("append")
@click.argument("document_id")
@click.argument("text")
def append(document_id, text):
    """Append text to the end of a document."""
    service = _get_service()
    doc = service.documents().get(documentId=document_id).execute()

    body_content = doc.get("body", {}).get("content", [])
    end_index = body_content[-1]["endIndex"] - 1 if body_content else 1

    requests = [
        {"insertText": {"location": {"index": end_index}, "text": text + "\n"}}
    ]
    service.documents().batchUpdate(
        documentId=document_id, body={"requests": requests}
    ).execute()
    click.echo("Text appended.")


@docs.command("replace")
@click.argument("document_id")
@click.argument("find_text")
@click.argument("replace_text")
def replace(document_id, find_text, replace_text):
    """Find and replace text in a document."""
    service = _get_service()
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": find_text, "matchCase": True},
                "replaceText": replace_text,
            }
        }
    ]
    result = service.documents().batchUpdate(
        documentId=document_id, body={"requests": requests}
    ).execute()
    count = result.get("replies", [{}])[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
    click.echo(f"Replaced {count} occurrence(s).")


@docs.command("export")
@click.argument("document_id")
@click.option("-o", "--output", default=None, help="Output PDF path.")
def export(document_id, output):
    """Export a document as PDF."""
    from googleapiclient.http import MediaIoBaseDownload
    import io

    drive_service = build_service("drive", "v3")
    out_path = output or f"{document_id}.pdf"

    request = drive_service.files().export_media(
        fileId=document_id, mimeType="application/pdf"
    )
    with open(out_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
    click.echo(f"Exported to: {out_path}")
