"""Google Drive CLI commands."""

import io
import os

import click
from rich.console import Console
from rich.table import Table

from gws_cli.auth import build_service

console = Console()


def _get_service():
    return build_service("drive", "v3")


@click.group()
def drive():
    """Google Drive operations."""


@drive.command("ls")
@click.argument("folder_id", default="root")
@click.option("-n", "--limit", default=20, help="Max number of results.")
@click.option("-q", "--query", default=None, help="Custom Drive query filter.")
def list_files(folder_id, limit, query):
    """List files in a Drive folder (default: root)."""
    service = _get_service()
    q = query or f"'{folder_id}' in parents and trashed = false"
    results = (
        service.files()
        .list(q=q, pageSize=limit, fields="files(id,name,mimeType,modifiedTime,size)")
        .execute()
    )
    files = results.get("files", [])
    if not files:
        click.echo("No files found.")
        return

    table = Table(title="Drive Files")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Modified", style="yellow")
    table.add_column("ID", style="dim")

    for f in files:
        mime = f.get("mimeType", "")
        short_type = mime.split(".")[-1] if "." in mime else mime.split("/")[-1]
        table.add_row(
            f["name"],
            short_type,
            f.get("modifiedTime", "")[:10],
            f["id"],
        )
    console.print(table)


@drive.command("upload")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--folder", default=None, help="Destination folder ID.")
@click.option("--name", default=None, help="Override file name in Drive.")
def upload(file_path, folder, name):
    """Upload a file to Google Drive."""
    from googleapiclient.http import MediaFileUpload

    service = _get_service()
    file_name = name or os.path.basename(file_path)
    metadata = {"name": file_name}
    if folder:
        metadata["parents"] = [folder]

    media = MediaFileUpload(file_path, resumable=True)
    result = service.files().create(body=metadata, media_body=media, fields="id,name").execute()
    click.echo(f"Uploaded: {result['name']} (ID: {result['id']})")


@drive.command("download")
@click.argument("file_id")
@click.option("-o", "--output", default=None, help="Output file path.")
def download(file_id, output):
    """Download a file from Google Drive."""
    from googleapiclient.http import MediaIoBaseDownload

    service = _get_service()
    meta = service.files().get(fileId=file_id, fields="name").execute()
    out_path = output or meta["name"]

    request = service.files().get_media(fileId=file_id)
    with open(out_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                click.echo(f"Download {int(status.progress() * 100)}%")
    click.echo(f"Saved to: {out_path}")


@drive.command("mkdir")
@click.argument("name")
@click.option("--parent", default=None, help="Parent folder ID.")
def mkdir(name, parent):
    """Create a folder in Google Drive."""
    service = _get_service()
    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent:
        metadata["parents"] = [parent]

    result = service.files().create(body=metadata, fields="id,name").execute()
    click.echo(f"Created folder: {result['name']} (ID: {result['id']})")


@drive.command("rm")
@click.argument("file_id")
@click.option("--permanent", is_flag=True, help="Permanently delete (skip trash).")
@click.confirmation_option(prompt="Are you sure you want to delete this file?")
def rm(file_id, permanent):
    """Delete (trash) a file in Google Drive."""
    service = _get_service()
    if permanent:
        service.files().delete(fileId=file_id).execute()
        click.echo("Permanently deleted.")
    else:
        service.files().update(fileId=file_id, body={"trashed": True}).execute()
        click.echo("Moved to trash.")


@drive.command("info")
@click.argument("file_id")
def info(file_id):
    """Show metadata for a Drive file."""
    service = _get_service()
    meta = service.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size,modifiedTime,createdTime,owners,webViewLink",
    ).execute()

    table = Table(title="File Info")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    for key, val in meta.items():
        if key == "owners":
            val = ", ".join(o.get("emailAddress", "") for o in val)
        table.add_row(key, str(val))
    console.print(table)
