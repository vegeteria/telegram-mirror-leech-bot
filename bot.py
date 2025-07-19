import os
import time
import zipfile
import asyncio
import requests
import aiohttp
import uuid
import psutil
import shutil
import re
import json
import sys
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.custom import Button
from telethon.tl.types import KeyboardButtonUrl, DocumentAttributeFilename
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
from status_utils import get_readable_file_size, get_readable_time, get_progress_bar_string
from lxml.html import fromstring as HTML
from requests import Session as RSession
from hashlib import sha256
import base64
import shlex
from ytdlp import YoutubeDownloader
from telethon.errors.rpcerrorlist import MessageNotModifiedError
from status_utils import get_readable_file_size, get_readable_time, get_progress_bar_string
from telegram_uploader import LeechHandler

class DirectDownloadLinkException(Exception):
    """Custom exception for direct download link errors."""
    pass

def speed_string_to_bytes(size_str):
    """Converts a string with size units (e.g., '1.23 GB', '500 MB') to bytes."""
    size_str = size_str.strip()
    size_data = size_str.split()
    size_val = float(size_data[0])
    size_unit = size_data[1].upper()

    if 'KB' in size_unit:
        return size_val * 1024
    elif 'MB' in size_unit:
        return size_val * 1024 * 1024
    elif 'GB' in size_unit:
        return size_val * 1024 * 1024 * 1024
    elif 'TB' in size_unit:
        return size_val * 1024 * 1024 * 1024 * 1024
    else:
        return size_val

def buzzheavier(url):
    """
    Generate a direct download link for buzzheavier URLs.
    @param url: URL from buzzheavier
    @return: Direct download link or details for folders
    """
    pattern = r"^https?://buzzheavier\.com/[a-zA-Z0-9]+$"
    if not re.match(pattern, url):
        return url

    def _bhscraper(scrape_url, folder=False):
        with RSession() as session:
            if "/download" not in scrape_url:
                scrape_url += "/download"
            scrape_url = scrape_url.strip()
            session.headers.update(
                {
                    "referer": scrape_url.split("/download")[0],
                    "hx-current-url": scrape_url.split("/download")[0],
                    "hx-request": "true",
                    "priority": "u=1, i",
                }
            )
            try:
                response = session.get(scrape_url)
                d_url = response.headers.get("Hx-Redirect")
                if not d_url:
                    if not folder:
                        raise DirectDownloadLinkException("ERROR: Failed to get data")
                    return None
                return d_url
            except Exception as e:
                raise DirectDownloadLinkException(f"ERROR: {e}") from e

    with RSession() as session:
        response = session.get(url)
        response.raise_for_status()
        tree = HTML(response.text)

        if link := tree.xpath("//a[contains(@class, 'link-button') and contains(@class, 'gay-button')]/@hx-get"):
            return _bhscraper("https://buzzheavier.com" + link[0])
        
        if folders := tree.xpath("//tbody[@id='tbody']/tr"):
            details = {"contents": [], "title": "", "total_size": 0}
            title_element = tree.xpath("//span/text()")
            if title_element:
                details["title"] = title_element[0].strip()

            for data in folders:
                try:
                    filename_element = data.xpath(".//a")
                    if not filename_element: continue
                    filename = filename_element[0].text.strip()
                    _id = filename_element[0].attrib.get("href", "").strip()
                    
                    size_element = data.xpath(".//td[@class='text-center']/text()")
                    if not size_element: continue
                    size_str = size_element[0].strip()
                    
                    item_url = _bhscraper(f"https://buzzheavier.com{_id}", True)
                    if not item_url: continue

                    item = {
                        "path": "",
                        "filename": filename,
                        "url": item_url,
                    }
                    details["contents"].append(item)
                    size_in_bytes = speed_string_to_bytes(size_str)
                    details["total_size"] += size_in_bytes
                except Exception:
                    continue
            return details
        
        raise DirectDownloadLinkException("ERROR: No download link found")

def gofile(url):
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    PASSWORD_ERROR_MESSAGE = "The GoFile URL {} requires a password."
    try:
        if "::" in url:
            _password = url.split("::")[-1]
            _password = sha256(_password.encode("utf-8")).hexdigest()
            url = url.split("::")[-2]
        else:
            _password = ""
        _id = url.split("/")[-1]
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")

    def __get_token(session):
        headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        __url = "https://api.gofile.io/accounts"
        try:
            __res = session.post(__url, headers=headers).json()
            if __res["status"] != "ok":
                raise DirectDownloadLinkException("ERROR: Failed to get token.")
            return __res["data"]["token"]
        except Exception as e:
            raise e

    def __fetch_links(session, _id, folderPath=""):
        _url = f"https://api.gofile.io/contents/{_id}?wt=4fd6sg89d7s6&cache=true"
        headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "*/*",
            "Connection": "keep-alive",
            "Authorization": "Bearer" + " " + token,
        }
        if _password:
            _url += f"&password={_password}"
        try:
            _json = session.get(_url, headers=headers).json()
        except Exception as e:
            raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
        if _json["status"] in "error-passwordRequired":
            raise DirectDownloadLinkException(
                f"ERROR:\n{PASSWORD_ERROR_MESSAGE.format(url)}"
            )
        if _json["status"] in "error-passwordWrong":
            raise DirectDownloadLinkException("ERROR: This password is wrong !")
        if _json["status"] in "error-notFound":
            raise DirectDownloadLinkException(
                "ERROR: File not found on gofile's server"
            )
        if _json["status"] in "error-notPublic":
            raise DirectDownloadLinkException("ERROR: This folder is not public")

        data = _json["data"]

        if not details["title"]:
            details["title"] = data["name"] if data["type"] == "folder" else _id

        contents = data["children"]
        for content in contents.values():
            if content["type"] == "folder":
                if not content["public"]:
                    continue
                if not folderPath:
                    newFolderPath = os.path.join(details["title"], content["name"])
                else:
                    newFolderPath = os.path.join(folderPath, content["name"])
                __fetch_links(session, content["id"], newFolderPath)
            else:
                if not folderPath:
                    folderPath = details["title"]
                item = {
                    "path": folderPath,
                    "filename": content["name"],
                    "url": content["link"],
                }
                if "size" in content:
                    size = content["size"]
                    if isinstance(size, str) and size.isdigit():
                        size = float(size)
                    details["total_size"] += size
                details["contents"].append(item)

    details = {"contents": [], "title": "", "total_size": 0}
    with RSession() as session:
        try:
            token = __get_token(session)
        except Exception as e:
            raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")
        details["header"] = [f"Cookie: accountToken={token}"]
        try:
            __fetch_links(session, _id)
        except Exception as e:
            raise DirectDownloadLinkException(e)

    if len(details["contents"]) == 1:
        return (details["contents"][0]["url"], details["header"])
    return details

# Load environment variables from .env file
load_dotenv()


# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_SESSION_NAME = os.getenv('BOT_SESSION_NAME')
DOWNLOAD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
OWNER_ID = int(os.getenv('OWNER_ID'))
SUDO_USERS = [int(user_id) for user_id in os.getenv('SUDO_USERS', '').split(',') if user_id]
AUTHORISED_CHATS = [int(chat_id) for chat_id in os.getenv('AUTHORISED_CHATS', '').split(',') if chat_id]

if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# Initialize the Telethon client
client = TelegramClient(BOT_SESSION_NAME, API_ID, API_HASH)
main_loop = asyncio.get_event_loop()
bot_start_time = time.time()

# --- Authorization ---
def is_owner(user_id):
    return user_id == OWNER_ID

def is_sudo(user_id):
    return user_id in SUDO_USERS or is_owner(user_id)

def is_authorized(chat_id):
    return chat_id in AUTHORISED_CHATS or is_sudo(chat_id)

def authorized_users(func):
    async def wrapper(event):
        user_id = event.sender_id
        chat_id = event.chat_id
        if not (is_owner(user_id) or is_sudo(user_id) or is_authorized(chat_id)):
            await event.respond("You are not authorized to use this command.")
            return
        await func(event)
    return wrapper

def sudo_users(func):
    async def wrapper(event):
        user_id = event.sender_id
        if not is_sudo(user_id):
            await event.respond("This command is restricted to sudo users only.")
            return
        await func(event)
    return wrapper

def owner_only(func):
    async def wrapper(event):
        user_id = event.sender_id
        if not is_owner(user_id):
            await event.respond("This command is restricted to the owner only.")
            return
        await func(event)
    return wrapper

def update_env_file(key, value):
    with open('.env', 'r') as file:
        lines = file.readlines()

    with open('.env', 'w') as file:
        for line in lines:
            if line.startswith(key + '='):
                file.write(key + '=' + value + '\n')
            else:
                file.write(line)
# --- End Authorization ---


# Dictionary to store task information
tasks = {}
status_message_info = {}

async def send_status_message(chat_id, event_message=None):
    if chat_id in status_message_info:
        try:
            await status_message_info[chat_id]['message'].delete()
        except Exception:
            pass
        del status_message_info[chat_id]

    status_text, _ = await get_status_text()

    try:
        if event_message:
            new_status_message = await event_message.respond(status_text, parse_mode='md')
        else:
            new_status_message = await client.send_message(chat_id, status_text, parse_mode='md')
        
        status_message_info[chat_id] = {
            'message': new_status_message,
            'last_text': status_text
        }
    except Exception as e:
        print(f"Error sending status message to chat {chat_id}: {e}")

async def get_status_text():
    if not tasks:
        return "No active tasks.", True

    status_summary = "**Current Tasks:**\n\n"
    is_static = True

    for task_id, task_info in list(tasks.items()):
        progress_data = task_info.get('progress_data', {})
        task_status_text = ""
        
        action = progress_data.get('action', 'Initializing...')
        file_name = progress_data.get('file_name', '')
        uploader = task_info.get('uploader', '')

        if action in ["Download", "Upload", "Unzipping", "Zipping"]:
            is_static = False
            percent = progress_data.get('percent', 0)
            progress_bar = get_progress_bar_string(percent)
            task_status_text = (
                f"**{action}...**\n"
                f"**File:** `{file_name}`\n"
                f"**Task ID:** `{task_id}`\n"
                f"{progress_bar} {percent:.2f}%\n"
                f"**Size:** {get_readable_file_size(progress_data.get('current', 0))} / {get_readable_file_size(progress_data.get('total', 0))}\n"
                f"**Speed:** {get_readable_file_size(progress_data.get('speed', 0))}/S\n"
                f"**ETA:** {progress_data.get('eta', 'N/A')}\n"
                f"**Uploader:** {uploader}"
            )
        else:
            task_status_text = f"**Status:** {action}\n"
            if file_name:
                task_status_text += f"**File:** `{file_name}`\n"
            task_status_text += f"**Task ID:** `{task_id}`\n"
            task_status_text += f"**Uploader:** {uploader}"
        
        status_summary += task_status_text + "\n\n"

    return status_summary.strip(), is_static

async def update_all_status_messages():
    while True:
        await asyncio.sleep(2)
        
        if not tasks:
            if status_message_info:
                for chat_id, info in list(status_message_info.items()):
                    try:
                        await info['message'].edit("No active tasks.", parse_mode='md')
                    except Exception:
                        pass
                    del status_message_info[chat_id]
            continue

        status_summary, _ = await get_status_text()

        for chat_id, info in list(status_message_info.items()):
            if info.get('last_text') != status_summary:
                try:
                    await info['message'].edit(status_summary, parse_mode='md')
                    info['last_text'] = status_summary
                except Exception as e:
                    if "MESSAGE_ID_INVALID" in str(e) or "could not be found" in str(e):
                        del status_message_info[chat_id]
                    elif "Message not modified" not in str(e):
                        print(f"Error updating status in chat {chat_id}: {e}")


async def progress_callback(task_id, current, total, action, file_name, uploader, start_time):
    if task_id not in tasks or tasks[task_id].get('is_cancelled'):
        raise asyncio.CancelledError

    now = time.time()
    task_info = tasks[task_id]
    progress_data = task_info.setdefault('progress_data', {})

    elapsed = now - start_time
    if elapsed == 0:
        elapsed = 1

    speed = current / elapsed if elapsed > 0 else 0

    progress_data.update({
        'current': current,
        'total': total,
        'speed': speed,
        'percent': (current / total) * 100 if total > 0 else 0,
        'eta': get_readable_time(((total - current) / speed) if speed > 0 else None),
        'action': action,
        'file_name': file_name,
        'uploader': uploader,
        'start_time': start_time
    })

async def download_telegram_file(message, task_id, uploader):
    file_name = None
    if message.document:
        for attr in message.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                file_name = attr.file_name
                break
    if not file_name:
        file_name = getattr(message.file, 'name', None)
    
    if not file_name:
        ext = getattr(message.file, 'ext', '.dat')
        file_name = f"telegram_file_{task_id}{ext}"

    downloaded_file_path = os.path.join(DOWNLOAD_PATH, f"{task_id}_{file_name}")
    tasks[task_id]['downloaded_path'] = downloaded_file_path
    start_time = time.time()
    
    tasks[task_id]['progress_data'].update({'file_name': file_name, 'action': 'Download'})
    
    try:
        total_size = message.file.size
        
        async def progress(current, total):
            if tasks.get(task_id, {}).get('is_cancelled'):
                raise asyncio.CancelledError("Download cancelled by user.")
            await progress_callback(task_id, current, total, "Download", file_name, uploader, start_time)

        downloaded_file = await client.download_media(message.media, file=downloaded_file_path, progress_callback=progress)
        
        if not downloaded_file:
             raise Exception("File could not be downloaded (maybe it's empty or failed).")

        return downloaded_file_path, file_name, total_size
    except asyncio.CancelledError as e:
        if task_id in tasks:
            tasks[task_id]['progress_data']['action'] = "Download Cancelled"
        raise e
    except Exception as e:
        if task_id in tasks:
            tasks[task_id]['progress_data']['action'] = f"Download Error: {e}"
        return None, None, None

async def download_file(url, task_id, uploader):
    file_name = os.path.basename(url)
    downloaded_file_path = os.path.join(DOWNLOAD_PATH, f"{task_id}_{file_name}")
    tasks[task_id]['downloaded_path'] = downloaded_file_path
    start_time = time.time()
    
    tasks[task_id]['progress_data'].update({'file_name': file_name, 'action': 'Download'})
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                with open(downloaded_file_path, 'wb') as f:
                    downloaded_size = 0
                    async for chunk in response.content.iter_chunked(8192):
                        if tasks.get(task_id, {}).get('is_cancelled'):
                            raise asyncio.CancelledError
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            await progress_callback(task_id, downloaded_size, total_size, "Download", file_name, uploader, start_time)
        return downloaded_file_path, file_name, total_size
    except (aiohttp.ClientError, asyncio.CancelledError) as e:
        if task_id in tasks:
            if isinstance(e, asyncio.CancelledError):
                tasks[task_id]['progress_data']['action'] = "Download Cancelled"
            else:
                tasks[task_id]['progress_data']['action'] = f"Download Error: {e}"
        return None, None, None

def sync_upload_to_gofile(file_path, task_id, file_name, uploader, folder_id=None, api_key=None):
    try:
        get_server = requests.get('https://api.gofile.io/servers')
        get_server.raise_for_status()
        best_server = get_server.json()['data']['servers'][0]['name']
        upload_url = f'https://{best_server}.gofile.io/uploadFile'
    except Exception as e:
        print(f"Gofile: Could not get best server, falling back. Error: {e}")
        upload_url = 'https://upload.gofile.io/uploadFile'

    start_time = time.time()

    def progress_adapter(monitor):
        if tasks.get(task_id, {}).get('is_cancelled'):
            raise Exception("Upload cancelled by user.")
        
        future = asyncio.run_coroutine_threadsafe(
            progress_callback(task_id, monitor.bytes_read, monitor.len, "Upload", file_name, uploader, start_time),
            main_loop
        )
        future.result()

    with open(file_path, 'rb') as f:
        fields = {'file': (file_name, f, 'application/octet-stream')}
        if folder_id:
            fields['folderId'] = folder_id
        if api_key:
            fields['token'] = api_key
        
        encoder = MultipartEncoder(fields=fields)
        monitor = MultipartEncoderMonitor(encoder, progress_adapter)
        
        headers = {'Content-Type': monitor.content_type}
        
        upload_response = requests.post(upload_url, data=monitor, headers=headers)
        upload_response.raise_for_status()
        return upload_response.json()

def sync_upload_to_buzzheavier(file_path, task_id, file_name, uploader):
    upload_url = f"https://w.buzzheavier.com/{file_name}"
    start_time = time.time()

    def progress_adapter(monitor):
        if tasks.get(task_id, {}).get('is_cancelled'):
            raise Exception("Upload cancelled by user.")
        
        future = asyncio.run_coroutine_threadsafe(
            progress_callback(task_id, monitor.bytes_read, monitor.len, "Upload", file_name, uploader, start_time),
            main_loop
        )
        future.result()

    with open(file_path, 'rb') as f:
        encoder = MultipartEncoder(fields={'file': (file_name, f, 'application/octet-stream')})
        monitor = MultipartEncoderMonitor(encoder, progress_adapter)
        
        upload_response = requests.put(upload_url, data=monitor, headers={'Content-Type': monitor.content_type})
        upload_response.raise_for_status()
        return upload_response.json()

def sync_upload_to_pixeldrain(file_path, task_id, file_name, uploader, api_key=None):
    upload_url = "https://pixeldrain.com/api/file"
    start_time = time.time()

    def progress_adapter(monitor):
        if tasks.get(task_id, {}).get('is_cancelled'):
            raise Exception("Upload cancelled by user.")
        
        future = asyncio.run_coroutine_threadsafe(
            progress_callback(task_id, monitor.bytes_read, monitor.len, "Upload", file_name, uploader, start_time),
            main_loop
        )
        future.result()

    with open(file_path, 'rb') as f:
        encoder = MultipartEncoder(fields={'file': (file_name, f, 'application/octet-stream')})
        monitor = MultipartEncoderMonitor(encoder, progress_adapter)
        
        headers = {'Content-Type': monitor.content_type}
        if api_key:
            auth_str = f":{api_key}"
            auth_bytes = auth_str.encode("utf-8")
            auth_b64 = base64.b64encode(auth_bytes).decode("utf-8")
            headers['Authorization'] = f"Basic {auth_b64}"

        upload_response = requests.post(upload_url, data=monitor, headers=headers)
        upload_response.raise_for_status()
        return upload_response.json()

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond('Hi! I am a mirror and leech bot. Send /help for more info.')
    raise events.StopPropagation

@client.on(events.NewMessage(pattern='/help'))
async def help_command(event):
    user_id = event.sender_id
    help_text = "Here are the available commands:\n\n"
    help_text += "/leech - Leech a file or link\n"
    help_text += "/mirror - Mirror a file or link\n"
    help_text += "/zipmirror - Zip and mirror a file or link\n"
    help_text += "/unzipmirror - Unzip and mirror a file or link\n"
    help_text += "/ytdlp - Download a video from a URL\n"
    help_text += "/status - Show the status of all tasks\n"
    help_text += "/stats - Show bot statistics\n"
    help_text += "/stop - Stop a task\n"
    help_text += "/ping - Check the bot's latency\n"

    if is_sudo(user_id):
        help_text += "\n**Sudo Commands:**\n"
        help_text += "/authorize - Authorize a chat\n"
        help_text += "/unauthorize - Unauthorize a chat\n"
        help_text += "/restart - Restart the bot\n"

    if is_owner(user_id):
        help_text += "\n**Owner Commands:**\n"
        help_text += "/addsudo - Add a sudo user\n"
        help_text += "/rmsudo - Remove a sudo user\n"

    await event.respond(help_text)

@client.on(events.NewMessage(pattern='/addsudo'))
@owner_only
async def addsudo_command(event):
    if len(event.message.text.split()) == 1:
        await event.respond("Please provide a user ID. Usage: /addsudo <user_id>")
        return
    
    user_id_to_add = int(event.message.text.split()[1])
    if user_id_to_add in SUDO_USERS:
        await event.respond(f"User `{user_id_to_add}` is already a sudo user.")
        return

    SUDO_USERS.append(user_id_to_add)
    update_env_file('SUDO_USERS', ','.join(map(str, SUDO_USERS)))
    await event.respond(f"User `{user_id_to_add}` has been added as a sudo user.")

@client.on(events.NewMessage(pattern='/rmsudo'))
@owner_only
async def rmsudo_command(event):
    if len(event.message.text.split()) == 1:
        await event.respond("Please provide a user ID. Usage: /rmsudo <user_id>")
        return

    user_id_to_remove = int(event.message.text.split()[1])
    if user_id_to_remove not in SUDO_USERS:
        await event.respond(f"User `{user_id_to_remove}` is not a sudo user.")
        return

    SUDO_USERS.remove(user_id_to_remove)
    update_env_file('SUDO_USERS', ','.join(map(str, SUDO_USERS)))
    await event.respond(f"User `{user_id_to_remove}` has been removed as a sudo user.")

@client.on(events.NewMessage(pattern='/authorize'))
@sudo_users
async def authorize_command(event):
    if len(event.message.text.split()) == 1:
        await event.respond("Please provide a chat ID. Usage: /authorize <chat_id>")
        return

    chat_id_to_add = int(event.message.text.split()[1])
    if chat_id_to_add in AUTHORISED_CHATS:
        await event.respond(f"Chat `{chat_id_to_add}` is already authorized.")
        return

    AUTHORISED_CHATS.append(chat_id_to_add)
    update_env_file('AUTHORISED_CHATS', ','.join(map(str, AUTHORISED_CHATS)))
    await event.respond(f"Chat `{chat_id_to_add}` has been authorized.")

@client.on(events.NewMessage(pattern='/unauthorize'))
@sudo_users
async def unauthorize_command(event):
    if len(event.message.text.split()) == 1:
        await event.respond("Please provide a chat ID. Usage: /unauthorize <chat_id>")
        return

    chat_id_to_remove = int(event.message.text.split()[1])
    if chat_id_to_remove not in AUTHORISED_CHATS:
        await event.respond(f"Chat `{chat_id_to_remove}` is not authorized.")
        return

    AUTHORISED_CHATS.remove(chat_id_to_remove)
    update_env_file('AUTHORISED_CHATS', ','.join(map(str, AUTHORISED_CHATS)))
    await event.respond(f"Chat `{chat_id_to_remove}` has been unauthorized.")

async def _cleanup_task_files(task_id):
    task_info = tasks.get(task_id, {})
    download_path = task_info.get('downloaded_path')
    zip_path = task_info.get('zip_path')
    unzip_path = task_info.get('unzip_path')
    download_dir = task_info.get('download_dir')

    if download_path and os.path.exists(download_path):
        os.remove(download_path)
    if zip_path and os.path.exists(zip_path):
        os.remove(zip_path)
    if unzip_path and os.path.exists(unzip_path):
        shutil.rmtree(unzip_path)
    if download_dir and os.path.exists(download_dir):
        shutil.rmtree(download_dir)

async def _unzip_mirror_worker(event, source, task_id, uploader, reply_to_msg, password=None, uploader_choice='gofile'):
    try:
        if isinstance(source, str):
            downloaded_file_path, file_name, _ = await download_file(source, task_id, uploader)
        else:
            downloaded_file_path, file_name, _ = await download_telegram_file(source, task_id, uploader)

        if not downloaded_file_path:
            return

        tasks[task_id]['progress_data']['action'] = "Unzipping"
        unzip_path = downloaded_file_path.rsplit('.', 1)[0]
        tasks[task_id]['unzip_path'] = unzip_path
        os.makedirs(unzip_path, exist_ok=True)

        command = ['7z', 'x', f'-o{unzip_path}', downloaded_file_path]
        if password:
            command.append(f'-p{password}')

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_message = stderr.decode().strip()
            if "Wrong password" in error_message:
                await client.send_message(event.chat_id, "The provided password for the ZIP file is incorrect.", reply_to=reply_to_msg)
            else:
                await client.send_message(event.chat_id, f"Failed to extract the archive. Error: {error_message}", reply_to=reply_to_msg)
            return

        tasks[task_id]['progress_data']['action'] = "Uploading"

        files_to_upload = []
        for root, _, files in os.walk(unzip_path):
            for f in files:
                files_to_upload.append(os.path.join(root, f))

        if uploader_choice == 'gofile':
            gofile_api_key = os.getenv('GOFILE_API_KEY')
            if not gofile_api_key:
                raise Exception("GOFILE_API_KEY not found in environment for authenticated upload.")

            folder_id = None
            first_upload = True
            gofile_link = None

            for file_path in files_to_upload:
                upload_response = await asyncio.to_thread(sync_upload_to_gofile, file_path, task_id, os.path.basename(file_path), uploader, folder_id, gofile_api_key)
                if first_upload:
                    if upload_response.get('status') == 'ok':
                        folder_id = upload_response['data']['parentFolder']
                        gofile_link = upload_response['data']['downloadPage']
                        first_upload = False
                    else:
                        error_message = upload_response.get('status', 'Unknown error')
                        raise Exception(f"Gofile upload failed: {error_message}")

            message_text = f"**Unzip and upload successful!**"
            await client.send_message(
                event.chat_id,
                message_text,
                buttons=[[KeyboardButtonUrl("View Folder", gofile_link)]],
                parse_mode='md',
                reply_to=reply_to_msg
            )
        elif uploader_choice == 'pixeldrain':
            pixeldrain_api_key = os.getenv('PIXELDRAIN_API_KEY')
            uploaded_files_info = []
            for file_path in files_to_upload:
                upload_response = await asyncio.to_thread(sync_upload_to_pixeldrain, file_path, task_id, os.path.basename(file_path), uploader, pixeldrain_api_key)
                if upload_response.get('success'):
                    file_id = upload_response.get('id')
                    file_name = os.path.basename(file_path)
                    file_size = get_readable_file_size(os.path.getsize(file_path))
                    direct_download_link = f"https://pixeldrain.com/api/file/{file_id}"
                    
                    file_info = (
                        f"**File:** `{file_name}`\n"
                        f"**Size:** {file_size}\n"
                        f"**Link:** {direct_download_link}"
                    )
                    uploaded_files_info.append(file_info)
                else:
                    error_message = upload_response.get('message', 'Unknown error')
                    await client.send_message(event.chat_id, f"Pixeldrain upload failed for `{os.path.basename(file_path)}`: {error_message}", reply_to=reply_to_msg)
            
            if uploaded_files_info:
                message_text = "**Unzip and upload to Pixeldrain successful!**\n\n" + "\n\n".join(uploaded_files_info)
                await client.send_message(
                    event.chat_id,
                    message_text,
                    parse_mode='md',
                    reply_to=reply_to_msg
                )

    except Exception as e:
        if task_id in tasks:
            tasks[task_id]['progress_data']['action'] = f"Error: {e}"
        await client.send_message(event.chat_id, f"An error occurred: {e}", reply_to=reply_to_msg)
    finally:
        await _cleanup_task_files(task_id)
        if task_id in tasks:
            if tasks[task_id].get('is_cancelled'):
                await asyncio.sleep(10)
            del tasks[task_id]


async def _mirror_upload_worker(event, source, is_zip, task_id, uploader, uploader_choice, reply_to_msg, downloaded_file_path=None):
    try:
        if not downloaded_file_path:
            if isinstance(source, str):
                downloaded_file_path, file_name, _ = await download_file(source, task_id, uploader)
            else:
                downloaded_file_path, file_name, _ = await download_telegram_file(source, task_id, uploader)
            
            if not downloaded_file_path:
                return
        else:
            file_name = os.path.basename(downloaded_file_path)

        file_to_upload = downloaded_file_path
        original_file_name = file_name
        
        if is_zip:
            tasks[task_id]['progress_data']['action'] = "Zipping..."
            zip_file_path = downloaded_file_path + ".zip"
            tasks[task_id]['zip_path'] = zip_file_path
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(downloaded_file_path, original_file_name)
            file_to_upload = zip_file_path
            file_name += ".zip"
            tasks[task_id]['progress_data']['file_name'] = file_name
        
        tasks[task_id]['progress_data']['action'] = "Starting Upload..."

        if uploader_choice == 'buzz':
            upload_response = await asyncio.to_thread(sync_upload_to_buzzheavier, file_to_upload, task_id, file_name, uploader)
            
            response_data = upload_response.get('data', {})
            if response_data.get('id'):
                file_id = response_data['id']
                file_name_from_api = response_data.get('name', os.path.basename(file_to_upload))
                expiry_str = response_data.get('expiry')
                buzzheavier_page_link = f"https://buzzheavier.com/{file_id}"
                direct_download_link = buzzheavier(buzzheavier_page_link)

                expiry_formatted = ""
                if expiry_str:
                    try:
                        expiry_dt = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                        expiry_formatted = f"Expires on: {expiry_dt.strftime('%B %d, %Y, at %I:%M %p UTC')}"
                    except (ValueError, TypeError):
                        expiry_formatted = f"Expires on: {expiry_str}"

                message_text = f"**Upload successful!**\n\n**File:** `{file_name_from_api}`\n{expiry_formatted}"
                
                buttons = [
                    [KeyboardButtonUrl("Download Page", buzzheavier_page_link)],
                    [KeyboardButtonUrl("Direct Download Link", direct_download_link)]
                ]

                await client.send_message(
                    event.chat_id,
                    message_text,
                    buttons=buttons,
                    parse_mode='md',
                    reply_to=reply_to_msg
                )
            else:
                await client.send_message(event.chat_id, "Buzzheavier upload failed or could not retrieve the download link.", reply_to=reply_to_msg)
        
        elif uploader_choice == 'gofile':
            upload_response = await asyncio.to_thread(sync_upload_to_gofile, file_to_upload, task_id, file_name, uploader)
            response_data = upload_response.get('data', {})
            if upload_response.get('status') == 'ok' and response_data.get('downloadPage'):
                gofile_link = response_data['downloadPage']
                file_name_from_api = response_data.get('name', os.path.basename(file_to_upload))
                
                message_text = f"**Upload successful!**\n\n**File:** `{file_name_from_api}`"
                
                direct_download_link = None
                try:
                    gofile_result = await asyncio.to_thread(gofile, gofile_link)
                    if isinstance(gofile_result, tuple):
                        direct_download_link = gofile_result[0]
                except Exception as e:
                    print(f"Could not get gofile direct link: {e}")

                buttons = [[KeyboardButtonUrl("Download Page", gofile_link)]]
                if direct_download_link:
                    buttons.append([KeyboardButtonUrl("Direct Download", direct_download_link)])

                await client.send_message(
                    event.chat_id,
                    message_text,
                    buttons=buttons,
                    parse_mode='md',
                    reply_to=reply_to_msg
                )
            else:
                error_message = upload_response.get('status', 'Unknown error')
                await client.send_message(event.chat_id, f"Gofile upload failed: {error_message}", reply_to=reply_to_msg)

        elif uploader_choice == 'pixeldrain':
            pixeldrain_api_key = os.getenv('PIXELDRAIN_API_KEY')
            upload_response = await asyncio.to_thread(sync_upload_to_pixeldrain, file_to_upload, task_id, file_name, uploader, pixeldrain_api_key)
            if upload_response.get('success'):
                file_id = upload_response.get('id')
                pixeldrain_page_link = f"https://pixeldrain.com/u/{file_id}"
                direct_download_link = f"https://pixeldrain.com/api/file/{file_id}"
                message_text = f"**Upload successful!**\n\n**File:** `{file_name}`"
                
                buttons = [
                    [KeyboardButtonUrl("Download Page", pixeldrain_page_link)],
                    [KeyboardButtonUrl("Direct Download", direct_download_link)]
                ]

                await client.send_message(
                    event.chat_id,
                    message_text,
                    buttons=buttons,
                    parse_mode='md',
                    reply_to=reply_to_msg
                )
            else:
                error_message = upload_response.get('message', 'Unknown error')
                await client.send_message(event.chat_id, f"Pixeldrain upload failed: {error_message}", reply_to=reply_to_msg)

    except asyncio.CancelledError:
        if task_id in tasks:
            tasks[task_id]['progress_data']['action'] = "Cancelled by user."
    except Exception as e:
        if task_id in tasks:
            tasks[task_id]['progress_data']['action'] = f"Error: {e}"
        await client.send_message(event.chat_id, f"An error occurred: {e}", reply_to=reply_to_msg)
    finally:
        await _cleanup_task_files(task_id)
        if task_id in tasks:
            if tasks[task_id].get('is_cancelled'):
                await asyncio.sleep(10)
            del tasks[task_id]

async def handle_mirror_upload(event, source, is_zip, uploader_choice, reply_to_msg):
    task_id = str(uuid.uuid4())
    uploader = f"[{event.sender.first_name}](tg://user?id={event.sender.id})"
    
    task = asyncio.create_task(_mirror_upload_worker(event, source, is_zip, task_id, uploader, uploader_choice, reply_to_msg))
    tasks[task_id] = {
        'uploader': uploader, 
        'progress_data': {'action': 'Initializing...'},
        'async_task': task,
        'is_cancelled': False,
        'chat_id': event.chat_id
    }
    await send_status_message(event.chat_id, event_message=reply_to_msg)

async def handle_unzip_mirror(event, source, reply_to_msg, uploader_choice, password=None):
    task_id = str(uuid.uuid4())
    uploader = f"[{event.sender.first_name}](tg://user?id={event.sender.id})"
    
    task = asyncio.create_task(_unzip_mirror_worker(event, source, task_id, uploader, reply_to_msg, password, uploader_choice))
    tasks[task_id] = {
        'uploader': uploader, 
        'progress_data': {'action': 'Initializing...'},
        'async_task': task,
        'is_cancelled': False,
        'chat_id': event.chat_id
    }
    await send_status_message(event.chat_id, event_message=reply_to_msg)

leech_handler = LeechHandler(client, tasks, progress_callback, download_file, download_telegram_file, _cleanup_task_files)

@client.on(events.NewMessage(pattern='/leech'))
@authorized_users
async def leech_command(event):
    replied_message = await event.get_reply_message()
    is_link = len(event.message.text.split()) > 1
    is_file = replied_message and replied_message.file

    if not is_link and not is_file:
        await event.respond("Please provide a direct download link or reply to a file with /leech.")
        return

    source = None
    if is_file:
        source = replied_message
    else:
        source = event.message.text.split()[1]

    task_id = str(uuid.uuid4())
    uploader = f"[{event.sender.first_name}](tg://user?id={event.sender.id})"
    
    task = asyncio.create_task(leech_handler.leech_worker(event, source, task_id, uploader, event.message))
    tasks[task_id] = {
        'uploader': uploader, 
        'progress_data': {'action': 'Initializing...'},
        'async_task': task,
        'is_cancelled': False,
        'chat_id': event.chat_id
    }
    await send_status_message(event.chat_id, event_message=event.message)

@client.on(events.NewMessage(pattern='/mirror'))
@authorized_users
async def mirror_command(event):
    replied_message = await event.get_reply_message()
    is_link = len(event.message.text.split()) > 1
    is_file = replied_message and replied_message.file

    if not is_link and not is_file:
        await event.respond("Please provide a direct download link or reply to a file with /mirror.")
        return
    
    buttons = [
        [
            Button.inline("Buzzheavier", data=b"mirror_buzz"),
            Button.inline("Gofile", data=b"mirror_gofile"),
            Button.inline("Pixeldrain", data=b"mirror_pixeldrain")
        ]
    ]
    await event.respond("Choose upload destination:", buttons=buttons, reply_to=event.message)

@client.on(events.NewMessage(pattern='/zipmirror'))
@authorized_users
async def zipmirror_command(event):
    replied_message = await event.get_reply_message()
    is_link = len(event.message.text.split()) > 1
    is_file = replied_message and replied_message.file

    if not is_link and not is_file:
        await event.respond("Please provide a direct download link or reply to a file with /zipmirror.")
        return
    
    buttons = [
        [
            Button.inline("Buzzheavier", data=b"zipmirror_buzz"),
            Button.inline("Gofile", data=b"zipmirror_gofile"),
            Button.inline("Pixeldrain", data=b"zipmirror_pixeldrain")
        ]
    ]
    await event.respond("Choose upload destination:", buttons=buttons, reply_to=event.message)

@client.on(events.NewMessage(pattern='/unzipmirror'))
@authorized_users
async def unzipmirror_command(event):
    replied_message = await event.get_reply_message()
    parts = event.message.text.split()
    is_link = any(re.match(r'https?://', p) for p in parts)
    is_file = replied_message and replied_message.file

    if not is_link and not is_file:
        help_text = """**How to use /unzipmirror:**

**With a direct link:**
• `/unzipmirror <link>`
• `/unzipmirror <password> <link>` (for password-protected files)

**By replying to a file:**
• Reply to a file with `/unzipmirror`
• Reply to a password-protected file with `/unzipmirror <password>`"""
        await event.respond(help_text, parse_mode='md')
        return
    
    buttons = [
        [
            Button.inline("Gofile", data=b"unzipmirror_gofile"),
            Button.inline("Pixeldrain", data=b"unzipmirror_pixeldrain")
        ]
    ]
    await event.respond("Choose upload destination for extracted files:", buttons=buttons, reply_to=event.message)

@client.on(events.CallbackQuery(pattern=b'^(zip|unzip)?mirror_'))
async def on_upload_choice(event):
    await event.answer()
    
    original_message = await event.get_message()
    command_message = await original_message.get_reply_message()
    
    if not command_message:
        await event.edit("Error: Could not find the original command message to process.")
        return

    file_message = await command_message.get_reply_message()
    is_file_download = file_message and file_message.file

    source = None
    password = None
    parts = command_message.text.split()

    if is_file_download:
        source = file_message
        if len(parts) > 1:
            password = parts[1]
    else:
        # This logic assumes the link is the last element, and a password might precede it.
        if len(parts) > 2:
            password = parts[1]
            source = parts[2]
        elif len(parts) > 1:
            source = parts[1]
        else:
            await event.edit("Error: The original message does not contain a link or a file to process.")
            return

    if not source:
        await event.edit("Error: Could not determine the source to download.")
        return

    data = event.data.decode('utf-8')
    command_parts = data.split('_')
    command = command_parts[0]
    uploader_choice = command_parts[1]
    
    await original_message.delete()

    if command == 'unzipmirror':
        asyncio.create_task(handle_unzip_mirror(event, source, command_message, uploader_choice, password))
    else:
        is_zip = command == 'zipmirror'
        asyncio.create_task(handle_mirror_upload(event, source, is_zip, uploader_choice, command_message))

@client.on(events.NewMessage(pattern='/status'))
@authorized_users
async def status_command(event):
    await send_status_message(event.chat_id, event_message=event.message)

@client.on(events.NewMessage(pattern='/stats'))
@authorized_users
async def stats_command(event):
    total, used, free, disk = psutil.disk_usage("/")
    swap = psutil.swap_memory()
    memory = psutil.virtual_memory()
    stats = f"""
<b>Bot Uptime:</b> {get_readable_time(time.time() - bot_start_time)}
<b>OS Uptime:</b> {get_readable_time(time.time() - psutil.boot_time())}

<b>Total Disk Space:</b> {get_readable_file_size(total)}
<b>Used:</b> {get_readable_file_size(used)} | <b>Free:</b> {get_readable_file_size(free)}

<b>Upload:</b> {get_readable_file_size(psutil.net_io_counters().bytes_sent)}
<b>Download:</b> {get_readable_file_size(psutil.net_io_counters().bytes_recv)}

<b>CPU:</b> {psutil.cpu_percent(interval=0.5)}%
<b>RAM:</b> {memory.percent}%
<b>DISK:</b> {disk}%

<b>Physical Cores:</b> {psutil.cpu_count(logical=False)}
<b>Total Cores:</b> {psutil.cpu_count(logical=True)}
<b>SWAP:</b> {get_readable_file_size(swap.total)} | <b>Used:</b> {swap.percent}%

<b>Memory Total:</b> {get_readable_file_size(memory.total)}
<b>Memory Free:</b> {get_readable_file_size(memory.available)}
<b>Memory Used:</b> {get_readable_file_size(memory.used)}
"""
    await event.respond(stats, parse_mode='html')


@client.on(events.NewMessage(pattern='/stop'))
@authorized_users
async def stop_command(event):
    if len(event.message.text.split()) == 1:
        await event.respond("Please provide a task ID. Usage: /stop <task_id>")
        return
    
    task_id_to_stop = event.message.text.split()[1]
    
    if task_id_to_stop not in tasks:
        await event.respond(f"Task with ID `{task_id_to_stop}` not found.")
        return

    task_info = tasks[task_id_to_stop]
    if task_info.get('is_cancelled'):
        await event.respond(f"Task `{task_id_to_stop}` is already being cancelled.")
        return

    task_info['is_cancelled'] = True
    task_info['progress_data']['action'] = "Cancelling..."
    
    if 'async_task' in task_info and task_info['async_task']:
        task_info['async_task'].cancel()
    
    await event.respond(f"Cancellation request sent for task `{task_id_to_stop}`.")
    await send_status_message(task_info['chat_id'])


@client.on(events.NewMessage(pattern='/ping'))
async def ping_command(event):
    ping_message = await event.respond('Pinging...')
    
    for i in range(5):
        start_time = datetime.now()
        # A lightweight API call to measure round-trip latency
        await event.client.get_me()
        end_time = datetime.now()
        latency = (end_time - start_time).total_seconds() * 1000
        
        try:
            await ping_message.edit(f"**Ping:** `{latency:.2f} ms`")
        except telethon.errors.rpcerrorlist.MessageNotModifiedError:
            # Ignore if the latency is the same as the previous one
            pass
            
        if i < 4:
            await asyncio.sleep(1)


@client.on(events.NewMessage(pattern='/restart'))
@sudo_users
async def restart_command(event):
    await event.respond("Bot is restarting... All tasks will be cancelled.")

    # Cancel all tasks
    for task_id, task_info in list(tasks.items()):
        if not task_info.get('is_cancelled'):
            task_info['is_cancelled'] = True
            task_info['progress_data']['action'] = "Cancelled due to restart."
            if 'async_task' in task_info and task_info['async_task']:
                task_info['async_task'].cancel()

    # Give a moment for tasks to cancel
    await asyncio.sleep(2)

    # Restart the bot
    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        await event.respond(f"Failed to restart bot: {e}")


async def _ytdlp_download_worker(event, task_id, uploader, url, quality, is_leech, uploader_choice, is_zip, cookie_path=None):
    class YtdlpListener:
        def __init__(self, task_id, uploader):
            self.task_id = task_id
            self.uploader = uploader
            self.start_time = time.time()
            self.downloaded_path = None

        def on_download_start(self):
            tasks[self.task_id]['progress_data'].update({'action': 'Download', 'file_name': 'N/A'})

        def on_download_progress(self, d):
            file_name = os.path.basename(d.get('filename', 'N/A'))
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded_bytes = d.get('downloaded_bytes', 0)
            
            main_loop.create_task(progress_callback(
                self.task_id, downloaded_bytes, total_bytes, "Download", file_name, self.uploader, self.start_time
            ))

        def on_download_finished(self):
            pass

        def on_download_complete(self, path):
            self.downloaded_path = path

        def on_download_error(self, error):
            if self.task_id in tasks:
                tasks[self.task_id]['progress_data']['action'] = f"Error: {error}"

    try:
        listener = YtdlpListener(task_id, uploader)
        downloader = YoutubeDownloader(listener)
        
        download_path = os.path.join(DOWNLOAD_PATH, task_id)
        os.makedirs(download_path, exist_ok=True)
        if task_id in tasks:
            tasks[task_id]['download_dir'] = download_path

        download_opts = {}
        if cookie_path:
            download_opts['cookiefile'] = cookie_path

        downloaded_file = await asyncio.to_thread(downloader.download, url, download_path, quality, options=download_opts)

        if not downloaded_file:
            if task_id in tasks and not tasks[task_id]['progress_data'].get('action', '').startswith("Error"):
                tasks[task_id]['progress_data']['action'] = "Error: Download failed."
            return

        if is_leech:
            await leech_handler.leech_worker(event, url, task_id, uploader, event.message, downloaded_file_path=downloaded_file)
        else:
            await _mirror_upload_worker(event, url, is_zip, task_id, uploader, uploader_choice, event.message, downloaded_file_path=downloaded_file)

    except Exception as e:
        if task_id in tasks:
            tasks[task_id]['progress_data']['action'] = f"Error: {e}"
    finally:
        if cookie_path and os.path.exists(cookie_path):
            os.remove(cookie_path)

qualities = {
    "best": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "audio": "bestaudio/best"
}

@client.on(events.NewMessage(pattern='/ytdlp'))
@authorized_users
async def ytdlp_command(event):
    if len(event.message.text.split()) < 2:
        await event.respond("Usage: /ytdlp <url> or reply to a cookies.txt file with /ytdlp <url>")
        return

    url = event.message.text.split(maxsplit=1)[1]
    
    cookie_path = None
    replied_message = await event.get_reply_message()
    if replied_message and replied_message.document:
        for attr in replied_message.document.attributes:
            if isinstance(attr, DocumentAttributeFilename) and attr.file_name.lower() == 'cookies.txt':
                cookie_path = os.path.join(DOWNLOAD_PATH, f"cookies_{event.sender_id}.txt")
                await replied_message.download_media(file=cookie_path)
                break

    try:
        downloader = YoutubeDownloader(None)
        info = await asyncio.to_thread(downloader.extract_info, url, {'playlist_items': '0'})
        if not info:
            await event.respond("Could not extract video info. The link might be invalid or private.")
            if cookie_path and os.path.exists(cookie_path):
                os.remove(cookie_path)
            return

        request_id = uuid.uuid4().hex[:8]
        ytdlp_requests[request_id] = {'url': url, 'event': event, 'cookie_path': cookie_path}

        buttons = []
        for q_name, q_key in {"Best": "best", "1080p": "1080p", "720p": "720p", "480p": "480p", "360p": "360p", "Audio Only": "audio"}.items():
            buttons.append(Button.inline(q_name, data=f"ytq_{q_key}_{request_id}".encode()))

        button_grid = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
        button_grid.append([Button.inline("Cancel", data=f"ytq_cancel_{request_id}".encode())])
        
        await event.respond("Choose video quality:", buttons=button_grid)

    except Exception as e:
        await event.respond(f"An error occurred: {e}")
        if cookie_path and os.path.exists(cookie_path):
            os.remove(cookie_path)

ytdlp_requests = {}

@client.on(events.CallbackQuery(pattern=b"ytq_"))
async def on_ytdlp_quality_choice(event):
    data_parts = event.data.decode().split('_')
    quality_key = data_parts[1]
    request_id = data_parts[2]

    if request_id not in ytdlp_requests:
        await event.answer("This request has expired.", alert=True)
        return

    if quality_key == "cancel":
        del ytdlp_requests[request_id]
        await event.edit("Task cancelled.")
        return
    
    quality = qualities.get(quality_key)
    if not quality:
        await event.answer("Invalid quality selection.", alert=True)
        return

    ytdlp_requests[request_id]['quality'] = quality

    buttons = [
        [
            Button.inline("Leech", data=f"ytu_leech_{request_id}".encode()),
            Button.inline("Gofile", data=f"ytu_gofile_{request_id}".encode())
        ],
        [
            Button.inline("Buzzheavier", data=f"ytu_buzz_{request_id}".encode()),
            Button.inline("Pixeldrain", data=f"ytu_pixeldrain_{request_id}".encode())
        ],
        [
            Button.inline("Cancel", data=f"ytu_cancel_{request_id}".encode())
        ]
    ]
    
    await event.edit("Choose upload destination:", buttons=buttons)

@client.on(events.CallbackQuery(pattern=b"ytu_"))
async def on_ytdlp_upload_choice(event):
    data_parts = event.data.decode().split('_')
    uploader_choice = data_parts[1]
    request_id = data_parts[2]

    if request_id not in ytdlp_requests:
        await event.answer("This request has expired.", alert=True)
        return

    request_data = ytdlp_requests.pop(request_id)
    original_event = request_data['event']
    url = request_data['url']
    quality = request_data['quality']
    cookie_path = request_data.get('cookie_path')

    if uploader_choice == "cancel":
        if cookie_path and os.path.exists(cookie_path):
            os.remove(cookie_path)
        await event.edit("Task cancelled.")
        return
        
    await event.edit(f"Starting download...")

    task_id = str(uuid.uuid4())
    uploader = f"[{original_event.sender.first_name}](tg://user?id={original_event.sender.id})"
    is_leech = uploader_choice == 'leech'
    
    task = asyncio.create_task(_ytdlp_download_worker(
        original_event, task_id, uploader, url, quality, is_leech, uploader_choice, False, cookie_path=cookie_path
    ))
    
    tasks[task_id] = {
        'uploader': uploader, 
        'progress_data': {'action': 'Initializing...'},
        'async_task': task,
        'is_cancelled': False,
        'chat_id': original_event.chat_id
    }
    await send_status_message(original_event.chat_id, event_message=original_event.message)

async def main():
    await client.start(bot_token=TELEGRAM_BOT_TOKEN)
    print("Bot started...")
    asyncio.create_task(update_all_status_messages())
    print("Bot is running. Press Ctrl+C to stop.")
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        main_loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\nStopping the bot...")
    finally:
        if main_loop.is_running() and not main_loop.is_closed():
            if client.is_connected():
                main_loop.run_until_complete(client.disconnect())
            
            tasks_to_cancel = asyncio.all_tasks(loop=main_loop)
            for task in tasks_to_cancel:
                task.cancel()
            
            main_loop.run_until_complete(asyncio.gather(*tasks_to_cancel, return_exceptions=True))
            main_loop.close()
        
        print("Bot stopped and cleaned up.")
