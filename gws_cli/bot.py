"""Telegram Bot interface for Google Workspace CLI."""

import io
import logging
import os
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from gws_cli.auth import build_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Restrict bot to allowed user IDs (comma-separated env var)
ALLOWED_USERS = set()
_allowed = os.environ.get("GWS_BOT_ALLOWED_USERS", "")
if _allowed:
    ALLOWED_USERS = {int(uid.strip()) for uid in _allowed.split(",") if uid.strip()}


def _check_auth(func):
    """Decorator to restrict commands to allowed users."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if ALLOWED_USERS and update.effective_user.id not in ALLOWED_USERS:
            await update.message.reply_text("⛔ You are not authorized to use this bot.")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# ── Helpers ──────────────────────────────────────────────────────────────────

def _drive():
    return build_service("drive", "v3")

def _slides():
    return build_service("slides", "v1")

def _gmail():
    return build_service("gmail", "v1")

def _docs():
    return build_service("docs", "v1")


def _escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


# ── /start & /help ──────────────────────────────────────────────────────────

@_check_auth
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🗂 *Google Workspace Bot*\n\n"
        "*Drive*\n"
        "/drive\\_ls \\[folder\\_id\\] — List files\n"
        "/drive\\_upload — Reply to a file to upload\n"
        "/drive\\_download <file\\_id> — Download a file\n"
        "/drive\\_mkdir <name> — Create folder\n"
        "/drive\\_info <file\\_id> — File info\n\n"
        "*Slides*\n"
        "/slides\\_create <title> — New presentation\n"
        "/slides\\_info <pres\\_id> — Slide list\n"
        "/slides\\_add <pres\\_id> — Add blank slide\n"
        "/slides\\_export <pres\\_id> — Export as PDF\n\n"
        "*Gmail*\n"
        "/gmail\\_inbox \\[n\\] — Recent messages\n"
        "/gmail\\_read <msg\\_id> — Read message\n"
        "/gmail\\_send <to> \\| <subject> \\| <body> — Send email\n"
        "/gmail\\_search <query> — Search\n"
        "/gmail\\_labels — List labels\n\n"
        "*Docs*\n"
        "/docs\\_create <title> — New document\n"
        "/docs\\_info <doc\\_id> — Doc info\n"
        "/docs\\_read <doc\\_id> — Read content\n"
        "/docs\\_append <doc\\_id> \\| <text> — Append text\n"
        "/docs\\_export <doc\\_id> — Export as PDF\n"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


# ── Drive Commands ───────────────────────────────────────────────────────────

@_check_auth
async def cmd_drive_ls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    folder_id = context.args[0] if context.args else "root"
    service = _drive()
    q = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(
        q=q, pageSize=15, fields="files(id,name,mimeType)"
    ).execute()
    files = results.get("files", [])
    if not files:
        await update.message.reply_text("No files found.")
        return

    lines = []
    for f in files:
        mime = f.get("mimeType", "")
        icon = "📁" if "folder" in mime else "📄"
        lines.append(f"{icon} {f['name']}\n    `{f['id']}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@_check_auth
async def cmd_drive_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.reply_to_message or not msg.reply_to_message.document:
        await msg.reply_text("Reply to a file message with /drive_upload to upload it to Drive.")
        return

    doc = msg.reply_to_message.document
    file = await doc.get_file()

    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{doc.file_name}") as tmp:
        await file.download_to_drive(tmp.name)
        tmp_path = tmp.name

    try:
        from googleapiclient.http import MediaFileUpload
        service = _drive()
        folder_id = context.args[0] if context.args else None
        metadata = {"name": doc.file_name}
        if folder_id:
            metadata["parents"] = [folder_id]
        media = MediaFileUpload(tmp_path, resumable=True)
        result = service.files().create(body=metadata, media_body=media, fields="id,name").execute()
        await msg.reply_text(f"✅ Uploaded: {result['name']}\nID: `{result['id']}`", parse_mode="Markdown")
    finally:
        os.unlink(tmp_path)


@_check_auth
async def cmd_drive_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /drive_download <file_id>")
        return

    file_id = context.args[0]
    service = _drive()
    meta = service.files().get(fileId=file_id, fields="name,size").execute()

    from googleapiclient.http import MediaIoBaseDownload
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    buf.seek(0)
    await update.message.reply_document(document=buf, filename=meta["name"])


@_check_auth
async def cmd_drive_mkdir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /drive_mkdir <name>")
        return

    name = " ".join(context.args)
    service = _drive()
    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    result = service.files().create(body=metadata, fields="id,name").execute()
    await update.message.reply_text(f"📁 Created: {result['name']}\nID: `{result['id']}`", parse_mode="Markdown")


@_check_auth
async def cmd_drive_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /drive_info <file_id>")
        return

    file_id = context.args[0]
    service = _drive()
    meta = service.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size,modifiedTime,createdTime,webViewLink",
    ).execute()

    lines = [f"📋 *{_escape_md(meta.get('name', '?'))}*"]
    for key in ["id", "mimeType", "size", "modifiedTime", "createdTime", "webViewLink"]:
        if key in meta:
            lines.append(f"*{_escape_md(key)}*: {_escape_md(str(meta[key]))}")
    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


# ── Slides Commands ──────────────────────────────────────────────────────────

@_check_auth
async def cmd_slides_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /slides_create <title>")
        return

    title = " ".join(context.args)
    service = _slides()
    pres = service.presentations().create(body={"title": title}).execute()
    pid = pres["presentationId"]
    await update.message.reply_text(
        f"✅ Created: {pres['title']}\nID: `{pid}`\nhttps://docs.google.com/presentation/d/{pid}",
        parse_mode="Markdown",
    )


@_check_auth
async def cmd_slides_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /slides_info <presentation_id>")
        return

    pres_id = context.args[0]
    service = _slides()
    pres = service.presentations().get(presentationId=pres_id).execute()
    slide_list = pres.get("slides", [])

    lines = [f"📊 *{pres.get('title', 'Untitled')}* — {len(slide_list)} slides"]
    for i, s in enumerate(slide_list, 1):
        lines.append(f"  {i}. `{s['objectId']}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@_check_auth
async def cmd_slides_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /slides_add <presentation_id> [layout]")
        return

    pres_id = context.args[0]
    layout = context.args[1] if len(context.args) > 1 else "BLANK"
    service = _slides()
    req = {"createSlide": {"slideLayoutReference": {"predefinedLayout": layout}}}
    result = service.presentations().batchUpdate(
        presentationId=pres_id, body={"requests": [req]}
    ).execute()
    slide_id = result["replies"][0]["createSlide"]["objectId"]
    await update.message.reply_text(f"✅ Added slide: `{slide_id}`", parse_mode="Markdown")


@_check_auth
async def cmd_slides_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /slides_export <presentation_id>")
        return

    pres_id = context.args[0]
    drive_service = _drive()
    from googleapiclient.http import MediaIoBaseDownload

    request = drive_service.files().export_media(fileId=pres_id, mimeType="application/pdf")
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    buf.seek(0)
    await update.message.reply_document(document=buf, filename=f"{pres_id}.pdf")


# ── Gmail Commands ───────────────────────────────────────────────────────────

@_check_auth
async def cmd_gmail_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limit = int(context.args[0]) if context.args else 5
    service = _gmail()
    results = service.users().messages().list(
        userId="me", q="in:inbox", maxResults=limit
    ).execute()
    messages = results.get("messages", [])

    if not messages:
        await update.message.reply_text("No messages found.")
        return

    lines = []
    for msg_ref in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subj = headers.get("Subject", "(no subject)")[:40]
        frm = headers.get("From", "?")[:25]
        lines.append(f"📩 *{frm}*\n    {subj}\n    ID: `{msg_ref['id']}`")
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


@_check_auth
async def cmd_gmail_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /gmail_read <message_id>")
        return

    import base64
    msg_id = context.args[0]
    service = _gmail()
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

    text = f"From: {headers.get('From', '?')}\n"
    text += f"To: {headers.get('To', '?')}\n"
    text += f"Date: {headers.get('Date', '?')}\n"
    text += f"Subject: {headers.get('Subject', '(no subject)')}\n"
    text += "─" * 30 + "\n"

    body = _extract_gmail_body(msg["payload"])
    text += body or "(no text body)"

    # Telegram message limit is 4096 chars
    if len(text) > 4000:
        text = text[:4000] + "\n... (truncated)"
    await update.message.reply_text(text)


def _extract_gmail_body(payload):
    import base64
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _extract_gmail_body(part)
        if result:
            return result
    return None


@_check_auth
async def cmd_gmail_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import base64
    from email.mime.text import MIMEText

    raw_text = " ".join(context.args) if context.args else ""
    parts = raw_text.split("|")
    if len(parts) < 3:
        await update.message.reply_text("Usage: /gmail_send <to> | <subject> | <body>")
        return

    to, subject, body = parts[0].strip(), parts[1].strip(), parts[2].strip()
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service = _gmail()
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    await update.message.reply_text(f"✅ Sent! Message ID: `{result['id']}`", parse_mode="Markdown")


@_check_auth
async def cmd_gmail_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /gmail_search <query>")
        return

    query = " ".join(context.args)
    service = _gmail()
    results = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
    messages = results.get("messages", [])

    if not messages:
        await update.message.reply_text("No messages found.")
        return

    lines = []
    for msg_ref in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="metadata",
            metadataHeaders=["From", "Subject"],
        ).execute()
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        lines.append(f"📩 {headers.get('From', '?')[:25]}\n    {headers.get('Subject', '')[:40]}\n    `{msg_ref['id']}`")
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


@_check_auth
async def cmd_gmail_labels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = _gmail()
    results = service.users().labels().list(userId="me").execute()
    labels = sorted(results.get("labels", []), key=lambda l: l["name"])
    lines = [f"🏷 {l['name']}" for l in labels]
    await update.message.reply_text("\n".join(lines))


# ── Docs Commands ────────────────────────────────────────────────────────────

@_check_auth
async def cmd_docs_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /docs_create <title>")
        return

    title = " ".join(context.args)
    service = _docs()
    doc = service.documents().create(body={"title": title}).execute()
    did = doc["documentId"]
    await update.message.reply_text(
        f"✅ Created: {doc['title']}\nID: `{did}`\nhttps://docs.google.com/document/d/{did}",
        parse_mode="Markdown",
    )


@_check_auth
async def cmd_docs_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /docs_info <document_id>")
        return

    doc_id = context.args[0]
    service = _docs()
    doc = service.documents().get(documentId=doc_id).execute()
    await update.message.reply_text(
        f"📝 *{doc.get('title', 'Untitled')}*\n"
        f"ID: `{doc['documentId']}`\n"
        f"https://docs.google.com/document/d/{doc['documentId']}",
        parse_mode="Markdown",
    )


@_check_auth
async def cmd_docs_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /docs_read <document_id>")
        return

    doc_id = context.args[0]
    service = _docs()
    doc = service.documents().get(documentId=doc_id).execute()

    text = f"📝 {doc.get('title', 'Untitled')}\n{'─' * 30}\n"
    for elem in doc.get("body", {}).get("content", []):
        if "paragraph" in elem:
            for run in elem["paragraph"].get("elements", []):
                content = run.get("textRun", {}).get("content", "")
                if content:
                    text += content

    if len(text) > 4000:
        text = text[:4000] + "\n... (truncated)"
    await update.message.reply_text(text)


@_check_auth
async def cmd_docs_append(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = " ".join(context.args) if context.args else ""
    parts = raw_text.split("|", 1)
    if len(parts) < 2:
        await update.message.reply_text("Usage: /docs_append <doc_id> | <text>")
        return

    doc_id, text = parts[0].strip(), parts[1].strip()
    service = _docs()
    doc = service.documents().get(documentId=doc_id).execute()
    body_content = doc.get("body", {}).get("content", [])
    end_index = body_content[-1]["endIndex"] - 1 if body_content else 1

    service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": end_index}, "text": text + "\n"}}]},
    ).execute()
    await update.message.reply_text("✅ Text appended.")


@_check_auth
async def cmd_docs_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /docs_export <document_id>")
        return

    doc_id = context.args[0]
    drive_service = _drive()
    from googleapiclient.http import MediaIoBaseDownload

    request = drive_service.files().export_media(fileId=doc_id, mimeType="application/pdf")
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    buf.seek(0)
    await update.message.reply_document(document=buf, filename=f"{doc_id}.pdf")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: Set TELEGRAM_BOT_TOKEN environment variable.")
        print("Get a token from @BotFather on Telegram.")
        raise SystemExit(1)

    app = Application.builder().token(token).build()

    # General
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))

    # Drive
    app.add_handler(CommandHandler("drive_ls", cmd_drive_ls))
    app.add_handler(CommandHandler("drive_upload", cmd_drive_upload))
    app.add_handler(CommandHandler("drive_download", cmd_drive_download))
    app.add_handler(CommandHandler("drive_mkdir", cmd_drive_mkdir))
    app.add_handler(CommandHandler("drive_info", cmd_drive_info))

    # Slides
    app.add_handler(CommandHandler("slides_create", cmd_slides_create))
    app.add_handler(CommandHandler("slides_info", cmd_slides_info))
    app.add_handler(CommandHandler("slides_add", cmd_slides_add))
    app.add_handler(CommandHandler("slides_export", cmd_slides_export))

    # Gmail
    app.add_handler(CommandHandler("gmail_inbox", cmd_gmail_inbox))
    app.add_handler(CommandHandler("gmail_read", cmd_gmail_read))
    app.add_handler(CommandHandler("gmail_send", cmd_gmail_send))
    app.add_handler(CommandHandler("gmail_search", cmd_gmail_search))
    app.add_handler(CommandHandler("gmail_labels", cmd_gmail_labels))

    # Docs
    app.add_handler(CommandHandler("docs_create", cmd_docs_create))
    app.add_handler(CommandHandler("docs_info", cmd_docs_info))
    app.add_handler(CommandHandler("docs_read", cmd_docs_read))
    app.add_handler(CommandHandler("docs_append", cmd_docs_append))
    app.add_handler(CommandHandler("docs_export", cmd_docs_export))

    logger.info("Bot started. Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
