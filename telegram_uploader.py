import os
import time
import asyncio
from telethon.tl.types import DocumentAttributeFilename

class LeechHandler:
    def __init__(self, client, tasks, progress_callback, download_file, download_telegram_file, _cleanup_task_files):
        self.client = client
        self.tasks = tasks
        self.progress_callback = progress_callback
        self.download_file = download_file
        self.download_telegram_file = download_telegram_file
        self._cleanup_task_files = _cleanup_task_files

    async def leech_worker(self, event, source, task_id, uploader, reply_to_msg, downloaded_file_path=None):
        try:
            if not downloaded_file_path:
                if isinstance(source, str):
                    downloaded_file_path, file_name, _ = await self.download_file(source, task_id, uploader)
                else:
                    downloaded_file_path, file_name, _ = await self.download_telegram_file(source, task_id, uploader)

                if not downloaded_file_path:
                    return
            else:
                file_name = os.path.basename(downloaded_file_path)

            self.tasks[task_id]['progress_data']['action'] = "Uploading"
            start_time = time.time()

            async def upload_progress(current, total):
                if self.tasks.get(task_id, {}).get('is_cancelled'):
                    raise asyncio.CancelledError("Upload cancelled by user.")
                await self.progress_callback(task_id, current, total, "Upload", file_name, uploader, start_time)

            await self.client.send_file(
                event.chat_id,
                downloaded_file_path,
                reply_to=reply_to_msg,
                progress_callback=upload_progress,
                attributes=[DocumentAttributeFilename(file_name)]
            )
            self.tasks[task_id]['progress_data']['action'] = "Leech Complete"

        except asyncio.CancelledError:
            if task_id in self.tasks:
                self.tasks[task_id]['progress_data']['action'] = "Cancelled by user."
        except Exception as e:
            if task_id in self.tasks:
                self.tasks[task_id]['progress_data']['action'] = f"Error: {e}"
            await self.client.send_message(event.chat_id, f"An error occurred during leech: {e}", reply_to=reply_to_msg)
        finally:
            await self._cleanup_task_files(task_id)
            if task_id in self.tasks:
                if self.tasks[task_id].get('is_cancelled'):
                    await asyncio.sleep(10)
                del self.tasks[task_id]
