"""BUTTERGEN: Let your cat decide. The player's cat makes the big choices on their own: their path,
retiring, their deputy, names and the warrior code choices. Each is a clan setting (the "your cat"
tab). Texts: events/let_decide.json."""

from random import choices as weighted_choice, random

from scripts.cat.enums import CatRank
from scripts.cat.skills import SkillPath
from scripts.clan_package.settings import get_clan_setting
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.game.switches import (
    Switch,
    switch_append_list_value,
    switch_get_value,
    switch_remove_list_value,
)
from scripts.game_structure.localization import load_lang_resource

# the clan settings
ALL = "decide all"
PATH, RETIRE, DEPUTY, NAMES, CODE, MATES = (
    "decide path", "decide retire", "decide deputy", "decide names", "decide code", "decide mates")

WARRIOR, HEALER, MEDIATOR, QUEEN = "warrior", "healer", "mediator", "queen"
RANKS = {
    WARRIOR: (CatRank.APPRENTICE, CatRank.WARRIOR),
    HEALER: (CatRank.MEDICINE_APPRENTICE, CatRank.MEDICINE_CAT),
    MEDIATOR: (CatRank.MEDIATOR_APPRENTICE, CatRank.MEDIATOR),
    QUEEN: (CatRank.QUEENS_APPRENTICE, CatRank.QUEEN),
}
WARRIOR_SKILLS = {SkillPath.HUNTER, SkillPath.FIGHTER, SkillPath.RUNNER, SkillPath.CLIMBER,
                  SkillPath.SWIMMER, SkillPath.STEALTH, SkillPath.TRACKER}
SPIRIT_SKILLS = {SkillPath.STAR, SkillPath.OMEN, SkillPath.DREAM, SkillPath.CLAIRVOYANT,
                 SkillPath.PROPHET, SkillPath.SENSE}
SPEAKING_SKILLS = {SkillPath.SPEAKER, SkillPath.INSIGHTFUL}
CARING_TRAITS = {"motherly", "maternal", "gentle", "warm", "protective", "sweet", "sweetie"}
CALM_TRAITS = {"calm", "mellow", "relaxed", "peaceful", "easy-going"}
AMBITIOUS_TRAITS = {"ambitious", "competitive", "driven", "hardworking", "power-hungry"}

# reasons the event line can give
NO_APPRENTICE, SKILL, PERSONALITY = "no_apprentice", "skill", "personality"

OLD = 119
ASK_AGAIN = 6
RETIRE_OLD, RETIRE_HURT, RETIRE_SEVERE = 50, 30, 30
RETIRE_SICK, RETIRE_CALM, RETIRE_AMBITIOUS, RETIRE_RANK = 10, 15, -25, -15
RETIRE_MIN, RETIRE_MAX = 5, 95


def texts() -> dict:
    return load_lang_resource("events/let_decide.json")


def on(setting) -> bool:
    return bool(get_clan_setting(ALL, default=False) or get_clan_setting(setting, default=False))


def button_text() -> str:
    """"Let m_c decide", the same as in the warrior code choices"""
    from scripts.honor import choices

    return choices.texts()["let_decide"].replace("%{name}", str(_you().name))


def _you():
    return game.clan.your_cat if game.clan else None


def _in_clan(cat) -> bool:
    return bool(cat) and not cat.dead and cat.status.alive_in_player_clan


def _clan_cats():
    from scripts.cat.cats import Cat

    return [c for c in Cat.all_cats_list if _in_clan(c)]


def _render(text, random_cat=None):
    from scripts.cat.cats import Cat

    return event_text_adjust(Cat, text, main_cat=_you(), random_cat=random_cat, clan=game.clan)


def _post(text, random_cat=None):
    cats = [c.ID for c in (_you(), random_cat) if c]
    game.cur_events_list.insert(0, EventInformation(_render(text, random_cat), ["misc"], cats))


def _traits(cat) -> set:
    return {t for t in (cat.personality.trait, cat.personality.trait2) if t}


# their path

def path_points(cat) -> dict:
    """for each path: (points, {reason: how much it gave})"""
    skills = {s.path for s in (cat.skills.primary, cat.skills.secondary) if s} if cat.skills else set()
    traits = _traits(cat)
    p = cat.personality
    ranks = [c.status.rank for c in _clan_cats()]
    healers = ranks.count(CatRank.MEDICINE_CAT)
    healer_apps = ranks.count(CatRank.MEDICINE_APPRENTICE)
    mediators = ranks.count(CatRank.MEDIATOR)

    skill = {
        WARRIOR: 2 if skills & WARRIOR_SKILLS else 0,
        HEALER: (5 if SkillPath.HEALER in skills else 0) + (2 if skills & SPIRIT_SKILLS else 0),
        MEDIATOR: (5 if SkillPath.MEDIATOR in skills else 0) + (3 if skills & SPEAKING_SKILLS else 0),
        QUEEN: 5 if SkillPath.KIT in skills else 0,
    }
    personality = {
        WARRIOR: 2 if p.aggression >= 10 else 0,
        HEALER: 2 if p.stability >= 10 else 0,
        MEDIATOR: 2 if p.sociability >= 11 else 0,
        QUEEN: (2 if p.sociability >= 10 and p.aggression <= 6 else 0) + (1 if traits & CARING_TRAITS else 0),
    }
    found = {}
    for path, base in ((WARRIOR, 6), (HEALER, 1), (MEDIATOR, 1), (QUEEN, 1)):
        points = base + skill[path] + personality[path]
        gave = {SKILL: skill[path], PERSONALITY: personality[path]}
        if path == HEALER and healers and not healer_apps:
            gave[NO_APPRENTICE] = points * 2
            points *= 3
        elif path == HEALER and healer_apps >= 2:
            points *= 0.3
        elif path == MEDIATOR and mediators >= 2:
            points *= 0.5
        found[path] = (points, gave)
    return found


def choose_path() -> CatRank:
    """picks the rank, and keeps the event line for the skip that comes right after"""
    you = _you()
    points = path_points(you)
    path = weighted_choice(list(points), [points[name][0] for name in points])[0]
    gave = points[path][1]
    reason = max(gave, key=gave.get)
    t = texts()["path"]
    text = t[path]
    if gave[reason]:
        text += " " + t["reasons"][reason]
    # written now, while they still have their kit name
    game.decide_lines = [_render(text)]
    return RANKS[path][0 if you.moons < 12 else 1]


# retiring

def retire_chance(cat) -> int:
    """in percent"""
    if cat.moons >= OLD:
        chance = RETIRE_OLD
    else:
        chance = RETIRE_HURT
        if any(c.severity == "severe" for c in cat.permanent_conditions):
            chance += RETIRE_SEVERE
    if any(c.name != "pregnant" for c in cat.temporary_conditions):
        chance += RETIRE_SICK
    traits = _traits(cat)
    if traits & CALM_TRAITS:
        chance += RETIRE_CALM
    if traits & AMBITIOUS_TRAITS:
        chance += RETIRE_AMBITIOUS
    if cat.status.rank in (CatRank.LEADER, CatRank.DEPUTY):
        chance += RETIRE_RANK
    return max(RETIRE_MIN, min(RETIRE_MAX, chance))


def said_no_lately(cat) -> bool:
    """they decided not to retire, and aren't asked again for a while"""
    moon = game.clan.decide_retire_no.get(cat.ID)
    return moon is not None and game.clan.age - moon < ASK_AGAIN


def decide_retire() -> bool:
    from scripts.ui.windows.retire_prompt import RetireWindow

    you = _you()
    yes = random() * 100 < retire_chance(you)
    t = texts()["retire"]
    if yes:
        game.clan.decide_retire_no.pop(you.ID, None)
        RetireWindow.retire_your_cat()
    else:
        game.clan.decide_retire_no[you.ID] = game.clan.age
    _post(t["yes" if yes else "no"])
    return yes


def _retire_on_skip():
    you = _you()
    can = (_in_clan(you) and you.status.rank != CatRank.ELDER and not you.status.is_shunned()
           and not you.no_retire)
    waiting = switch_get_value(Switch.windows_dict)
    # old cats are only asked at 119 moons by the game, so this asks again
    moon = game.clan.decide_retire_no.get(you.ID)
    if (can and moon is not None and you.moons >= OLD and game.clan.age - moon >= ASK_AGAIN
            and "retire" not in waiting):
        game.clan.decide_retire_no.pop(you.ID)
        switch_append_list_value(Switch.windows_dict, "retire")
    if on(RETIRE) and "retire" in switch_get_value(Switch.windows_dict):
        switch_remove_list_value(Switch.windows_dict, "retire")
        if can:
            decide_retire()


# their deputy

_deputy_now = False


def picks_deputy(clan) -> bool:
    """the player's cat is the leader, and picks for themselves"""
    you = _you()
    return (clan is game.clan and _in_clan(you) and clan.leader is you and not you.status.is_shunned()
            and (_deputy_now or on(DEPUTY)))


def trust_in(cat, other) -> int:
    rel = cat.relationships.get(other.ID)
    return rel.respect * 3 + rel.trust * 2 + rel.like + rel.comfort if rel else 0


def most_trusted(cats):
    you = _you()
    return max(cats, key=lambda c: trust_in(you, c))


def post_deputy(deputy):
    _post(texts()["deputy"], deputy)


def decide_deputy():
    """the button in the deputy window"""
    global _deputy_now
    from scripts.events_module.ceremony.perform_ceremony import check_and_promote_deputy

    _deputy_now = True
    try:
        check_and_promote_deputy(game.clan)
    finally:
        _deputy_now = False


# every skip

def on_skip():
    """at the end of a skip, after everything that asks the player something"""
    if not game.clan or not _you():
        return
    lines, game.decide_lines = getattr(game, "decide_lines", []), []
    _retire_on_skip()
    from scripts.honor import choices

    choices.decide_waiting()
    if _in_clan(_you()):
        for line in lines:
            game.cur_events_list.insert(0, EventInformation(line, ["misc"], [_you().ID]))
