"""BUTTERGEN: challenging a leader whose Clan trust is broken (honor step 8b)."""

from random import choice, randint, random

from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank
from scripts.events_module import weekskip
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.honor import core
from scripts.honor.leader import _like, _record, _you, is_leader, texts

BROKEN = -40
CALL_CHANCE = 0.15
YOU_CALL_WEIGHT = 3
PASS_AT = 0.75
FAILED_REPUTATION = (5, 10)
FAILED_LIKE = (15, 25)
FAILED_LOST_TRUST = 0.5
REFUSED_TRUST = (3, 6)
COOLDOWN_MOONS = 12
VOTE, GATHERING, LIVES = "vote", "gathering", "lives"
CALL, QUIET = "call", "quiet"
SUPPORT, STAND = "support", "stand"


def _alive_in_clan(cat) -> bool:
    return bool(cat) and not cat.dead and cat.status.alive_in_player_clan


def _post(key, leader, other, important=True):
    """posts texts()["challenge"][key], or its "_you" / "_leader_you" line when your cat is in it"""
    lines = texts()["challenge"]
    you = _you()
    if other is you and key + "_you" in lines:
        key += "_you"
    elif leader is you and key + "_leader_you" in lines:
        key += "_leader_you"
    text = event_text_adjust(Cat, choice(lines[key]), main_cat=leader, random_cat=other, clan=game.clan)
    event = EventInformation(text, ["misc"], [c.ID for c in (leader, other) if c])
    if you in (leader, other) and important:
        game.cur_events_list.insert(0, event)
    else:
        game.cur_events_list.append(event)
    return text


def current():
    return _record().get("challenge")


def _end(leader=None, cooldown=False):
    rec = _record()
    rec["challenge"] = None
    if cooldown and leader:
        rec["cooldown"] = {"leader": leader.ID, "until": game.clan.age + COOLDOWN_MOONS}


def broken(leader) -> bool:
    return leader.clan_trust <= BROKEN


def can_challenge(leader) -> bool:
    if not _alive_in_clan(leader) or not is_leader(leader) or not broken(leader) or current():
        return False
    cd = _record().get("cooldown")
    return not (cd and cd.get("leader") == leader.ID and game.clan.age < cd.get("until", 0))


def voters(leader) -> list:
    from scripts.honor.temptation import clanmates

    return [c for c in clanmates(exclude=leader) if not c.status.rank.is_baby()]


def _call_weight(cat, leader) -> float:
    return (0.2 + cat.personality.lawfulness / 16 + max(0, cat.honor) / 50
            + max(0, -_like(cat, leader)) / 30)


def pick_caller(leader):
    pool = [c for c in voters(leader) if c.status.rank != CatRank.DEPUTY]
    if not pool:
        return None
    weights = [_call_weight(c, leader) * (YOU_CALL_WEIGHT if c is _you() else 1) for c in pool]
    roll = random() * sum(weights)
    for cat, w in zip(pool, weights):
        roll -= w
        if roll <= 0:
            return cat
    return pool[-1]


def decide_call(cat, leader) -> str:
    """your cat deciding alone: likelier to speak up the more lawful, honorable and unhappy"""
    chance = min(0.9, _call_weight(cat, leader) / 3)
    return CALL if random() < chance else QUIET


def call(challenger, leader):
    """the challenge is called: the Clan votes"""
    from scripts.honor import choices

    _record()["challenge"] = {"leader": leader.ID, "challenger": challenger.ID, "stage": VOTE,
                              "at": _record().get("skips", 0)}
    _post("called", leader, challenger)
    you = _you()
    if you is not challenger and you in voters(leader) and choices.can_offer():
        choices.offer_vote(leader, challenger)
        return
    vote(leader, challenger, your_vote=None)


def kin_or_friend(cat, leader) -> bool:
    if leader.ID in cat.mate or _like(cat, leader) > 30:
        return True
    kin = set(cat.get_parents()) | set(cat.get_siblings()) | set(cat.get_children())
    return leader.ID in kin


def yes_chance(cat, leader) -> float:
    rel = cat.relationships.get(leader.ID)
    trust = rel.trust if rel else 0
    respect = rel.respect if rel else 0
    p = 0.55 + min(0.3, (BROKEN - leader.clan_trust) / 100)
    p -= (trust + respect) / 400
    p += (cat.personality.lawfulness - 8) / 16 * 0.2
    if kin_or_friend(cat, leader):
        p -= 0.4
    return max(0.02, min(0.98, p))


def decide_vote(cat, leader) -> str:
    return SUPPORT if random() < yes_chance(cat, leader) else STAND


def vote(leader, challenger, your_vote=None):
    """counts the votes. your_vote is your cat's answer, or None to let them decide"""
    you = _you()
    cats = voters(leader)
    yes = 0
    for cat in cats:
        if cat is challenger:
            yes += 1
        elif cat is you and your_vote:
            yes += your_vote == SUPPORT
        else:
            yes += decide_vote(cat, leader) == SUPPORT
    rec = _record()
    if cats and yes >= PASS_AT * len(cats):
        rec["challenge"].update({"stage": GATHERING, "at": rec.get("skips", 0)})
        _post("vote_pass", leader, challenger)
        return True
    _post("vote_fail", leader, challenger)
    _failed(leader, challenger)
    _end(leader, cooldown=True)
    return False


def _failed(leader, challenger):
    from scripts.honor import judgment
    from scripts.honor.temptation import nudge

    if not _alive_in_clan(challenger):
        return
    core.change_reputation(challenger, -randint(*FAILED_REPUTATION))
    nudge(leader, challenger, like=-randint(*FAILED_LIKE))
    if random() < FAILED_LOST_TRUST:
        age = game.clan.age
        challenger.code_record.append([age, judgment.LOST_TRUST])
        challenger.code_sentence = {"type": judgment.LOST_TRUST, "start": age,
                                    "until": age + randint(*judgment.DURATION[judgment.LOST_TRUST])}
        _post("lost_trust", leader, challenger)


def _other_leader_agrees(clan) -> bool:
    from scripts.honor.exile import _leader_of

    p = 0.5
    if game.clan.clancount == "multiclan":
        other = _leader_of(clan)
        if other is not None:
            p += (other.personality.lawfulness - 8) / 16 * 0.4
    label = game.clan.get_relations(game.clan, clan, get_label=True)
    p += {"ally": 0.2, "hostile": -0.2}.get(label, 0)
    return random() < p


def gathering(leader, challenger):
    clans = game.clan.all_other_clans
    agree = sum(1 for clan in clans if _other_leader_agrees(clan))
    if agree * 2 > len(clans) or not clans:
        _post("leaders_agree", leader, challenger)
        _record()["challenge"].update({"stage": LIVES})
        return True
    _post("leaders_refuse", leader, challenger)
    from scripts.honor.leader import change_trust

    change_trust(leader, randint(*REFUSED_TRUST))
    _end(leader, cooldown=True)
    return False


def move_lives(leader):
    """False while there's no deputy to take them"""
    from scripts.events_module.ceremony.perform_ceremony import trigger_ceremony

    deputy = game.clan.deputy
    if not _alive_in_clan(deputy) or deputy is leader:
        return False
    lives = max(1, game.clan.leader_lives)
    _post("lives_moved", leader, deputy)
    leader.rank_change(CatRank.WARRIOR, resort=True)
    trigger_ceremony(deputy, CatRank.LEADER)
    deputy.generate_lead_ceremony(lives=lives)
    game.clan.deputy = None
    game.clan.leader = deputy
    game.clan.leader_lives = lives
    if leader is _you():
        _post("old_leader", leader, None)
    rec = _record()
    rec["leader"], rec["trust_moon"] = deputy.ID, game.clan.age
    _end()
    return True


def on_skip(full_moon: bool):
    rec = _record()
    rec["skips"] = rec.get("skips", 0) + 1
    leader = game.clan.leader
    if not _alive_in_clan(leader) or not is_leader(leader):
        if current():
            _end()
        return
    ch = current()
    if ch and ch["leader"] != leader.ID:
        _end()
        ch = None
    _whispers(leader)
    if ch:
        challenger = Cat.fetch_cat(ch["challenger"])
        from scripts.honor import choices

        waiting = choices.pending()
        if ch["stage"] == VOTE and not (waiting and waiting["kind"] == choices.VOTE):
            # your cat's vote choice went away without an answer: the Clan votes without it
            vote(leader, challenger, your_vote=None)
        elif ch["stage"] == GATHERING and full_moon and rec["skips"] > ch["at"]:
            if gathering(leader, challenger):
                move_lives(leader)
        elif ch["stage"] == LIVES:
            move_lives(leader)
        return
    scale = 1 / weekskip.WEEKS_IN_MOON if weekskip.on() else 1.0
    if not can_challenge(leader) or random() >= CALL_CHANCE * scale:
        return
    caller = pick_caller(leader)
    if caller is None:
        return
    if caller is _you():
        from scripts.honor import choices

        if choices.can_offer():
            choices.offer_call(leader)
            return
        if decide_call(caller, leader) != CALL:
            return
    call(caller, leader)


def _whispers(leader):
    rec = _record()
    if not broken(leader):
        rec["whispered"] = False
        return
    if leader is _you() and not rec.get("whispered"):
        rec["whispered"] = True
        _post("whispers", leader, None)


def resolve_call(leader, option):
    you = _you()
    if option == "decide":
        option = decide_call(you, leader)
    if option == CALL and can_challenge(leader):
        call(you, leader)
    return option


def resolve_vote(leader, option):
    ch = current()
    if not ch or ch["stage"] != VOTE:
        return None
    if option == "decide":
        option = decide_vote(_you(), leader)
    vote(leader, Cat.fetch_cat(ch["challenger"]), your_vote=option)
    return option
