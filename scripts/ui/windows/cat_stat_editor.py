"""
The "edit cat" window. Lets you change a cat's personality, lifegen stats, faith, skills, health
and other life stuff, with max out and reset buttons on each tab. Only reachable when the Cat Editor
setting is on.
"""

import pygame
import pygame_gui

from scripts.cat.enums import CatRank
from scripts.cat_editor_logic import (
    BIRTH_CONDITIONS,
    LIFE_FLAGS,
    LIFEGEN_STATS,
    honor_stats_for,
    PERSONALITY_FACETS,
    SKILL_SLOTS,
    all_traits,
    clear_permanent,
    condition_options,
    get_stat,
    give_condition,
    heal_all,
    hidden_options,
    max_skills,
    max_stats,
    nudge_stat,
    remove_condition,
    remove_second_skill,
    reset_skills,
    unshun,
    reset_stats,
    second_trait_options,
    set_second_trait,
    set_moons,
    set_hidden,
    set_rank,
    set_skill_path,
    set_trait,
    skill_options,
    skill_text,
    nudge_skill_points,
    toggle_skill_interest,
)
from scripts.ui.elements.image_button import UIImageButton
from scripts.ui.scale import ui_scale
from scripts.ui.windows.cat_editor import EditorWindowBase

TABS = [
    ("personality", "Personality"),
    ("stats", "Stats & faith"),
    ("skills", "Skills"),
    ("health", "Health & life"),
]

# ranks the editor can hand out, outsider ranks are left to the normal game
EDITABLE_RANKS = [
    CatRank.NEWBORN,
    CatRank.KITTEN,
    CatRank.APPRENTICE,
    CatRank.MEDICINE_APPRENTICE,
    CatRank.MEDIATOR_APPRENTICE,
    CatRank.QUEEN_APPRENTICE,
    CatRank.WARRIOR,
    CatRank.MEDICINE_CAT,
    CatRank.MEDIATOR,
    CatRank.QUEEN,
    CatRank.DEPUTY,
    CatRank.LEADER,
    CatRank.ELDER,
]

PICKER_COLUMNS = 3
PICKER_ROWS = 9
PICKER_PAGE = PICKER_COLUMNS * PICKER_ROWS

# injuries and illnesses are both temporary conditions in this ClanGen
CONDITION_KINDS = [
    ("temporary", "temporary_conditions", "Injury or illness"),
    ("permanent", "permanent_conditions", "Lasting condition"),
]


class CatStatEditorWindow(EditorWindowBase):
    def __init__(self, cat, on_close=None):
        super().__init__(pygame.Rect((50, 20), (700, 660)))
        self.the_cat = cat
        self.on_close = on_close
        self.tab = "personality"
        # picker = (title, options, on_pick) when choosing a trait/rank/condition
        self.picker = None
        self.page = 0
        self.leaving_to_customizer = False
        self.redraw_content()

    # ------------------------------------------------------------------ layout
    def redraw_content(self):
        self._clear()
        if self.picker:
            self._build_picker()
            return
        cat = self.the_cat
        self._text(f"Edit Cat - {cat.name}", (0, 10, 700, 34), "#text_box_34_horizcenter")
        for i, (key, label) in enumerate(TABS):
            self._button(label, (20 + i * 124, 50, 118, 32), lambda k=key: self._set_tab(k),
                         disabled=self.tab == key)
        self._button("Appearance", (518, 50, 162, 32), self._open_appearance,
                     disabled=cat.dead,
                     tooltip="Opens the cat customizer for this cat. Only what you change there gets changed, "
                             "the rest of their looks and genes stay as they are. Their family keeps its genes too, "
                             "only kits born after the change inherit the new ones.")
        if self.tab == "personality":
            self._build_personality()
        elif self.tab == "stats":
            self._build_stats()
        elif self.tab == "skills":
            self._build_skills()
        else:
            self._build_health()
        self._text(
            "Changes apply straight away and are saved with your next save.",
            (20, 612, 660, 30),
            "#text_box_26_horizleft_pad_10_14",
        )

    def _stat_rows(self, table, top, steps, spacing=40):
        """a row per stat: name, value, and buttons that move it"""
        for i, (attr, label, low, high, _reset) in enumerate(table):
            y = top + i * spacing
            value = round(get_stat(self.the_cat, attr))
            self._text(f"{label}: {value}", (20, y, 260, 30))
            self._text(f"({low} to {high})", (230, y, 120, 30), "#text_box_26_horizleft_pad_10_14")
            for j, step in enumerate(steps):
                label_text = f"+{step}" if step > 0 else str(step)
                self._button(label_text, (360 + j * 78, y, 70, 30),
                             lambda a=attr, s=step: nudge_stat(self.the_cat, a, s))

    def _max_reset(self, top, on_max, on_reset, max_tip, reset_tip, max_label="Max out", reset_label="Reset"):
        self._button(max_label, (20, top, 200, 34), on_max, tooltip=max_tip)
        self._button(reset_label, (230, top, 200, 34), on_reset, tooltip=reset_tip)

    def _build_personality(self):
        cat = self.the_cat
        self._text(f"Trait: {cat.personality.trait}", (20, 96, 380, 30))
        self._button("change trait", (400, 94, 170, 32), self._open_trait_picker)
        self._text(f"Second trait: {cat.personality.trait2}", (20, 134, 380, 30))
        self._button("change", (400, 132, 170, 32), self._open_second_trait_picker)
        self._stat_rows(PERSONALITY_FACETS, 186, (-4, -1, 1, 4))
        self._text(
            "The four facets decide which traits fit a cat, so changing them can change the traits too. "
            "Second traits only list the ones that can go with the first.",
            (20, 350, 660, 60),
            "#text_box_26_horizleft_pad_10_14",
        )
        self._max_reset(
            560,
            lambda: max_stats(cat, PERSONALITY_FACETS),
            lambda: reset_stats(cat, PERSONALITY_FACETS),
            "Every facet to 16. The trait changes to whatever fits.",
            "Every facet back to the middle (8).",
        )

    def _build_stats(self):
        cat = self.the_cat
        lock = "no faith" if cat.no_faith else f"faith lock: {cat.lock_faith}"
        self._text(f"Effective faith {round(cat.get_effective_faith())}, {lock}", (20, 96, 660, 30),
                   "#text_box_26_horizleft_pad_10_14")
        four = [row for row in LIFEGEN_STATS if row[0] in ("courage", "intelligence", "empathy", "compassion", "faith")]
        affinity = [row for row in LIFEGEN_STATS if row[0].endswith("affinity")]
        # BUTTERGEN: honor and reputation, and Clan trust for leaders, deputies and healers
        honor = honor_stats_for(cat)
        self._stat_rows(four, 128, (-5, -1, 1, 5), spacing=36)
        self._stat_rows(affinity + honor, 312, (-50, -10, 10, 50), spacing=36)
        self._text(
            "Affinity is how much StarClan or the Dark Forest likes this cat, it matters when they die. "
            "Honor is how well they really follow the warrior code, reputation is what the Clan knows.",
            (20, 492, 660, 64),
            "#text_box_26_horizleft_pad_10_14",
        )
        self._max_reset(
            560,
            lambda: max_stats(cat, LIFEGEN_STATS + honor),
            lambda: reset_stats(cat, LIFEGEN_STATS + honor),
            "Courage, intelligence, empathy and compassion to 10, faith to 9, StarClan affinity, "
            "honor and reputation to 100.",
            "Everything back to 0.",
        )

    def _build_skills(self):
        cat = self.the_cat
        for i, (slot, label) in enumerate(SKILL_SLOTS):
            top = 100 + i * 150
            skill = getattr(cat.skills, slot)
            self._text(f"{label}: {skill_text(cat, slot)}", (20, top, 660, 30))
            self._button("change skill", (20, top + 36, 170, 32), lambda s=slot: self._open_skill_picker(s))
            if slot == "secondary":
                self._button("remove", (200, top + 36, 120, 32), lambda: remove_second_skill(cat),
                             disabled=skill is None)
            self._button("make it a real skill" if skill and skill.interest_only else "make it an interest",
                         (330, top + 36, 230, 32), lambda s=slot: toggle_skill_interest(cat, s),
                         disabled=skill is None,
                         tooltip="Kits have interests, grown cats have real skills with levels.")
            self._text("Points:", (20, top + 80, 100, 30))
            for j, step in enumerate((-10, -1, 1, 10)):
                self._button(f"+{step}" if step > 0 else str(step), (120 + j * 78, top + 78, 70, 30),
                             lambda s=slot, n=step: nudge_skill_points(cat, s, n), disabled=skill is None)
        hidden = cat.skills.hidden.value if cat.skills.hidden else "none"
        self._text(f"Hidden knowledge: {hidden}", (20, 400, 420, 30))
        self._button("change", (450, 398, 140, 32), self._open_hidden_picker)
        self._text(
            "Points go from 0 to 29: level 1 at 0, level 2 at 10 and level 3 at 20. "
            "Hidden knowledge is what rogues, loners and kittypets learned outside the Clans.",
            (20, 440, 660, 80),
            "#text_box_26_horizleft_pad_10_14",
        )
        self._max_reset(
            560,
            lambda: max_skills(cat),
            lambda: reset_skills(cat),
            "Both skills to level 3, as real skills.",
            "Both skills back to 0 points.",
        )

    def _build_health(self):
        cat = self.the_cat
        # age and rank
        self._text(f"Moons: {cat.moons} ({cat.age})", (20, 96, 300, 30))
        for j, step in enumerate((-12, -1, 1, 12)):
            self._button(f"+{step}" if step > 0 else str(step), (330 + j * 70, 96, 62, 30),
                         lambda s=step: set_moons(cat, cat.moons + s))
        shunned = not cat.dead and cat.status.is_shunned()
        self._text(f"Rank: {cat.status.rank}" + (" (shunned)" if shunned else ""), (20, 136, 300, 30))
        self._button("change rank", (330, 134, 170, 32), self._open_rank_picker, disabled=cat.dead)
        self._button("unshun", (510, 134, 170, 32), lambda: unshun(cat), disabled=not shunned,
                     tooltip="Welcomes this cat back into the Clan, like the Clan forgiving them")

        # conditions the cat has right now, click to remove
        self._text("Conditions (click one to remove it):", (20, 176, 660, 30))
        current = []
        for kind, attr, _label in CONDITION_KINDS:
            for condition in getattr(cat, attr):
                current.append((kind, condition.name))
        if not current:
            self._text("None", (20, 206, 300, 30), "#text_box_26_horizleft_pad_10_14")
        for i, (kind, name) in enumerate(current[:12]):
            col, row = i % 3, i // 3
            self._button(name.replace("_", " "), (20 + col * 222, 208 + row * 36, 214, 30),
                         lambda k=kind, n=name: remove_condition(cat, k, n),
                         disabled=name in BIRTH_CONDITIONS, tooltip="click to remove")
        if len(current) > 12:
            self._text(f"...and {len(current) - 12} more", (20, 352, 300, 30), "#text_box_26_horizleft_pad_10_14")

        # adding
        for i, (kind, _attr, label) in enumerate(CONDITION_KINDS):
            self._button(f"Add {label.lower()}", (20 + i * 333, 386, 325, 32),
                         lambda k=kind, l=label: self._open_condition_picker(k, l), disabled=cat.dead)

        # flags
        for i, (flag, label) in enumerate(LIFE_FLAGS):
            box = UIImageButton(
                ui_scale(pygame.Rect((22 + i * 222, 434, 30, 30))),
                "",
                container=self,
                # the plain @checked_checkbox style has no images in this ClanGen's theme
                object_id="@checked_checkbox_smalltooltip" if getattr(cat, flag) else "@unchecked_checkbox_smalltooltip",
            )
            self.elements.append(box)
            self.actions[box] = lambda f=flag: setattr(cat, f, not getattr(cat, f))
            self._text(label, (58 + i * 222, 434, 160, 30))

        # life and death
        if cat.dead:
            self._button("Revive", (20, 480, 200, 34), cat.revive, tooltip="Brings the cat back to their last group.")
        else:
            self._text("To kill a cat use the kill button on their profile.", (20, 480, 660, 30),
                       "#text_box_26_horizleft_pad_10_14")

        self._max_reset(
            560,
            lambda: heal_all(cat),
            lambda: (heal_all(cat), clear_permanent(cat)),
            "Clears every injury and illness. Pregnancy and permanent conditions stay.",
            "Clears every injury, illness and permanent condition.",
            max_label="Heal all",
            reset_label="Clear everything",
        )

    # ------------------------------------------------------------------ picker
    def _open_picker(self, title, options, on_pick):
        self.picker = (title, options, on_pick)
        self.page = 0

    def _open_trait_picker(self):
        self._open_picker("Choose a trait", all_traits(self.the_cat), lambda t: set_trait(self.the_cat, t))

    def _open_skill_picker(self, slot):
        options = skill_options()
        self._open_picker("Choose a skill", list(options),
                          lambda label: set_skill_path(self.the_cat, slot, options[label]))

    def _open_hidden_picker(self):
        self._open_picker("Choose hidden knowledge", hidden_options(), lambda h: set_hidden(self.the_cat, h))

    def _open_second_trait_picker(self):
        options = second_trait_options(self.the_cat.personality.kit, self.the_cat.personality.trait)
        self._open_picker("Choose a second trait", options, lambda t: set_second_trait(self.the_cat, t))

    def _open_rank_picker(self):
        self._open_picker("Choose a rank", [str(r) for r in EDITABLE_RANKS],
                          lambda r: set_rank(self.the_cat, CatRank(r)))

    def _open_condition_picker(self, kind, label):
        self._open_picker(f"Add {label.lower()}", condition_options(kind),
                          lambda n: give_condition(self.the_cat, kind, n))

    def _pick(self, option):
        _title, _options, on_pick = self.picker
        on_pick(option)
        self.picker = None

    def _close_picker(self):
        self.picker = None

    def _build_picker(self):
        title, options, _on_pick = self.picker
        self._text(title, (0, 10, 700, 34), "#text_box_34_horizcenter")
        pages = max(1, (len(options) + PICKER_PAGE - 1) // PICKER_PAGE)
        self.page = max(0, min(self.page, pages - 1))
        chunk = options[self.page * PICKER_PAGE:(self.page + 1) * PICKER_PAGE]
        for i, option in enumerate(chunk):
            col, row = i % PICKER_COLUMNS, i // PICKER_COLUMNS
            # internal condition names use underscores, like broken_bone
            self._button(option.replace("_", " "), (20 + col * 222, 56 + row * 58, 214, 44),
                         lambda o=option: self._pick(o))
        self._button("Back", (540, 612, 140, 32), self._close_picker)
        self._button("Prev", (20, 612, 100, 32), self._prev_page, disabled=self.page == 0)
        self._text(f"Page {self.page + 1} / {pages}", (290, 614, 120, 30), "#text_box_26_horizcenter")
        self._button("Next", (400, 612, 100, 32), self._next_page, disabled=self.page >= pages - 1)

    def _prev_page(self):
        self.page -= 1

    def _next_page(self):
        self.page += 1

    def _set_tab(self, tab):
        self.tab = tab

    def _open_appearance(self):
        # imported here, the screens import this window
        from scripts.game_structure import game
        from scripts.screens.make_clan_screens.CustomCat import CustomCatScreen
        from scripts.screens.enums import GameScreen

        CustomCatScreen.edit_target_id = self.the_cat.ID
        self.leaving_to_customizer = True
        self.kill()
        game.all_screens[GameScreen.PROFILE].change_screen(GameScreen.MAKE_CLAN_CUSTOM_CAT)

    # ------------------------------------------------------------------ closing
    def kill(self):
        super().kill()
        if self.leaving_to_customizer:
            # the profile is being left, dont redraw it
            return
        if self.on_close:
            try:
                self.on_close()
            except Exception as error:  # pylint: disable=broad-except
                print("Cat editor: on_close failed:", error)
        else:
            self._refresh_profile()
