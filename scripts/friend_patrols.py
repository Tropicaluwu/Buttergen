"""BUTTERGEN: in multi clan mode, the patrols about the player's cat's friend from another Clan use a
real cat they've met (f_c), from that cat's Clan. Texts: events/friend_patrols.json."""

import copy
from random import choice

from scripts.cat.enums import CatRank
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource

# patrol id: does the friend have to be an apprentice
FRIEND_PATROLS = {"gen_life_J1": False, "any_bord_appfriend": True}
MIN_LIKE = 20
COOLDOWN = 6
SUCCESS = {"like": 5, "trust": 3}
DECLINE_LIKE = -3
BREAKUP = {"any_bord_appfriend_fail2": -5}
NOT_FRIENDS = (CatRank.LEADER, CatRank.DEPUTY, CatRank.MEDICINE_CAT)


def _texts(patrol_id) -> dict:
    return load_lang_resource("events/friend_patrols.json").get(patrol_id, {})


def _you():
    return game.clan.your_cat if game.clan else None


def _uses_friend(patrol_event, patrol) -> bool:
    """this patrol, with these cats, is about the player's cat's friend"""
    from scripts import outsiders

    if patrol_event.event_id not in FRIEND_PATROLS or not outsiders.on():
        return False
    # Theo's patrol is about whoever leads it; only the player's cat gets a real friend
    return patrol.involved_cats.get("p_l") is _you()


def friends(apprentice: bool) -> list:
    """the met cats from other Clans who like the player's cat enough, and aren't on a break"""
    from scripts import outsiders
    from scripts.cat.cats import Cat

    you = _you()
    if not you:
        return []
    found = []
    for cat_id, entry in outsiders._met().items():
        cat = Cat.fetch_cat(cat_id)
        if not cat or not outsiders.has_met(cat) or outsiders.clan_of(cat) is None:
            continue
        if cat.status.rank.is_baby() or cat.status.rank in NOT_FRIENDS:
            continue
        if apprentice and cat.status.rank != CatRank.APPRENTICE:
            continue
        rel = cat.relationships.get(you.ID)
        if not rel or rel.like < MIN_LIKE:
            continue
        if game.clan.age - entry.get("friend_break", -COOLDOWN) < COOLDOWN:
            continue
        found.append(cat)
    return found


def allowed(patrol_event, patrol) -> bool:
    """in multi clan mode a friend patrol only comes up when there's a friend for it"""
    if not _uses_friend(patrol_event, patrol):
        return True
    return bool(friends(FRIEND_PATROLS[patrol_event.event_id]))


def setup(patrol):
    """the patrol was picked: choose the friend, and the other Clan becomes theirs"""
    from scripts import outsiders

    patrol.friend = None
    if not patrol.patrol_event or not _uses_friend(patrol.patrol_event, patrol):
        return
    pool = friends(FRIEND_PATROLS[patrol.patrol_event.event_id])
    if not pool:
        return
    patrol.friend = choice(pool)
    patrol.other_clan = outsiders.clan_of(patrol.friend)
    patrol.involved_cats["f_c"] = patrol.friend


def intro(patrol):
    if getattr(patrol, "friend", None):
        return _texts(patrol.patrol_event.event_id).get("intro")
    return None


def decline(patrol):
    """the friend's text for turning back, and the friend minds being ignored"""
    from scripts.honor.temptation import nudge

    friend = getattr(patrol, "friend", None)
    if not friend:
        return None
    texts = _texts(patrol.patrol_event.event_id)
    if "decline" in texts:
        # only where the friend sees the player's cat leave
        nudge(friend, _you(), like=DECLINE_LIKE)
    return texts.get("decline")


def outcome(patrol, chosen_outcome, outcome_cats):
    """the outcome with the friend's text, the friend as the cat who joins, and no renaming"""
    friend = getattr(patrol, "friend", None)
    if not friend:
        return chosen_outcome
    suffix = chosen_outcome.event_id[len(patrol.patrol_event.event_id) + 1:]
    text = _texts(patrol.patrol_event.event_id).get(suffix)
    outcome_cats["f_c"] = friend
    changed = copy.copy(chosen_outcome)
    if text:
        changed.strings = [text]
    if chosen_outcome.join:
        rank = "apprentice" if friend.status.rank.is_any_apprentice_rank() else "warrior"
        changed.join = []
        for block in chosen_outcome.join:
            block = dict(block, change_name=False, new_status=[rank])
            if "n_c0" in block.get("cats", []):
                outcome_cats["n_c0"] = friend
            changed.join.append(block)
    return changed


def after_outcome(patrol, chosen_outcome, success: bool):
    from scripts import outsiders
    from scripts.honor.temptation import nudge

    friend = getattr(patrol, "friend", None)
    you = _you()
    if not friend or not you:
        return
    outsiders.meet(friend, "border")
    if chosen_outcome.event_id in BREAKUP:
        nudge(you, friend, like=BREAKUP[chosen_outcome.event_id])
        outsiders._met()[friend.ID]["friend_break"] = game.clan.age
    elif success and not chosen_outcome.relationship_changes:
        nudge(you, friend, **SUCCESS)
        nudge(friend, you, **SUCCESS)
