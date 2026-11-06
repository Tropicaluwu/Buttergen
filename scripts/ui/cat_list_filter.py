"""Group, sort and search bar for screens where a cat is picked from a long list."""

import pygame
import pygame_gui

from scripts.cat.enums import CatRank
from scripts.clan_package.settings import get_clan_setting
from scripts.events_module.text_adjust import shorten_text_to_fit
from scripts.game_structure import game
from scripts.game_structure.screen_settings import MANAGER
from scripts.ui.elements.search_bar import UISearchBar
from scripts.ui.elements.sprite_button import UISpriteButton
from scripts.ui.scale import ui_scale

SORTS = {
    "name": "Sort: name",
    "age": "Sort: age",
    "rank": "Sort: rank",
    "liked": "Sort: liked most",
}
RANK_ORDER = [
    CatRank.LEADER, CatRank.DEPUTY, CatRank.MEDICINE_CAT, CatRank.MEDICINE_APPRENTICE, CatRank.MEDIATOR,
    CatRank.MEDIATOR_APPRENTICE, CatRank.WARRIOR, CatRank.APPRENTICE, CatRank.ELDER, CatRank.KITTEN, CatRank.NEWBORN,
]
# grid the screens share: 10 cats a row, a label under each
COLUMNS = 10
ROWS = 2
PAGE_SIZE = COLUMNS * ROWS
CELL_W = 60
CELL_H = 85


def group_key(cat) -> str:
    """which group a cat goes under in the dropdown"""
    if cat.dead:
        return "dead"
    if cat.status.group and cat.status.group.is_any_clan_group():
        return str(cat.status.group_ID)
    return str(cat.status.social)


def group_label(key) -> str:
    if key == "all":
        return "All groups"
    if key == "dead":
        return "Dead"
    if key in ("loner", "rogue", "kittypet"):
        return key.capitalize() + "s"
    if not game.clan:
        return "Others"
    clan = game.clan if key == str(game.clan.group_ID) else next(
        (c for c in game.clan.all_other_clans if str(c.group_ID) == key), None
    )
    return str(clan.name) if clan else "Others"


def pov_key() -> str:
    """the group of the player's cat, where the dropdown starts"""
    you = game.clan.your_cat if game.clan else None
    return group_key(you) if you else "all"


class CatListFilter:
    def __init__(self, pos, container=None, groups=True, start_group=None):
        """pos: top left of the bar in screen units. groups: show the group dropdown"""
        self.container = container
        self.pos = pos
        self.show_groups = groups
        self.group = start_group or pov_key()
        self.sort = "name"
        self.search = ""
        self.group_dropdown = None
        self.sort_dropdown = None
        self.search_entry = None
        self.search_bar = None
        self._group_options = []
        self._build_sort_and_search()

    # ------------------------------------------------------------ elements
    def _build_sort_and_search(self):
        x, y = self.pos
        offset = 160 if self.show_groups else 0
        self.sort_dropdown = pygame_gui.elements.UIDropDownMenu(
            [(label, key) for key, label in SORTS.items()],
            (SORTS[self.sort], self.sort),
            ui_scale(pygame.Rect((x + offset, y), (150, 28))),
            manager=MANAGER,
            container=self.container,
        )
        # the game's own search bar, like the relationships screen
        self.search_bar = UISearchBar((x + offset + 160, y - 2), container=self.container)
        self.search_entry = self.search_bar.text_entry

    def _build_group_dropdown(self, keys):
        if not self.show_groups:
            return
        own = pov_key()
        clans = sorted((k for k in keys if k[:1].isdigit() and k != own), key=group_label)
        order = ["all"] + ([own] if own in keys else []) + clans
        order += [k for k in ("loner", "rogue", "kittypet", "dead") if k in keys and k != own]
        if self.group not in order:
            self.group = own if own in order else "all"
        if order == self._group_options and self.group_dropdown:
            return
        self._group_options = order
        if self.group_dropdown:
            self.group_dropdown.kill()
        x, y = self.pos
        self.group_dropdown = pygame_gui.elements.UIDropDownMenu(
            [(group_label(k), k) for k in order],
            (group_label(self.group), self.group),
            ui_scale(pygame.Rect((x, y), (150, 28))),
            manager=MANAGER,
            container=self.container,
        )

    def kill(self):
        for element in (self.group_dropdown, self.sort_dropdown, self.search_bar):
            if element:
                element.kill()
        self.group_dropdown = self.sort_dropdown = self.search_entry = self.search_bar = None
        self._group_options = []

    # ------------------------------------------------------------ filtering
    def apply(self, cats) -> list:
        """the cats in the chosen group that match the search, sorted"""
        cats = list(cats)
        self._build_group_dropdown({group_key(c) for c in cats})
        if self.show_groups and self.group != "all":
            cats = [c for c in cats if group_key(c) == self.group]
        text = self.search.strip().lower()
        if text:
            cats = [c for c in cats if text in str(c.name).lower()]
        return sorted(cats, key=self._sort_key)

    def _sort_key(self, cat):
        if self.sort == "age":
            return (-cat.moons, str(cat.name).lower())
        if self.sort == "rank":
            rank = cat.status.rank
            return (RANK_ORDER.index(rank) if rank in RANK_ORDER else len(RANK_ORDER), str(cat.name).lower())
        if self.sort == "liked":
            you = game.clan.your_cat if game.clan else None
            rel = you.relationships.get(cat.ID) if you else None
            fondness = (rel.like + rel.romance + rel.comfort + rel.trust) if rel else 0
            return (-fondness, str(cat.name).lower())
        return (str(cat.name).lower(),)

    def process_event(self, event) -> bool:
        """True when the list should be redrawn"""
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if self.group_dropdown and event.ui_element == self.group_dropdown:
                self.group = self.group_dropdown.selected_option[1]
                return True
            if self.sort_dropdown and event.ui_element == self.sort_dropdown:
                self.sort = self.sort_dropdown.selected_option[1]
                return True
        elif event.type == pygame_gui.UI_TEXT_ENTRY_CHANGED and event.ui_element == self.search_entry:
            self.search = self.search_entry.get_text()
            return True
        return False


def draw_grid(buttons: dict, cats, left, top, container=None, fav: dict = None, cell_h=CELL_H, columns=COLUMNS):
    """draws a page of cats into buttons, each with its name under it (fav: the screen's favorite markers)"""
    if fav is not None:
        for marker in fav.values():
            marker.kill()
        fav.clear()
    for element in buttons.values():
        element.kill()
    buttons.clear()
    for i, cat in enumerate(cats):
        x = left + (i % columns) * CELL_W
        y = top + (i // columns) * cell_h
        if fav is not None and get_clan_setting("show fav") and cat.favourite != 0:
            fav[str(i)] = pygame_gui.elements.UIImage(
                ui_scale(pygame.Rect((x, y), (50, 50))),
                pygame.transform.scale(
                    pygame.image.load(f"resources/images/fav_marker{cat.favourite}.png").convert_alpha(), (50, 50)
                ),
                manager=MANAGER,
                container=container,
            )
            fav[str(i)].disable()
        buttons["cat" + str(i)] = UISpriteButton(
            ui_scale(pygame.Rect((x, y), (50, 50))),
            cat.sprite,
            cat_object=cat,
            manager=MANAGER,
            container=container,
            tool_tip_text=f"{cat.name}, {cat.moons} moons, {cat.status.rank}"
            + (f", {group_label(group_key(cat))}" if not cat.dead else ""),
        )
        # a one line label, so long names can't wrap and grow a scroll bar
        label = pygame_gui.elements.UILabel(
            ui_scale(pygame.Rect((x - 7, y + 50), (64, 22))),
            shorten_text_to_fit(str(cat.name), 60, 13),
            object_id="#text_box_22_horizcenter",
            manager=MANAGER,
            container=container,
        )
        buttons["label" + str(i)] = label
