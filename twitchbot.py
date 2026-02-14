import asyncio
import os
import configparser
import json
import sys
import re
import signal
import argparse
import aiohttp
from urllib.parse import quote
from datetime import datetime, date
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatCommand, ChatSub
from aioconsole import ainput

# --- COLORS & ANSI CODES FOR TERMINAL ---
class Color:
    RED = '\033[91m'
    ORANGE = '\033[38;5;208m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GREY = '\033[90m'
    RESET = '\033[0m'

class ANSI:
    SAVE_CURSOR = '\033[s'
    RESTORE_CURSOR = '\033[u'
    CLEAR_LINE = '\033[2K'
    CURSOR_TO_BOTTOM = '\033[999;0H'  # Move to bottom
    DARK_BLUE_BG = '\033[48;5;17m'  # Dunkles Blau als Hintergrund
    ORANGE_TEXT = '\033[38;5;208m'  # Orange für Name
    YELLOW_TEXT = '\033[93m'  # Gelb für Input
    RESET = '\033[0m'
    HIDE_CURSOR = '\033[?25l'
    SHOW_CURSOR = '\033[?25h'

# --- CONFIG LOADING ---
config = configparser.ConfigParser()
config.read('config.ini')
APP_ID = config['TWITCH']['app_id']
APP_SECRET = config['TWITCH']['app_secret']
TARGET_CHANNEL = config['TWITCH']['target_channel']
OWNER_NAME = config['TWITCH']['owner_name'].lower()
MIMO_LIVE_COMMENTS = config['TWITCH'].getboolean('mimoLiveComments', fallback=False)
UNKNOWN_COMMANDS_FEEDBACK = config['TWITCH'].getboolean('unknownCommandsFeedback', fallback=True)

USER_SCOPE = [
    AuthScope.CHAT_READ,
    AuthScope.CHAT_EDIT,
    AuthScope.CHANNEL_MANAGE_BROADCAST,
    AuthScope.MODERATOR_MANAGE_BANNED_USERS,
    AuthScope.CHANNEL_MANAGE_VIPS,
    AuthScope.CHANNEL_MANAGE_MODERATORS,
    AuthScope.MODERATOR_MANAGE_CHAT_SETTINGS,
    AuthScope.MODERATOR_MANAGE_SHOUTOUTS
]

TOKEN_FILE = 'token.json'
UNKNOWN_COMMANDS_FILE = 'unknown_commands.json'  # with date prefix in LOG_DIR
LOG_DIR = './log'
LIVE_DIR = './live'
today_topic = "I'm sorry, this is currently a huge surprise. I don't know."
poll_active = False
poll_data = {}

# --- CLI ARGUMENTS ---
parser = argparse.ArgumentParser()
parser.add_argument('--nocommentpush', action='store_true', help='Disable pushing comments to streaming software')
args = parser.parse_args()

chat_instance = None
twitch_instance = None

# --- USER IMAGE CACHE (resets daily) ---
user_image_cache = {}
user_image_cache_date = None

async def get_user_image(username):
    """Holt Profilbild-URL, mit täglichem Cache."""
    global user_image_cache, user_image_cache_date
    today = date.today()
    if user_image_cache_date != today:
        user_image_cache = {}
        user_image_cache_date = today
    if username in user_image_cache:
        return user_image_cache[username]
    try:
        async for u in twitch_instance.get_users(logins=[username]):
            url = u.profile_image_url or ''
            user_image_cache[username] = url
            return url
    except Exception:
        pass
    user_image_cache[username] = ''
    return ''

# --- PUSH COMMENT TO STREAMING SOFTWARE ---

PUSH_URL = 'http://localhost:8888/'

async def push_comment(username, message, userimageurl='', favorite=False):
    """Pusht einen Kommentar an die Streaming-Software."""
    if args.nocommentpush or not MIMO_LIVE_COMMENTS:
        return
    params = {
        'f': 'functions/new-comment',
        'username': username,
        'message': message,
        'userimageurl': userimageurl,
        'plattform': 'twitch',
        'favorite': 'true' if favorite else 'false',
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(PUSH_URL, params=params, timeout=aiohttp.ClientTimeout(total=5)):
                pass
    except Exception as e:
        chat_print(f"{Color.GREY}PUSH ERROR: {e}{Color.RESET}")

KNOWN_COMMANDS = {'today', 'settoday', 'faq', 'commands', 'suggest', 'poll', 'title', 'a', 'b', 'c', 'd', 'clip', 'vip', 'unvip', 'mod', 'unmod', 'ban', 'unban', 'chatmode', 'so', 'shoutout'}

def get_unknown_commands_path():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    date_str = datetime.now().strftime('%Y-%m-%d')
    return os.path.join(LOG_DIR, f"{date_str}-{UNKNOWN_COMMANDS_FILE}")

def load_unknown_commands():
    path = get_unknown_commands_path()
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_unknown_commands(data):
    path = get_unknown_commands_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def track_unknown_command(cmd_name):
    """Zählt unbekannte Commands. Gibt (cmd_name, neuer_count) zurück oder None."""
    cmd_name = cmd_name.lower()
    if cmd_name in KNOWN_COMMANDS:
        return None
    data = load_unknown_commands()
    data[cmd_name] = data.get(cmd_name, 0) + 1
    save_unknown_commands(data)
    write_unknown_commands_live(data)
    return (cmd_name, data[cmd_name])

def track_clip(username):
    """Speichert Clip-Zeitstempel in Log und aktualisiert Live-Datei."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_write("clip.txt", f"{timestamp} {username}")
    # Clip-Count für Live-Datei berechnen
    date_str = datetime.now().strftime('%Y-%m-%d')
    clip_path = os.path.join(LOG_DIR, f"{date_str}-clip.txt")
    count = 0
    if os.path.exists(clip_path):
        with open(clip_path, 'r', encoding='utf-8') as f:
            count = sum(1 for line in f if line.strip())
    write_live_file('current-clip-count.txt', str(count))

def write_live_file(filename, content):
    """Schreibt eine einzelne Live-Datei für Streaming-Software."""
    if not os.path.exists(LIVE_DIR):
        os.makedirs(LIVE_DIR)
    with open(os.path.join(LIVE_DIR, filename), 'w', encoding='utf-8') as f:
        f.write(content)

def write_unknown_commands_live(data):
    """Schreibt unknown commands als TAB-getrennte Live-Datei für Streaming-Software."""
    lines = [f"{cmd}\t{count}" for cmd, count in sorted(data.items(), key=lambda x: x[1], reverse=True)]
    write_live_file('current-unknown-commands.txt', '\n'.join(lines))

# --- LIVE POLL FILES ---

def write_poll_live_files():
    """Schreibt Live-Dateien für aktive Poll (Streaming-Software)."""
    write_live_file('current-poll-question.txt', poll_data.get('question', ''))
    results = {l: list(poll_data['votes'].values()).count(l) for l in poll_data['options']}
    for letter in ['a', 'b', 'c', 'd']:
        opt_text = poll_data['options'].get(letter, '')
        count = results.get(letter, 0) if opt_text else ''
        write_live_file(f'current-poll-{letter}.txt', opt_text)
        write_live_file(f'current-poll-{letter}-amount.txt', str(count) if opt_text else '')

def clear_poll_live_files():
    """Leert alle Live-Poll-Dateien nach Poll-Ende."""
    write_live_file('current-poll-question.txt', '')
    for letter in ['a', 'b', 'c', 'd']:
        write_live_file(f'current-poll-{letter}.txt', '')
        write_live_file(f'current-poll-{letter}-amount.txt', '')

# Input line state
current_input = ""

# --- HELPER FUNCTIONS ---

def get_terminal_height():
    """Ermittelt Terminal-Höhe"""
    import shutil
    return shutil.get_terminal_size().lines

def setup_split_screen():
    """Richtet Split-Screen ein: Chat oben, Input-Zeile unten"""
    height = get_terminal_height()
    # Cursor verstecken
    sys.stdout.write(f"{ANSI.HIDE_CURSOR}")
    # Scroll-Region setzen: Zeile 1 bis N-1
    sys.stdout.write(f"\033[1;{height-1}r")
    # Cursor auf Zeile 1
    sys.stdout.write(f"\033[1;1H")
    sys.stdout.flush()

def handle_resize(signum, frame):
    """Handler für Terminal-Resize (SIGWINCH)"""
    setup_split_screen()
    draw_input_line()

def draw_input_line():
    """Zeichnet die Input-Zeile fixiert am unteren Rand"""
    height = get_terminal_height()
    width = os.get_terminal_size().columns

    # Cursor zur letzten Zeile (außerhalb der Scroll-Region)
    sys.stdout.write(f"\033[{height};1H")
    # Zeile löschen
    sys.stdout.write(f"{ANSI.CLEAR_LINE}")

    # Text zusammenbauen
    prompt_text = f"{OWNER_NAME}: {current_input}"

    # Dunkelblaues BG für die ganze Zeile, orangener Name, gelber Input-Text
    sys.stdout.write(f"{ANSI.DARK_BLUE_BG}{ANSI.ORANGE_TEXT}{OWNER_NAME}: {ANSI.YELLOW_TEXT}{current_input}")
    # Restliche Zeile mit dunkelblauem BG auffüllen
    remaining_spaces = width - len(prompt_text)
    if remaining_spaces > 0:
        sys.stdout.write(" " * remaining_spaces)
    sys.stdout.write(f"{ANSI.RESET}")

    # Cursor zurück in die Scroll-Region
    sys.stdout.write(f"\033[{height-1};1H")
    sys.stdout.flush()

def chat_print(text):
    """Gibt Chat-Text im Scroll-Bereich aus"""
    # Text ausgeben OHNE automatische Leerzeile
    sys.stdout.write(text + '\n')
    sys.stdout.flush()
    # Input-Zeile neu zeichnen
    draw_input_line()

def clean_all_unwanted_parts(text: str) -> str:
    # 1. ANSI weg (als String, nicht Bytes!)
    ansi_pattern = re.compile(
        r'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])'
    )
    text = ansi_pattern.sub('', text)

    # 2. Alle Whitespaces (Tabs, \n, \r) zu Leerzeichen
    text = re.sub(r'\s+', ' ', text)

    return text.strip()

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def log_write(filename_suffix, content, is_csv=False):
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    date_str = datetime.now().strftime('%Y-%m-%d')
    path = os.path.join(LOG_DIR, f"{date_str}-{filename_suffix}")
    
    if is_csv and not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write("time,user_name,user_color,message\n")
            
    with open(path, 'a', encoding='utf-8') as f:
        f.write(content + "\n")

async def send_and_log(room, message, is_bot=True):
    """Zentraler Ausgang: Bot-Nachrichten bekommen (Bot) Prefix"""
    if is_bot:
        final_msg = f"(Bot) {message}"
        chat_print(f"{Color.RED}{OWNER_NAME} (Bot){Color.RESET}: {Color.WHITE}{message}{Color.RESET}")
        ts = int(datetime.now().timestamp())
        csv_line = f'{ts},{OWNER_NAME}_bot,#FF0000,"{final_msg}"'
        log_write("messages.csv", csv_line, is_csv=True)
        push_name = f"{OWNER_NAME} (Bot)"
    else:
        # Normale Streamer-Message (ohne Bot-Prefix)
        final_msg = message
        chat_print(f"{Color.RED}{OWNER_NAME}{Color.RESET}: {Color.WHITE}{message}{Color.RESET}")
        ts = int(datetime.now().timestamp())
        csv_line = f'{ts},{OWNER_NAME},#FF0000,"{final_msg}"'
        log_write("messages.csv", csv_line, is_csv=True)
        push_name = OWNER_NAME

    await chat_instance.send_message(room, final_msg)

    # Push to streaming software
    owner_image = await get_user_image(OWNER_NAME)
    await push_comment(push_name, final_msg, userimageurl=owner_image, favorite=True)

def is_mod_or_owner(user):
    return user.mod or user.name.lower() == OWNER_NAME

# --- COMMAND HANDLERS ---

async def cmd_title(cmd: ChatCommand):
    if cmd.user.name.lower() != OWNER_NAME: return
    new_title = cmd.parameter.strip()
    if not new_title:
        await send_and_log(cmd.room, "Usage: !title My New Title")
        return
    try:
        user_info = None
        async for u in twitch_instance.get_users(logins=[TARGET_CHANNEL]):
            user_info = u
            break
        if user_info:
            await twitch_instance.modify_channel_information(user_info.id, title=new_title)
            write_live_file('current-title.txt', new_title)
            await send_and_log(cmd.room, f"Title updated to: {new_title}")
    except Exception as e:
        chat_print(f"{Color.GREY}API ERROR: {e}{Color.RESET}")
        await send_and_log(cmd.room, "Failed to update title.")

async def cmd_poll(cmd: ChatCommand):
    global poll_active, poll_data
    if cmd.user.name.lower() != OWNER_NAME: return
    
    parts = [p.strip() for p in cmd.parameter.split('/')]
    action = parts[0].lower()
    
    if action == 'start' and len(parts) >= 3:
        poll_data = {'question': parts[1], 'options': {}, 'votes': {}}
        letters = ['a', 'b', 'c', 'd']
        options_info = []
        for i, opt_text in enumerate(parts[2:6]):
            char = letters[i]
            poll_data['options'][char] = opt_text
            options_info.append(f"!{char}: {opt_text}")
        poll_active = True
        write_poll_live_files()
        await send_and_log(cmd.room, f"POLL: {poll_data['question']} -> {' | '.join(options_info)}")
        
    elif action == 'status' and poll_active:
        results = {l: list(poll_data['votes'].values()).count(l) for l in poll_data['options']}
        res_str = " | ".join([f"{k.upper()}: {v}" for k, v in results.items()])
        await send_and_log(cmd.room, f"STAND: {res_str}")

    elif action == 'stop' and poll_active:
        results = {l: list(poll_data['votes'].values()).count(l) for l in poll_data['options']}
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        log_entry = f"[{timestamp}]\n{poll_data['question']}\n"
        for l, text in poll_data['options'].items():
            log_entry += f"{l}: {text} ({results[l]})\n"
        
        log_write("polls.txt", log_entry + "\n")
        
        res_str = " | ".join([f"{k.upper()}: {v}" for k, v in results.items()])
        poll_active = False
        clear_poll_live_files()
        await send_and_log(cmd.room, f"POLL ENDED: {res_str}")

async def cmd_today(cmd: ChatCommand):
    await send_and_log(cmd.room, f"Topic: {today_topic}")

async def cmd_set_today(cmd: ChatCommand):
    global today_topic
    if cmd.user.name.lower() == OWNER_NAME:
        today_topic = cmd.parameter
        write_live_file('current-topic.txt', today_topic)
        await send_and_log(cmd.room, "Topic updated!")

async def cmd_faq(cmd: ChatCommand):
    if os.path.exists('faq.txt'):
        with open('faq.txt', 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content: await send_and_log(cmd.room, content)

async def cmd_commands(cmd: ChatCommand):
    if os.path.exists('commands.txt'):
        with open('commands.txt', 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content: await send_and_log(cmd.room, content)

async def cmd_suggest(cmd: ChatCommand):
    if not cmd.parameter: return
    log_write("suggestions.txt", f"{cmd.user.name}: {cmd.parameter}")
    write_live_file('current-suggestion.txt', f"{cmd.user.name}: {cmd.parameter}")
    await send_and_log(cmd.room, f"@{cmd.user.name} Suggestion saved!")

async def cmd_vote(cmd: ChatCommand):
    if poll_active and cmd.name.lower() in poll_data['options']:
        poll_data['votes'][cmd.user.name] = cmd.name.lower()
        write_poll_live_files()

# --- HELPER: Resolve user/broadcaster IDs ---

async def get_broadcaster_id():
    """Gibt die Broadcaster-ID für den TARGET_CHANNEL zurück."""
    async for u in twitch_instance.get_users(logins=[TARGET_CHANNEL]):
        return u.id
    return None

async def get_user_id(username):
    """Gibt die User-ID für einen Twitch-Usernamen zurück."""
    async for u in twitch_instance.get_users(logins=[username]):
        return u.id
    return None

async def get_authenticated_user_id():
    """Gibt die User-ID des authentifizierten Users zurück."""
    async for u in twitch_instance.get_users():
        return u.id
    return None

# --- MODERATION COMMANDS ---

async def _check_mod_permission(cmd, action_name):
    """Prüft Mod/Owner-Berechtigung. Gibt False zurück wenn nicht erlaubt."""
    if not is_mod_or_owner(cmd.user):
        target = cmd.parameter.strip().lstrip('@')
        await send_and_log(cmd.room, f"Ok, ok... We noticed your effort to {action_name} @{target}, but unfortunately you're not in the position to do so.")
        return False
    return True

def _is_owner_target(target):
    """Prüft ob das Ziel der Owner ist."""
    return target.lower() == OWNER_NAME

async def cmd_vip(cmd: ChatCommand):
    if not await _check_mod_permission(cmd, "vip"): return
    target = cmd.parameter.strip().lstrip('@')
    if not target:
        await send_and_log(cmd.room, "Usage: !vip <username>")
        return
    if _is_owner_target(target):
        await send_and_log(cmd.room, f"We know, @{target} is a bit strange, but this request is impossible, fortunately it's my channel.")
        return
    try:
        broadcaster_id = await get_broadcaster_id()
        user_id = await get_user_id(target)
        if not user_id:
            await send_and_log(cmd.room, f"User '{target}' not found.")
            return
        await twitch_instance.add_channel_vip(broadcaster_id, user_id)
        await send_and_log(cmd.room, f"@{target} is now a VIP!")
    except Exception as e:
        chat_print(f"{Color.GREY}API ERROR: {e}{Color.RESET}")
        await send_and_log(cmd.room, f"Failed to VIP {target}.")

async def cmd_unvip(cmd: ChatCommand):
    if not await _check_mod_permission(cmd, "unvip"): return
    target = cmd.parameter.strip().lstrip('@')
    if not target:
        await send_and_log(cmd.room, "Usage: !unvip <username>")
        return
    if _is_owner_target(target):
        await send_and_log(cmd.room, f"We know, @{target} is a bit strange, but this request is impossible, fortunately it's my channel.")
        return
    try:
        broadcaster_id = await get_broadcaster_id()
        user_id = await get_user_id(target)
        if not user_id:
            await send_and_log(cmd.room, f"User '{target}' not found.")
            return
        await twitch_instance.remove_channel_vip(broadcaster_id, user_id)
        await send_and_log(cmd.room, f"@{target} is no longer a VIP.")
    except Exception as e:
        chat_print(f"{Color.GREY}API ERROR: {e}{Color.RESET}")
        await send_and_log(cmd.room, f"Failed to remove VIP from {target}.")

async def cmd_mod(cmd: ChatCommand):
    if not await _check_mod_permission(cmd, "mod"): return
    target = cmd.parameter.strip().lstrip('@')
    if not target:
        await send_and_log(cmd.room, "Usage: !mod <username>")
        return
    if _is_owner_target(target):
        await send_and_log(cmd.room, f"We know, @{target} is a bit strange, but this request is impossible, fortunately it's my channel.")
        return
    try:
        broadcaster_id = await get_broadcaster_id()
        user_id = await get_user_id(target)
        if not user_id:
            await send_and_log(cmd.room, f"User '{target}' not found.")
            return
        await twitch_instance.add_channel_moderator(broadcaster_id, user_id)
        await send_and_log(cmd.room, f"@{target} is now a Moderator!")
    except Exception as e:
        chat_print(f"{Color.GREY}API ERROR: {e}{Color.RESET}")
        await send_and_log(cmd.room, f"Failed to mod {target}.")

async def cmd_unmod(cmd: ChatCommand):
    if not await _check_mod_permission(cmd, "unmod"): return
    target = cmd.parameter.strip().lstrip('@')
    if not target:
        await send_and_log(cmd.room, "Usage: !unmod <username>")
        return
    if _is_owner_target(target):
        await send_and_log(cmd.room, f"We know, @{target} is a bit strange, but this request is impossible, fortunately it's my channel.")
        return
    try:
        broadcaster_id = await get_broadcaster_id()
        user_id = await get_user_id(target)
        if not user_id:
            await send_and_log(cmd.room, f"User '{target}' not found.")
            return
        await twitch_instance.remove_channel_moderator(broadcaster_id, user_id)
        await send_and_log(cmd.room, f"@{target} is no longer a Moderator.")
    except Exception as e:
        chat_print(f"{Color.GREY}API ERROR: {e}{Color.RESET}")
        await send_and_log(cmd.room, f"Failed to unmod {target}.")

async def cmd_ban(cmd: ChatCommand):
    if not await _check_mod_permission(cmd, "ban"): return
    target = cmd.parameter.strip().lstrip('@')
    if not target:
        await send_and_log(cmd.room, "Usage: !ban <username>")
        return
    if _is_owner_target(target):
        await send_and_log(cmd.room, f"We know, @{target} is a bit strange, but this request is impossible, fortunately it's my channel.")
        return
    try:
        broadcaster_id = await get_broadcaster_id()
        moderator_id = await get_authenticated_user_id()
        user_id = await get_user_id(target)
        if not user_id:
            await send_and_log(cmd.room, f"User '{target}' not found.")
            return
        await twitch_instance.ban_user(broadcaster_id, moderator_id, user_id, reason="Banned via bot command")
        await send_and_log(cmd.room, f"@{target} has been banned.")
    except Exception as e:
        chat_print(f"{Color.GREY}API ERROR: {e}{Color.RESET}")
        await send_and_log(cmd.room, f"Failed to ban {target}.")

async def cmd_unban(cmd: ChatCommand):
    if not await _check_mod_permission(cmd, "unban"): return
    target = cmd.parameter.strip().lstrip('@')
    if not target:
        await send_and_log(cmd.room, "Usage: !unban <username>")
        return
    if _is_owner_target(target):
        await send_and_log(cmd.room, f"We know, @{target} is a bit strange, but this request is impossible, fortunately it's my channel.")
        return
    try:
        broadcaster_id = await get_broadcaster_id()
        moderator_id = await get_authenticated_user_id()
        user_id = await get_user_id(target)
        if not user_id:
            await send_and_log(cmd.room, f"User '{target}' not found.")
            return
        await twitch_instance.unban_user(broadcaster_id, moderator_id, user_id)
        await send_and_log(cmd.room, f"@{target} has been unbanned.")
    except Exception as e:
        chat_print(f"{Color.GREY}API ERROR: {e}{Color.RESET}")
        await send_and_log(cmd.room, f"Failed to unban {target}.")

async def cmd_chatmode(cmd: ChatCommand):
    if not is_mod_or_owner(cmd.user):
        await send_and_log(cmd.room, f"Ok, ok... We noticed your effort to chatmode, but unfortunately you're not in the position to do so.")
        return
    mode = cmd.parameter.strip().lower()
    if mode not in ('followers', 'subs', 'all', ''):
        await send_and_log(cmd.room, "Usage: !chatmode <followers|subs|all>")
        return
    try:
        broadcaster_id = await get_broadcaster_id()
        moderator_id = await get_authenticated_user_id()
        if not mode:
            # Aktuellen Modus anzeigen
            settings = await twitch_instance.get_chat_settings(broadcaster_id)
            if settings.subscriber_mode:
                current = "subs"
            elif settings.follower_mode:
                current = "followers"
            else:
                current = "all"
            await send_and_log(cmd.room, f"Current chat mode: {current}")
        elif mode == 'followers':
            await twitch_instance.update_chat_settings(broadcaster_id, moderator_id, follower_mode=True, subscriber_mode=False)
            await send_and_log(cmd.room, "Chat mode set to: followers only")
        elif mode == 'subs':
            await twitch_instance.update_chat_settings(broadcaster_id, moderator_id, subscriber_mode=True, follower_mode=False)
            await send_and_log(cmd.room, "Chat mode set to: subscribers only")
        elif mode == 'all':
            await twitch_instance.update_chat_settings(broadcaster_id, moderator_id, follower_mode=False, subscriber_mode=False)
            await send_and_log(cmd.room, "Chat mode set to: everyone")
    except Exception as e:
        chat_print(f"{Color.GREY}API ERROR: {e}{Color.RESET}")
        await send_and_log(cmd.room, f"Failed to change chat mode.")

# --- SHOUTOUT COMMAND ---

async def cmd_shoutout(cmd: ChatCommand):
    if not await _check_mod_permission(cmd, "shoutout"): return
    target = cmd.parameter.strip().lstrip('@')
    if not target:
        await send_and_log(cmd.room, "Usage: !so <username>")
        return
    try:
        broadcaster_id = await get_broadcaster_id()
        moderator_id = await get_authenticated_user_id()
        target_id = await get_user_id(target)
        if not target_id:
            await send_and_log(cmd.room, f"User '{target}' not found.")
            return
        # Twitch native shoutout
        await twitch_instance.send_a_shoutout(broadcaster_id, moderator_id, target_id)
        # Chat message
        await send_and_log(cmd.room, f"Check out @{target}! Go give them a follow!")
        # Log
        ts = int(datetime.now().timestamp())
        log_write("shoutouts.csv", f"{ts},{target}")
        # Live files
        write_live_file('current-shoutout.txt', target)
        # Count today's shoutouts
        date_str = datetime.now().strftime('%Y-%m-%d')
        shoutout_path = os.path.join(LOG_DIR, f"{date_str}-shoutouts.csv")
        count = 0
        if os.path.exists(shoutout_path):
            with open(shoutout_path, 'r', encoding='utf-8') as f:
                count = sum(1 for line in f if line.strip())
        write_live_file('current-shoutout-count.txt', str(count))
    except Exception as e:
        chat_print(f"{Color.GREY}API ERROR: {e}{Color.RESET}")
        await send_and_log(cmd.room, f"Failed to shoutout {target}.")

# --- EVENTS ---

async def on_ready(ready_event: EventData):
    chat_print(f"{Color.GREY}--- SYSTEM: ONLINE (Logged in as {OWNER_NAME}) ---{Color.RESET}")
    # Initialize all live files as empty on startup
    live_files = [
        'current-poll-question.txt',
        'current-poll-a.txt', 'current-poll-b.txt', 'current-poll-c.txt', 'current-poll-d.txt',
        'current-poll-a-amount.txt', 'current-poll-b-amount.txt', 'current-poll-c-amount.txt', 'current-poll-d-amount.txt',
        'current-topic.txt',
        'current-title.txt',
        'current-suggestion.txt',
        'current-sub.txt',
        'current-unknown-commands.txt',
        'current-clip-count.txt',
        'current-shoutout.txt',
        'current-shoutout-count.txt',
    ]
    for lf in live_files:
        write_live_file(lf, '')
    chat_print(f"{Color.GREY}--- SYSTEM: All live files initialized ---{Color.RESET}")
    await ready_event.chat.join_room(TARGET_CHANNEL)
    # Set chat to followers-only on startup
    try:
        broadcaster_id = await get_broadcaster_id()
        moderator_id = await get_authenticated_user_id()
        await twitch_instance.update_chat_settings(broadcaster_id, moderator_id, follower_mode=True, subscriber_mode=False)
        chat_print(f"{Color.GREY}--- SYSTEM: Chat mode set to followers only ---{Color.RESET}")
    except Exception as e:
        chat_print(f"{Color.GREY}--- SYSTEM: Failed to set chat mode: {e} ---{Color.RESET}")
    await send_and_log(TARGET_CHANNEL, "Bot ready and listening! :)")

async def on_message(msg: ChatMessage):
    # Clean incoming message text first
    cleaned_text = clean_all_unwanted_parts(msg.text)

    chat_print(f"{Color.ORANGE}{msg.user.name}{Color.RESET}: {Color.WHITE}{cleaned_text}{Color.RESET}")
    ts = int(msg.sent_timestamp / 1000) if msg.sent_timestamp else 0
    csv_line = f'{ts},{msg.user.name},{msg.user.color or "#FFFFFF"},"{cleaned_text}"'
    log_write("messages.csv", csv_line, is_csv=True)

    for match in re.findall(r'(?:^|(?<=\s))!(\w+)', cleaned_text, re.UNICODE):
        if match.lower() == 'clip':
            track_clip(msg.user.name)
        else:
            result = track_unknown_command(match)
            if result and UNKNOWN_COMMANDS_FEEDBACK:
                cmd, count = result
                await send_and_log(msg.room, f"!{cmd} was counted, total: {count}")

    # Push to streaming software
    user_image = await get_user_image(msg.user.name)
    is_favorite = msg.user.mod or msg.user.subscriber or msg.user.name.lower() == OWNER_NAME
    await push_comment(msg.user.name, cleaned_text, userimageurl=user_image, favorite=is_favorite)

async def on_sub(sub: ChatSub):
    tier = "Tier 1"
    if sub.data.sub_plan == '2000': tier = "Tier 2"
    elif sub.data.sub_plan == '3000': tier = "Tier 3"
    elif sub.data.sub_plan == 'Prime': tier = "Prime"
    
    chat_print(f"{Color.YELLOW}NEW SUB! {sub.data.user_name} ({tier}){Color.RESET}")
    log_write("new-subs.txt", f"User: {sub.data.user_name} | {tier}")
    write_live_file('current-sub.txt', f"{sub.data.user_name} | {tier}")

# --- INPUT HANDLER ---

async def handle_bot_input(user_input: str):
    """Verarbeitet Bot-Input: Commands oder Chat-Messages"""
    # Input bereinigen (wie bei Chat-Messages)
    user_input = clean_all_unwanted_parts(user_input)

    if not user_input.strip():
        return

    # Erst: Deine Message IMMER in den Chat senden (ohne Bot-Prefix)
    await send_and_log(TARGET_CHANNEL, user_input, is_bot=False)

    # Dann: Wenn es ein Command ist, ausführen (Bot antwortet automatisch)
    if user_input.startswith('!'):
        parts = user_input[1:].split(' ', 1)
        cmd_name = parts[0].lower()
        param = parts[1] if len(parts) > 1 else ''

        # Fake Command Object
        class FakeCmd:
            def __init__(self):
                self.parameter = param
                self.room = TARGET_CHANNEL
                self.user = type('obj', (object,), {'name': OWNER_NAME, 'mod': True})()

        # Commands ausführen (Bot-Antworten kommen automatisch)
        if cmd_name == 'poll':
            await cmd_poll(FakeCmd())
        elif cmd_name == 'title':
            await cmd_title(FakeCmd())
        elif cmd_name == 'settoday':
            await cmd_set_today(FakeCmd())
        elif cmd_name == 'today':
            await cmd_today(FakeCmd())
        elif cmd_name == 'faq':
            await cmd_faq(FakeCmd())
        elif cmd_name == 'commands':
            await cmd_commands(FakeCmd())
        elif cmd_name == 'vip':
            await cmd_vip(FakeCmd())
        elif cmd_name == 'unvip':
            await cmd_unvip(FakeCmd())
        elif cmd_name == 'mod':
            await cmd_mod(FakeCmd())
        elif cmd_name == 'unmod':
            await cmd_unmod(FakeCmd())
        elif cmd_name == 'ban':
            await cmd_ban(FakeCmd())
        elif cmd_name == 'unban':
            await cmd_unban(FakeCmd())
        elif cmd_name == 'chatmode':
            await cmd_chatmode(FakeCmd())
        elif cmd_name in ('so', 'shoutout'):
            await cmd_shoutout(FakeCmd())
        elif cmd_name == 'clip':
            track_clip(OWNER_NAME)
        else:
            result = track_unknown_command(cmd_name)
            if result and UNKNOWN_COMMANDS_FEEDBACK:
                cmd, count = result
                await send_and_log(TARGET_CHANNEL, f"!{cmd} was counted, total: {count}")

async def input_loop():
    """Async Input-Loop für Bot-Eingaben"""
    global current_input
    import termios
    import tty
    import select

    # Terminal in raw mode setzen
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    # Initiale Input-Zeile zeichnen
    draw_input_line()

    try:
        tty.setraw(fd)

        while True:
            try:
                # Character-by-character lesen (non-blocking)
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    char = sys.stdin.read(1)

                    if char == '\r' or char == '\n':
                        # Enter gedrückt
                        user_input = current_input
                        current_input = ""

                        # Input verarbeiten (chat_print macht die Ausgabe)
                        await handle_bot_input(user_input)

                        # Input-Zeile neu zeichnen
                        draw_input_line()
                    elif char == '\x7f' or char == '\x08':
                        # Backspace
                        if current_input:
                            current_input = current_input[:-1]
                            draw_input_line()
                    elif char == '\x03':
                        # Ctrl+C
                        break
                    elif ord(char) >= 32:
                        # Printable character
                        current_input += char
                        draw_input_line()

                await asyncio.sleep(0.01)
            except (EOFError, KeyboardInterrupt):
                break
    finally:
        # Terminal zurücksetzen
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# --- MAIN ---

async def main():
    global chat_instance, twitch_instance
    clear_terminal()

    # Split-Screen einrichten
    setup_split_screen()

    # Resize-Handler registrieren
    signal.signal(signal.SIGWINCH, handle_resize)

    try:
        twitch_instance = await Twitch(APP_ID, APP_SECRET)
        token = None
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'r') as f:
                tdata = json.load(f)
                token = tdata.get('token')
                refresh_token = tdata.get('refresh_token')
        
        if not token:
            auth = UserAuthenticator(twitch_instance, USER_SCOPE)
            token, refresh_token = await auth.authenticate()
            with open(TOKEN_FILE, 'w') as f:
                json.dump({'token': token, 'refresh_token': refresh_token}, f)

        await twitch_instance.set_user_authentication(token, USER_SCOPE, refresh_token)
        
        chat_instance = await Chat(twitch_instance)
        chat_instance.set_prefix('!') 
        
        chat_instance.register_event(ChatEvent.READY, on_ready)
        chat_instance.register_event(ChatEvent.MESSAGE, on_message)
        chat_instance.register_event(ChatEvent.SUB, on_sub)

        # Commands registrieren
        chat_instance.register_command('today', cmd_today)
        chat_instance.register_command('setToday', cmd_set_today)
        chat_instance.register_command('faq', cmd_faq)
        chat_instance.register_command('commands', cmd_commands)
        chat_instance.register_command('suggest', cmd_suggest)
        chat_instance.register_command('poll', cmd_poll)
        chat_instance.register_command('title', cmd_title)
        for v in ['a', 'b', 'c', 'd']: chat_instance.register_command(v, cmd_vote)
        chat_instance.register_command('vip', cmd_vip)
        chat_instance.register_command('unvip', cmd_unvip)
        chat_instance.register_command('mod', cmd_mod)
        chat_instance.register_command('unmod', cmd_unmod)
        chat_instance.register_command('ban', cmd_ban)
        chat_instance.register_command('unban', cmd_unban)
        chat_instance.register_command('chatmode', cmd_chatmode)
        chat_instance.register_command('so', cmd_shoutout)
        chat_instance.register_command('shoutout', cmd_shoutout)

        chat_instance.start()

        # Starte Input-Loop parallel
        input_task = asyncio.create_task(input_loop())

        # Warte bis Input-Loop beendet wird
        await input_task

    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        # Cursor wieder anzeigen
        sys.stdout.write(f"{ANSI.SHOW_CURSOR}")
        # Scroll-Region zurücksetzen
        sys.stdout.write(f"\033[r")
        sys.stdout.flush()

        if chat_instance: chat_instance.stop()
        if twitch_instance: await twitch_instance.close()
        print(f"\n{Color.GREY}--- SYSTEM: Offline. Bye! ---{Color.RESET}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)