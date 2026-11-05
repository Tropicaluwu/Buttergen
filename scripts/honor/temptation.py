"""BUTTERGEN: temptation and the code events it leads to (honor system step 2).

Every skip each Clan cat's temptations build from what's going on around them (hunger,
longing for a cat in another Clan, grudges, restlessness, Dark Forest ties), and their duty
builds from lawfulness and honor. How many events happen is set by the Clan setting
(Rare / Normal / Often). Who acts, and what they do, comes from their temptations: the most
tempted cats act, and they act on what tempts them most. Acting resets that temptation.

With weekskip on, temptation builds a quarter as fast per week and each event gets a 1 in 4
roll per week, so the totals per moon match moon skipping.

Nobody sees a broken rule yet, witnesses come in step 3.
"""

from random import choice, randint, random

from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank
from scripts.cat_relations.relationship import create_one_relationship
from scripts.clan_package import cotc
from scripts.events_module import weekskip
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.honor import core
from scripts.honor.acts import (
    ACTS, CAUSES, COOLDOWN_MOONS, DARK, DUTY, GRUDGE, HONOR_GAIN, HONOR_LOSS, HUNGER, LONGING,
    REPUTATION_GAIN, RESTLESS,
)

MAX_TEMPTATION = 100
# step 5: serious and grave acts count this much more when your cat picks what to do
BIG_FOR_YOU = ("serious", "grave")
BIG_WEIGHT_FOR_YOU = 2
# chance per moon that your cat has a code event
YOUR_CHANCE = {"rare": 1 / 6, "normal": 1 / 3.5, "often": 1 / 2}
# how many other cats have one per moon
CLAN_EVENTS = {"rare": (0, 1), "normal": (1, 3), "often": (2, 4)}


def texts() -> dict:
    return load_lang_resource("events/honor_acts.json")


# ------------------------------------------------------------------ who's around

def clanmates(exclude=None) -> list:
    cats = []
    for cat_id in game.clan.clan_cats:
        cat = Cat.fetch_cat(cat_id)
        if cat and cat is not exclude and not cat.dead and cat.status.alive_in_player_clan:
            cats.append(cat)
    return cats


def can_act(cat) -> bool:
    """living Clan cats from kit up, leaders too (step 8)"""
    if cat.dead or not cat.status.alive_in_player_clan:
        return False
    return cat.status.rank != CatRank.NEWBORN


def other_clan_cats() -> list:
    return [
        c for c in Cat.all_cats_list
        if not c.dead and c.status.is_other_clancat and not c.status.is_exiled() and not c.status.is_lost()
    ]


def clan_of(cat):
    clan = cat.status.fetch_clan_object(game.clan)
    return clan if clan is not game.clan else None


def relation(cat_from, cat_to):
    return cat_from.relationships.get(cat_to.ID) or create_one_relationship(cat_from, cat_to)


def nudge(cat_from, cat_to, **stats):
    if not cat_from or not cat_to or cat_from is cat_to:
        return
    rel = relation(cat_from, cat_to)
    if rel:
        for stat, amount in stats.items():
            setattr(rel, stat, getattr(rel, stat) + amount)


# ------------------------------------------------------------------ temptation

def _crush_clan(cat):
    """the other Clan of the cat this one likes most romantically, if it's over 10"""
    best, best_clan = 10, None
    for other in other_clan_cats():
        rel = cat.relationships.get(other.ID)
        if rel and rel.romance > best:
            best, best_clan = rel.romance, clan_of(other)
    return best, best_clan


def _worst_grudge(cat):
    worst, who = -30, None
    for other_id, rel in cat.relationships.items():
        other = Cat.fetch_cat(other_id)
        if other and rel.like < worst and not other.dead and other.status.alive_in_player_clan:
            worst, who = rel.like, other
    return -worst, who


def build(cat, scale: float):
    """adds this skip's temptation. scale is 1 for a moon, a quarter for a week"""
    t = cat.temptation
    honor_mult = 1 - cat.honor / 200
    pile = getattr(game.clan, "freshkill_pile", None)
    hunger = 0
    if pile is not None and not pile.clan_has_enough_food():
        hunger += 12
    if "bare" in str(game.clan.current_season).lower():
        hunger += 5
    romance, _ = _crush_clan(cat)
    longing = min(15, romance / 4) if romance > 10 else 0
    if not core.card("longing_temptation"):
        longing = 0  # step 8c: Heartless
    dislike, _ = _worst_grudge(cat)
    grudge = min(12, dislike / 5) if dislike > 30 else 0
    restless = 1 + max(0, 9 - cat.personality.lawfulness) * 1.2 + (3 if cat.moons < 18 else 0)
    dark = (8 if cat.joined_df else 0) + (4 if cat.lock_faith == "dark forest" else 0)
    dark += 3 if cat.dark_forest_affinity > cat.starclan_affinity else 0
    if cat.status.rank == CatRank.DEPUTY:
        # step 8c: Anything For The Throne, while the leader's trust is broken
        from scripts.honor.challenge import broken

        leader = game.clan.leader
        if leader and not leader.dead and broken(leader):
            dark = (dark + core.card("deputy_dark_base_when_broken")) * core.card("deputy_dark_when_broken")
    gains = {HUNGER: hunger, LONGING: longing, GRUDGE: grudge, RESTLESS: restless, DARK: dark}
    for cause, amount in gains.items():
        t[cause] = min(MAX_TEMPTATION, t.get(cause, 0) + amount * scale * honor_mult)
    duty = 2 + cat.personality.lawfulness * 0.8 + max(0, cat.honor) / 15
    t[DUTY] = min(MAX_TEMPTATION, t.get(DUTY, 0) + duty * scale)


# ------------------------------------------------------------------ picking an act

def find_other(cat, need):
    """r_c for an act, or None if nobody fits"""
    if need == "leader":
        leader = game.clan.leader
        ok = leader and leader is not cat and not leader.dead and leader.status.alive_in_player_clan
        return leader if ok else None
    if need == "mentor":
        return Cat.fetch_cat(cat.mentor) if cat.mentor else None
    if need == "dead":
        # step 8: a Clanmate who died this moon, for the leader's vigil
        group = cat.status.group_ID
        dead = [c for c in Cat.all_cats_list
                if c.dead and c.dead_for <= 1 and c.status.get_last_living_group() == group]
        return choice(dead) if dead else None
    if need == "apprentice":
        apps = [Cat.fetch_cat(i) for i in cat.apprentice]
        apps = [a for a in apps if a and not a.dead]
        return choice(apps) if apps else None
    mates = clanmates(exclude=cat)
    if need == "elder":
        pool = [c for c in mates if c.status.rank == CatRank.ELDER]
    elif need == "healer":
        pool = [c for c in mates if c.status.rank == CatRank.MEDICINE_CAT]
    elif need == "queen":
        pool = [c for c in mates if c.status.rank == CatRank.QUEEN]
    elif need == "sick":
        pool = [c for c in mates if c.temporary_conditions]
    elif need == "hungry":
        pile = getattr(game.clan, "freshkill_pile", None)
        info = getattr(pile, "nutrition_info", {}) if pile is not None else {}
        pool = [c for c in mates if c.status.rank != CatRank.NEWBORN]
        pool.sort(key=lambda c: info[c.ID].percentage if c.ID in info else 100)
        pool = pool[:5]
    elif need == "liked":
        def like(c):
            rel = cat.relationships.get(c.ID)
            return rel.like if rel else 0

        pool = [c for c in sorted(mates, key=like)[-5:] if like(c) > 0]
    elif need == "disliked":
        _, who = _worst_grudge(cat)
        return who or (choice(mates) if mates else None)
    else:
        pool = [c for c in mates if not c.status.rank.is_baby()]
    return choice(pool) if pool else None


def pick_other_clan(cat):
    clans = game.clan.all_other_clans
    if not clans:
        return None
    _, crush = _crush_clan(cat)
    return crush if crush and cat.temptation.get(LONGING, 0) > 0 else choice(clans)


def options_for(cat, full_moon: bool) -> list:
    """(weight, key, r_c, other_clan) for each act the cat can do right now"""
    out = []
    now = game.clan.age
    for key, a in ACTS.items():
        if cat.status.rank not in a["roles"]:
            continue
        if a["full_moon"] and not full_moon:
            continue
        if a.get("hungry") and not _hungry():
            continue
        done = cat.code_done.get(key)
        if done is not None and now - done < COOLDOWN_MOONS:
            continue
        other = None
        if a["other"]:
            other = find_other(cat, a["other"])
            if other is None:
                continue
        oc = None
        if a["other_clan"]:
            oc = pick_other_clan(cat)
            if oc is None:
                continue
        weight = sum(cat.temptation.get(c, 0) for c in a["causes"])
        if cat is game.clan.your_cat and a["kind"] == "break" and a["level"] in BIG_FOR_YOU:
            # step 5: the big temptations, the ones that become your choice, come up more for your cat
            weight *= BIG_WEIGHT_FOR_YOU
        if weight > 0:
            out.append((weight, key, other, oc))
    return out


def _hungry() -> bool:
    pile = getattr(game.clan, "freshkill_pile", None)
    return pile is not None and not pile.clan_has_enough_food()


def weighted(options):
    total = sum(o[0] for o in options)
    roll = random() * total
    for option in options:
        roll -= option[0]
        if roll <= 0:
            return option
    return options[-1]


# ------------------------------------------------------------------ doing it

def do_act(cat, key, other, other_clan):
    a = ACTS[key]
    you = cat is game.clan.your_cat
    if a["kind"] == "break":
        core.change_honor(cat, -randint(*HONOR_LOSS[a["level"]]))
    elif a["kind"] == "follow":
        core.change_honor(cat, randint(*HONOR_GAIN))
        core.change_reputation(cat, randint(*REPUTATION_GAIN))
    for cause in a["causes"]:
        cat.temptation[cause] = 0
    cat.code_done[key] = game.clan.age
    side_effects(cat, key, other, other_clan)

    text = choice(texts()[key]["you" if you else "others"])
    text = event_text_adjust(Cat, text, main_cat=cat, random_cat=other, clan=game.clan, other_clan=other_clan)
    ids = [cat.ID] + ([other.ID] if other else [])
    event = EventInformation(text, ["misc"], ids)
    if you:
        game.cur_events_list.insert(0, event)
    else:
        game.cur_events_list.append(event)
    # step 3: someone may have seen it
    from scripts.honor import leader

    if a["kind"] == "break":
        from scripts.honor import witness

        witness.after_break(cat, key, other_clan)
        # step 8: StarClan may send the healers an omen about a leader, and with Watchful Stars
        # (step 8c) about anyone's grave misdeed
        if leader.is_leader(cat) or (a["level"] == "grave" and core.card("omens_for_everyone")):
            leader.after_break(cat, key, other_clan)
    elif a["kind"] == "follow" and leader.is_leader(cat):
        # step 8: a leader's good deed is seen by the Clan
        leader.good_deed(cat)
    return text


def side_effects(cat, key, other, other_clan):
    pile = getattr(game.clan, "freshkill_pile", None)
    if key in ("eat_first", "app_eat_first") and pile is not None:
        pile.remove_freshkill(1)
    elif key == "hunt_border" and pile is not None:
        pile.add_freshkill(weekskip.weekly_prey(randint(2, 4)))
    elif key in ("feed_elders", "give_share", "nurse_kit", "sick_vigil", "favorite_herbs"):
        nudge(other, cat, like=randint(3, 7), comfort=randint(2, 5))
    elif key == "defend_clanmate":
        nudge(other, cat, like=randint(4, 8), trust=randint(4, 8))
    elif key in ("unfair_patrols", "best_nest"):
        nudge(other, cat, like=-randint(3, 7))
    elif key == "spread_rumors" and other:
        core.change_reputation(other, -randint(1, 2))
    elif key in ("share_herbs", "help_kit") and other_clan:
        cotc.change_clan_relations(game.clan, other_clan, 1)
    elif key == "hunt_border" and other_clan:
        cotc.change_clan_relations(game.clan, other_clan, -1)


def act_once(cat, full_moon: bool):
    options = options_for(cat, full_moon)
    if not options:
        return None
    _, key, other, oc = weighted(options)
    if cat is game.clan.your_cat:
        # step 5: a serious or grave act becomes your choice (one a moon)
        from scripts.honor import choices

        if choices.is_big(key) and choices.can_offer():
            choices.offer_temptation(key, other, oc)
            return None
    return do_act(cat, key, other, oc)


# ------------------------------------------------------------------ every skip

def on_skip(full_moon: bool):
    """called once every skip (every moon, or every week with weekskip)"""
    if not game.clan:
        return
    # step 5: a choice nobody made last skip is made by your cat
    from scripts.honor import choices, judgment, witness

    choices.on_skip_start()
    # step 4: misdeeds that came out before this skip are judged at the full moon

    judgment.on_skip(full_moon)
    # step 7: secret healer mates can come out
    if full_moon:
        from scripts.honor import healer

        healer.on_full_moon()
    # step 3: old secrets spread, get called in or come out
    witness.on_skip()
    # step 8: the leader's Clan trust drifts back toward steady
    from scripts.honor import leader

    leader.on_skip(full_moon)
    scale = 1 / weekskip.WEEKS_IN_MOON if weekskip.on() else 1.0
    cats = [c for c in clanmates() if can_act(c)]
    for cat in cats:
        build(cat, scale)

    frequency = core.code_frequency()
    you = game.clan.your_cat
    # step 8c: Fading Code makes code events more common
    factor = core.card("code_event_factor")
    if you in cats and random() < min(1.0, YOUR_CHANCE[frequency] * factor) * scale:
        act_once(you, full_moon)

    low, high = CLAN_EVENTS[frequency]
    count = round(randint(low, high) * factor)
    if weekskip.on():
        count = sum(1 for _ in range(count) if random() < scale)
    pool = [c for c in cats if c is not you]
    for _ in range(count):
        if not pool:
            break
        weights = [(max(c.temptation.values()) + 1, c) for c in pool]
        total = sum(w for w, _ in weights)
        roll = random() * total
        chosen = weights[-1][1]
        for w, c in weights:
            roll -= w
            if roll <= 0:
                chosen = c
                break
        pool.remove(chosen)
        act_once(chosen, full_moon)
