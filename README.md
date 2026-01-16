# Twitch Chatbot (forbiddenPHPbot)

A custom-built Twitch chatbot for logging, polls, and moderation. Built with the modern `twitchAPI` library, featuring automatic token handling.

## 🛠 Features

* **Full Logging**: All chat messages are stored in `./log/YYYY-MM-DD-messages.csv`.
* **Poll System**: Create interactive polls with `!poll start / Question / Option A / Option B`.
* **Moderation**: Quick commands for VIP, Ban, and Chat modes (Followers/Subs/All).
* **Topic Tracking**: Set and display the current stream topic.
* **Auto-Auth**: Log in once via browser; session is saved in `token.json` for future starts.

## 🚀 Setup & Installation

### 1. Get Twitch API Keys

1. Visit the [Twitch Dev Console](https://dev.twitch.tv/console).
2. Click **Register Your Application**.
3. **Name**: `forbiddenPHPbot` (or your preferred name).
4. **OAuth Redirect URLs**: MUST be set to `http://localhost:17563`.
5. **Category**: "Chat Bot".
6. Copy your **Client ID** and **Client Secret**.

### 2. Prepare Twitch Permissions

Log into Twitch with your **Main Streamer Account** and grant your bot moderator privileges by typing this in your chat:

```text
/mod forbiddenPHPbot

```

### 3. Configure the Bot

Create a `config.ini` file in the root folder:

```ini
[TWITCH]
app_id = YOUR_CLIENT_ID
app_secret = YOUR_CLIENT_SECRET
target_channel = YOUR_STREAM_CHANNEL
owner_name = YOUR_MAIN_ACCOUNT_NAME

```

### 4. Installation & Launch

1. Install dependencies:
```bash
pip install -r requirements.txt

```


2. Edit `faq.txt` with your desired FAQ response text.
3. Run the bot:
```bash
python twitchbot.py

```


4. **Important on first run:** A browser window will open. Log in as the **Bot Account** (`forbiddenPHPbot`) and click "Authorize". The `token.json` will be created automatically, and you won't need to log in again.

## 📜 Supported Commands

### Syntax Overview

| Command | User | Description |
| --- | --- | --- |
| `!today` | Everyone | Shows the current stream topic |
| `!setToday <text>` | Owner | Updates the stream topic |
| `!title <text>` | Owner | Updates the stream title |
| `!faq` | Everyone | Posts the content of faq.txt |
| `!suggest <text>` | Everyone | Saves suggestions to suggestions.txt |
| `!poll start / Q / A / B` | Owner | Starts a new poll |
| `!poll status` | Owner | Shows current poll standings |
| `!poll stop` | Owner | Ends the poll and logs the results |
| `!a, !b, !c, !d` | Everyone | Vote in an active poll |

### Command Examples

**Stream Management:**
- `!today` - Displays the current topic
- `!setToday We're building a new feature today!` - Sets stream topic
- `!title Building an awesome Twitch bot` - Updates stream title

**Interactive Features:**
- `!faq` - Shows FAQ text
- `!suggest Add dark mode please` - Saves user suggestion

**Polls:**
- `!poll start / What should we build? / Feature A / Feature B / Feature C` - Start a poll (2-4 options)
- `!poll status` - Check current vote counts
- `!poll stop` - End poll and save results
- `!a` or `!b` or `!c` or `!d` - Cast your vote

### File Logging

All logs are automatically saved with date prefixes in the `./log/` directory:
- `YYYY-MM-DD-messages.csv` - All chat messages
- `YYYY-MM-DD-polls.txt` - Poll results
- `YYYY-MM-DD-new-subs.txt` - New subscriber notifications

## 📂 Security

The files `config.ini` and `token.json` contain sensitive credentials and **must never** be uploaded to GitHub (they are already included in the `.gitignore`).

## How to contribute

⚠️ This is a personal repository designed to work specifically for my setup. If you have contributions that would improve functionality for me AND could be useful for your own setup, I'm open to contributions. However, I cannot guarantee that all changes will be merged into this codebase.