import asyncio
import os
import re
from yt_dlp import YoutubeDL, DownloadError

class MyLogger:
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        pass

class YoutubeDownloader:
    def __init__(self, listener):
        self.listener = listener
        self.is_cancelled = False
        self.opts = {
            'progress_hooks': [self.on_progress],
            'logger': MyLogger(),
            'noprogress': True,
            'overwrites': True,
            'writethumbnail': True,
            'trim_file_name': 220,
            'fragment_retries': 10,
            'retries': 10,
            'ignoreerrors': True,
            'cookiefile': 'cookies.txt'
        }

    def on_progress(self, d):
        if self.is_cancelled:
            raise ValueError("Cancelling...")
        if d['status'] == 'downloading':
            self.listener.on_download_progress(d)
        elif d['status'] == 'finished':
            self.listener.on_download_finished()

    def extract_info(self, link, options=None):
        opts = self.opts.copy()
        if options:
            opts.update(options)
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(link, download=False)

    def download(self, link, path, qual, options=None):
        self.listener.on_download_start()
        opts = self.opts.copy()
        if options:
            opts.update(options)
        
        file_name_template = '%(title)s.%(ext)s'
        if 'outtmpl' in opts:
            file_name_template = opts['outtmpl']
            del opts['outtmpl']

        opts['outtmpl'] = os.path.join(path, file_name_template)
        opts['format'] = qual
        opts['writethumbnail'] = False
        
        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([link])
            
            if self.is_cancelled:
                return None

            files = os.listdir(path)
            downloaded_path = os.path.join(path, files[0]) if files else None
            self.listener.on_download_complete(downloaded_path)
            return downloaded_path
        except Exception as e:
            if not self.is_cancelled:
                self.listener.on_download_error(str(e))
            return None

    def cancel(self):
        self.is_cancelled = True
