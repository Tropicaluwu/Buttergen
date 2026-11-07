import pygame
import pygame_gui

from scripts.cat.cats import Cat
from scripts.cat_editor_logic import (
    REL_STATS,
    apply_preset,
    get_rel_value,
    nudge_faith,
    nudge_rel_stat,
    set_faith_mode,
)
from scripts.cat_relations.relationship import Relationship
from scripts.clan_package.settings import get_clan_setting
from scripts.game_structure import game, image_cache
from scripts.game_structure.screen_settings import MANAGER
from scripts.screens.enums import GameScreen
from scripts.ui import cat_list_filter
from scripts.ui.elements.image_button import UIImageButton
from scripts.ui.elements.relation_display import UIRelationDisplay
from scripts.ui.elements.sprite_button import UISpriteButton
from scripts.ui.elements.surface_image_button import UISurfaceImageButton
from scripts.ui.generate_button import ButtonStyles, get_button_dict
from scripts.ui.scale import ui_scale, ui_scale_dimensions, ui_scale_value
from scripts.ui.theme import get_text_box_theme
from scripts.game_structure.game.settings import game_setting_get
from scripts.ui.windows.window_base_class import GameWindow
from scripts.events_module.text_adjust import shorten_text_to_fit

COLUMNS = 5
ROWS = 2
PAGE_SIZE = COLUMNS * ROWS

FAITH_BUTTONS = [
    ("StarClan", "starclan"),
    ("Neutral", "neutral"),
    ("Dark Forest", "darkforest"),
    ("Free", "flexible"),
]

# (button label, preset key) in two columns
PRESET_BUTTONS = [
    ("Rival", "rival"),
    ("Enemy", "enemy"),
    ("Friend", "friend"),
    ("Best friend", "bestfriend"),
    ("Crush", "crush"),
    ("Lover", "lover"),
    ("Soulmate", "soulmate"),
    ("Reset", "stranger"),
]

GENDER_ICONS = {
    "female": "resources/images/female_big.png",
    "male": "resources/images/male_big.png",
    "trans female": "resources/images/transfem_big.png",
    "trans male": "resources/images/transmasc_big.png",
    # genemod names
    "molly": "resources/images/female_big.png",
    "tom": "resources/images/male_big.png",
    "trans molly": "resources/images/transfem_big.png",
    "trans tom": "resources/images/transmasc_big.png",
}


class EditorWindowBase(GameWindow):
    """Shared bits for the editor windows: dark mode panel, text, buttons that run a function."""

    def __init__(self, rect):
        super().__init__(ui_scale(rect))
        self.dark = bool(game_setting_get("dark mode"))
        if self.dark:
            self._make_dark(rect)
        self.elements = []
        self.actions = {}

    def _make_dark(self, rect):
        """Dark mode: swap the tan window box for a dark panel like the rest of the dark UI."""
        if self.box:
            self.box.kill()
        panel_rect = ui_scale(pygame.Rect((rect.x - 6, rect.y - 6), (rect.w + 12, rect.h + 12)))
        panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        panel.fill((38, 31, 26, 255))
        pygame.draw.rect(panel, (121, 96, 69, 255), panel.get_rect(), ui_scale_value(3))
        pygame.draw.rect(
            panel,
            (74, 60, 45, 255),
            panel.get_rect().inflate(-ui_scale_value(8), -ui_scale_value(8)),
            ui_scale_value(2),
        )
        self.box = pygame_gui.elements.UIImage(
            panel_rect,
            panel,
            starting_height=self.layer,
            manager=MANAGER,
        )

    def _text(self, text, rect, object_id="#text_box_30_horizleft_pad_0_8", disable=False):
        if self.dark:
            object_id = get_text_box_theme(object_id)
            # colour the text directly too, some text styles have no dark variant
            text = f"<font color='#EFE5CE'>{text}</font>"
        box = pygame_gui.elements.UITextBox(
            text,
            ui_scale(pygame.Rect(rect)),
            object_id=object_id,
            container=self,
        )
        if disable:
            box.disable()
        self.elements.append(box)
        return box

    def _button(self, text, rect, action, disabled=False, tooltip=None):
        size = (rect[2], rect[3])
        button = UISurfaceImageButton(
            ui_scale(pygame.Rect(rect)),
            text,
            get_button_dict(ButtonStyles.SQUOVAL, size),
            object_id="@buttonstyles_squoval",
            manager=MANAGER,
            container=self,
            tool_tip_text=tooltip,
        )
        if disabled:
            button.disable()
        self.elements.append(button)
        self.actions[button] = action
        return button

    def _clear(self):
        for element in self.elements:
            element.kill()
        self.elements = []
        self.actions = {}

    def redraw_content(self):
        raise NotImplementedError

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_START_PRESS and event.ui_element in self.actions:
            action = self.actions[event.ui_element]
            action()
            # the action might have closed the window
            if self.alive():
                self.redraw_content()
            return True
        return super().process_event(event)

    @staticmethod
    def _refresh_profile():
        try:
            profile = game.all_screens[GameScreen.PROFILE]
            profile.clear_profile()
            profile.build_profile()
            profile.update_disabled_buttons_and_text()
        except Exception as error:  # pylint: disable=broad-except
            print("Cat editor: could not refresh the profile screen:", error)


class CatEditorWindow(EditorWindowBase):
    """Cat editor: change faith, relationships and mates for a cat."""

    def __init__(self, cat, target=None, on_close=None, section="all"):
        """section: "faith", "relationship" or "all". target: start on this cat's relationship"""
        self.section = section
        if section == "faith":
            rect = pygame.Rect((170, 190), (460, 300))
        else:
            rect = pygame.Rect((50, 20), (700, 660))
        super().__init__(rect)
        self.the_cat = cat
        self.target = target if target is not None and target.ID != cat.ID else None
        self.on_close = on_close
        self.both_ways = True
        self.page = 0
        self.mode = "main"  # "main" or "picker"

        # the picker's group, sort and search bar
        self.cat_filter = None
        self.redraw_content()

    # ------------------------------------------------------------------ helpers
    def _candidates(self):
        # every living cat, the bar starts on your Clan
        cats = [c for c in Cat.all_cats_list if c.ID != self.the_cat.ID and not c.dead and not c.faded]
        return self.cat_filter.apply(cats) if self.cat_filter else cats

    def _relationship(self, other):
        """The existing relationship from the edited cat to other, or a throw-away blank one for display."""
        rel = self.the_cat.relationships.get(other.ID)
        return rel if rel else Relationship(self.the_cat, other)

    def redraw_content(self):
        self._clear()
        if self.mode == "picker":
            self._build_picker()
        else:
            self._destroy_filter_entry()
            self._build_main()

    def _destroy_filter_entry(self):
        if self.cat_filter:
            self.cat_filter.kill()
            self.cat_filter = None

    # ------------------------------------------------------------------ cat card (same look as the relationship screen)
    def _card(self, other, x, y, sprite_size=50, on_click=None):
        """A cat card: name, sprite, gender, mate heart and the relationship bars from the edited cat to `other`."""
        sprite = UISpriteButton(
            ui_scale(pygame.Rect((x + 22 - (sprite_size - 50) // 2, y), (sprite_size, sprite_size))),
            other.sprite,
            cat_object=other,
            container=self,
            manager=MANAGER,
        )
        self.elements.append(sprite)
        if on_click:
            self.actions[sprite.button] = on_click

        name = shorten_text_to_fit(str(other.name), 90, 13)
        self._text(name, (x - 5, y - 25, 110, 30), "#text_box_26_horizcenter", disable=True)

        gender_path = GENDER_ICONS.get(other.genderalign, "resources/images/nonbi_big.png")
        gender = pygame_gui.elements.UIImage(
            ui_scale(pygame.Rect((x + 80, y + 5), (18, 18))),
            pygame.transform.scale(
                image_cache.load_image(gender_path).convert_alpha(), ui_scale_dimensions((18, 18))
            ),
            container=self,
        )
        self.elements.append(gender)

        if other.ID in self.the_cat.mate:
            heart = pygame_gui.elements.UIImage(
                ui_scale(pygame.Rect((x + 5, y + 5), (11, 10))),
                image_cache.load_image("resources/images/heart_big.png").convert_alpha(),
                container=self,
            )
            self.elements.append(heart)

        display = UIRelationDisplay(
            unscaled_position=(x + 3, 0),
            relationship=self._relationship(other),
            romance=True,
            container=self,
            manager=MANAGER,
            anchors={"top_target": sprite},
        )
        self.elements.append(display)

    # ------------------------------------------------------------------ main page
    def _faith_summary(self):
        cat = self.the_cat
        if cat.joined_df:
            lock = "training in the Dark Forest"
        elif cat.no_faith:
            lock = "no faith"
        else:
            lock = f"lock: {cat.lock_faith}"
        return f"Faith {round(cat.faith)} (effective {round(cat.get_effective_faith())}) - {lock}"

    def _build_faith(self, top):
        """Faith controls; `top` is the y position of the first row."""
        cat = self.the_cat
        self._text("Faith", (20, top, 300, 30))
        width = 100 if self.section == "faith" else 158
        gap = 8 if self.section == "faith" else 166
        step = 108 if self.section == "faith" else gap
        for i, (label, mode) in enumerate(FAITH_BUTTONS):
            self._button(label, (20 + i * step, top + 32, width, 32), lambda m=mode: self._set_faith(m))
        if self.section == "faith":
            # the summary gets its own row, the -/+ buttons sit underneath it
            self._text(self._faith_summary(), (20, top + 68, 420, 30), "#text_box_26_horizleft_pad_10_14")
            self._button("-", (20, top + 102, 60, 30), lambda: self._nudge_faith(-1))
            self._button("+", (88, top + 102, 60, 30), lambda: self._nudge_faith(1))
            return
        self._text(self._faith_summary(), (20, top + 68, 500, 30), "#text_box_26_horizleft_pad_10_14")
        self._button("-", (540, top + 68, 60, 30), lambda: self._nudge_faith(-1))
        self._button("+", (608, top + 68, 60, 30), lambda: self._nudge_faith(1))

    def _build_main(self):
        cat = self.the_cat
        if self.section == "faith":
            self._text(f"Faith - {cat.name}", (0, 10, 460, 34), "#text_box_34_horizcenter")
            self._build_faith(50)
            faith_number = round(cat.get_effective_faith())
            try:
                bar = pygame_gui.elements.UIImage(
                    ui_scale(pygame.Rect((20, 196, 421, 39))),
                    image_cache.load_image(f"resources/images/faith{faith_number}.png").convert_alpha(),
                    container=self,
                )
                self.elements.append(bar)
            except (FileNotFoundError, pygame.error):
                pass
            self._text(
                "Changes apply straight away and are saved with your next save.",
                (20, 246, 420, 40),
                "#text_box_26_horizleft_pad_10_14",
            )
            return

        # y offset: the relationship-only editor has no faith rows on top of it
        oy = 0 if self.section == "all" else -114
        width = 700
        self._text(
            f"Cat Editor - {cat.name}" if self.section == "all" else f"Relationships - {cat.name}",
            (0, 10, width, 34),
            "#text_box_34_horizcenter",
        )
        if self.section == "all":
            self._build_faith(50)

        # Relationships
        self._text("Relationship with", (20, 164 + oy, 200, 30))
        target_name = str(self.target.name) if self.target else "Choose a cat..."
        self._button(target_name, (230, 164 + oy, 270, 32), self._open_picker)
        # the plain @checked_checkbox style has no images in this ClanGen's theme
        both_id = "@checked_checkbox_smalltooltip" if self.both_ways else "@unchecked_checkbox_smalltooltip"
        box = UIImageButton(
            ui_scale(pygame.Rect((526, 164 + oy, 30, 30))),
            "",
            container=self,
            object_id=both_id,
            tool_tip_text="Apply the change to both cats' feelings toward each other.",
        )
        self.elements.append(box)
        self.actions[box] = self._toggle_both
        self._text("Both ways", (562, 164 + oy, 130, 30))

        if self.target:
            other = self.target
            # how the edited cat feels about the target, same display as Relations > See relationships
            self._card(other, 25, 240 + oy, sprite_size=64)

            for i, stat in enumerate(REL_STATS):
                y = 216 + oy + i * 40
                value = get_rel_value(cat, other, stat)
                self._text(f"{stat.title()}: {value}", (190, y, 150, 30))
                self._button("-10", (330, y, 62, 30), lambda s=stat: self._nudge_rel(s, -10))
                self._button("+10", (398, y, 62, 30), lambda s=stat: self._nudge_rel(s, 10))
            for i, (label, preset) in enumerate(PRESET_BUTTONS):
                col, row = i % 2, i // 2
                self._button(
                    label,
                    (490 + col * 100, 216 + oy + row * 44, 94, 32),
                    lambda p=preset: self._preset(p),
                )

            # Mates
            is_mate = other.ID in cat.mate
            # siblings, parents, children and other close relatives can't be made mates
            is_related = cat.is_related(other, get_clan_setting("first cousin mates"))
            self._text("Mates: Yes" if is_mate else "Mates: No", (190, 428 + oy, 150, 30))
            self._button(
                "Make mates",
                (330, 426 + oy, 160, 34),
                self._make_mates,
                disabled=is_mate or is_related,
            )
            self._button("End mate bond", (500, 426 + oy, 170, 34), self._end_mates, disabled=not is_mate)
            self._text(
                "These two are related, so they can't be made mates."
                if is_related and not is_mate
                else "Cats can have several mates at once (open relationships and polycules).",
                (190, 466 + oy, 500, 30),
                "#text_box_26_horizleft_pad_10_14",
            )
        else:
            self._text(
                "Pick a cat to edit how they feel about each other, set rivals, lovers or mates.",
                (20, 220 + oy, 660, 60),
                "#text_box_26_horizleft_pad_10_14",
            )

        self._text(
            "Changes apply straight away and are saved with your next save.",
            (20, 610, 660, 30),
            "#text_box_26_horizleft_pad_10_14",
        )

    # ------------------------------------------------------------------ picker page
    def _build_picker(self):
        self._text("Choose a cat", (0, 10, 700, 34), "#text_box_34_horizcenter")
        if not self.cat_filter:
            self.cat_filter = cat_list_filter.CatListFilter((20, 50), container=self)
        cats = self._candidates()
        pages = max(1, (len(cats) + PAGE_SIZE - 1) // PAGE_SIZE)
        self.page = max(0, min(self.page, pages - 1))
        chunk = cats[self.page * PAGE_SIZE : (self.page + 1) * PAGE_SIZE]

        for i, other in enumerate(chunk):
            col, row = i % COLUMNS, i // COLUMNS
            self._card(
                other,
                25 + col * 134,
                125 + row * 235,
                on_click=lambda c=other: self._choose_target(c),
            )
        if not chunk:
            self._text("No matching cats.", (20, 110, 400, 30))

        self._button("Back", (580, 48, 100, 32), self._close_picker)
        self._button("Prev", (20, 612, 100, 32), self._prev_page, disabled=self.page == 0)
        self._text(f"Page {self.page + 1} / {pages}", (290, 614, 120, 30), "#text_box_26_horizcenter")
        self._button("Next", (580, 612, 100, 32), self._next_page, disabled=self.page >= pages - 1)

    # ------------------------------------------------------------------ actions
    def _set_faith(self, mode):
        set_faith_mode(self.the_cat, mode)

    def _nudge_faith(self, amount):
        nudge_faith(self.the_cat, amount)

    def _toggle_both(self):
        self.both_ways = not self.both_ways

    def _nudge_rel(self, stat, amount):
        nudge_rel_stat(self.the_cat, self.target, stat, amount, self.both_ways)

    def _preset(self, preset):
        apply_preset(self.the_cat, self.target, preset, self.both_ways)

    def _make_mates(self):
        self.the_cat.set_mate(self.target)

    def _end_mates(self):
        self.the_cat.unset_mate(self.target)

    def _open_picker(self):
        self.mode = "picker"
        self.page = 0

    def _close_picker(self):
        self.mode = "main"

    def _choose_target(self, other):
        self.target = other
        self.mode = "main"

    def _prev_page(self):
        self.page -= 1

    def _next_page(self):
        self.page += 1

    # ------------------------------------------------------------------ events
    def process_event(self, event):
        if self.cat_filter and self.cat_filter.process_event(event):
            self.page = 0
            self._clear()
            self._build_picker()
            return True

        return super().process_event(event)

    def kill(self):
        if self.cat_filter:
            self.cat_filter.kill()
            self.cat_filter = None
        super().kill()
        if self.on_close:
            try:
                self.on_close()
            except Exception as error:  # pylint: disable=broad-except
                print("Cat editor: on_close failed:", error)
        else:
            self._refresh_profile()
