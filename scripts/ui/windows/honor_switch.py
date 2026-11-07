"""BUTTERGEN: "Which Clan will you ask?" for your cat (honor system step 9). Opened by the profile's
switch button in multi clan mode. The asking happens at the next Gathering."""

import pygame
import pygame_gui

from scripts.cat.cats import Cat
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.honor import switching
from scripts.screens.enums import GameScreen
from scripts.ui.elements.surface_image_button import UISurfaceImageButton
from scripts.ui.generate_button import get_button_dict, ButtonStyles
from scripts.ui.scale import ui_scale
from scripts.ui.windows.window_base_class import GameWindow

WIDTH, BUTTON_W, BUTTON_H, GAP = 460, 400, 30, 38


def _with_wait(t, label, moons):
    if not moons:
        return label
    key = "wait_one" if moons == 1 else "wait"
    return t[key].replace("%{option}", label).replace("%{moons}", str(moons))


class HonorSwitchWindow(GameWindow):
    def __init__(self, cat, profile_screen=None):
        t = switching.texts()["window"]
        self.the_cat = cat
        self.profile_screen = profile_screen
        options = []
        for group_ID in switching.targets(cat):
            clan = switching.clan_of_group(group_ID)
            label = event_text_adjust(Cat, t["clan"], main_cat=cat, clan=game.clan, other_clan=clan)
            wait = switching.wait_for(cat, group_ID)
            options.append((group_ID, _with_wait(t, label, wait), wait == 0))
        height = 90 + GAP * len(options)
        super().__init__(ui_scale(pygame.Rect(((800 - WIDTH) // 2, (700 - height) // 2), (WIDTH, height))))
        self.set_blocking(True)
        self.title = pygame_gui.elements.UITextBox(
            t["title"],
            ui_scale(pygame.Rect((20, 15), (WIDTH - 40, 40))),
            object_id="#text_box_30_horizcenter",
            container=self,
        )
        self.option_buttons = {}
        y = 60
        for group_ID, label, ready in options:
            button = UISurfaceImageButton(
                ui_scale(pygame.Rect(((WIDTH - BUTTON_W) // 2, y), (BUTTON_W, BUTTON_H))),
                label,
                get_button_dict(ButtonStyles.SQUOVAL, (BUTTON_W, BUTTON_H)),
                object_id="@buttonstyles_squoval",
                container=self,
            )
            if not ready:
                button.disable()
            self.option_buttons[button] = group_ID
            y += GAP

    def process_event(self, event):
        handled = super().process_event(event)
        if event.type != pygame_gui.UI_BUTTON_START_PRESS or event.ui_element not in self.option_buttons:
            return handled
        switching.queue_your_ask(self.option_buttons[event.ui_element])
        self.kill()
        if self.profile_screen is not None:
            self.profile_screen.change_screen(GameScreen.EVENTS)
        return True
