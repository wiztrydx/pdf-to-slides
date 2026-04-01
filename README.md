# gws-cli

Google Workspace CLI — manage Drive, Slides, Gmail, and Docs from the terminal.

## Setup

### 1. Install

```bash
pip install -e .
```

### 2. Configure OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a project (or select an existing one)
3. Enable the following APIs:
   - Google Drive API
   - Google Slides API
   - Gmail API
   - Google Docs API
4. Create an **OAuth 2.0 Client ID** (type: Desktop app)
5. Download the JSON and save it to:

```
~/.config/gws-cli/credentials.json
```

### 3. Authenticate

Run any command — a browser window will open for OAuth consent on first use:

```bash
gws drive ls
```

## Usage

```
gws [SERVICE] [COMMAND] [OPTIONS]
```

### Drive

```bash
gws drive ls                           # List files in root
gws drive ls FOLDER_ID                 # List files in a folder
gws drive upload ./file.pdf            # Upload a file
gws drive upload ./file.pdf --folder FOLDER_ID
gws drive download FILE_ID             # Download a file
gws drive download FILE_ID -o out.pdf
gws drive mkdir "New Folder"           # Create a folder
gws drive rm FILE_ID                   # Trash a file
gws drive info FILE_ID                 # Show file metadata
```

### Slides

```bash
gws slides create "My Presentation"    # Create a new presentation
gws slides info PRESENTATION_ID        # List slides
gws slides add-slide PRES_ID           # Add a blank slide
gws slides add-slide PRES_ID --layout TITLE_AND_BODY
gws slides add-text PRES_ID 0 "Hello"  # Insert text into slide 0
gws slides export PRES_ID              # Export as PDF
gws slides delete-slide PRES_ID SLIDE_ID
```

### Gmail

```bash
gws gmail inbox                        # Show recent inbox messages
gws gmail inbox -n 20                  # Show 20 messages
gws gmail read MESSAGE_ID              # Read a message
gws gmail send --to user@example.com --subject "Hi" --body "Hello!"
gws gmail send --to user@example.com --subject "Hi" --body "See attached" --attach ./file.pdf
gws gmail labels                       # List labels
gws gmail search "from:boss subject:urgent"
```

### Docs

```bash
gws docs create "My Document"          # Create a new doc
gws docs info DOCUMENT_ID              # Show doc info
gws docs read DOCUMENT_ID              # Print doc text
gws docs append DOCUMENT_ID "New text" # Append text
gws docs replace DOC_ID "old" "new"    # Find & replace
gws docs export DOCUMENT_ID            # Export as PDF
```

### Other

```bash
gws auth-logout                        # Remove stored credentials
gws --version                          # Show version
```

## Telegram Bot

Use gws from your phone via Telegram.

### Setup

1. Install with bot extras:

```bash
pip install -e ".[bot]"
```

2. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram and get the token.

3. Run the bot:

```bash
export TELEGRAM_BOT_TOKEN="your-token-here"

# Optional: restrict to specific Telegram user IDs (comma-separated)
export GWS_BOT_ALLOWED_USERS="123456789,987654321"

gws-bot
```

### Bot Commands

| Command | Description |
|---|---|
| `/start` | Show help |
| `/drive_ls [folder_id]` | List files |
| `/drive_upload` | Reply to file to upload |
| `/drive_download <id>` | Download file |
| `/drive_mkdir <name>` | Create folder |
| `/drive_info <id>` | File info |
| `/slides_create <title>` | New presentation |
| `/slides_info <id>` | List slides |
| `/slides_add <id> [layout]` | Add slide |
| `/slides_export <id>` | Export as PDF |
| `/gmail_inbox [n]` | Recent messages |
| `/gmail_read <id>` | Read message |
| `/gmail_send <to> \| <subj> \| <body>` | Send email |
| `/gmail_search <query>` | Search |
| `/gmail_labels` | List labels |
| `/docs_create <title>` | New doc |
| `/docs_read <id>` | Read content |
| `/docs_append <id> \| <text>` | Append text |
| `/docs_export <id>` | Export PDF |

## License

MIT
