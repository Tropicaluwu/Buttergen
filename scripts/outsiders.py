"""BUTTERGEN: Other Clans step 1. The cats from outside the player's Clan that the player's cat has
met (other Clans' cats, kittypets, loners and rogues), Gatherings, and meeting cats on border
patrols. Multi clan mode only. Texts: events/outsiders.json."""

from random import choice, randint, random, sample

from scripts.cat.enums import CatRank
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource

MET_MOONS = 12
# any relationship value over this keeps a cat met
KEEP_MET_AT = 10
# Gatherings: chance the player's cat goes, by rank (leader and deputy always)
ATTEND = 0.5
ATTEND_ELDER = 0.25
MEET_AT_GATHERING = (1, 3)
LIKE_AT_GATHERING = {"ally": (2, 6), "neutral": (2, 6), "hostile": (-2, 2)}
BORDER_MEET = 0.5


def texts() -> dict:
    return load_lang_resource("events/outsiders.json")


def on() -> bool:
    return bool(game.clan) and game.clan.clancount == "multiclan"


def _you():
    return game.clan.your_cat if game.clan else None


def _met() -> dict:
    if getattr(game.clan, "met", None) is None:
        game.clan.met = {}
    return game.clan.met


def _render(text, main_cat, other_clan=None, random_cat=None):
    from scripts.cat.cats import Cat

    return event_text_adjust(Cat, text, main_cat=main_cat, random_cat=random_cat, clan=game.clan,
                             other_clan=other_clan)


def is_outside(cat) -> bool:
    """alive and not in the player's Clan: another Clan's cat, or a kittypet, loner or rogue"""
    return bool(cat) and not cat.dead and not cat.status.alive_in_player_clan


def clan_of(cat):
    """the OtherClan a cat lives in, or None for kittypets, loners and rogues"""
    for clan in game.clan.all_other_clans:
        if cat.status.group_ID == clan.group_ID:
            return clan
    return None


def mood(cat) -> str:
    """how the cat's Clan gets along with the player's: ally, neutral or hostile ("outsider" for
    kittypets, loners and rogues)"""
    other = clan_of(cat)
    if other is None:
        return "outsider"
    return game.clan.get_relations(game.clan, other, get_label=True)


def _close(cat) -> bool:
    you = _you()
    rel = you.relationships.get(cat.ID) if you else None
    if not rel:
        return False
    return max(rel.like, rel.respect, rel.comfort, rel.trust, rel.romance) > KEEP_MET_AT


def has_met(cat) -> bool:
    if not on() or not is_outside(cat):
        return False
    entry = _met().get(cat.ID)
    if entry and game.clan.age - entry["moon"] <= MET_MOONS:
        return True
    return bool(entry) and _close(cat)


def meet(cat, how, like=None):
    """the player's cat meets them: remembered, and a relationship starts if there isn't one"""
    from scripts.honor.temptation import nudge

    you = _you()
    if not you or not is_outside(cat) or cat is you:
        return
    _met()[cat.ID] = {"moon": game.clan.age, "how": how}
    if like:
        nudge(you, cat, like=like)
        nudge(cat, you, like=like)
    else:
        # touching the relationship makes it exist for both cats
        nudge(you, cat, like=0)
        nudge(cat, you, like=0)


def met_note(cat) -> str:
    """for the profile: "met at the Gathering, 3 moons ago" """
    entry = _met().get(cat.ID) if on() else None
    if not entry or not has_met(cat):
        return ""
    t = texts()["profile"]
    moons = game.clan.age - entry["moon"]
    when = t["this_moon"] if moons == 0 else t["moons_ago"].replace("%{moons}", str(moons))
    return t["met"].replace("%{how}", t["how"].get(entry["how"], entry["how"])).replace("%{when}", when)


def can_talk(cat_to, cat_from) -> bool:
    """the player's cat and a cat they've met may talk, flirt and insult, both ways"""
    you = _you()
    if not on() or you is None:
        return False
    other = cat_to if cat_from is you else cat_from if cat_to is you else None
    return other is not None and not you.dead and you.status.alive_in_player_clan and has_met(other)


def _attends(you) -> bool:
    if you.dead or not you.status.alive_in_player_clan or you.status.is_shunned():
        return False
    if you.status.rank.is_baby():
        return False
    if not you.can_work():
        return False
    from scripts.honor import judgment

    sentence = judgment.sentence(you)
    if sentence and sentence["type"] == judgment.DUTIES:
        return False
    if you.status.rank in (CatRank.LEADER, CatRank.DEPUTY):
        return True
    return random() < (ATTEND_ELDER if you.status.rank == CatRank.ELDER else ATTEND)


def _gathering_pool(you):
    from scripts.cat.cats import Cat

    pool = []
    for cat in Cat.all_cats_list:
        if cat.dead or cat.status.rank.is_baby() or clan_of(cat) is None:
            continue
        # mostly cats near the player's cat's rank and age
        weight = 1.0
        if cat.status.rank.is_any_apprentice_rank() == you.status.rank.is_any_apprentice_rank():
            weight += 3
        weight += max(0, 3 - abs(cat.moons - you.moons) / 12)
        pool.append((weight, cat))
    return pool


def _pick(pool, amount):
    chosen = []
    pool = list(pool)
    for _ in range(min(amount, len(pool))):
        total = sum(w for w, _ in pool)
        roll = random() * total
        for i, (w, cat) in enumerate(pool):
            roll -= w
            if roll <= 0:
                chosen.append(cat)
                pool.pop(i)
                break
    return chosen


def gathering():
    you = _you()
    if not you or not _attends(you):
        return None
    cats = _pick(_gathering_pool(you), randint(*MEET_AT_GATHERING))
    if not cats:
        return None
    t = texts()["gathering"]
    first = cats[0]
    first_mood = mood(first)
    for cat in cats:
        meet(cat, "gathering", like=randint(*LIKE_AT_GATHERING[mood(cat)]))
    group = "apprentice" if (first.status.rank.is_any_apprentice_rank()
                             and you.status.rank.is_any_apprentice_rank()) else first_mood
    text = _render(choice(t[group] if group in t else t["neutral"]), first, clan_of(first))
    if len(cats) > 1:
        others = [f"{c.name} of {clan_of(c).name}" for c in cats[1:]]
        names = others[0] if len(others) == 1 else ", ".join(others[:-1]) + " and " + others[-1]
        text += " " + t["also"].replace("%{names}", names)
    game.cur_events_list.append(EventInformation(text, ["other_clans"], [you.ID] + [c.ID for c in cats]))
    return text


def after_patrol(patrol, processed_text, patrol_cats):
    """the player's cat was on a patrol that ran into another Clan: they may meet one of its cats"""
    from scripts.cat.cats import Cat

    you = _you()
    other = getattr(patrol, "other_clan", None)
    if (not on() or not you or you not in patrol_cats or other is None
            or not processed_text or other.name not in processed_text or random() >= BORDER_MEET):
        return []
    pool = [c for c in Cat.all_cats_list if not c.dead and c.status.group_ID == other.group_ID
            and not c.status.rank.is_baby() and c.status.rank != CatRank.ELDER]
    if not pool:
        return []
    cat = choice(pool)
    meet(cat, "border")
    return [_render(choice(texts()["border"]), cat, other)]


def on_skip(full_moon: bool):
    if not on():
        return
    if full_moon:
        gathering()
    # met cats who are gone, or long forgotten, drop off the list
    from scripts.cat.cats import Cat

    for cat_id in list(_met()):
        cat = Cat.fetch_cat(cat_id)
        if cat is None or cat.dead:
            del _met()[cat_id]


def pick_cats(group_id, amount=1, exclude=()):
    """some living, grown cats of a group (for exploring patrols)"""
    from scripts.cat.cats import Cat

    pool = [c for c in Cat.all_cats_list if not c.dead and c.status.group_ID == group_id
            and not c.status.rank.is_baby() and c not in exclude]
    return sample(pool, min(amount, len(pool)))
