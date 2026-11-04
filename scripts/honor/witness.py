"""BUTTERGEN: witnesses and secrets (honor system step 3).

When a cat breaks the code, someone may see. The witness reports it, keeps the secret, or
holds it over the offender. Kept and held secrets live in game.clan.code_secrets and can come
out later through gossip, a falling-out, the witness naming them when caught, or the witness
dying. Secrets older than 24 moons are forgotten.

Your cat picks for themself as a witness until step 5 adds the choice button.
"""

from random import choice, randint, random

from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank
from scripts.events_module import weekskip
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.honor import core
from scripts.honor.acts import ACTS

# where each act happens, and the chance someone sees it there
SEE_CHANCE = {"public": 1.0, "camp": 0.45, "border": 0.25, "secret": 0.12}
WHERE = {
    "gathering_fight": "public",
    "eat_first": "camp", "skip_duties": "camp", "app_eat_first": "camp", "disobey_mentor": "camp",
    "favorite_herbs": "camp", "leave_den": "camp", "kits_wander": "camp", "best_nest": "camp",
    "spread_rumors": "camp", "unfair_patrols": "camp", "twist_words": "camp",
    "hunt_border": "border", "let_trespasser": "border", "markers_lapse": "border",
    "neglect_kit": "border", "twoleg_food": "border",
    "sneak_out": "secret", "lie_leader": "secret", "hide_sign": "secret", "bend_sign": "secret",
    "hide_news": "secret", "pass_secrets": "secret", "carry_messages": "secret",
}
# reputation lost when it comes out
REPUTATION_LOSS = {"minor": (3, 5), "serious": (8, 12), "grave": (15, 25)}
# what reporting gives the witness, it's following the code
REPORT_HONOR, REPORT_REPUTATION = 2, 1
FORGET_AFTER = 24
OUT_AT_KNOWERS = 4
NAME_OTHERS_CHANCE = 0.3
DEATHBED_CHANCE = 0.4
FALLING_OUT_LIKE = -40
# chance per moon a held secret gets a favor called in
FAVOR_CHANCE = 0.15
# other cats' keep and hold events show this often, so the events don't fill up
SHOW_OTHERS_QUIET = 1 / 3


def texts() -> dict:
    return load_lang_resource("events/honor_witness.json")


def _you():
    return game.clan.your_cat


def _alive_in_clan(cat) -> bool:
    return bool(cat) and not cat.dead and cat.status.alive_in_player_clan


def _like(cat_from, cat_to) -> int:
    rel = cat_from.relationships.get(cat_to.ID) if cat_from and cat_to else None
    return rel.like if rel else 0


def _nudge(cat_from, cat_to, **stats):
    from scripts.honor.temptation import nudge

    nudge(cat_from, cat_to, **stats)


def _clan_by_name(name):
    for clan in game.clan.all_other_clans:
        if clan.name == name:
            return clan
    return None


# ------------------------------------------------------------------ text

def _phrase(key, you: bool, who="m_c") -> str:
    them, yours = texts()["acts"][key]
    return yours if you else them.replace("m_c", who)


def _post(group, offender, witness, key, other_clan, variant=None, named_key=None):
    """picks the right text for who's involved and adds it to the events"""
    you = _you()
    lines = texts()[group]
    if variant is None:
        if offender is you:
            variant = "you_did"
        elif witness is you:
            variant = "you_saw"
        else:
            variant = "others"
    if variant not in lines:
        return None
    text = choice(lines[variant])
    if key:
        text = text.replace("[act you]", _phrase(key, True)).replace("[act]", _phrase(key, False))
    if named_key:
        text = text.replace("[act r_c]", _phrase(named_key, False, "r_c"))
    text = event_text_adjust(Cat, text, main_cat=offender, random_cat=witness, clan=game.clan,
                             other_clan=other_clan)
    ids = [c.ID for c in (offender, witness) if c]
    event = EventInformation(text, ["misc"], ids)
    if you in (offender, witness):
        game.cur_events_list.insert(0, event)
    else:
        game.cur_events_list.append(event)
    return text


# ------------------------------------------------------------------ who sees

def _clanmates(exclude):
    from scripts.honor.temptation import clanmates

    return [
        c for c in clanmates(exclude=exclude)
        if not c.status.rank.is_baby() and c.status.rank != CatRank.LEADER
    ]


def pick_witness(offender, key):
    where = WHERE.get(key, "camp")
    pool = _clanmates(offender)
    weights = []
    for cat in pool:
        w = 1.0
        if where == "camp":
            if cat.status.rank == offender.status.rank:
                w += 1
            if _like(cat, offender) < -10:
                w += 2
        elif where == "border":
            if cat.ID == offender.mentor:
                w += 3
            elif cat.status.rank not in (CatRank.WARRIOR, CatRank.APPRENTICE, CatRank.DEPUTY):
                w = 0.2
        else:
            close = cat.ID in offender.mate or cat.ID == offender.mentor or cat.ID in offender.apprentice
            if close:
                w += 4
            elif cat.status.rank == offender.status.rank:
                w += 1
            else:
                w = 0.3
        weights.append(w)
    if not pool:
        return None
    roll = random() * sum(weights)
    for cat, w in zip(pool, weights):
        roll -= w
        if roll <= 0:
            return cat
    return pool[-1]


def decide(witness, offender, key) -> str:
    """"report", "keep" or "hold" """
    law = witness.personality.lawfulness / 16
    like = _like(witness, offender)
    level_bonus = {"minor": 0, "serious": 0.15, "grave": 0.35}[ACTS[key]["level"]]
    scores = {
        "report": 0.15 + law * 0.5 + max(0, witness.honor) / 200 + max(0, -like) / 150 + level_bonus,
        "keep": 0.25 + max(0, like) / 100,
        "hold": 0.05 + (1 - law) * 0.25 + max(0, -witness.honor) / 200 + max(0, -like) / 200,
    }
    roll = random() * sum(scores.values())
    for what, score in scores.items():
        roll -= score
        if roll <= 0:
            return what
    return "report"


# ------------------------------------------------------------------ after a broken rule

def after_break(offender, key, other_clan):
    """called by temptation.do_act after a cat breaks the code"""
    where = WHERE.get(key)
    if where is None or random() >= SEE_CHANCE[where]:
        return
    witness = pick_witness(offender, key)
    if witness is None:
        return
    if where == "public":
        report(offender, witness, key, other_clan, "report")
        return
    what = decide(witness, offender, key)
    if what == "report":
        report(offender, witness, key, other_clan, "report")
        return
    held = what == "hold"
    game.clan.code_secrets.append({
        "offender": offender.ID,
        "witness": witness.ID,
        "act": key,
        "moon": game.clan.age,
        "held": held,
        "knowers": [witness.ID],
        "clan": other_clan.name if other_clan else None,
    })
    if held:
        _nudge(offender, witness, trust=-randint(6, 12), like=-randint(3, 6))
    you = _you()
    if you in (offender, witness) or random() < SHOW_OTHERS_QUIET:
        _post("hold" if held else "keep", offender, witness, key, other_clan)


def report(offender, witness, key, other_clan, group, naming=True):
    """the offender's misdeed comes out. witness is None when the whole Clan finds out"""
    core.change_reputation(offender, -randint(*REPUTATION_LOSS[ACTS[key]["level"]]))
    # step 4: the leader judges it at the next full moon
    from scripts.honor import judgment

    judgment.queue(offender, key, other_clan)
    leader = game.clan.leader
    if _alive_in_clan(leader) and leader is not offender:
        _nudge(leader, offender, respect=-randint(3, 8), trust=-randint(3, 8))
    if witness is not None and group in ("report", "falling_out"):
        _nudge(offender, witness, like=-randint(5, 10))
        if group == "report":
            core.change_honor(witness, REPORT_HONOR)
            core.change_reputation(witness, REPORT_REPUTATION)
    _post(group, offender, witness, key, other_clan)
    if naming:
        name_others(offender)


def name_others(caught):
    """a caught cat may name someone whose secret they know, to share the blame"""
    theirs = [s for s in game.clan.code_secrets if caught.ID in s["knowers"]]
    if not theirs or random() >= NAME_OTHERS_CHANCE:
        return
    secret = choice(theirs)
    named = Cat.fetch_cat(secret["offender"])
    game.clan.code_secrets.remove(secret)
    if not _alive_in_clan(named):
        return
    key, other_clan = secret["act"], _clan_by_name(secret["clan"])
    core.change_reputation(named, -randint(*REPUTATION_LOSS[ACTS[key]["level"]]))
    from scripts.honor import judgment

    judgment.queue(named, key, other_clan)
    _nudge(named, caught, like=-randint(8, 14))
    you = _you()
    variant = "you_named" if named is you else ("you_name" if caught is you else "others")
    _post("naming", caught, named, None, other_clan, variant=variant, named_key=key)


# ------------------------------------------------------------------ every skip

def on_skip():
    """secrets age, spread, get called in, or come out"""
    if not game.clan:
        return
    scale = 1 / weekskip.WEEKS_IN_MOON if weekskip.on() else 1.0
    you = _you()
    for secret in list(game.clan.code_secrets):
        if secret not in game.clan.code_secrets:
            continue  # named and removed earlier this skip
        offender = Cat.fetch_cat(secret["offender"])
        witness = Cat.fetch_cat(secret["witness"])
        key = secret["act"]
        other_clan = _clan_by_name(secret["clan"])
        if not _alive_in_clan(offender) or key not in ACTS or game.clan.age - secret["moon"] > FORGET_AFTER:
            game.clan.code_secrets.remove(secret)
            continue
        if witness is None or witness.dead:
            game.clan.code_secrets.remove(secret)
            if witness is not None and random() < DEATHBED_CHANCE:
                report(offender, witness, key, other_clan, "deathbed")
            continue
        if _like(witness, offender) < FALLING_OUT_LIKE and witness.status.alive_in_player_clan:
            game.clan.code_secrets.remove(secret)
            report(offender, witness, key, other_clan, "falling_out")
            continue
        # gossip
        spread = 0.05 + witness.personality.sociability / 16 * 0.10 + (0.05 if secret["held"] else 0)
        if random() < spread * scale:
            new = [c for c in _clanmates(offender) if c.ID not in secret["knowers"]]
            if new:
                secret["knowers"].append(choice(new).ID)
                core.change_reputation(offender, -randint(1, 2))
                if len(secret["knowers"]) >= OUT_AT_KNOWERS:
                    game.clan.code_secrets.remove(secret)
                    report(offender, None, key, other_clan, "out")
                    continue
                if you in (offender, witness):
                    _post("gossip", offender, witness, key, other_clan)
        # favors
        if secret["held"] and random() < FAVOR_CHANCE * scale:
            _nudge(offender, witness, like=-2)
            if you in (offender, witness) or random() < SHOW_OTHERS_QUIET:
                _post("favor", offender, witness, key, other_clan)
