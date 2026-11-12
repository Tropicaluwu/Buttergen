"""BUTTERGEN: the player's leader names new warriors and mediators, and the player's healer names
their own apprentice when they become a full healer. Comes up after the skip, like the mate one.
Closing it keeps the name the game picked."""

from re import sub

import pygame
import pygame_gui

from scripts.cat.enums import CatRank
from scripts.game_structure import game
from scripts.game_structure.game.switches import (
    Switch,
    switch_append_list_value,
    switch_get_value,
    switch_set_value,
)
from scripts.game_structure.localization import load_lang_resource
from scripts.ui.elements.surface_image_button import UISurfaceImageButton
from scripts.ui.generate_button import get_button_dict, ButtonStyles
from scripts.ui.scale import ui_scale
from scripts.ui.windows.window_base_class import GameWindow

WINDOW_KEY = "warrior name"


def texts() -> dict:
    return load_lang_resource("events/naming.json")


def _queue() -> list:
    if not hasattr(game, "naming_queue"):
        game.naming_queue = []
    return game.naming_queue


def maybe_queue(cat, new_rank, was_apprentice, old_mentor):
    """called at a ceremony, after the rank change"""
    you = game.clan.your_cat if game.clan else None
    if (not you or you is cat or you.dead or not you.status.alive_in_player_clan
            or not cat.status.alive_in_player_clan or not was_apprentice):
        return
    leader_names = new_rank in (CatRank.WARRIOR, CatRank.MEDIATOR) and you.status.rank == CatRank.LEADER
    healer_names = (new_rank == CatRank.MEDICINE_CAT and old_mentor is you
                    and you.status.rank == CatRank.MEDICINE_CAT)
    if not (leader_names or healer_names):
        return
    if cat.ID not in _queue():
        _queue().append(cat.ID)
    if WINDOW_KEY not in switch_get_value(Switch.windows_dict):
        switch_append_list_value(Switch.windows_dict, WINDOW_KEY)


def next_cat():
    from scripts.cat.cats import Cat

    while _queue():
        cat = Cat.fetch_cat(_queue().pop(0))
        if cat and not cat.dead:
            return cat
    return None


def rename(cat, suffix):
    """gives the new suffix, and fixes this skip's events that used the old name"""
    old = str(cat.name)
    cat.name.suffix = suffix
    new = str(cat.name)
    if old != new:
        for event in game.cur_events_list:
            if isinstance(event.text, str) and old in event.text:
                event.text = event.text.replace(old, new)
    return new


class NameWarriorWindow(GameWindow):
    def __init__(self, last_screen):
        self.cat = next_cat()
        # no closing by clicking outside, so a stray click doesn't lose a typed name
        super().__init__(ui_scale(pygame.Rect((200, 190), (400, 220))), click_outside_to_close=False)
        self.set_blocking(True)
        switch_set_value(Switch.window_open, True)
        self.last_screen = last_screen
        if self.cat is None:
            self.close()
            return
        t = texts()
        kind = {CatRank.MEDIATOR: "mediator", CatRank.MEDICINE_CAT: "healer"}.get(self.cat.status.rank, "warrior")
        from scripts.cat.cats import Cat
        from scripts.events_module.text_adjust import event_text_adjust

        prompt = event_text_adjust(Cat, t["prompt"].replace("[kind]", t["kinds"][kind]), main_cat=self.cat)
        self.message = pygame_gui.elements.UITextBox(
            prompt,
            ui_scale(pygame.Rect((20, 15), (360, 70))),
            object_id="#text_box_30_horizcenter",
            container=self,
        )
        self.prefix_box = pygame_gui.elements.UITextBox(
            self.cat.name.prefix,
            ui_scale(pygame.Rect((20, 92), (150, 34))),
            object_id="#text_box_30_horizright",
            container=self,
        )
        self.suffix_entry = pygame_gui.elements.UITextEntryLine(
            ui_scale(pygame.Rect((175, 95), (150, 30))),
            initial_text=self.cat.name.suffix,
            container=self,
        )
        self.random_button = UISurfaceImageButton(
            ui_scale(pygame.Rect((40, 150), (140, 30))),
            t["random"],
            get_button_dict(ButtonStyles.SQUOVAL, (140, 30)),
            object_id="@buttonstyles_squoval",
            container=self,
        )
        self.use_button = UISurfaceImageButton(
            ui_scale(pygame.Rect((210, 150), (150, 30))),
            t["use"],
            get_button_dict(ButtonStyles.SQUOVAL, (150, 30)),
            object_id="@buttonstyles_squoval",
            container=self,
        )

    def close(self):
        self.kill()

    def kill(self):
        # every way of closing ends here (the X too): let the next window come up
        if not getattr(self, "_closed", False):
            self._closed = True
            switch_set_value(Switch.window_open, False)
            # more cats waiting: the screen opens the window again for the next one
            if _queue() and WINDOW_KEY not in switch_get_value(Switch.windows_dict):
                switch_append_list_value(Switch.windows_dict, WINDOW_KEY)
        super().kill()

    def process_event(self, event):
        handled = super().process_event(event)
        if event.type != pygame_gui.UI_BUTTON_START_PRESS or self.cat is None:
            return handled
        if event.ui_element == self.random_button:
            from scripts.cat.names import Name

            self.suffix_entry.set_text(Name(self.cat, self.cat.name.prefix, None).suffix)
            return True
        if event.ui_element == self.use_button:
            suffix = sub(r"[^\w'\- ]+", "", self.suffix_entry.get_text()).strip()
            if suffix:
                rename(self.cat, suffix.lower())
            self.close()
            self.refresh_events()
            return True
        return handled

    def refresh_events(self):
        screen = game.all_screens.get(switch_get_value(Switch.cur_screen)) if hasattr(game, "all_screens") else None
        try:
            screen.update_events_display()
        except Exception:
            pass
