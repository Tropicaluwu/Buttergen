"""BUTTERGEN: more honor choices. Your cat as mentor or parent, as deputy, and as leader picking the
sentence, "why did they do it?" questions, and relationship log lines for honor changes.
Texts: events/honor_moments.json."""

from random import randint, random, sample, shuffle

import i18n

from scripts.cat.cats import Cat
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.honor import core
from scripts.honor.acts import ACTS, CAUSES, HONOR_LOSS

MENTOR, DEPUTY, SENTENCE, WHY = "mentor", "deputy", "sentence", "why"
KINDS = (MENTOR, DEPUTY, SENTENCE, WHY)
SCOLD, COVER, ASK, LEAVE = "scold", "cover", "ask", "leave"
HARSHER, SOFTER = "harsher", "softer"
FUN = "fun"

SCOLD_LIKE = (3, 6)
DEPUTY_HARSH_LIKE = (5, 10)
DEPUTY_SOFT_LIKE = (3, 6)
WHY_RESPECT = (3, 6)
WHY_CHANCE = 1 / 3
# a right guess makes the next "talk to them" likelier to work
WHY_TALK_BONUS = 0.3
# your leader going softer than the Clan wants, or harsher than it asked for
SOFTER_CLAN_TRUST = (2, 4)
HARSHER_TRUST = (3, 6)
FORGET_AFTER = 24


def texts() -> dict:
    return load_lang_resource("events/honor_moments.json")


def _you():
    return game.clan.your_cat if game.clan else None


def _alive_in_clan(cat) -> bool:
    return bool(cat) and not cat.dead and cat.status.alive_in_player_clan


def _render(text, main_cat, random_cat=None, other_clan=None):
    return event_text_adjust(Cat, text, main_cat=main_cat, random_cat=random_cat, clan=game.clan,
                             other_clan=other_clan)


def _phrase(cat, key) -> str:
    from scripts.honor.witness import _phrase as phrase

    return phrase(key, False) + reason_suffix(cat, key)


def _post(text, cats):
    game.cur_events_list.insert(0, EventInformation(text, ["misc"], [c.ID for c in cats if c]))
    return text


def _entry_for(cat):
    for entry in game.clan.code_judgments:
        if entry["cat"] == cat.ID:
            return entry
    return None


def _leader():
    leader = game.clan.leader
    return leader if _alive_in_clan(leader) else None


# relationship log lines

def log(cat_from, cat_to, text, amount):
    """a line in cat_from's relationship log about cat_to, in Lifegen's style:
    "<text> (low negative effect) - <name> was 12 moons old". Under 5 is low, 5 to 9 medium, 10 up high"""
    if not cat_from or not cat_to or cat_from is cat_to or not text or not amount:
        return
    rel = cat_from.relationships.get(cat_to.ID)
    if rel is None:
        return
    size = "low" if abs(amount) < 5 else "medium" if abs(amount) < 10 else "high"
    sign = "positive" if amount > 0 else "negative"
    line = i18n.t(f"relationships.{sign}_postscript_{size}", text=text)
    rel.log.append(i18n.t("relationships.age_postscript", text=line, name=str(cat_from.name),
                          count=cat_from.moons))


def log_line(group, main_cat, random_cat, key=None, other_clan=None, **extra) -> str:
    """the text for a log line from honor_moments.json "log", with [act] and [sentence] filled in"""
    text = texts()["log"][group]
    if key:
        text = text.replace("[act]", _phrase(main_cat, key))
    for name, value in extra.items():
        text = text.replace(f"[{name}]", value)
    return _render(text, main_cat, random_cat, other_clan)


# "why did they do it?"

def remember_reason(cat, key):
    """when the act happens: the cause that pushed the cat hardest, before temptation resets"""
    causes = ACTS[key]["causes"]
    if not causes or ACTS[key]["kind"] != "break":
        return
    real = max(causes, key=lambda c: cat.temptation.get(c, 0))
    game.clan.code_why[f"{cat.ID}:{key}"] = {"real": real, "moon": game.clan.age}


def reason_suffix(cat, key) -> str:
    """the reason your cat guessed, for later lines about the misdeed ("... to meet someone")"""
    if not cat or not key or not game.clan:
        return ""
    entry = game.clan.code_why.get(f"{cat.ID}:{key}")
    if not entry or not entry.get("guess"):
        return ""
    return " " + texts()["why"]["reasons"][entry["guess"]]


def _real_reason(cat, key):
    entry = game.clan.code_why.get(f"{cat.ID}:{key}")
    if entry:
        return entry["real"]
    causes = ACTS[key]["causes"]
    return causes[0] if causes else None


def can_ask_why(cat, key) -> bool:
    return (_alive_in_clan(cat) and key in ACTS and ACTS[key]["kind"] == "break"
            and bool(ACTS[key]["causes"]) and cat is not _you())


def _other_clan(c):
    """the other Clan an act was about, or any of them if it's gone"""
    from random import choice as pick

    from scripts.honor.witness import _clan_by_name

    found = _clan_by_name(c.get("clan")) if c.get("clan") else None
    if found is None and ACTS.get(c.get("act"), {}).get("other_clan") and game.clan.all_other_clans:
        found = pick(game.clan.all_other_clans)
        c["clan"] = found.name
    return found


def offer_why(cat, key, heard=False, other_clan=None):
    from scripts.honor import choices

    real = _real_reason(cat, key)
    others = [c for c in CAUSES if c != real]
    answers = [real] + sample(others, 2) + [FUN]
    shuffle(answers)
    choices._offer({"kind": WHY, "offender": cat.ID, "act": key, "answers": answers, "heard": heard,
                    "clan": other_clan.name if other_clan else None})


def maybe_why_after_witness(cat, key, other_clan=None):
    """after your cat chose what to do about a misdeed they saw (1 in 3)"""
    from scripts.honor import choices

    if can_ask_why(cat, key) and choices.pending() is None and random() < WHY_CHANCE:
        offer_why(cat, key, other_clan=other_clan)


def maybe_why_from_gossip(cat, key, other_clan=None):
    """your cat heard about it through gossip (1 in 3)"""
    from scripts.honor import choices

    if can_ask_why(cat, key) and choices.can_offer() and random() < WHY_CHANCE:
        offer_why(cat, key, heard=True, other_clan=other_clan)


def talk_bonus(cat) -> float:
    """used once: a right guess about this cat makes talking to them work more often"""
    understood = game.clan.code_why.get("understood", [])
    if cat.ID in understood:
        understood.remove(cat.ID)
        return WHY_TALK_BONUS
    return 0.0


def _resolve_why(c, option):
    you, cat, key = _you(), Cat.fetch_cat(c["offender"]), c["act"]
    if option not in c["answers"] or not _alive_in_clan(cat):
        return None
    t = texts()["why"]
    record = game.clan.code_why.setdefault(f"{cat.ID}:{key}", {"real": _real_reason(cat, key),
                                                                 "moon": game.clan.age})
    record["guess"] = option
    text = t["answer"].replace("[act]", _phrase(cat, key))
    oc = _other_clan(c)
    if option == record["real"]:
        from scripts.honor.temptation import nudge

        for a, b in ((you, cat), (cat, you)):
            amount = randint(*WHY_RESPECT)
            nudge(a, b, respect=amount, log=log_line("why_right", cat, you, key) if a is you
                  else log_line("why_right_them", cat, you, key), log_amount=amount)
        understood = game.clan.code_why.setdefault("understood", [])
        if cat.ID not in understood:
            understood.append(cat.ID)
        text += " " + t["right"]
    return _post(_render(text, cat, you, oc), (cat, you))


# your cat as mentor or parent

def _close_to(you, cat):
    """"mentor" or "parent" if your cat is one of those to the cat, else None"""
    if cat.mentor == you.ID:
        return "mentor"
    parents = {cat.parent1, cat.parent2, *getattr(cat, "adoptive_parents", [])}
    if you.ID in parents:
        return "parent"
    return None


def after_came_out(cat, key, other_clan, level=None, by=None):
    """a misdeed came out and waits for the full moon. Your cat may get a say in it"""
    from scripts.honor import choices
    from scripts.honor.leader import is_leader

    you = _you()
    if (not _alive_in_clan(you) or you is cat or you is by or you.status.rank.is_baby()
            or _entry_for(cat) is None or is_leader(you)):
        return
    role = _close_to(you, cat)
    if role and choices.can_offer():
        choices._offer({"kind": MENTOR, "offender": cat.ID, "act": key, "role": role,
                        "clan": other_clan.name if other_clan else None})
        return
    if game.clan.deputy is you and _leader() and choices.can_offer():
        choices._offer({"kind": DEPUTY, "offender": cat.ID, "act": key,
                        "clan": other_clan.name if other_clan else None})


def _decide_mentor(you, cat) -> str:
    from scripts.honor.witness import _like

    law = you.personality.lawfulness / 16
    like = _like(you, cat)
    weights = [0.2 + law * 0.6, 0.05 + (1 - law) * 0.3 + max(0, like) / 150, 0.15, 0.3]
    roll = random() * sum(weights)
    for option, w in zip((SCOLD, COVER, ASK, LEAVE), weights):
        roll -= w
        if roll <= 0:
            return option
    return LEAVE


def _resolve_mentor(c, option):
    from scripts.honor import choices, witness
    from scripts.honor.temptation import nudge

    you, cat, key = _you(), Cat.fetch_cat(c["offender"]), c["act"]
    entry = _entry_for(cat)
    if entry is None or not _alive_in_clan(cat):
        return None
    if option == choices.DECIDE:
        option = _decide_mentor(you, cat)
        # "ask why" needs the player, the cat just leaves it then
        if option == ASK:
            option = LEAVE
    t = texts()["mentor"]
    leader = _leader()
    if option == SCOLD:
        for cause in ACTS[key]["causes"]:
            cat.temptation[cause] = 0
        amount = randint(*SCOLD_LIKE)
        nudge(cat, you, like=-amount, log=log_line("scolded", cat, you, key), log_amount=-amount)
        return _post(_render(t["scold"].replace("[act]", _phrase(cat, key)), cat, you, _other_clan(c)), (cat, you))
    if option == COVER:
        entry["softer"] = entry.get("softer", 0) + 1
        amount = randint(*SCOLD_LIKE)
        nudge(cat, you, like=amount, log=log_line("covered", cat, you, key), log_amount=amount)
        text = _post(_render(t["cover"].replace("[act]", _phrase(cat, key)), cat, leader or you, _other_clan(c)),
                     (cat, you))
        # lying to the leader is a misdeed of its own, and can come out like any other
        core.change_honor(you, -randint(*HONOR_LOSS["minor"]))
        if "lie_leader" in ACTS:
            witness.after_break(you, "lie_leader", None, level="minor")
        return text
    if option == ASK:
        offer_why(cat, key, other_clan=_other_clan(c))
        return None
    return None


# your cat as deputy

def _resolve_deputy(c, option):
    from scripts.honor import choices
    from scripts.honor.temptation import nudge

    you, cat, key = _you(), Cat.fetch_cat(c["offender"]), c["act"]
    entry = _entry_for(cat)
    if entry is None or not _alive_in_clan(cat) or option in (LEAVE, choices.DECIDE):
        return None
    t = texts()["deputy"]
    if option == HARSHER:
        entry["deputy_choice"] = 1
        amount = randint(*DEPUTY_HARSH_LIKE)
        nudge(cat, you, like=-amount, log=log_line("deputy_harsher", cat, you, key), log_amount=-amount)
    else:
        entry["deputy_choice"] = -1
        amount = randint(*DEPUTY_SOFT_LIKE)
        nudge(cat, you, like=amount, log=log_line("deputy_softer", cat, you, key), log_amount=amount)
    return _post(_render(t[option].replace("[act]", _phrase(cat, key)), cat, _leader() or you, _other_clan(c)),
                 (cat, you))


# your cat as leader, picking the sentence

def waiting_sentences():
    return [e for e in game.clan.code_judgments if e.get("usual")]


def offer_next_sentence():
    """offers the next sentence waiting for your leader, if nothing else is waiting"""
    from scripts.honor import choices

    if not game.clan or choices.pending() is not None:
        return
    for entry in waiting_sentences():
        cat = Cat.fetch_cat(entry["cat"])
        if _alive_in_clan(cat):
            choices._offer({"kind": SENTENCE, "offender": cat.ID, "act": entry["act"], "clan": entry.get("clan")})
            return
        game.clan.code_judgments.remove(entry)


def sentence_options(entry):
    from scripts.honor.judgment import LADDER

    usual = entry["usual"]
    i = LADDER.index(usual)
    options = [(usual, True)]
    if i > 0:
        options.append((LADDER[i - 1], False))
    if i < len(LADDER) - 1:
        options.append((LADDER[i + 1], False))
    return options


def _resolve_sentence(c, option):
    from scripts.honor import choices, judgment
    from scripts.honor.judgment import LADDER
    from scripts.honor.temptation import nudge

    you, cat = _you(), Cat.fetch_cat(c["offender"])
    entry = _entry_for(cat)
    if entry is None or not entry.get("usual"):
        return None
    usual = entry["usual"]
    step = usual if option == choices.DECIDE or option not in LADDER else option
    deputy_push, clan_push = entry.get("pushes", [0, 0])
    if LADDER.index(step) < LADDER.index(usual) and clan_push >= 0 and core.has_clan_trust(you):
        core.change_clan_trust(you, -randint(*SOFTER_CLAN_TRUST))
    elif LADDER.index(step) > LADDER.index(usual) and clan_push <= 0:
        amount = randint(*HARSHER_TRUST)
        nudge(cat, you, trust=-amount, log=log_line("harsher_sentence", cat, you, entry["act"]),
              log_amount=-amount)
    game.clan.code_judgments.remove(entry)
    return judgment.finish(entry, cat, you, step, deputy_push, clan_push)


def settle():
    """at the start of a skip: anything your leader didn't pick gets the usual sentence"""
    from scripts.honor import judgment

    for entry in waiting_sentences():
        cat = Cat.fetch_cat(entry["cat"])
        game.clan.code_judgments.remove(entry)
        if _alive_in_clan(cat) and _alive_in_clan(_you()):
            deputy_push, clan_push = entry.get("pushes", [0, 0])
            judgment.finish(entry, cat, _you(), entry["usual"], deputy_push, clan_push)


# the choice window and the event line

def pending_gone(c) -> bool:
    cat = Cat.fetch_cat(c.get("offender"))
    if not _alive_in_clan(cat):
        return True
    if c["kind"] in (MENTOR, DEPUTY, SENTENCE):
        return _entry_for(cat) is None
    return False


def window_text(c):
    """(prompt, options) for the new kinds. Options don't get "let your cat decide" added"""
    t = texts()
    you, cat, key = _you(), Cat.fetch_cat(c["offender"]), c["act"]
    act = _phrase(cat, key)
    leader = _leader() or you
    oc = _other_clan(c)
    if c["kind"] == MENTOR:
        m = t["mentor"]
        prompt = _render(m["prompt_" + c["role"]].replace("[act]", act), cat, leader, oc)
        options = [(o, _render(label, cat, leader, oc)) for o, label in zip((SCOLD, COVER, ASK, LEAVE), m["options"])]
        return prompt, options, True
    if c["kind"] == DEPUTY:
        d = t["deputy"]
        prompt = _render(d["prompt"].replace("[act]", act), cat, leader, oc)
        options = [(o, _render(label, cat, leader, oc)) for o, label in zip((HARSHER, SOFTER, LEAVE), d["options"])]
        return prompt, options, False
    if c["kind"] == SENTENCE:
        s = t["sentence"]
        entry = _entry_for(cat)
        prompt = _render(s["prompt"].replace("[act]", act), cat, you, oc)
        options = []
        for step, usual in sentence_options(entry):
            label = s["steps"][step]
            if usual:
                label = s["usual"].replace("[sentence]", label)
            options.append((step, label))
        return prompt, options, False
    w = t["why"]
    prompt = _render(w["prompt_heard" if c.get("heard") else "prompt"].replace("[act]", act), cat, you, oc)
    options = [(answer, _render(w["answers"][answer], cat, you, oc)) for answer in c["answers"]]
    return prompt, options, False


def resolve(c, option):
    if c["kind"] == MENTOR:
        return _resolve_mentor(c, option)
    if c["kind"] == DEPUTY:
        return _resolve_deputy(c, option)
    if c["kind"] == SENTENCE:
        return _resolve_sentence(c, option)
    return _resolve_why(c, option)


def announce():
    """an event line for the waiting choice, with a button that opens the window (part 3)"""
    from scripts.honor import choices

    shown = choices.window_text()
    if not shown:
        return
    event = EventInformation(shown[0], ["misc"], [_you().ID] if _you() else [])
    event.honor_choice = True
    game.cur_events_list.insert(0, event)


def cleanup():
    """old reasons are forgotten"""
    if not game.clan:
        return
    for k in [k for k, v in game.clan.code_why.items()
              if k != "understood" and game.clan.age - v.get("moon", 0) > FORGET_AFTER]:
        del game.clan.code_why[k]
