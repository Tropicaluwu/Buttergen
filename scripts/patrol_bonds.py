"""BUTTERGEN: patrols the player's cat goes on change how they and the other cats in it feel about
each other, when the outcome has no relationship changes of its own. Texts: events/patrol_bonds.json."""

from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.game import Switch
from scripts.game_structure.game.switches import switch_get_value
from scripts.game_structure.localization import load_lang_resource

SUCCESS = {"like": 3, "trust": 2}
FAILURE = {"like": 1}


def _cats_in(outcome_cats) -> list:
    """every cat object in the outcome's cat dict (values can be single cats or lists)"""
    from scripts.cat.cats import Cat

    found = []
    for value in outcome_cats.values():
        for cat in value if isinstance(value, (list, tuple)) else [value]:
            if isinstance(cat, Cat) and cat not in found:
                found.append(cat)
    return found


def after_patrol(patrol, outcome, outcome_cats, success: bool):
    from scripts import outsiders
    from scripts.cat.cats import Cat
    from scripts.honor.temptation import nudge

    you = game.clan.your_cat if game.clan else None
    if not you or you.dead or you not in patrol.patrol_cats:
        return
    if getattr(outcome, "relationship_changes", None):
        return
    # friend patrols and date patrols have their own
    if getattr(patrol, "friend", None):
        return
    if switch_get_value(Switch.patrol_category) == "date":
        return
    others = []
    for cat in list(patrol.patrol_cats) + _cats_in(outcome_cats):
        if cat is you or cat in others or cat.dead:
            continue
        if cat.status.alive_in_player_clan or outsiders.has_met(cat):
            others.append(cat)
    stats = SUCCESS if success else FAILURE
    text = load_lang_resource("events/patrol_bonds.json")["good" if success else "bad"]
    for cat in others:
        nudge(you, cat, log=event_text_adjust(Cat, text, main_cat=cat), **stats)
        nudge(cat, you, log=event_text_adjust(Cat, text, main_cat=you), **stats)
