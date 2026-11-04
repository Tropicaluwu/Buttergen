"""BUTTERGEN: the window behind the "Your cat has a choice" badge (honor system step 5)."""

import pygame
import pygame_gui

from scripts.honor import choices
from scripts.ui.elements.surface_image_button import UISurfaceImageButton
from scripts.ui.generate_button import get_button_dict, ButtonStyles
from scripts.ui.scale import ui_scale
from scripts.ui.windows.window_base_class import GameWindow

WIDTH, BUTTON_W, BUTTON_H, GAP = 520, 440, 30, 38


class HonorChoiceWindow(GameWindow):
    def __init__(self, events_screen=None):
        shown = choices.window_text()
        prompt, options = shown if shown else ("", [])
        height = 150 + GAP * len(options)
        super().__init__(ui_scale(pygame.Rect(((800 - WIDTH) // 2, (700 - height) // 2), (WIDTH, height))))
        self.set_blocking(True)
        self.events_screen = events_screen
        self.prompt = pygame_gui.elements.UITextBox(
            prompt,
            ui_scale(pygame.Rect((20, 15), (WIDTH - 40, 100))),
            object_id="#text_box_30_horizcenter",
            container=self,
        )
        self.option_buttons = {}
        y = 120
        for option, label in options:
            self.option_buttons[option] = UISurfaceImageButton(
                ui_scale(pygame.Rect(((WIDTH - BUTTON_W) // 2, y), (BUTTON_W, BUTTON_H))),
                label,
                get_button_dict(ButtonStyles.SQUOVAL, (BUTTON_W, BUTTON_H)),
                object_id="@buttonstyles_squoval",
                container=self,
            )
            y += GAP

    def close(self):
        self.kill()

    def process_event(self, event):
        handled = super().process_event(event)
        if event.type != pygame_gui.UI_BUTTON_START_PRESS:
            return handled
        for option, button in self.option_buttons.items():
            if event.ui_element == button:
                choices.resolve(option)
                self.close()
                self.refresh_events()
                return True
        return handled

    def refresh_events(self):
        """puts the result at the top of the events screen and takes the badge away"""
        screen = self.events_screen
        if screen is None:
            return
        try:
            screen.update_display_events_lists()
            screen.display_events = screen.all_events
            screen.current_display = "all events"
            screen.update_events_display()
        except Exception:
            pass
        choices.show_badge(screen)
