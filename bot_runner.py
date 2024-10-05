import subprocess
import time
import sys
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class BotRunner:
    def __init__(self):
        self.process = None
        self.restart_needed = False

    def start_bot(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
        print("Starting bot...")
        self.process = subprocess.Popen([sys.executable, "discord_bot.py"])

    def stop_bot(self):
        if self.process:
            print("Stopping bot...")
            self.process.terminate()
            self.process.wait()
            self.process = None

    def run(self):
        self.start_bot()
        while True:
            if self.restart_needed:
                self.restart_needed = False
                self.stop_bot()
                time.sleep(1)  # Short delay before restarting
                self.start_bot()
            time.sleep(1)

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, bot_runner):
        self.bot_runner = bot_runner

    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            print(f"File {event.src_path} has been modified. Restarting bot...")
            self.bot_runner.restart_needed = True

if __name__ == "__main__":
    bot_runner = BotRunner()
    event_handler = FileChangeHandler(bot_runner)
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()

    try:
        bot_runner.run()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
