"""BUTTERGEN: your cat's choices (honor system step 5).

Two kinds of moment become a choice: your cat about to do a serious or grave act, and your cat
witnessing a Clanmate break the code. At most one per moon. The skip never stops: a "Your cat has
a choice" button shows on the events screen, and if you skip again without opening it, your cat
decides by personality at the start of that skip.

Your cat never holds a secret over anyone, even when deciding alone.
"""

from random import choice, choices as weighted_choice, randint, random

from scripts.cat.cats import Cat
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.honor import core
from scripts.honor.acts import ACTS, HONOR_LOSS

TEMPTATION, WITNESS = "temptation", "witness"
# step 7: a healer's romance, and what to do with a healer's kits
MATE, KITS = "mate", "kits"
GIVE, BETWEEN, RESIST = "give", "between", "resist"
REPORT, KEEP, TALK = "report", "keep", "talk"
DECIDE = "decide"
RESIST_HONOR = (1, 2)
TALK_LIKE = (3, 6)


def texts() -> dict:
    return load_lang_resource("events/honor_choices.json")


def _you():
    return game.clan.your_cat if game.clan else None


def _alive_in_clan(cat) -> bool:
    return bool(cat) and not cat.dead and cat.status.alive_in_player_clan


def _clan(name):
    from scripts.honor.witness import _clan_by_name

    return _clan_by_name(name)


# ------------------------------------------------------------------ the waiting choice

def pending():
    """the choice waiting for you, or None"""
    c = getattr(game.clan, "code_choice", None) if game.clan else None
    if not c:
        return None
    gone = (
        not _alive_in_clan(_you())
        or (c["kind"] == WITNESS and not _alive_in_clan(Cat.fetch_cat(c["offender"])))
        or (c["kind"] == MATE and not _alive_in_clan(Cat.fetch_cat(c["other"])))
        or (c["kind"] == KITS and not [k for k in (Cat.fetch_cat(i) for i in c["kits"]) if k and not k.dead])
    )
    if gone:
        game.clan.code_choice = None
        return None
    return c


def can_offer() -> bool:
    """one choice per moon, and never two waiting at once"""
    return (
        bool(game.clan)
        and pending() is None
        and getattr(game.clan, "code_choice_moon", None) != game.clan.age
    )


def _offer(entry):
    game.clan.code_choice = entry
    game.clan.code_choice_moon = game.clan.age


def offer_temptation(key, other, other_clan):
    _offer({"kind": TEMPTATION, "act": key, "other": other.ID if other else None,
            "clan": other_clan.name if other_clan else None})


def offer_witness(offender, key, other_clan, level=None):
    _offer({"kind": WITNESS, "act": key, "offender": offender.ID,
            "clan": other_clan.name if other_clan else None, "level": level})


def offer_mate(other):
    _offer({"kind": MATE, "other": other.ID})


def offer_kits(kits, healers):
    _offer({"kind": KITS, "kits": [k.ID for k in kits], "healers": [h.ID for h in healers]})


def is_big(key) -> bool:
    a = ACTS.get(key)
    return bool(a) and a["kind"] == "break" and a["level"] in ("serious", "grave")


# ------------------------------------------------------------------ what the window shows

def _render(text, main_cat, random_cat, other_clan):
    return event_text_adjust(Cat, text, main_cat=main_cat, random_cat=random_cat, clan=game.clan,
                             other_clan=other_clan)


def _leader_or(cat):
    leader = game.clan.leader
    return cat or (leader if _alive_in_clan(leader) else None)


def window_text():
    """(prompt, [(option, label), ...]) for the waiting choice, or None"""
    c = pending()
    if not c:
        return None
    you = _you()
    t = texts()
    oc = _clan(c.get("clan"))
    if c["kind"] == MATE:
        other = Cat.fetch_cat(c["other"])
        m = t["healer_mate"]
        prompt = _render(m["prompt"], you, other, None)
        options = [(o, _render(label, you, other, None)) for o, label in zip(("take", "refuse"), m["options"])]
    elif c["kind"] == KITS:
        healers = [Cat.fetch_cat(i) for i in c["healers"]]
        k = t["healer_kits"]
        other = next((h for h in healers if h is not you), None)
        prompt = _render(k["prompt_healer" if you in healers else "prompt_mate"], you, other, None)
        options = [(o, _render(label, you, other, None)) for o, label in zip(("raise", "queen", "found"), k["options"])]
    elif c["kind"] == TEMPTATION:
        a = t["acts"][c["act"]]
        r = _leader_or(Cat.fetch_cat(c["other"]) if c.get("other") else None)
        prompt = _render(a["prompt"], you, r, oc)
        options = [(o, _render(label, you, r, oc)) for o, label in zip((GIVE, BETWEEN, RESIST), a["options"])]
    else:
        from scripts.honor.witness import _phrase

        offender = Cat.fetch_cat(c["offender"])
        w = t["witness"]
        leader = _leader_or(None)
        prompt = _render(w["prompt"].replace("[act]", _phrase(c["act"], False)), offender, leader, oc)
        options = [(o, _render(label, offender, leader, oc)) for o, label in zip((REPORT, KEEP, TALK), w["options"])]
    options.append((DECIDE, t["let_decide"].replace("%{name}", str(you.name))))
    return prompt, options


# ------------------------------------------------------------------ deciding

def _personality_temptation(cat, key) -> str:
    law = cat.personality.lawfulness / 16
    pull = min(1.0, sum(cat.temptation.get(c, 0) for c in ACTS[key]["causes"]) / 60)
    weights = [0.15 + pull * (1 - law) * 0.8, 0.3, 0.15 + law * 0.7 + max(0, cat.honor) / 200]
    return weighted_choice((GIVE, BETWEEN, RESIST), weights)[0]


def personality_witness(witness, offender, key) -> str:
    """like witness.decide, but talking it over takes the place of holding it over them"""
    from scripts.honor.witness import _like

    law = witness.personality.lawfulness / 16
    like = _like(witness, offender)
    level_bonus = {"minor": 0, "serious": 0.15, "grave": 0.35}[ACTS[key]["level"]]
    weights = [
        0.15 + law * 0.5 + max(0, witness.honor) / 200 + max(0, -like) / 150 + level_bonus,
        0.25 + max(0, like) / 100,
        0.1 + witness.personality.sociability / 16 * 0.3 + (0.15 if like > 0 else 0),
    ]
    return weighted_choice((REPORT, KEEP, TALK), weights)[0]


def resolve(option):
    """carries out the waiting choice. option is one of the window's, or DECIDE"""
    c = pending()
    if not c:
        return None
    game.clan.code_choice = None
    if c["kind"] in (MATE, KITS):
        return _resolve_healer(c, option)
    if c["kind"] == TEMPTATION:
        return _resolve_temptation(c, option)
    offender = Cat.fetch_cat(c["offender"])
    return resolve_witness(_you(), offender, c["act"], _clan(c.get("clan")), option, c.get("level"))


def _resolve_healer(c, option):
    from scripts.honor import healer

    you = _you()
    if c["kind"] == MATE:
        other = Cat.fetch_cat(c["other"])
        if option == DECIDE:
            option = healer.decide_mate(you, other)
        if option == "take":
            you.set_mate(other)
            if not healer.is_healer(you):
                return _post(_render(texts()["healer_mate"]["take_mate"], you, other, None))
            return None
        return _post(_render(choice(healer.texts()["refuse_you"]), you, other, None))
    kits = [k for k in (Cat.fetch_cat(i) for i in c["kits"]) if k and not k.dead]
    healers = [h for h in (Cat.fetch_cat(i) for i in c["healers"]) if h]
    if option == DECIDE:
        option = healer.decide_kits(you)
    healer.resolve_kits(you, healers, kits, option)
    if option == "raise":
        return _post(_render(texts()["healer_kits"]["raise"], you, None, None))
    return None


def _post(text):
    game.cur_events_list.insert(0, EventInformation(text, ["misc"], [_you().ID]))
    return text


def _resolve_temptation(c, option):
    from scripts.honor import temptation, witness

    you = _you()
    key = c["act"]
    other = Cat.fetch_cat(c["other"]) if c.get("other") else None
    if other is not None and not _alive_in_clan(other):
        other = None
    oc = _clan(c.get("clan"))
    if option == DECIDE:
        option = _personality_temptation(you, key)
    if option == GIVE:
        return temptation.do_act(you, key, other, oc)
    a = texts()["acts"][key]
    for cause in ACTS[key]["causes"]:
        you.temptation[cause] = 0
    you.code_done[key] = game.clan.age
    text = _render(a[option], you, _leader_or(other), oc)
    if option == RESIST:
        core.change_honor(you, randint(*RESIST_HONOR))
        return _post(text)
    _post(text)
    if a.get("between_breaks"):
        core.change_honor(you, -randint(*HONOR_LOSS["minor"]))
        witness.after_break(you, key, oc, level="minor")
    return text


def resolve_witness(you, offender, key, oc, option, level=None):
    """your cat's answer to what they saw: report, keep it, or talk to them"""
    from scripts.honor import witness
    from scripts.honor.temptation import nudge

    if not _alive_in_clan(offender):
        return None
    if option == DECIDE:
        option = personality_witness(you, offender, key)
    if option == REPORT:
        return witness.report(offender, you, key, oc, "report", level=level)
    witness.add_secret(offender, you, key, oc, held=False, level=level)
    if option == KEEP:
        return witness._post("keep", offender, you, key, oc)
    w = texts()["witness"]
    listens = witness._like(offender, you) > 10 or (offender.personality.aggression < 8 and random() < 0.5)
    if listens:
        for cause in ACTS[key]["causes"]:
            offender.temptation[cause] = 0
        nudge(offender, you, like=randint(*TALK_LIKE))
    else:
        nudge(offender, you, like=-randint(*TALK_LIKE))
    text = _render(w["listen" if listens else "bristle"], offender, you, oc)
    game.cur_events_list.insert(0, EventInformation(text, ["misc"], [offender.ID, you.ID]))
    return text


# ------------------------------------------------------------------ every skip

def on_skip_start():
    """a choice left waiting through a whole skip is made by your cat"""
    if pending():
        resolve(DECIDE)


# ------------------------------------------------------------------ the events screen

def show_badge(screen):
    """adds or removes the badge on the events screen"""
    import pygame

    from scripts.ui.elements.surface_image_button import UISurfaceImageButton
    from scripts.ui.generate_button import get_button_dict, ButtonStyles
    from scripts.ui.scale import ui_scale

    badge = getattr(screen, "honor_choice_badge", None)
    if badge is not None:
        badge.kill()
        screen.honor_choice_badge = None
    if pending() is None:
        return
    screen.honor_choice_badge = UISurfaceImageButton(
        ui_scale(pygame.Rect(BADGE_SPOT, (172, 30))),
        texts()["badge"],
        get_button_dict(ButtonStyles.SQUOVAL, (172, 30)),
        object_id="@buttonstyles_squoval",
        starting_height=2,
        container=screen.event_screen_container,
    )


BADGE_SPOT = (33, 634)


def open_window(screen=None):
    from scripts.ui.windows.honor_choice import HonorChoiceWindow

    return HonorChoiceWindow(screen)
