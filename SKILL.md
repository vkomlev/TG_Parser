# Telegram Channel Parser Skill

## Description
A skill to parse Telegram channels and export their content as structured JSON data with media files, similar to Telegram Desktop's export functionality.

## Requirements
- Python 3.8+
- Telethon library
- Telegram API credentials (api_id, api_hash)
- User authorization to access channels (supports 2FA)
- Environment variables stored securely in .env file

## Features
- List accessible channels/chats
- Parse channel messages with metadata
- Export to structured JSON format with file paths
- Download and save media files to organized directory structure
- Support for various content types (text, photos, videos, documents)
- Pagination handling for large channels
- Support for both public and private channels
- Update mode - adds new messages to existing exports
- Keyword filtering option
- Forwarded message information
- Media file size limiting
- Organized file storage (by channel and media type)

## Commands
- `/telegram_parse <channel_link_or_username>` - Parse a specific channel
- `/telegram_channels` - List available channels
- `/telegram_help` - Show help information

## Options
- `--limit <number>` - Limit number of messages to parse
- `--start-date <YYYY-MM-DD>` - Parse messages starting from date
- `--end-date <YYYY-MM-DD>` - Parse messages until date
- `--media-only` - Export only media messages
- `--text-only` - Export only text messages
- `--keyword-filter <word1> <word2> ...` - Only include messages containing these keywords (optional, parses all by default)
- `--max-media-size <number>` - Maximum media file size in MB (optional, no limit by default)
- `--output-dir <path>` - Output directory for exports (default: ./telegram_exports)

## JSON Structure
```json
{
  "channel_info": {
    "id": "...",
    "username": "...",
    "title": "...",
    "participants_count": "...",
    "description": "...",
    "date_created": "..."
  },
  "messages": [
    {
      "id": "...",
      "date": "...",
      "sender_id": "...",
      "sender_username": "...",
      "sender_first_name": "...",
      "sender_last_name": "...",
      "text": "...",
      "media_files": [
        {
          "type": "photo|video|document",
          "path": "relative/path/to/media/file",
          "filename": "filename.ext",
          "size": 123456
        }
      ],
      "forwarded": {
        "from_name": "...",
        "date": "...",
        "channel_post_id": "...",
        "post_author": "..."
      },
      "reply_to_msg_id": "...",
      "views": "...",
      "forwards": "..."
    }
  ],
  "export_date": "...",
  "total_messages": "..."
}
```

## Directory Structure
```
output_dir/
└── channel_title/
    ├── channel_title.json
    └── media/
        ├── photos/
        ├── videos/
        └── documents/
```

## Configuration
Requires TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables stored securely in .env file.
Supports two-factor authentication during initial login.

## Dependencies
- telethon
- json
- datetime
- pathlib
- typing