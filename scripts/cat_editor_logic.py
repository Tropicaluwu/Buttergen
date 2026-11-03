"""Shared helpers for the cat editor, used by the editor window and the debug console. No UI in here."""

from scripts.cat.cats import Cat
from scripts.game_structure.game.settings import game_setting_get

REL_STATS = ["like", "respect", "trust", "comfort", "romance"]

# name -> (romance, like, respect, trust, comfort)
REL_PRESETS = {
    "rival": (0, -45, 15, -20, -25),
    "enemy": (0, -80, -40, -70, -60),
    "nemesis": (0, -100, -60, -100, -90),
    "friend": (0, 45, 30, 35, 40),
    "bestfriend": (0, 80, 60, 70, 75),
    "crush": (45, 35, 20, 15, 20),
    "lover": (75, 60, 45, 40, 55),
    "soulmate": (100, 100, 90, 90, 100),
    "stranger": (0, 0, 0, 0, 0),
}

FAITH_MODES = ["starclan", "darkforest", "neutral", "flexible", "none"]


def editor_enabled() -> bool:
    """the editor is off unless its turned on in the settings"""
    return bool(game_setting_get("cat_editor"))


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def get_rel_value(cat_from: Cat, cat_to: Cat, stat: str) -> int:
    rel = cat_from.relationships.get(cat_to.ID)
    return getattr(rel, stat) if rel else 0


def set_rel_stat(cat_from: Cat, cat_to: Cat, stat: str, value: int):
    rel = cat_from.create_one_relationship(cat_to)
    if rel is None:
        return
    low = 0 if stat == "romance" else -100
    setattr(rel, stat, clamp(int(value), low, 100))


def nudge_rel_stat(cat_from: Cat, cat_to: Cat, stat: str, amount: int, both: bool = False):
    set_rel_stat(cat_from, cat_to, stat, get_rel_value(cat_from, cat_to, stat) + amount)
    if both:
        set_rel_stat(cat_to, cat_from, stat, get_rel_value(cat_to, cat_from, stat) + amount)


def apply_preset(cat_from: Cat, cat_to: Cat, preset: str, both: bool = False):
    values = dict(zip(["romance", "like", "respect", "trust", "comfort"], REL_PRESETS[preset]))
    for stat, value in values.items():
        set_rel_stat(cat_from, cat_to, stat, value)
        if both:
            set_rel_stat(cat_to, cat_from, stat, value)


def set_faith_mode(cat: Cat, mode: str, number: int = None) -> bool:
    """Set a cat's faith. mode is one of FAITH_MODES, or 'number' together with the number argument.
    Returns False if the mode is unknown."""
    if mode not in FAITH_MODES and mode != "number":
        return False

    if mode == "darkforest":
        # dark forest trainee the normal lifegen way, join_df also finds them a df mentor
        if not cat.joined_df:
            cat.join_df()
        cat.lock_faith = "dark forest"
        cat.no_faith = False
        cat.faith = min(-6, cat.faith)
        return True

    # every other choice takes them out of dark forest training
    if cat.joined_df:
        cat.leave_df()
    cat.no_faith = False

    if mode == "starclan":
        cat.lock_faith = "starclan"
        cat.faith = max(6, cat.faith)
    elif mode == "neutral":
        cat.lock_faith = "neutral"
        cat.faith = clamp(cat.faith, -3, 3)
    elif mode == "flexible":
        cat.lock_faith = "flexible"
    elif mode == "none":
        cat.no_faith = True
        cat.lock_faith = "flexible"
    else:
        cat.lock_faith = "flexible"
        cat.faith = clamp(int(number), -9, 9)
    return True


def nudge_faith(cat: Cat, amount: int):
    """Move raw faith by amount (-9..9) and unlock it so the change actually shows."""
    cat.lock_faith = "flexible"
    cat.no_faith = False
    cat.faith = clamp(round(cat.faith) + amount, -9, 9)


# ------------------------------------------------------------------ stat editor stuff

# (attribute, label, low, high, reset value)
PERSONALITY_FACETS = [
    ("lawfulness", "Lawfulness", 0, 16, 8),
    ("sociability", "Sociability", 0, 16, 8),
    ("aggression", "Aggression", 0, 16, 8),
    ("stability", "Stability", 0, 16, 8),
]

# lifegen stats have no real cap in the game, queen training moves them by 1
LIFEGEN_STATS = [
    ("courage", "Courage", -10, 10, 0),
    ("intelligence", "Intelligence", -10, 10, 0),
    ("empathy", "Empathy", -10, 10, 0),
    ("compassion", "Compassion", -10, 10, 0),
    ("faith", "Faith", -9, 9, 0),
    ("starclan_affinity", "StarClan affinity", -100, 100, 0),
    ("dark_forest_affinity", "Dark Forest affinity", -100, 100, 0),
]

# BUTTERGEN: the honor system. Clan trust only shows for leaders, deputies and healers
HONOR_STATS = [
    ("honor", "Honor", -100, 100, 0),
    ("reputation", "Reputation", -100, 100, 0),
    ("clan_trust", "Clan trust", -100, 100, 0),
]


def honor_stats_for(cat: Cat) -> list:
    from scripts.honor.core import has_clan_trust

    return [row for row in HONOR_STATS if row[0] != "clan_trust" or has_clan_trust(cat)]

# these come from genes in genemod, adding them by hand wouldnt match how the cat looks
GENETIC_ONLY_CONDITIONS = [
    "manx syndrome", "flat nose", "rabbit gait", "albinism", "ocular albinism",
    "fully hairless", "partially hairless", "bad back", "narrowed chest", "bumpy skin",
]

# pregnancy and birth are handled by the pregnancy code, the editor leaves them alone
BIRTH_CONDITIONS = ("pregnant", "recovering_from_birth")

LIFE_FLAGS = [
    ("no_kits", "No kits"),
    ("no_mates", "No mates"),
    ("no_retire", "No retiring"),
]


def get_stat(cat: Cat, attr: str):
    if attr in ("lawfulness", "sociability", "aggression", "stability"):
        return getattr(cat.personality, attr)
    return getattr(cat, attr)


def set_stat(cat: Cat, attr: str, value: int):
    """sets a facet or lifegen stat, clamped to its range"""
    for table in (PERSONALITY_FACETS, LIFEGEN_STATS, HONOR_STATS):
        for name, _label, low, high, _reset in table:
            if name != attr:
                continue
            value = clamp(int(round(value)), low, high)
            if table is PERSONALITY_FACETS:
                # the setter picks a new trait if this facet doesnt fit the old one anymore
                setattr(cat.personality, attr, value)
            else:
                if attr == "faith":
                    # otherwise the faith lock would hide the change
                    cat.lock_faith = "flexible"
                    cat.no_faith = False
                setattr(cat, attr, value)
            return


def nudge_stat(cat: Cat, attr: str, amount: int):
    set_stat(cat, attr, get_stat(cat, attr) + amount)


def max_stats(cat: Cat, table):
    for name, _label, _low, high, _reset in table:
        if name == "dark_forest_affinity":
            # maxing out means a good cat, not a dark forest one
            set_stat(cat, name, 0)
            continue
        set_stat(cat, name, high)


def reset_stats(cat: Cat, table):
    for name, _label, _low, _high, reset in table:
        set_stat(cat, name, reset)


def all_traits(cat: Cat) -> list:
    from scripts.cat.personality import Personality

    table = Personality.trait_ranges["kit_traits" if cat.personality.kit else "normal_traits"]
    return sorted(table)


FACETS = (("lawfulness", "_law"), ("sociability", "_social"), ("aggression", "_aggress"), ("stability", "_stable"))


def _trait_table(kit: bool) -> dict:
    from scripts.cat.personality import Personality

    return Personality.trait_ranges["kit_traits" if kit else "normal_traits"]


def _shared_ranges(table: dict, trait: str, trait2: str):
    """the facet ranges both traits allow, or None if they can't both fit one cat"""
    shared = {}
    for facet, _attr in FACETS:
        low = max(table[trait][facet][0], table[trait2][facet][0])
        high = min(table[trait][facet][1], table[trait2][facet][1])
        if low > high:
            return None
        shared[facet] = (low, high)
    return shared


def second_trait_options(kit: bool, trait: str) -> list:
    """second traits that can go with this trait, since both have to fit the cat's facets"""
    table = _trait_table(kit)
    if trait not in table:
        return []
    return sorted(other for other in table if other != trait and _shared_ranges(table, trait, other))


def set_traits(cat: Cat, trait: str, trait2: str = None) -> bool:
    """Changes the trait, and the second trait if given, and moves the facets into the middle of
    what both allow so they stick. A second trait that can't go with the first is rerolled."""
    personality = cat.personality
    table = _trait_table(personality.kit)
    if trait not in table:
        return False
    trait2 = trait2 or personality.trait2
    shared = _shared_ranges(table, trait, trait2) if trait2 in table and trait2 != trait else None
    ranges = shared or {facet: table[trait][facet] for facet, _attr in FACETS}
    # set the private values straight away, going through the setters one at a time
    # would keep picking new traits in between
    for facet, attr in FACETS:
        setattr(personality, attr, (ranges[facet][0] + ranges[facet][1]) // 2)
    personality.trait = trait
    personality.trait2 = trait2 if shared else personality.choose_trait(exclude=trait)
    return True


def set_trait(cat: Cat, trait: str) -> bool:
    """changes the trait and moves the facets into that trait's range so it sticks"""
    return set_traits(cat, trait)


def set_second_trait(cat: Cat, trait2: str) -> bool:
    return set_traits(cat, cat.personality.trait, trait2)


# ------------------------------------------------------------------ skills

SKILL_SLOTS = [("primary", "Main skill"), ("secondary", "Second skill")]


def skill_options() -> dict:
    """{label: SkillPath} for every skill path, labels like "hunting". Two paths that share a
    label get their path name added."""
    from scripts.cat.skills import Skill, SkillPath

    labels = {path: Skill(path).get_short_skill_string() for path in SkillPath}
    counts = {}
    for label in labels.values():
        counts[label] = counts.get(label, 0) + 1
    options = {}
    for path, label in labels.items():
        if counts[label] > 1:
            label = f"{label} ({path.name.lower()})"
        options[label] = path
    return dict(sorted(options.items()))


def skill_text(cat: Cat, slot: str) -> str:
    import i18n

    skill = getattr(cat.skills, slot)
    if not skill:
        return "none"
    name = i18n.t(f"cat.skills.{skill.skill}")
    if skill.interest_only:
        return f"{name} (just an interest, {skill.points} points)"
    return f"{name} (level {skill.tier}, {skill.points} points)"


def set_skill_path(cat: Cat, slot: str, path) -> None:
    """Changes which skill a slot has. The points stay, a new skill starts at 0"""
    from scripts.cat.skills import Skill

    old = getattr(cat.skills, slot)
    other_slot = "secondary" if slot == "primary" else "primary"
    other = getattr(cat.skills, other_slot)
    if other and other.path == path:
        # the same skill twice would count double, swap the two instead
        setattr(cat.skills, slot, other)
        setattr(cat.skills, other_slot, old)
        return
    if old:
        old.path = path
    else:
        setattr(cat.skills, slot, Skill(path, 0, interest_only=cat.moons < 6))


def nudge_skill_points(cat: Cat, slot: str, amount: int) -> None:
    skill = getattr(cat.skills, slot)
    if skill:
        skill.points += amount


def toggle_skill_interest(cat: Cat, slot: str) -> None:
    """Kits only have interests, grown cats have real levels"""
    skill = getattr(cat.skills, slot)
    if skill:
        skill.interest_only = not skill.interest_only


def remove_second_skill(cat: Cat) -> None:
    # the main skill can only be changed, the game expects every cat to have one
    cat.skills.secondary = None


def hidden_options() -> list:
    from scripts.cat.skills import HiddenSkillEnum

    return ["none"] + [hidden.value for hidden in HiddenSkillEnum]


def set_hidden(cat: Cat, value: str) -> None:
    from scripts.cat.skills import HiddenSkillEnum

    cat.skills.hidden = None if value == "none" else HiddenSkillEnum(value)


def max_skills(cat: Cat) -> None:
    for slot, _label in SKILL_SLOTS:
        skill = getattr(cat.skills, slot)
        if skill:
            skill.interest_only = False
            skill.points = skill.point_range[1]


def reset_skills(cat: Cat) -> None:
    for slot, _label in SKILL_SLOTS:
        skill = getattr(cat.skills, slot)
        if skill:
            skill.points = 0


def condition_options(kind: str) -> list:
    """names that can be given to a cat, kind is temporary (injuries and illnesses) or permanent"""
    from scripts.cat.constants import PERMANENT_CONDITIONS, TEMPORARY_CONDITIONS

    if kind == "temporary":
        return sorted(name for name in TEMPORARY_CONDITIONS if name not in BIRTH_CONDITIONS)
    return sorted(name for name in PERMANENT_CONDITIONS
                  if name.replace("_", " ") not in GENETIC_ONLY_CONDITIONS)


def give_condition(cat: Cat, kind: str, name: str):
    from scripts.cat.conditions.gain_conditions import gain_permanent_condition, gain_temporary_condition

    if cat.dead:
        return
    if kind == "temporary":
        gain_temporary_condition(cat, name, prevent_death=True)
    else:
        gain_permanent_condition(cat, name)
    cat.pelt.rebuild_sprite = True


def remove_condition(cat: Cat, kind: str, name: str):
    cat.remove_condition(name)
    if name == "paralyzed":
        cat.pelt.paralyzed = False
    cat.pelt.rebuild_sprite = True


def heal_all(cat: Cat):
    """clears injuries and illnesses, keeps pregnancy and permanent conditions"""
    cat.temporary_conditions = [c for c in cat.temporary_conditions if c.name in BIRTH_CONDITIONS]
    cat.pelt.rebuild_sprite = True


def clear_permanent(cat: Cat):
    cat.permanent_conditions = []
    cat.pelt.paralyzed = False
    cat.pelt.rebuild_sprite = True


def unshun(cat: Cat):
    """welcomes a shunned cat back, the same way the clan forgiving them does"""
    if cat.status.is_shunned():
        cat.status.unshun_from_group(cat.status.group_ID)


def set_moons(cat: Cat, moons: int):
    cat.moons = max(0, int(moons))
    cat.pelt.rebuild_sprite = True


def set_rank(cat: Cat, rank) -> None:
    from scripts.cat.enums import CatRank
    from scripts.game_structure import game

    if rank == CatRank.LEADER:
        game.clan.new_leader(cat)
    else:
        cat.rank_change(rank, resort=True)
        if rank == CatRank.DEPUTY:
            game.clan.new_deputy(cat)
