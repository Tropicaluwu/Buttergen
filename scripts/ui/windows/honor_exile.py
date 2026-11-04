"""BUTTERGEN: "Where will you go?" for an exiled cat (honor system step 6). Opened by the
profile's return button: come home, or (multi clan mode) ask another Clan."""

import pygame
import pygame_gui

from scripts.cat.cats import Cat
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.honor import exile
from scripts.screens.enums import GameScreen
from scripts.ui.elements.surface_image_button import UISurfaceImageButton
from scripts.ui.generate_button import get_button_dict, ButtonStyles
from scripts.ui.scale import ui_scale
from scripts.ui.windows.window_base_class import GameWindow

WIDTH, BUTTON_W, BUTTON_H, GAP = 460, 400, 30, 38


def _label(text, cat, other_clan=None):
    return event_text_adjust(Cat, text, main_cat=cat, clan=game.clan, other_clan=other_clan)


def _with_wait(t, label, moons):
    if not moons:
        return label
    key = "wait_one" if moons == 1 else "wait"
    return t[key].replace("%{option}", label).replace("%{moons}", str(moons))


class HonorExileWindow(GameWindow):
    def __init__(self, cat, profile_screen=None):
        t = exile.texts()["window"]
        self.the_cat = cat
        self.profile_screen = profile_screen
        options = [("home", None, _with_wait(t, _label(t["home"], cat), exile.moons_until_home(cat)),
                    exile.moons_until_home(cat) == 0)]
        if game.clan.clancount == "multiclan":
            for clan in game.clan.all_other_clans:
                if exile._leader_of(clan) is None:
                    continue
                wait = exile.clan_wait(cat, clan)
                options.append(("clan", clan, _with_wait(t, _label(t["clan"], cat, clan), wait), wait == 0))
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
        for kind, clan, label, ready in options:
            button = UISurfaceImageButton(
                ui_scale(pygame.Rect(((WIDTH - BUTTON_W) // 2, y), (BUTTON_W, BUTTON_H))),
                label,
                get_button_dict(ButtonStyles.SQUOVAL, (BUTTON_W, BUTTON_H)),
                object_id="@buttonstyles_squoval",
                container=self,
            )
            if not ready:
                button.disable()
            self.option_buttons[button] = (kind, clan)
            y += GAP

    def process_event(self, event):
        handled = super().process_event(event)
        if event.type != pygame_gui.UI_BUTTON_START_PRESS or event.ui_element not in self.option_buttons:
            return handled
        kind, clan = self.option_buttons[event.ui_element]
        if kind == "home":
            exile.ask_home(self.the_cat)
        else:
            exile.ask_clan(self.the_cat, clan)
        self.kill()
        if self.profile_screen is not None:
            # the answer is at the top of the events, like LifeGen's return button did
            self.profile_screen.change_screen(GameScreen.EVENTS)
        return True
