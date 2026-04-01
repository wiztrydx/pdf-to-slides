"""Google Slides CLI commands."""

import json

import click
from rich.console import Console
from rich.table import Table

from gws_cli.auth import build_service

console = Console()


def _get_service():
    return build_service("slides", "v1")


@click.group()
def slides():
    """Google Slides operations."""


@slides.command("create")
@click.argument("title")
def create(title):
    """Create a new presentation."""
    service = _get_service()
    body = {"title": title}
    pres = service.presentations().create(body=body).execute()
    click.echo(f"Created: {pres['title']}")
    click.echo(f"ID: {pres['presentationId']}")
    click.echo(f"URL: https://docs.google.com/presentation/d/{pres['presentationId']}")


@slides.command("info")
@click.argument("presentation_id")
def info(presentation_id):
    """Show presentation info and slide list."""
    service = _get_service()
    pres = service.presentations().get(presentationId=presentation_id).execute()

    click.echo(f"Title: {pres.get('title', 'Untitled')}")
    click.echo(f"Slides: {len(pres.get('slides', []))}")
    click.echo(f"Size: {pres.get('pageSize', {}).get('width', {}).get('magnitude', '?')} x "
               f"{pres.get('pageSize', {}).get('height', {}).get('magnitude', '?')}")
    click.echo()

    table = Table(title="Slides")
    table.add_column("#", style="cyan")
    table.add_column("Slide ID", style="dim")
    table.add_column("Layout", style="green")

    for i, slide in enumerate(pres.get("slides", []), 1):
        layout = slide.get("slideProperties", {}).get("layoutObjectId", "—")
        table.add_row(str(i), slide["objectId"], layout)
    console.print(table)


@slides.command("add-slide")
@click.argument("presentation_id")
@click.option("--layout", default="BLANK", help="Predefined layout (e.g. TITLE, BLANK, TITLE_AND_BODY).")
@click.option("--index", default=None, type=int, help="Insert position (0-based).")
def add_slide(presentation_id, layout, index):
    """Add a new slide to a presentation."""
    service = _get_service()
    request = {
        "createSlide": {
            "slideLayoutReference": {"predefinedLayout": layout},
        }
    }
    if index is not None:
        request["createSlide"]["insertionIndex"] = index

    result = service.presentations().batchUpdate(
        presentationId=presentation_id, body={"requests": [request]}
    ).execute()
    slide_id = result["replies"][0]["createSlide"]["objectId"]
    click.echo(f"Added slide: {slide_id}")


@slides.command("add-text")
@click.argument("presentation_id")
@click.argument("slide_index", type=int)
@click.argument("text")
@click.option("--shape-id", default=None, help="Target shape ID (auto-detects first text box if omitted).")
def add_text(presentation_id, slide_index, text, shape_id):
    """Insert text into a slide's text box."""
    service = _get_service()
    pres = service.presentations().get(presentationId=presentation_id).execute()
    slides_list = pres.get("slides", [])

    if slide_index < 0 or slide_index >= len(slides_list):
        raise click.ClickException(f"Slide index {slide_index} out of range (0-{len(slides_list)-1})")

    slide = slides_list[slide_index]

    if shape_id is None:
        for elem in slide.get("pageElements", []):
            if elem.get("shape", {}).get("shapeType") in ("TEXT_BOX", None) and "text" in elem.get("shape", {}):
                shape_id = elem["objectId"]
                break
            if "shape" in elem:
                shape_id = elem["objectId"]
                break

    if shape_id is None:
        raise click.ClickException("No suitable text box found. Use --shape-id to specify one.")

    requests = [
        {"insertText": {"objectId": shape_id, "text": text, "insertionIndex": 0}}
    ]
    service.presentations().batchUpdate(
        presentationId=presentation_id, body={"requests": requests}
    ).execute()
    click.echo(f"Text inserted into shape {shape_id}")


@slides.command("export")
@click.argument("presentation_id")
@click.option("-o", "--output", default=None, help="Output PDF path.")
def export(presentation_id, output):
    """Export a presentation as PDF."""
    from googleapiclient.http import MediaIoBaseDownload
    import io

    drive_service = build_service("drive", "v3")
    out_path = output or f"{presentation_id}.pdf"

    request = drive_service.files().export_media(
        fileId=presentation_id, mimeType="application/pdf"
    )
    with open(out_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
    click.echo(f"Exported to: {out_path}")


@slides.command("delete-slide")
@click.argument("presentation_id")
@click.argument("slide_id")
@click.confirmation_option(prompt="Delete this slide?")
def delete_slide(presentation_id, slide_id):
    """Delete a slide from a presentation."""
    service = _get_service()
    requests = [{"deleteObject": {"objectId": slide_id}}]
    service.presentations().batchUpdate(
        presentationId=presentation_id, body={"requests": requests}
    ).execute()
    click.echo(f"Deleted slide: {slide_id}")
