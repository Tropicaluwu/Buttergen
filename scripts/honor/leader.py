"""BUTTERGEN: leaders and the warrior code (honor system step 8a).

Nobody judges a leader. When a leader's misdeed comes out, the Clan's trust in them drops instead.
StarClan may also send the healers an omen when a leader breaks the code, seen or not, and each
healer decides whether to tell the Clan, tell the leader alone, or keep it to themself.

Inside a judgment, a leader's feelings can get the better of them: about 1 in 4 times they let a
favorite off, or punish a cat they dislike one step harder.

Challenges are in scripts/honor/challenge.py (step 8b).

A leader's Clan trust rises a little with each good deed, and drifts 1 back toward "steady" every
3 moons that nothing changes it.

game.clan.code_leader = {"leader": leader ID, "trust_moon": the Clan age trust last changed}
"""

from random import choice, choices as weighted_choice, randint, random

from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.honor import core
from scripts.honor.acts import ACTS, CAUSES, HONOR_LOSS

# Clan trust lost when a leader's misdeed comes out, by level
TRUST_LOSS = {"minor": (4, 6), "serious": (10, 15), "grave": (20, 30)}
GOOD_DEED_TRUST = (1, 3)
OMEN_TRUST_LOSS = (3, 6)
DRIFT_EVERY = 3
STEADY = (-9, 9)
# the chance StarClan sends the healers an omen when a leader breaks the code
OMEN_CHANCE = {"minor": 0.10, "serious": 0.30, "grave": 0.60}
# a leader judging a cat they feel strongly about
FEELINGS_AT = 30
FEELINGS_CHANCE = 0.25
# told alone, the leader's temptations drop to this much
SHAKEN = 0.5
TOLD_ALONE_LIKE = (2, 5)
TELL, ALONE, KEEP = "tell", "alone", "keep"
OMEN_OPTIONS = (TELL, ALONE, KEEP)


def texts() -> dict:
    return load_lang_resource("events/honor_leader.json")


def _you():
    return game.clan.your_cat


def _alive_in_clan(cat) -> bool:
    return bool(cat) and not cat.dead and cat.status.alive_in_player_clan


def _like(cat_from, cat_to) -> int:
    rel = cat_from.relationships.get(cat_to.ID) if cat_from and cat_to else None
    return rel.like if rel else 0


def is_leader(cat) -> bool:
    return bool(cat) and cat.status.rank == CatRank.LEADER


def _post(text, main_cat, random_cat, other_clan=None, important=True):
    text = event_text_adjust(Cat, text, main_cat=main_cat, random_cat=random_cat, clan=game.clan,
                             other_clan=other_clan)
    event = EventInformation(text, ["misc"], [c.ID for c in (main_cat, random_cat) if c])
    if _you() in (main_cat, random_cat) and important:
        game.cur_events_list.insert(0, event)
    else:
        game.cur_events_list.append(event)
    return text


# ------------------------------------------------------------------ Clan trust

def _record():
    rec = getattr(game.clan, "code_leader", None)
    if not isinstance(rec, dict):
        rec = game.clan.code_leader = {}
    return rec


def change_trust(leader, amount):
    core.change_clan_trust(leader, amount)
    rec = _record()
    rec["leader"] = leader.ID
    rec["trust_moon"] = game.clan.age


def misdeed_out(leader, key, level=None):
    """a leader's misdeed came out: no judgment, the Clan trusts them less"""
    change_trust(leader, -randint(*TRUST_LOSS[level or ACTS[key]["level"]]))


def good_deed(leader):
    change_trust(leader, randint(*GOOD_DEED_TRUST))


def drift():
    """every 3 moons nothing changes it, the leader's trust moves 1 back toward steady"""
    leader = game.clan.leader
    if not _alive_in_clan(leader) or not is_leader(leader):
        return
    rec = _record()
    if rec.get("leader") != leader.ID:
        rec["leader"], rec["trust_moon"] = leader.ID, game.clan.age
        return
    if game.clan.age - rec.get("trust_moon", game.clan.age) < DRIFT_EVERY:
        return
    low, high = STEADY
    if leader.clan_trust > high:
        change_trust(leader, -1)
    elif leader.clan_trust < low:
        change_trust(leader, 1)
    else:
        rec["trust_moon"] = game.clan.age


# ------------------------------------------------------------------ breaking the code

def after_break(cat, key, other_clan=None, level=None):
    """called after a leader breaks the code (or anyone a grave misdeed, with Watchful Stars):
    StarClan may send the healers an omen. Weakened Stars halves the chance, Forsaken stops it"""
    if random() < OMEN_CHANCE[level or ACTS[key]["level"]] * core.card("omen_factor"):
        omen(cat, key, other_clan)


def misdeed_in_judgment(leader, key):
    """let a favorite off, or punish out of spite: it costs honor, and someone may see"""
    from scripts.honor import witness

    core.change_honor(leader, -randint(*HONOR_LOSS[ACTS[key]["level"]]))
    leader.code_done[key] = game.clan.age
    witness.after_break(leader, key, None)
    after_break(leader, key)


def feelings(leader, cat, step, ladder):
    """inside a judgment: (None, "") to let the cat off, else (step, a line to put before the
    sentence). Out of spite the step is one harsher"""
    if not is_leader(leader):
        return step, ""
    like = _like(leader, cat)
    t = texts()
    you = leader is _you()
    # step 8c: never with Iron Code
    if like > FEELINGS_AT and core.card("favorites_off") and random() < FEELINGS_CHANCE:
        _post(choice(t["favorite_off"]["you" if you else "others"]), leader, cat)
        misdeed_in_judgment(leader, "favorite_off")
        return None, ""
    if like < -FEELINGS_AT and step != ladder[-1] and random() < FEELINGS_CHANCE:
        misdeed_in_judgment(leader, "spite")
        line = choice(t["spite"]["you" if you else "others"])
        # the sentence's text has the judged cat as m_c, so swap the names around here
        line = event_text_adjust(Cat, line, main_cat=leader, random_cat=cat, clan=game.clan)
        return ladder[ladder.index(step) + 1], line
    return step, ""


# ------------------------------------------------------------------ StarClan omens

def healers() -> list:
    from scripts.honor.temptation import clanmates

    return [c for c in clanmates() if c.status.rank == CatRank.MEDICINE_CAT]


def omen(leader, key=None, other_clan=None):
    """StarClan is troubled by the leader (or, with Watchful Stars, any cat). Every healer in the
    Clan sees it and decides"""
    from scripts.honor import choices

    told = False
    for healer in healers():
        if healer is leader:
            continue
        if healer is _you():
            if choices.can_offer():
                choices.offer_omen(leader, key, other_clan)
                continue
            option = decide(healer, leader)
        else:
            option = decide(healer, leader)
        if option == TELL and told:
            continue  # the Clan already knows
        told = resolve(healer, leader, option, key, other_clan) == TELL or told


def decide(healer, leader) -> str:
    law = healer.personality.lawfulness / 16
    like = _like(healer, leader)
    weights = [
        0.2 + law * 0.4 + max(0, -like) / 100 + max(0, healer.honor) / 200,
        0.3 + max(0, like) / 100,
        0.05 + (1 - law) * 0.2 + max(0, -healer.honor) / 200 + max(0, like) / 200,
    ]
    return weighted_choice(OMEN_OPTIONS, weights)[0]


def resolve(healer, leader, option, key=None, other_clan=None):
    """what the healer does with the omen. Returns the option carried out. leader is the cat
    StarClan is troubled by: with Watchful Stars it can be anyone, and telling the Clan makes
    their misdeed come out"""
    from scripts.honor import temptation

    if not _alive_in_clan(healer) or not _alive_in_clan(leader):
        return None
    if option == KEEP:
        # step 2's "keep a sign secret": it can come out later
        temptation.do_act(healer, "hide_sign", leader, None)
        return KEEP
    t = texts()["omen"]
    you = _you()
    if option == TELL and not is_leader(leader) and key:
        from scripts.honor import witness

        witness.report(leader, healer, key, other_clan, "omen", naming=False)
        return TELL
    if option == TELL:
        change_trust(leader, -randint(*OMEN_TRUST_LOSS))
        variant = "tell_you" if healer is you else "tell_leader_you" if leader is you else "tell"
        _post(choice(t[variant]), leader, healer)
        return TELL
    # told alone: the leader is shaken, and likes the healer more or less for it
    for cause in CAUSES:
        if cause in leader.temptation:
            leader.temptation[cause] *= SHAKEN
    from scripts.honor.temptation import nudge

    sign = 1 if random() < leader.personality.lawfulness / 16 else -1
    nudge(leader, healer, like=sign * randint(*TOLD_ALONE_LIKE))
    variant = "alone_you" if healer is you else "alone_leader_you" if leader is you else "alone"
    _post(choice(t[variant]), leader, healer, important=you in (healer, leader))
    return ALONE


# ------------------------------------------------------------------ every skip

def on_skip(full_moon: bool):
    if game.clan:
        drift()
        # step 8b: challenging a leader whose trust is broken
        from scripts.honor import challenge

        challenge.on_skip(full_moon)
