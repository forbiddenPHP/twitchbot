# Twitch Chatbot (forbiddenPHPbot)

A custom-built Twitch chatbot for logging, polls, and moderation. Built with the modern `twitchAPI` library, featuring automatic token handling.

## How to contribute

⚠️ This is a personal repository designed to work specifically for my setup. If you have contributions that would improve functionality for me AND could be useful for your own setup, I'm open to contributions. However, I cannot guarantee that all changes will be merged into this codebase.

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
3. **Name**: Choose any name for your application (e.g., `MyTwitchBot`).
4. **OAuth Redirect URLs**: MUST be set to `http://localhost:17563`.
5. **Category**: "Chat Bot".
6. Copy your **Client ID** and **Client Secret**.

### 2. Configure the Bot

Create a `config.ini` file in the root folder:

```ini
[TWITCH]
app_id = YOUR_CLIENT_ID
app_secret = YOUR_CLIENT_SECRET
target_channel = YOUR_TWITCH_CHANNEL
owner_name = YOUR_TWITCH_ACCOUNT_NAME

```

### 3. Installation & Launch

1. Install dependencies:
```bash
pip install -r requirements.txt

```


2. Edit `faq.txt` with your desired FAQ response text.
3. Run the bot:
```bash
python twitchbot.py

```


4. **Important on first run:** A browser window will open. Log in with your **Twitch Account** and click "Authorize". The `token.json` will be created automatically, and you won't need to log in again.

## 📜 Supported Commands

### Syntax Overview

| Command | User | Description |
| --- | --- | --- |
| `!commands` | Everyone | Shows link to command documentation |
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
- `!commands` - Shows link to command list
- `!faq` - Shows FAQ text
- `!suggest Add dark mode please` - Saves user suggestion

**Polls:**
- `!poll start / What should we build? / Feature A / Feature B / Feature C` - Start a poll (2-4 options)
- `!poll status` - Check current vote counts
- `!poll stop` - End poll and save results
- `!a` or `!b` or `!c` or `!d` - Cast your vote (you can change your vote anytime)

### Poll System Details

**Live Poll Files (Streaming Software Integration):**

While a poll is active, the following files are continuously updated in `./log/`:
- `current-poll-question.txt` - The poll question
- `current-poll-a.txt`, `current-poll-b.txt`, `current-poll-c.txt`, `current-poll-d.txt` - Option texts (empty if not used)
- `current-poll-a-amount.txt`, `current-poll-b-amount.txt`, etc. - Current vote counts (empty if option not used)
- `current-poll-votes.json` - Vote tracking metadata

These files remain persistent after a poll ends (showing last results) and are only overwritten when a new poll starts.

**Voting Rules:**
- Each user can vote only once
- Users can change their vote at any time (but cannot vote for multiple options)
- Vote changes are tracked in real-time

**Poll Archiving:**

When a poll ends, all files are archived with timestamps:
- `YYYY-MM-DD-HH-MM-poll-question.txt`
- `YYYY-MM-DD-HH-MM-poll-a.txt`, etc.

This allows you to review historical poll results.

### File Logging

All logs are automatically saved with date prefixes in the `./log/` directory:
- `YYYY-MM-DD-messages.csv` - All chat messages
- `YYYY-MM-DD-polls.txt` - Poll results summary
- `YYYY-MM-DD-new-subs.txt` - New subscriber notifications
- `YYYY-MM-DD-HH-MM-poll-*.txt` - Archived poll data (timestamped)

## 📂 Security

The files `config.ini` and `token.json` contain sensitive credentials and **must never** be uploaded to GitHub (they are already included in the `.gitignore`).

## 🚧 TODOs

The following commands are planned but not yet implemented:

### Moderation Commands

| Command | User | Description |
| --- | --- | --- |
| `!vip <username>` | Owner | Grants VIP status to a user |
| `!unvip <username>` | Owner | Removes VIP status from a user |
| `!mod <username>` | Owner | Grants moderator status to a user |
| `!unmod <username>` | Owner | Removes moderator status from a user |
| `!ban <username>` | Owner + Mods | Bans a user from the chat |
| `!unban <username>` | Owner + Mods | Unbans a user |
| `!chatmode` | Owner | Shows current chat mode (default: followers) |
| `!chatmode <followers\|subs\|all>` | Owner | Sets chat restriction mode |

### Shoutout System

| Command | User | Description |
| --- | --- | --- |
| `!so <username>` | Owner + Mods | Gives a shoutout to another streamer |
| `!shoutout <username>` | Owner + Mods | Alias for !so |

**Shoutout Files (Streaming Software Integration):**

Shoutouts are logged to `./log/YYYY-MM-DD-shoutouts.csv` with the following format:
```csv
timestamp,username,shown
1737208980,somestreamer,0
1737213900,anotherstreamer,0
```

The `shown` field starts at `0` and can be set to `1` by streaming software to track which shoutouts have been displayed on stream.

Additional files for Streaming Software integration:
- `current-shoutout.txt` - Username of the most recent shoutout
- `current-shoutout-count.txt` - Total number of shoutouts today

### Emote Tracking System

Tracks custom emote usage anywhere in messages (not just at the beginning). These work alongside Twitch custom emotes to provide analytics and interaction tracking.

**Tracked Emotes:**
- `!lurk` - User is lurking
- `!hype` - Hype moments
- `!coding` - Coding activity
- `!clip` - Clip-worthy moment marker

**Behavior:**
- Emotes are detected anywhere in any message (beginning, middle, end)
- Multiple emotes in one message are all counted
- No bot responses (silent tracking only)
- Works in parallel with regular commands (e.g., `!suggest I love !hype moments` counts the !hype AND saves the suggestion)

**Files (Streaming Software Integration):**

Per-emote CSV logs in `./log/`:
```csv
timestamp,username
1737208980,viewer1
1737213900,viewer2
1737215520,viewer1
```

- `YYYY-MM-DD-lurk.csv` - All !lurk usage
- `YYYY-MM-DD-hype.csv` - All !hype usage
- `YYYY-MM-DD-coding.csv` - All !coding usage
- `YYYY-MM-DD-clips.csv` - All !clip requests

Real-time counters for Streaming Software:
- `current-lurk-count.txt` - Total !lurk count today
- `current-hype-count.txt` - Total !hype count today
- `current-coding-count.txt` - Total !coding count today
- `current-clip-count.txt` - Total !clip requests today