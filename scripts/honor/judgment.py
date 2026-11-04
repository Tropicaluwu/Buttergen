"""BUTTERGEN: judgments (honor system step 4).

When a misdeed comes out (scripts/honor/witness.py), the cat waits for judgment. At the next full
moon the leader (or the deputy, with no leader) adds up points and picks a step on the ladder:

    warning --> extra duties --> lost trust --> demotion --> shunning --> exile

Extra duties and demotion are flavor only. Lost trust is real: the cat isn't picked as a mentor or
the new deputy while it lasts, unless nobody else could be. Shunning and exile are LifeGen's own.
Your cat stops at shunning until step 6 (exile and coming back).

Every skip, a few Clanmates also react to cats with a strong reputation.
"""

from random import choice, randint, random, sample

from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank
from scripts.events_module import weekskip
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.honor import core
from scripts.honor.acts import ACTS

LEVEL_POINTS = {"minor": 1, "serious": 3, "grave": 6}
RECORD_MOONS = 24
WARNING, DUTIES, LOST_TRUST, DEMOTION, SHUNNING, EXILE = (
    "warning", "duties", "lost_trust", "demotion", "shunning", "exile")
LADDER = (WARNING, DUTIES, LOST_TRUST, DEMOTION, SHUNNING, EXILE)
# how many moons the timed sentences last
DURATION = {DUTIES: (1, 3), LOST_TRUST: (3, 6), DEMOTION: (2, 4)}
CLAN_TRUST_LOSS = {WARNING: 2, DUTIES: 4, LOST_TRUST: 8, DEMOTION: 12, SHUNNING: 20, EXILE: 20}
WARNING_REPUTATION = (1, 2)
SERVED_HONOR = 1
# chance per moon that your cat gets a reminder of the sentence they're serving
REMINDER_CHANCE = 1 / 3
# reputation reactions
REACT_AT = 10
REACTORS = (2, 4)
REACT_AMOUNT = (1, 3)


def texts() -> dict:
    return load_lang_resource("events/honor_judgment.json")


def _you():
    return game.clan.your_cat


def _alive_in_clan(cat) -> bool:
    return bool(cat) and not cat.dead and cat.status.alive_in_player_clan


def _like(cat_from, cat_to) -> int:
    rel = cat_from.relationships.get(cat_to.ID) if cat_from and cat_to else None
    return rel.like if rel else 0


def step_for(points) -> str:
    if points <= 1:
        return WARNING
    if points == 2:
        return DUTIES
    if points <= 4:
        return LOST_TRUST
    if points == 5:
        return DEMOTION
    if points <= 7:
        return SHUNNING
    return EXILE


# ------------------------------------------------------------------ waiting for judgment

def queue(cat, key, other_clan=None):
    """called when a misdeed comes out. Two misdeeds before the judgment are judged together,
    as the worse one plus a point"""
    clan_name = other_clan.name if other_clan else None
    if not _alive_in_clan(cat) or key not in ACTS or cat.status.rank == CatRank.LEADER:
        return
    for entry in game.clan.code_judgments:
        if entry["cat"] == cat.ID:
            entry["extra"] = entry.get("extra", 0) + 1
            if LEVEL_POINTS[ACTS[key]["level"]] > LEVEL_POINTS[ACTS[entry["act"]]["level"]]:
                entry["act"], entry["clan"] = key, clan_name
            return
    game.clan.code_judgments.append(
        {"cat": cat.ID, "act": key, "extra": 0, "moon": game.clan.age, "clan": clan_name})


def _judge_for(cat):
    leader, deputy = game.clan.leader, game.clan.deputy
    if _alive_in_clan(leader) and leader is not cat and not leader.status.is_shunned():
        return leader
    if _alive_in_clan(deputy) and deputy is not cat and not deputy.status.is_shunned():
        return deputy
    return None


# ------------------------------------------------------------------ the sentence

def _clan_push(cat) -> int:
    """-1 if the Clan asks for mercy, +1 if it wants a harsh sentence"""
    likes = dislikes = total = 0
    for other_id in game.clan.clan_cats:
        other = Cat.fetch_cat(other_id)
        if other is cat or not _alive_in_clan(other) or other.status.rank.is_baby():
            continue
        total += 1
        like = _like(other, cat)
        if like > 10:
            likes += 1
        elif like < -10:
            dislikes += 1
    if not total:
        return 0
    if likes - dislikes >= total / 3:
        return -1
    if dislikes - likes >= total / 3:
        return 1
    return 0


def points_for(cat, judge, key, extra=0):
    """(points, deputy_push, clan_push)"""
    points = LEVEL_POINTS[ACTS[key]["level"]] + extra
    points += sum(1 for moon, _ in cat.code_record if game.clan.age - moon <= RECORD_MOONS)
    points += round((judge.personality.lawfulness - 8) / 8)
    like = _like(judge, cat)
    points += -1 if like > 30 else 1 if like < -30 else 0
    deputy_push = 0
    deputy = game.clan.deputy
    if judge is not deputy and _alive_in_clan(deputy) and deputy is not cat and random() < 0.5:
        deputy_like = _like(deputy, cat)
        deputy_push = -1 if deputy_like > 20 else 1 if deputy_like < -20 else 0
    clan_push = _clan_push(cat)
    rep = cat.reputation
    points += deputy_push + clan_push + (-1 if rep >= 10 else 1 if rep <= -10 else 0)
    return points, deputy_push, clan_push


def _phrases(key):
    from scripts.honor.witness import _phrase

    return _phrase(key, False), _phrase(key, True)


def _rank_kind(cat) -> str:
    if cat.status.rank in (CatRank.MEDICINE_CAT, CatRank.MEDICINE_APPRENTICE):
        return "healer"
    if cat.status.rank.is_any_apprentice_rank():
        return "apprentice"
    return "warrior"


def _post(text, cat, judge, important=True, other_clan=None):
    you = _you()
    text = event_text_adjust(Cat, text, main_cat=cat, random_cat=judge, clan=game.clan,
                             other_clan=other_clan)
    event = EventInformation(text, ["misc"], [c.ID for c in (cat, judge) if c])
    if you in (cat, judge) and important:
        game.cur_events_list.insert(0, event)
    else:
        game.cur_events_list.append(event)
    return text


def _sentence_text(step, cat, key, deputy_push, clan_push):
    t = texts()
    you = cat is _you()
    who = "you" if you else "others"
    kind = _rank_kind(cat)
    if step == DUTIES and kind == "healer":
        lines = t[DUTIES]["healer_" + who]
    elif step == DEMOTION:
        lines = t[DEMOTION][("you_" if you else "") + kind]
    else:
        lines = t[step][who]
    text = choice(lines)
    them, yours = _phrases(key)
    text = text.replace("[act you]", yours).replace("[act]", them)
    if deputy_push:
        deputy = game.clan.deputy
        line = choice(t["deputy_for" if deputy_push < 0 else "deputy_against"])
        text += " " + line.replace("[deputy]", str(deputy.name) if deputy is not _you() else "You")
    if clan_push:
        text += " " + choice(t["clan_mercy" if clan_push < 0 else "clan_harsh"])
    return text


def judge(entry) -> bool:
    """judges one waiting cat. False if there's nobody to judge them yet"""
    cat = Cat.fetch_cat(entry["cat"])
    if not _alive_in_clan(cat) or entry["act"] not in ACTS:
        return True
    judge_cat = _judge_for(cat)
    if judge_cat is None:
        return False
    key = entry["act"]
    points, deputy_push, clan_push = points_for(cat, judge_cat, key, entry.get("extra", 0))
    step = step_for(points)
    if step == EXILE and cat is _you():
        step = SHUNNING  # step 6 adds exiling your cat
    from scripts.honor.witness import _clan_by_name

    other_clan = _clan_by_name(entry.get("clan"))
    if ACTS[key]["other_clan"] and other_clan is None:
        # the other Clan is gone, so name any of them
        other_clan = choice(game.clan.all_other_clans) if game.clan.all_other_clans else None
    text = _sentence_text(step, cat, key, deputy_push, clan_push)
    apply(cat, judge_cat, step, clan_push)
    _post(text, cat, judge_cat, other_clan=other_clan)
    if step == SHUNNING:
        demotion = cat.shunned_demotion() if not cat.dead else ""
        if demotion:
            game.cur_events_list.insert(0 if cat is _you() else len(game.cur_events_list),
                                        EventInformation(demotion, ["misc"], [cat.ID]))
    return True


def apply(cat, judge_cat, step, clan_push=0):
    from scripts.honor.temptation import nudge

    age = game.clan.age
    cat.code_record.append([age, step])
    if core.has_clan_trust(cat):
        core.change_clan_trust(cat, -CLAN_TRUST_LOSS[step])
    if step == WARNING:
        core.change_reputation(cat, -randint(*WARNING_REPUTATION))
    elif step in DURATION:
        cat.code_sentence = {"type": step, "start": age, "until": age + randint(*DURATION[step])}
    elif step == SHUNNING:
        cat.code_sentence = None
        cat.status.shun_from_group()
    elif step == EXILE:
        cat.code_sentence = None
        cat.status.exile_from_group()
    if LADDER.index(step) >= LADDER.index(LOST_TRUST):
        nudge(cat, judge_cat, like=-randint(2, 5))
        if clan_push > 0:
            loud = sorted(
                (c for c in (Cat.fetch_cat(i) for i in game.clan.clan_cats)
                 if _alive_in_clan(c) and c is not cat and _like(c, cat) < -10),
                key=lambda c: _like(c, cat))[:3]
            for other in loud:
                nudge(cat, other, like=-randint(2, 4))


# ------------------------------------------------------------------ sentences being served

def sentence(cat):
    """the timed sentence the cat is serving, or None"""
    s = getattr(cat, "code_sentence", None)
    if s and game.clan and s.get("until", 0) > game.clan.age:
        return s
    return None


def lost_trust(cat) -> bool:
    s = sentence(cat)
    return bool(s) and s["type"] == LOST_TRUST


def trusted_first(cats: list) -> list:
    """the cats from the list who haven't lost the Clan's trust, or all of them if that's nobody"""
    trusted = [c for c in cats if not lost_trust(c)]
    return trusted or cats


def profile_note(cat) -> str:
    s = sentence(cat)
    if not s:
        return ""
    profile = core.texts()["profile"]
    left = s["until"] - game.clan.age
    note = profile["sentence_one" if left == 1 else "sentence"]
    return note.replace("%{sentence}", profile["sentences"][s["type"]]).replace("%{moons}", str(left))


def tick_sentences():
    """at the full moon: sentences end, and your cat is reminded of theirs now and then"""
    t = texts()
    you = _you()
    for cat in Cat.all_cats_list:
        s = getattr(cat, "code_sentence", None)
        if not s:
            continue
        if not _alive_in_clan(cat):
            cat.code_sentence = None
            continue
        if game.clan.age >= s["until"]:
            cat.code_sentence = None
            core.change_honor(cat, SERVED_HONOR)
            if cat is you:
                _post(choice(t[s["type"] + "_end"]["you"]), cat, _judge_for(cat))
        elif cat is you and game.clan.age > s["start"] and random() < REMINDER_CHANCE:
            during = t.get(s["type"] + "_during")
            if during:
                lines = during.get("healer_you" if _rank_kind(cat) == "healer" else "you") or during["you"]
                _post(choice(lines), cat, _judge_for(cat), important=False)


# ------------------------------------------------------------------ reputation reactions

def reputation_reactions(scale: float):
    from scripts.honor.temptation import clanmates, nudge

    mates = [c for c in clanmates() if not c.status.rank.is_baby()]
    for cat in mates:
        if abs(cat.reputation) < REACT_AT or random() >= scale:
            continue
        others = [c for c in mates if c is not cat]
        if not others:
            continue
        sign = 1 if cat.reputation > 0 else -1
        for other in sample(others, min(len(others), randint(*REACTORS))):
            nudge(other, cat, trust=sign * randint(*REACT_AMOUNT), respect=sign * randint(*REACT_AMOUNT))


# ------------------------------------------------------------------ every skip

def on_skip(full_moon: bool):
    """called at the start of every skip, before new misdeeds come out, so a misdeed is judged at
    the full moon after the one it came out in"""
    if not game.clan:
        return
    scale = 1 / weekskip.WEEKS_IN_MOON if weekskip.on() else 1.0
    reputation_reactions(scale)
    if not full_moon:
        return
    tick_sentences()
    waiting = []
    for entry in list(game.clan.code_judgments):
        if not judge(entry):
            waiting.append(entry)
    game.clan.code_judgments = waiting
