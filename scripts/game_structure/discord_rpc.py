"""
This file is used to connect to Discord's Rich Presence API.
This allows the game to show up on your Discord profile.

Discord RPC is not required for the game to run.
If you do not have the pypresence module installed,
this file will not be used, and the game will run as normal.
"""

import asyncio
import threading
from time import time


from scripts.game_structure.game.settings import game_setting_get
from scripts.game_structure.game.switches import switch_get_value, Switch
from scripts.game_structure import game
from scripts.screens.enums import GameScreen

status_dict = {
    GameScreen.START: "At the start screen",
    GameScreen.MEDIATION: "Mediating a dispute",
    GameScreen.PATROL: "On a patrol",
    GameScreen.PROFILE: "Viewing a cat's profile",
    GameScreen.CEREMONY: "Holding a ceremony",
    GameScreen.MED_DEN: "In the healer den",
}


# BUTTERGEN: Buttergen's own Discord app, so the status says "Playing Buttergen". Its one picture is
# named "buttergen" (Clangen's app has a camp picture for every biome and season, ours doesn't)
DISCORD_APP_ID = "1570359456405917797"
DISCORD_BUTTONS = [
    {"label": "Join the Discord", "url": "https://discord.gg/Kxdvk5eXC9"},
    {"label": "Get Buttergen", "url": "https://github.com/Tropicaluwu/Buttergen"},
]


class _DiscordRPC(threading.Thread):
    def __init__(self, client_id: str, daemon: bool):
        super().__init__(daemon=daemon)
        self._rpc = None
        self._client_id = client_id
        self._connected = False
        self._start_time = int(time())
        self._rpc_supported = False
        self._event_loop = asyncio.new_event_loop()

        self.start_rpc = threading.Event()
        self.update_rpc = threading.Event()
        self.close_rpc = threading.Event()

    def run(self):
        self.start_rpc.wait()
        self.get_rpc()
        while not self.close_rpc.is_set():
            self.update_rpc.wait()
            if not self.close_rpc.is_set():
                self.update()
        if self._connected:
            try:
                self._rpc.clear()
                self._rpc.close()
            except Exception:
                pass
            finally:
                self._connected = False

    def get_rpc(self):
        # Check if pypresence is available.
        if not game_setting_get("discord"):
            return
        try:
            # raise ImportError # uncomment this line to disable rpc without uninstalling pypresence
            from pypresence import Presence, DiscordNotFound

            print("Discord RPC is supported")
        except ImportError:
            print("Pypresence not installed, Discord RPC isn't supported.")
            print("To enable rpc, run 'uv add pypresence' in your terminal.")
            return
        # Check if Discord is running.
        try:
            self._rpc = Presence(client_id=self._client_id, loop=self._event_loop)
            print("Discord found!")
        except DiscordNotFound:
            print("Discord not running.")
            return
        # Try to connect.
        try:
            self._rpc_supported = True
            self.connect()
            print("Connected to discord!")
        except ConnectionError as e:
            print(f"Failed to connect to Discord: {e}")

    def connect(self):
        if self._rpc_supported:
            try:
                self._rpc.connect()
            except BaseException as e:
                self._rpc_supported = False
                print(f"Failed to connect to Discord: {e}")
                return
            self._connected = True
            self.update()

    def update(self):
        if self._connected:
            try:
                state_text = status_dict[switch_get_value(Switch.cur_screen)]
            except KeyError:
                state_text = "Leading the Clan"

            try:
                img_text = f"{game.clan.biome}, {game.clan.current_season}"
            except AttributeError:
                print(
                    "Failed to get image string, game may not be fully loaded yet. "
                    "Don't worry, it will fix itself. Hopefully."
                )
                img_text = "Buttergen"


            if game.clan:
                clan_name = game.clan.name
                cats_amount = len(game.clan.clan_cats)
                clan_age = game.clan.age
            else:
                clan_name = "Loading..."
                cats_amount = 0
                clan_age = 0
            try:
                self._rpc.update(
                    state=state_text,
                    details=f"{clan_name} ({clan_age} moons)",
                    large_image="buttergen",
                    large_text=img_text,
                    small_text=f"{cats_amount} cats",
                    start=self._start_time,
                    buttons=DISCORD_BUTTONS,
                )
            except BaseException:  # pylint: disable=broad-except
                print("Discord rpc had issue updating, disabling...")
                self._rpc_supported = False
                self._connected = False
                self._rpc = None
        self.update_rpc.clear()

    def close(self):
        self.close_rpc.set()
        self.update_rpc.set()
