# Twitch Chatbot (forbiddenPHPbot)

A custom-built Twitch chatbot for chat logging, polls, streaming software integration, and unknown command tracking. Built with the `twitchAPI` library (pyTwitchAPI), featuring automatic OAuth token handling and a split-screen terminal UI.

## How to contribute

⚠️ This is a personal repository designed to work specifically for my setup. If you have contributions that would improve functionality for me AND could be useful for your own setup, I'm open to contributions. However, I cannot guarantee that all changes will be merged into this codebase.

## Features

* **Full Chat Logging**: All chat messages (viewers, bot, owner) are stored as CSV in `./log/YYYY-MM-DD-messages.csv`.
* **Poll System**: Create interactive polls with up to 4 options. Live files for streaming software integration.
* **Topic & Title Management**: Set and display the current stream topic, update the Twitch stream title via API.
* **Suggestion System**: Viewers can submit suggestions that are logged and available as live files.
* **Subscriber Tracking**: New subscriber events are logged with tier information. Chat welcome message and mimoLive push.
* **Gift Sub Tracking**: Gift subs are buffered per gifter (configurable timeout) and announced as a single message with the total count.
* **Bits/Cheers Tracking**: Bits are buffered per user (same timeout) and announced as a single message with the total amount.
* **Hype Chat Tracking**: Hype Chat events are logged with amount, currency, and level.
* **Raid Detection**: Raid events trigger a thank-you message, mimoLive push (with raider's profile image), and logging.
* **Unknown Command Tracking**: Any `!command` that is not predefined gets counted in a daily JSON log. Detects commands inline in messages (not just at the beginning).
* **Streaming Software Push (mimoLive)**: Push all chat comments to `http://localhost:8888/` for live overlay display, with user profile images and favorite status.
* **Live Files**: Real-time state files in `./live/` for streaming software integration (polls, topic, title, suggestions, subs, unknown commands).
* **Split-Screen Terminal**: Chat output scrolls in the upper area, owner input is fixed at the bottom with colored prompt.
* **Auto-Auth**: Log in once via browser; session is saved in `token.json` for future starts.

## Setup & Installation

### 1. Get Twitch API Keys

1. Visit the [Twitch Dev Console](https://dev.twitch.tv/console).
2. Click **Register Your Application**.
3. **Name**: Choose any name for your application (e.g., `MyTwitchBot`).
4. **OAuth Redirect URLs**: MUST be set to `http://localhost:17563`.
5. **Category**: "Chat Bot".
6. Copy your **Client ID** and **Client Secret**.

### 2. Configure the Bot

Create a `config.ini` file in the root folder (see `config.demo.ini` for reference):

```ini
[TWITCH]
app_id = YOUR_CLIENT_ID
app_secret = YOUR_CLIENT_SECRET
target_channel = YOUR_TWITCH_CHANNEL
owner_name = YOUR_TWITCH_ACCOUNT_NAME
mimoLiveComments = true|false
unknownCommandsFeedback = true|false
giftBufferTimeout = 5
```

| Key | Required | Description |
| --- | --- | --- |
| `app_id` | Yes | Your Twitch application Client ID |
| `app_secret` | Yes | Your Twitch application Client Secret |
| `target_channel` | Yes | The Twitch channel the bot joins |
| `owner_name` | Yes | Your Twitch account name (used for permission checks) |
| `mimoLiveComments` | No | Enable/disable pushing comments to streaming software (`true`/`false`, default: `false`) |
| `unknownCommandsFeedback` | No | Enable/disable chat feedback when unknown commands are counted (`true`/`false`, default: `true`) |
| `giftBufferTimeout` | No | Seconds to wait before announcing buffered gift subs/bits (default: `5`) |

### 3. Installation & Launch

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Edit `faq.txt` with your desired FAQ response text.
3. Edit `commands.txt` with the text shown when a user types `!commands`.
4. Run the bot:
```bash
python twitchbot.py
```

5. **Important on first run:** A browser window will open. Log in with your **Twitch Account** and click "Authorize". The `token.json` will be created automatically, and you won't need to log in again.

### CLI Options

| Flag | Description |
| --- | --- |
| `--nocommentpush` | Disable pushing comments to streaming software, regardless of `config.ini` setting |

```bash
python twitchbot.py --nocommentpush
```

**Push behavior logic:**
- If `--nocommentpush` is set: push is **always disabled** (overrides config)
- If `--nocommentpush` is NOT set: the `mimoLiveComments` value in `config.ini` decides (`true`/`false`)
- If `mimoLiveComments` is missing from `config.ini`: defaults to `false` (disabled)

## Supported Commands

### Command Overview

| Command | User | Description |
| --- | --- | --- |
| `!commands` | Everyone | Shows the content of `commands.txt` |
| `!today` | Everyone | Shows the current stream topic |
| `!setToday <text>` | Owner | Updates the stream topic |
| `!title <text>` | Owner | Updates the Twitch stream title (via API) |
| `!faq` | Everyone | Posts the content of `faq.txt` |
| `!suggest <text>` | Everyone | Saves a suggestion to the daily log |
| `!poll start / Q / A / B` | Owner | Starts a new poll (2-4 options) |
| `!poll status` | Owner | Shows current poll standings |
| `!poll stop` | Owner | Ends the poll and logs the results |
| `!a`, `!b`, `!c`, `!d` | Everyone | Vote in an active poll |
| `!clip` | Everyone | Marks current timestamp as clip-worthy moment (silent, no chat response) |
| `!vip <username>` | Owner + Mods | Grants VIP status to a user |
| `!unvip <username>` | Owner + Mods | Removes VIP status from a user |
| `!mod <username>` | Owner + Mods | Grants moderator status to a user |
| `!unmod <username>` | Owner + Mods | Removes moderator status from a user |
| `!ban <username>` | Owner + Mods | Bans a user from the chat |
| `!unban <username>` | Owner + Mods | Unbans a user |
| `!chatmode` | Owner + Mods | Shows current chat mode |
| `!chatmode <followers\|subs\|all>` | Owner + Mods | Sets chat restriction mode |
| `!so <username>` | Owner + Mods | Gives a shoutout to another streamer |
| `!shoutout <username>` | Owner + Mods | Alias for !so |

### Command Examples

**Stream Management:**
- `!today` - Displays the current topic
- `!setToday We're building a new feature today!` - Sets stream topic
- `!title Building an awesome Twitch bot` - Updates the Twitch stream title

**Interactive Features:**
- `!commands` - Shows command list text
- `!faq` - Shows FAQ text
- `!suggest Add dark mode please` - Saves user suggestion

**Polls:**
- `!poll start / What should we build? / Feature A / Feature B / Feature C` - Start a poll (2-4 options)
- `!poll status` - Check current vote counts
- `!poll stop` - End poll and save results
- `!a` or `!b` or `!c` or `!d` - Cast your vote

### Poll System Details

**Voting Rules:**
- Each user can vote only once
- Users can change their vote at any time (previous vote is replaced)
- Vote counts update in real-time in the live files

**Poll Results Logging:**

When a poll ends (`!poll stop`), results are appended to `./log/YYYY-MM-DD-polls.txt`.

### Owner Terminal Input

The bot features a split-screen terminal. The owner can type directly in the bottom input line:
- Regular text is sent as a chat message (without `(Bot)` prefix)
- `!commands` typed in the terminal execute the command AND send the message to chat
- Bot responses always get a `(Bot)` prefix in chat

## Unknown Command Tracking

Any `!command` that is not one of the predefined commands gets tracked and counted.

**Detection rules:**
- Commands must be preceded by a space or be at the start of a message
- Inline detection: `Wer !hilfe braucht` detects `hilfe`
- No special characters: `!schoen!` detects `schoen`, `!test,` detects `test`
- Multilingual support (Unicode): works with all languages
- `test!inline` does NOT match (no space before `!`)
- Multiple commands per message are all counted

**Predefined commands (NOT counted):** `today`, `settoday`, `faq`, `commands`, `suggest`, `poll`, `title`, `a`, `b`, `c`, `d`, `clip`, `vip`, `unvip`, `mod`, `unmod`, `ban`, `unban`, `chatmode`, `so`, `shoutout`

**Chat Feedback:** When an unknown command is counted, the bot responds with e.g. `!hype was counted, total: 5`. This can be disabled via `unknownCommandsFeedback = false` in `config.ini`.

**Log file:** `./log/YYYY-MM-DD-unknown_commands.json`
```json
{
  "hilfe": 5,
  "helpme": 2,
  "dance": 12
}
```

## Streaming Software Integration (mimoLive)

The comment push feature requires the [mimoLive-automation](https://github.com/forbiddenPHP/mimoLive-automation) package to be running on `localhost:8888`.

### Comment Push

When enabled, every chat message (from viewers, bot, and owner) is pushed to `http://localhost:8888/` via HTTP GET with the following parameters:

| Parameter | Description |
| --- | --- |
| `f` | Always `functions/new-comment` |
| `username` | The sender's Twitch username |
| `message` | The message text |
| `userimageurl` | Twitch profile image URL (daily cached) |
| `plattform` | Always `twitch` |
| `favorite` | `true` for mods, subscribers, and the owner; `false` otherwise |

Profile images are fetched via the Twitch API and cached for the current day.

### Event Pushes

In addition to comments, the following events are pushed to mimoLive (same base URL):

| Event | `f` parameter | Additional parameters |
| --- | --- | --- |
| Comment | `functions/new-comment` | `username`, `message`, `userimageurl`, `plattform`, `favorite` |
| New Sub | `functions/new-sub` | `username`, `tier` |
| Gift Sub | `functions/gift-sub` | `username` (gifter), `count`, `tier` |
| Raid | `functions/raid-alert` | `username` (raider), `viewers`, `userimageurl` |
| Bits/Cheers | `functions/cheer-alert` | `username`, `bits` |
| Hype Chat | `functions/hype-chat` | `username`, `amount`, `currency`, `level` |

### Live Files (`./live/`)

The following files are continuously updated in `./live/` and can be read by streaming software (e.g., as text sources in OBS or mimoLive):

**Poll (updated while a poll is active, cleared when poll ends):**
- `current-poll-question.txt` - The poll question
- `current-poll-a.txt`, `current-poll-b.txt`, `current-poll-c.txt`, `current-poll-d.txt` - Option texts (empty if not used)
- `current-poll-a-amount.txt`, `current-poll-b-amount.txt`, etc. - Current vote counts (empty if option not used)

**General:**
- `current-topic.txt` - Current stream topic (updated on `!setToday`)
- `current-title.txt` - Current stream title (updated on `!title`)
- `current-suggestion.txt` - Latest suggestion (updated on each `!suggest`)
- `current-sub.txt` - Latest subscriber info (updated on each new sub event)
- `current-unknown-commands.txt` - All unknown commands with counts, tab-separated, sorted by count descending
- `current-clip-count.txt` - Total number of `!clip` markers today
- `current-shoutout.txt` - Username of the most recent shoutout
- `current-shoutout-count.txt` - Total number of shoutouts today
- `current-raid.txt` - Latest raid info (`raider: X viewers`)
- `current-giftsub.txt` - Latest gift sub info (`gifter: Nx Tier`)
- `current-giftsub-total.txt` - Total gift subs today
- `current-cheer.txt` - Latest cheer info (`user: X bits`)
- `current-cheer-total.txt` - Total bits today
- `current-hypechat.txt` - Latest Hype Chat info (`user: amount currency (Level)`)

**Unknown commands format:**
```
dance	12
hilfe	5
helpme	2
```

## Log Files (`./log/`)

All logs are automatically saved with date prefixes:

| File | Format | Description |
| --- | --- | --- |
| `YYYY-MM-DD-messages.csv` | CSV | All chat messages (timestamp, username, color, message) |
| `YYYY-MM-DD-polls.txt` | Text | Poll results summary (appended on `!poll stop`) |
| `YYYY-MM-DD-new-subs.txt` | Text | New subscriber notifications with tier |
| `YYYY-MM-DD-suggestions.txt` | Text | All suggestions (username + text) |
| `YYYY-MM-DD-unknown_commands.json` | JSON | Unknown command counts `{"command": count}` |
| `YYYY-MM-DD-clip.txt` | Text | Clip-worthy timestamps (`HH:MM:SS username`) |
| `YYYY-MM-DD-shoutouts.csv` | CSV | Shoutout log (`timestamp,username`) |
| `YYYY-MM-DD-raids.csv` | CSV | Raid log (`timestamp,raider,viewer_count`) |
| `YYYY-MM-DD-giftsubs.csv` | CSV | Gift sub log (`timestamp,gifter,count,tier`) |
| `YYYY-MM-DD-cheers.csv` | CSV | Bits/cheers log (`timestamp,username,bits`) |
| `YYYY-MM-DD-hypechat.csv` | CSV | Hype Chat log (`timestamp,username,amount,currency,level`) |

## Security

The files `config.ini` and `token.json` contain sensitive credentials and **must never** be uploaded to GitHub (they are already included in the `.gitignore`).


