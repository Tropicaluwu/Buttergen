"""BUTTERGEN: "Try for kits", a button for any cat with a mate. For a few moons the pair is much
likelier to have kits. The usual rules (age, settings, healers, the warrior code) still apply."""

from scripts.game_structure import game

TRY_MOONS = 3
# the kit roll is "1 in chance", so dividing it by 3 makes kits 3 times likelier
FACTOR = 3


def _tries() -> dict:
    if not hasattr(game.clan, "kit_tries") or game.clan.kit_tries is None:
        game.clan.kit_tries = {}
    return game.clan.kit_tries


def moons_left(cat) -> int:
    until = _tries().get(cat.ID)
    return max(0, until - game.clan.age) if until else 0


def can_try(cat) -> bool:
    from scripts.events_module.pregnancy.check_parents import check_if_can_have_kits

    return (
        bool(cat.mate)
        and not cat.dead
        and cat.status.group is not None
        and cat.status.group.is_any_clan_group()
        and moons_left(cat) == 0
        and check_if_can_have_kits(cat)
    )


def start(cat):
    """the cat and every mate they have start trying"""
    from scripts.cat.cats import Cat

    until = game.clan.age + TRY_MOONS
    for cat_id in [cat.ID] + list(cat.mate):
        mate = Cat.fetch_cat(cat_id)
        if mate and not mate.dead:
            _tries()[cat_id] = until


def adjust(chance, cat, second_parent):
    """the kit chance for this pair, 3 times likelier while either of them is trying"""
    if not game.clan or not second_parent:
        return chance
    mates = [p for p in second_parent if p != "Surrogate" and p.ID in cat.mate]
    if mates and (moons_left(cat) or any(moons_left(p) for p in mates)):
        return max(1, int(chance / FACTOR))
    return chance


def cleanup():
    for cat_id, until in list(_tries().items()):
        if until <= game.clan.age:
            del _tries()[cat_id]
