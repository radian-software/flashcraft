from configparser import ConfigParser
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
from typing_extensions import Never

import bs4
import requests

import flashcraft.logging as logging
from flashcraft.plugins import get_storage_plugin


class Runtime:
    def __init__(self, config: dict):
        self.config = config
        self.storage = get_storage_plugin(config["storage"])
        self.upload_lock = threading.Lock()
        self.ignore_files_from_before = datetime.fromtimestamp(0)

    @staticmethod
    def _download_minecraft_server(version: str) -> None:
        logging.info(f"Downloading Minecraft server version {version}...")
        resp = requests.get(f"https://mcversions.net/download/{version}")
        resp.raise_for_status()
        soup = bs4.BeautifulSoup(resp.text, "lxml")
        assert (link := soup.select_one("a[href*='/server.jar']"))
        assert isinstance(url := link.get("href"), str)
        with requests.get(url, stream=True) as resp:
            resp.raise_for_status()
            resp.raw.decode_content = True
            with open("server.jar.tmp", "wb") as f:
                shutil.copyfileobj(resp.raw, f)
        Path("server.jar.tmp").rename("server.jar")
        logging.info(f"Downloading Minecraft server version {version}...done")

    def _download_world(self) -> None:
        name = self.config["world_name_internal"]
        logging.info(f"Downloading Minecraft world {name}...")
        self.storage.download_prefix(f"worlds/{name}/world", "world")
        self.ignore_files_from_before = datetime.now()
        logging.info(f"Downloading Minecraft world {name}...done")

    def _upload_world(self) -> None:
        name = self.config["world_name_internal"]
        with self.upload_lock:
            logging.info(f"Uploading Minecraft world {name}...")
            now = datetime.now()
            self.storage.upload_prefix(
                "world",
                f"worlds/{self.config['world_name_internal']}/world",
                delete_missing_from_remote=True,
                skip_untouched_since=self.ignore_files_from_before,
            )
            self.ignore_files_from_before = now
            logging.info(f"Uploading Minecraft world {name}...done")

    def _upload_world_in_background(self) -> None:
        if not self.upload_lock.locked():
            self._upload_world()

    def _shutdown_gracefully(
        self, exit_code: int, *, server_already_halted: bool = False
    ) -> Never:
        if not server_already_halted:
            logging.info("Shutting down server...")
            try:
                self.server.terminate()
                self.server.wait(timeout=45)
            except (OSError, subprocess.TimeoutExpired):
                logging.info("Shutting down server...failed, killing...")
                try:
                    self.server.kill()
                    self.server.wait(timeout=15)
                except (OSError, subprocess.TimeoutExpired):
                    logging.info("Shutting down server...failed, killing...failed")
                else:
                    logging.info("Shutting down server...done")
            else:
                logging.info("Shutting down server...done")
        self._upload_world()
        sys.exit(exit_code)

    def _shutdown_gracefully_from_signal(self, signum, frame) -> Never:
        _ = frame
        signal.signal(signum, signal.SIG_DFL)
        self._shutdown_gracefully(128 + signum)

    def start(self) -> Never:
        Path("work").mkdir(exist_ok=True)
        os.chdir("work")
        if not self.config["generate_new_world"]:
            self._download_world()
        self._download_minecraft_server(self.config["minecraft_version"])
        with open("eula.txt", "w") as f:
            f.write("eula=true\n")
        with open("ops.json", "w") as f:
            json.dump(self.config["ops"], f, indent=2)
            f.write("\n")
        with open("whitelist.json", "w") as f:
            json.dump(self.config["whitelist"], f, indent=2)
            f.write("\n")
        props = dict(self.config["server_properties"])
        props.setdefault("motd", f"Flashcraft: {self.config['world_name']}")
        props.setdefault("enforce-whitelist", "true")
        props.setdefault("white-list", "true")
        with open("server.properties", "w") as f:
            ConfigParser(props).write(f, space_around_delimiters=False)
        logging.info("Starting Minecraft server...")
        self.server = subprocess.Popen(
            [
                "/usr/lib/jvm/java-17-openjdk-amd64/bin/java",
                "-jar",
                "server.jar",
            ],
            start_new_session=True,
        )
        timer = threading.Timer(interval=300, function=self._upload_world_in_background)
        timer.daemon = True
        timer.start()
        signal.signal(signal.SIGINT, self._shutdown_gracefully_from_signal)
        signal.signal(signal.SIGTERM, self._shutdown_gracefully_from_signal)
        signal.signal(signal.SIGQUIT, self._shutdown_gracefully_from_signal)
        # https://stackoverflow.com/a/71682744
        self.server.wait(timeout=float("inf"))
        logging.info("Server shut down on its own")
        self._shutdown_gracefully(self.server.returncode, server_already_halted=True)
