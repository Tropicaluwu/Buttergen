"""BUTTERGEN: the healer mates toggle (honor step 7)."""

from random import choice, choices as weighted_choice, randint, random

from scripts.cat.cats import Cat
from scripts.cat.enums import CatAge, CatRank
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.honor import core
from scripts.honor.acts import HONOR_LOSS

MATE_ACT, KITS_ACT = "healer_mate", "healer_kits"
HEALER_ACTS = (MATE_ACT, KITS_ACT)
HEALER_RANKS = (CatRank.MEDICINE_CAT, CatRank.MEDICINE_APPRENTICE)
BECOME_MATES = 0.35
KIT_CHANCE_FACTOR = 2  # the "1 in chance" gets twice as big, so kits are half as likely
FOUND_MATE, FOUND_EXPECTING = 0.02, 0.05
# at the birth, by what the cat giving birth chose (and whether they're the healer)
FOUND_AT_BIRTH = {"raise_healer": 1.0, "raise": 0.10, "queen": 0.06, "found": 0.04}
RAISE, QUEEN, FOUND = "raise", "queen", "found"
TAKE, REFUSE = "take", "refuse"


def texts() -> dict:
    return load_lang_resource("events/honor_healer.json")


def on() -> bool:
    # step 8c: with Heartless nobody takes mates, so the toggle does nothing
    return bool(game.clan) and core.healer_mates_break_code() and bool(core.card("healer_mates"))


def is_healer(cat) -> bool:
    return bool(cat) and cat.status.rank in HEALER_RANKS


def _you():
    return game.clan.your_cat


def _alive_in_clan(cat) -> bool:
    return bool(cat) and not cat.dead and cat.status.alive_in_player_clan


def _record(cat):
    rec = getattr(cat, "code_healer", None)
    if not rec:
        rec = cat.code_healer = {"secret": [], "known": []}
    return rec


def _post(text, cats, top=False, other_clan=None):
    main = cats[0]
    other = cats[1] if len(cats) > 1 else None
    text = event_text_adjust(Cat, text, main_cat=main, random_cat=other, clan=game.clan, other_clan=other_clan)
    event = EventInformation(text, ["misc"], [c.ID for c in cats if c])
    if top or _you() in cats:
        game.cur_events_list.insert(0, event)
    else:
        game.cur_events_list.append(event)
    return text


def gate(cat_a, cat_b) -> bool:
    """romance is about to make these two mates. False stops it (this moon). With your cat
    involved it becomes your choice, or your cat decides if a choice can't be offered now"""
    if not on() or not (is_healer(cat_a) or is_healer(cat_b)):
        return True
    you = _you()
    if you in (cat_a, cat_b):
        other = cat_b if cat_a is you else cat_a
        from scripts.honor import choices

        if choices.can_offer():
            choices.offer_mate(other)
            return False
        return decide_mate(you, other) == TAKE
    return random() < BECOME_MATES


def decide_mate(cat, other) -> str:
    law = cat.personality.lawfulness / 16
    rel = cat.relationships.get(other.ID)
    romance = min(1.0, (rel.romance if rel else 0) / 60)
    return weighted_choice((TAKE, REFUSE), (0.2 + romance * 0.6, 0.2 + law * 0.6))[0]


def on_new_mate(cat_a, cat_b):
    """called by Cat.set_mate. Taking a mate breaks the code (no honor lost for Clans just made)"""
    if not on():
        return
    for healer, mate in ((cat_a, cat_b), (cat_b, cat_a)):
        if not is_healer(healer) or not _alive_in_clan(healer):
            continue
        rec = _record(healer)
        if mate.ID in rec["secret"] or mate.ID in rec["known"]:
            continue
        rec["secret"].append(mate.ID)
        if game.clan.age > 0:
            core.change_honor(healer, -randint(*HONOR_LOSS["serious"]))
            from scripts.honor import witness

            if _alive_in_clan(mate):
                witness.add_secret(healer, mate, MATE_ACT, None)
            if healer is _you():
                _post(choice(texts()["mate_you"]), [healer, mate], top=True)


def mark_known(cat):
    """the Clan knows about the cat's mates now (it came out some other way, or was judged)"""
    rec = getattr(cat, "code_healer", None)
    if rec:
        rec["known"] = list(dict.fromkeys(rec["known"] + rec["secret"]))
        rec["secret"] = []


def _count_existing():
    """healers who already had a mate when the toggle went on: a secret from now on, no honor lost"""
    for cat in Cat.all_cats_list:
        if is_healer(cat) and _alive_in_clan(cat) and cat.mate:
            rec = _record(cat)
            for mate_id in cat.mate:
                if mate_id not in rec["secret"] and mate_id not in rec["known"]:
                    rec["secret"].append(mate_id)


def _expecting(cat) -> bool:
    data = getattr(game.clan, "pregnancy_data", {}) or {}
    if cat.ID in data:
        return True
    for mate_id in cat.mate:
        entry = data.get(mate_id)
        if entry:
            second = entry.get("second_parent")
            second = second if isinstance(second, list) else [second]
            if cat.ID in second:
                return True
    return False


def found_out(cat, kits=False):
    """the Clan learns about a healer's mate, or kits"""
    from scripts.honor import judgment
    from scripts.honor.witness import REPUTATION_LOSS

    rec = _record(cat)
    mate = Cat.fetch_cat((rec["secret"] or rec["known"] or [None])[0]) if (rec["secret"] or rec["known"]) else None
    mark_known(cat)
    game.clan.code_secrets = [s for s in game.clan.code_secrets
                              if not (s["offender"] == cat.ID and s["act"] in HEALER_ACTS)]
    core.change_reputation(cat, -randint(*REPUTATION_LOSS["serious"]))
    judgment.queue(cat, KITS_ACT if kits else MATE_ACT)
    who = "you" if cat is _you() else "others"
    _post(choice(texts()["out_kits" if kits else "out_mate"][who]), [cat, mate] if mate else [cat], top=True)


def on_full_moon():
    if not on():
        return
    _count_existing()
    for cat in list(Cat.all_cats_list):
        rec = getattr(cat, "code_healer", None)
        if not rec or not rec["secret"] or not is_healer(cat) or not _alive_in_clan(cat):
            continue
        # mates who died or left stay a secret, but only living mates keep the risk up
        if not any(m in cat.mate for m in rec["secret"]):
            continue
        if random() < (FOUND_EXPECTING if _expecting(cat) else FOUND_MATE):
            found_out(cat)


def kit_chance(chance, cat, second_parent):
    """handle_having_kits rolls 1 in chance. Healers' kits are half as likely"""
    if not on():
        return chance
    parents = [cat] + [c for c in (second_parent or []) if isinstance(c, Cat)]
    return chance * KIT_CHANCE_FACTOR if any(is_healer(c) for c in parents) else chance


def _foster(bearer, healers):
    """a queen (or any grown she-cat, then any grown cat) to raise the kits"""
    mates = [c for c in (Cat.fetch_cat(i) for i in game.clan.clan_cats)
             if _alive_in_clan(c) and c is not bearer and c not in healers and not c.status.rank.is_baby()]
    for pool in ([c for c in mates if c.status.rank == CatRank.QUEEN],
                 [c for c in mates if c.gender in ("female", "molly") and c.age not in (CatAge.ADOLESCENT,)],
                 [c for c in mates if c.age not in (CatAge.ADOLESCENT,)]):
        if pool:
            return choice(pool)
    return None


def decide_kits(bearer) -> str:
    law = bearer.personality.lawfulness / 16
    return weighted_choice((RAISE, QUEEN, FOUND), (0.1 + law * 0.7, 0.45, 0.35))[0]


def after_birth(bearer, other_parents, kits):
    """called after a birth. A healer's kits break the code, and the one who gave birth decides"""
    if not on() or not kits:
        return
    healers = [c for c in [bearer] + list(other_parents or []) if isinstance(c, Cat) and is_healer(c)]
    if not healers:
        return
    for healer in healers:
        core.change_honor(healer, -randint(*HONOR_LOSS["serious"]))
    living = [k for k in kits if not k.dead]
    if not living:
        return
    if bearer is _you():
        from scripts.honor import choices

        if choices.can_offer():
            choices.offer_kits(living, healers)
            return
    resolve_kits(bearer, healers, living, decide_kits(bearer))


def resolve_kits(bearer, healers, kits, option):
    t = texts()
    who = "you" if bearer is _you() else "others"
    if option in (QUEEN, FOUND):
        foster = _foster(bearer, healers)
        if foster is None:
            option = RAISE
        else:
            for kit in kits:
                kit.adoptive_parents = [foster.ID] + [m for m in foster.mate if m]
                if option == FOUND:
                    kit.backstory = "abandoned1"
                try:
                    kit.create_inheritance_new_cat()
                except Exception:
                    pass
            from scripts.honor import witness

            for healer in healers:
                if healer is not foster:
                    witness.add_secret(healer, foster, KITS_ACT, None)
            _post(choice(t["kits_" + option][who]), [bearer, foster])
    if option == RAISE:
        key = "raise_healer" if bearer in healers else "raise"
    else:
        key = option
    if random() < FOUND_AT_BIRTH[key]:
        for healer in healers:
            found_out(healer, kits=True)
