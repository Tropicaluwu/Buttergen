"""BUTTERGEN: exile and coming back (honor system step 6).

A cat exiled from your Clan (by a judgment, or by LifeGen's shunning) keeps a record of when and
why. After a wait that depends on why, they can ask to come home, or, in multi clan mode, ask
another Clan to take them in. The chances depend on the leader who answers, the Clan's feelings,
ties to that Clan, how the Clans get along, and what the cat offers.

Your cat asks through the profile's return button. Other exiled cats ask on their own now and then.
"""

from random import choice, random

from scripts.cat.cats import Cat
from scripts.cat.enums import CatAge, CatGroup, CatRank
from scripts.clan_package import cotc
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource

# moons to wait before asking to come home, by why the cat was exiled
WAIT = {"minor": 2, "serious": 4, "grave": 8, "shunning": 4}
RETRY_HOME = 3
RETRY_CLAN = 6
HOME_BASE, CLAN_BASE = 30, 25
LOWEST, HIGHEST = 5, 90
LOST_TRUST_MOONS = 6
# chance per moon that another exiled cat asks somewhere, once their wait is over
OTHERS_ASK = 1 / 6
OLD_CLAN_RELATION_LOSS = 3


def texts() -> dict:
    return load_lang_resource("events/honor_exile.json")


def _you():
    return game.clan.your_cat if game.clan else None


def _like(cat_from, cat_to) -> int:
    rel = cat_from.relationships.get(cat_to.ID) if cat_from and cat_to else None
    return rel.like if rel else 0


# ------------------------------------------------------------------ the record

def _prior_rank(cat):
    try:
        rank = cat.status.find_prior_clan_rank(CatGroup.PLAYER_CLAN_ID)
    except Exception:
        rank = None
    return rank.value if rank else None


def record(cat, level):
    """called when a cat is exiled from your Clan. level: minor, serious, grave or shunning"""
    age = game.clan.age
    cat.code_exile = {"moon": age, "level": level if level in WAIT else "shunning",
                      "rank": _prior_rank(cat),
                      "next_home": age + WAIT.get(level, WAIT["shunning"]), "refused": {}}


def is_exiled(cat) -> bool:
    """exiled from your Clan and not in any Clan now"""
    return (bool(cat) and not cat.dead and cat.status.is_exiled(CatGroup.PLAYER_CLAN_ID)
            and not cat.status.group.is_any_clan_group())


def info(cat):
    """the record, made now for cats exiled before step 6 (they can ask right away)"""
    if not getattr(cat, "code_exile", None):
        cat.code_exile = {"moon": game.clan.age, "level": "shunning", "rank": None,
                          "next_home": game.clan.age, "refused": {}}
    return cat.code_exile


def moons_until_home(cat) -> int:
    return max(0, info(cat)["next_home"] - game.clan.age)


def open_clans(cat) -> list:
    """the other Clans that will hear the cat now (multi clan mode only)"""
    if game.clan.clancount != "multiclan":
        return []
    refused = info(cat).get("refused", {})
    return [c for c in game.clan.all_other_clans
            if refused.get(c.group_ID, 0) <= game.clan.age and _leader_of(c) is not None]


def clan_wait(cat, clan) -> int:
    return max(0, info(cat).get("refused", {}).get(clan.group_ID, 0) - game.clan.age)


# ------------------------------------------------------------------ the chances

def _leader_of(clan):
    if clan is game.clan:
        from scripts.honor.judgment import _judge_for

        return _judge_for(None)
    alive = [c for c in Cat.all_cats_list if not c.dead and c.status.group_ID == clan.group_ID]
    for rank in (CatRank.LEADER, CatRank.DEPUTY):
        for c in alive:
            if c.status.rank == rank:
                return c
    return None


def _leader_terms(leader, cat) -> int:
    if leader is None:
        return 0
    chance = -10 * round((leader.personality.lawfulness - 8) / 8)
    like = _like(leader, cat)
    return chance + (10 if like > 30 else -10 if like < -30 else 0)


def home_chance(cat) -> int:
    from scripts.honor.judgment import _clan_push

    rec = info(cat)
    waited = game.clan.age - (rec["moon"] + WAIT.get(rec["level"], WAIT["shunning"]))
    chance = HOME_BASE + min(20, 5 * max(0, waited))
    chance += _leader_terms(_leader_of(game.clan), cat)
    chance -= 15 * _clan_push(cat)
    if rec["level"] == "grave":
        chance -= 15
    return max(LOWEST, min(HIGHEST, chance))


def _ties(cat, clan) -> int:
    there = [c for c in Cat.all_cats_list if not c.dead and c.status.group_ID == clan.group_ID]
    ids = {c.ID for c in there}
    bonus = 20 if any(m in ids for m in cat.mate) else 0
    kin = set(cat.get_parents()) | set(cat.get_siblings()) | set(cat.get_children())
    bonus += 10 if kin & ids else 0
    friends = sum(1 for c in there if _like(c, cat) > 30)
    return bonus + min(10, 5 * friends)


def clan_chance(cat, clan) -> int:
    rec = info(cat)
    chance = CLAN_BASE
    leader = _leader_of(clan)
    if leader is not None:
        chance += -10 * round((leader.personality.lawfulness - 8) / 8)
    chance += {"minor": 10, "grave": -15}.get(rec["level"], 0)
    chance += _ties(cat, clan)
    label = game.clan.get_relations(game.clan, clan, get_label=True)
    chance += {"hostile": 10, "ally": -10}.get(label, 0)
    if rec.get("rank") in (CatRank.MEDICINE_CAT.value, CatRank.MEDICINE_APPRENTICE.value):
        chance += 15
    if cat.age in (CatAge.YOUNG_ADULT, CatAge.ADULT):
        chance += 5
    skill = cat.skills.primary
    if skill and getattr(skill, "tier", 0) >= 2:
        chance += 5
    return max(LOWEST, min(HIGHEST, chance))


# ------------------------------------------------------------------ asking

def _post(key, cat, leader, other_clan=None):
    you = _you()
    lines = texts()[key]["you" if cat is you else "others"]
    if not lines:
        return ""
    text = event_text_adjust(Cat, choice(lines), main_cat=cat, random_cat=leader, clan=game.clan,
                             other_clan=other_clan)
    event = EventInformation(text, ["misc"], [c.ID for c in (cat, leader) if c])
    if cat is you:
        game.cur_events_list.insert(0, event)
    else:
        game.cur_events_list.append(event)
    return text


def _welcome(cat, group_ID):
    from scripts.cat.microservices.add_to_clan import add_to_clan

    add_to_clan(cat, group_ID)
    cat.code_exile = None
    cat.code_sentence = {"type": "lost_trust", "start": game.clan.age,
                         "until": game.clan.age + LOST_TRUST_MOONS}


def ask_home(cat):
    """the cat asks to come back to your Clan. Returns the event text"""
    if not is_exiled(cat) or moons_until_home(cat):
        return None
    leader = _leader_of(game.clan)
    if random() * 100 < home_chance(cat):
        _welcome(cat, CatGroup.PLAYER_CLAN_ID)
        return _post("home_yes", cat, leader)
    info(cat)["next_home"] = game.clan.age + RETRY_HOME
    return _post("home_no", cat, leader)


def ask_clan(cat, clan):
    """the cat asks another Clan to take them in. Returns the event text"""
    if not is_exiled(cat) or clan not in open_clans(cat):
        return None
    leader = _leader_of(clan)
    if random() * 100 < clan_chance(cat, clan):
        _welcome(cat, clan.group_ID)
        cotc.change_clan_relations(game.clan, clan, -OLD_CLAN_RELATION_LOSS)
        return _post("clan_yes", cat, leader, clan)
    info(cat).setdefault("refused", {})[clan.group_ID] = game.clan.age + RETRY_CLAN
    return _post("clan_no", cat, leader, clan)


# ------------------------------------------------------------------ every full moon

def on_full_moon():
    """other exiled cats ask on their own, now and then"""
    you = _you()
    for cat in list(Cat.all_cats_list):
        if cat is you or not getattr(cat, "code_exile", None) or not is_exiled(cat):
            continue
        if random() >= OTHERS_ASK:
            continue
        clans = open_clans(cat)
        if clans and random() < 0.5:
            ask_clan(cat, choice(clans))
        elif not moons_until_home(cat):
            ask_home(cat)
