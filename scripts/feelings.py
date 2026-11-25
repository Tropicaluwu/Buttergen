"""BUTTERGEN: relationships with more going on. Ambition, jealousy, wants and moods, on top of the five
relationship numbers. Texts: events/feelings.json. Design: Notes\\Buttergen relationships with more going
on (design draft).txt"""

from random import choice, choices as weighted_choice, randint, random, sample

from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank
from scripts.clan_package.settings import get_clan_setting
from scripts.events_module import weekskip
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource

AMBITION_SETTING, JEALOUSY_SETTING = "ambition", "jealousy"

# ambition
AMBITION_START = (
    (40, ("ambitious", "competitive", "leader-like", "arrogant", "cunning", "manipulative")),
    (25, ("confident", "bossy", "smug", "bold", "passionate")),
    (0, ("humble", "meek", "shy", "mellow")),
)
AMBITION_DEFAULT = 10
PASSED_OVER, YOUNGER_MENTOR, SKILLED = 10, 5, 3
GOT_APPRENTICE, GOT_DEPUTY, DRIFT = -15, -30, -2
RESENT_AT, ASK_AT, ASK_EVERY = 50, 75, 12
RESENT_DROP = (1, 3)
TURNED_DOWN_GRUDGE = 10
# the leader only gives the deputy's place away to a cat trusted this much more than the deputy
ASK_MARGIN = 30
# with Pride and Joy in play, a cat who isn't the leader's kit gets a yes this often (after the trust check)
NOT_KIN_YES = 0.2
TIE_BREAK = 1.1

# jealousy
JEALOUS_CHANCE = 0.3
JEALOUS_MORE = ("insecure", "obsessive", "competitive", "emotional", "vengeful")
JEALOUS_LESS = ("calm", "mellow", "trusting", "humble")
JEALOUS_MOONS = (3, 6)
JEALOUS_MAX = 2
CRUSH_AT = 30
JEALOUS_DROP = (1, 3)
MATE_EVENT, BREAKUP = 1 / 4, 0.05
MENTOR_FAVORITE = 20

# wants
WANT_FROM = 6
WANT_MOONS = 24
FRUSTRATED_AFTER = 12
FRUSTRATED_RESTLESS = 2
DONE_LIKE, DONE_RESTLESS = 5, -10
FRIEND_LIKE, FRIEND_BACK, FRIEND_DONE = 20, 15, 30
RESPECT_DONE = 30
EVEN_AT = -40
FRUSTRATED_LINE = 1 / 6
WARM = ("compassionate", "loving", "sweet", "bossy", "responsible", "patient", "thoughtful")
ROMANTIC = ("loving", "passionate", "charming", "flamboyant")
WANDERING = ("adventurous", "daring", "fearless", "energetic", "spontaneous")
CALM = ("calm", "mellow", "patient", "wise")
CHANGE_EVERY = 6
SEE_AT = 30

# moods
GRIEVING, BITTER, RESTLESS, LONELY, HAPPY, CONTENT = "grieving", "bitter", "restless", "lonely", "happy", "content"
MOODS = (GRIEVING, BITTER, RESTLESS, LONELY, HAPPY, CONTENT)
RECENT = 2
CLOSE_AT, LONELY_AT = 40, 30
MOOD_EVENT = 1 / 4
MOOD_TEMPTATION = 3


def texts() -> dict:
    return load_lang_resource("events/feelings.json")


def _you():
    return game.clan.your_cat if game.clan else None


def _alive_in_clan(cat) -> bool:
    return bool(cat) and not cat.dead and cat.status.alive_in_player_clan


def _clanmates(exclude=None) -> list:
    return [c for c in (Cat.fetch_cat(i) for i in game.clan.clan_cats)
            if _alive_in_clan(c) and c is not exclude]


def _grown(cat) -> bool:
    return cat.status.rank not in (CatRank.NEWBORN, CatRank.KITTEN)


def _rel(cat_from, cat_to):
    return cat_from.relationships.get(cat_to.ID) if cat_from and cat_to else None


def _stat(cat_from, cat_to, stat) -> int:
    rel = _rel(cat_from, cat_to)
    return getattr(rel, stat) if rel else 0


def _nudge(cat_from, cat_to, **stats):
    from scripts.honor.temptation import nudge

    nudge(cat_from, cat_to, **stats)


def _traits(cat) -> set:
    p = cat.personality
    return {p.trait, getattr(p, "trait2", None)} - {None}


def on(setting) -> bool:
    return bool(get_clan_setting(setting, default=True))


def data(cat) -> dict:
    """the cat's feelings, saved with the cat"""
    d = getattr(cat, "feelings", None)
    if not isinstance(d, dict):
        d = cat.feelings = {}
    d.setdefault("jealous", [])
    return d


def _record() -> dict:
    rec = getattr(game.clan, "feelings", None)
    if not isinstance(rec, dict):
        rec = game.clan.feelings = {}
    return rec


def _render(text, main_cat, other=None):
    return event_text_adjust(Cat, text, main_cat=main_cat, random_cat=other, clan=game.clan)


def _post(key, main_cat, other=None, force=False):
    """about the player's cat it always shows, about other cats now and then"""
    text = texts()[key]
    return _post_text(choice(text) if isinstance(text, list) else text, main_cat, other, force)


def _post_text(text, main_cat, other=None, force=False):
    you = _you()
    if not force and you not in (main_cat, other) and random() >= 1 / 3:
        return None
    text = _render(text, main_cat, other)
    event = EventInformation(text, ["relation"], [c.ID for c in (main_cat, other) if c])
    if you in (main_cat, other):
        game.cur_events_list.insert(0, event)
    else:
        game.cur_events_list.append(event)
    return text


# ambition

def ambition_start(cat) -> int:
    traits = _traits(cat)
    for value, names in AMBITION_START:
        if traits & set(names):
            return value
    return AMBITION_DEFAULT


def ambition(cat) -> int:
    d = data(cat)
    if "ambition" not in d:
        d["ambition"] = ambition_start(cat)
    return d["ambition"]


def _change_ambition(cat, amount):
    d = data(cat)
    d["ambition"] = max(ambition_start(cat), min(100, ambition(cat) + amount))


def deputy_weight(cat, value):
    """the game's own deputy math, with a small tie-breaker for ambitious cats"""
    if on(AMBITION_SETTING) and ambition(cat) >= RESENT_AT and value > 0:
        return value * TIE_BREAK
    return value


def _can_be_deputy(cat) -> bool:
    return (_alive_in_clan(cat) and cat.status.rank == CatRank.WARRIOR and not cat.status.is_shunned()
            and cat.moons > 12)


def _ambition_moon():
    clan = game.clan
    deputy = clan.deputy if _alive_in_clan(clan.deputy) else None
    warriors = [c for c in _clanmates() if c.status.rank == CatRank.WARRIOR]
    skilled = sorted(warriors, key=lambda c: c.experience, reverse=True)[:max(1, len(warriors) // 3)]
    for cat in _clanmates():
        if not _grown(cat) or cat.status.rank == CatRank.ELDER:
            continue
        _change_ambition(cat, SKILLED if cat in skilled else DRIFT)
        if deputy and cat is not deputy and cat.status.rank != CatRank.LEADER and ambition(cat) >= RESENT_AT:
            _nudge(cat, deputy, like=-randint(*RESENT_DROP), respect=-randint(*RESENT_DROP))
            if random() < 1 / 6:
                _post("resent", cat, deputy)


def _asks():
    """once in 12 moons, a very ambitious cat asks the leader for the deputy's place"""
    clan = game.clan
    leader, deputy = clan.leader, clan.deputy
    if not _alive_in_clan(leader) or not _alive_in_clan(deputy) or leader.status.is_shunned():
        return
    for cat in _clanmates():
        d = data(cat)
        if (not _can_be_deputy(cat) or ambition(cat) < ASK_AT
                or clan.age - d.get("asked", -99) < ASK_EVERY):
            continue
        d["asked"] = clan.age
        _post("ask", cat, deputy, force=True)
        if leader is _you():
            from scripts.honor import choices

            if choices.can_offer():
                choices._offer({"kind": ASK, "cat": cat.ID, "deputy": deputy.ID})
                return
        answer_ask(cat, deputy, _leader_says(leader, cat, deputy))
        return


def _not_kin(cat) -> bool:
    """Pride and Joy is in play, and cat isn't one of the leader's kits"""
    from scripts.config import get_config

    leader = game.clan.leader
    return bool(get_config("roles.only_leader_kits_deputy")) and bool(leader) and cat.ID not in leader.get_children()


def _leader_says(leader, cat, deputy) -> str:
    from scripts import let_decide

    if let_decide.trust_in(leader, cat) < let_decide.trust_in(leader, deputy) + ASK_MARGIN:
        return NO
    if _not_kin(cat) and random() >= NOT_KIN_YES:
        return NO
    return YES


def answer_ask(cat, deputy, option):
    from scripts.cat.enums import CatRank as R
    from scripts.events_module.ceremony.perform_ceremony import trigger_ceremony

    clan = game.clan
    not_kin = _not_kin(cat)
    if option == YES and _can_be_deputy(cat) and _alive_in_clan(deputy) and clan.deputy is deputy:
        if not_kin:
            _post("ask_yes_not_kin", cat, deputy, force=True)
        deputy.rank_change(R.WARRIOR)
        trigger_ceremony(cat, R.DEPUTY, {"past_deputy": deputy}, show_for_player_cat=True)
        clan.deputy = cat
        return
    d = data(cat)
    d["turned_down"] = d.get("turned_down", 0) + 1
    _post("ask_no_not_kin" if not_kin else "ask_no", cat, deputy, force=True)
    if d["turned_down"] >= 2:
        from scripts.honor.acts import GRUDGE

        cat.temptation[GRUDGE] = min(100, cat.temptation.get(GRUDGE, 0) + TURNED_DOWN_GRUDGE)


ASK, CONFESS = "feelings_ask", "feelings_confess"
YES, NO = "yes", "no"
KINDS = (ASK, CONFESS)


# confessions to the player's cat (romantic_events.py asks here first)

def offer_confession(cat, you) -> bool:
    """cat asks the player's cat to be mates: the player answers, unless their cat decides mates
    themselves, a choice is already waiting, or a healer is involved (the healer code asks then)"""
    from scripts import let_decide
    from scripts.events_module.relationship.romantic_events import can_confess
    from scripts.honor import choices
    from scripts.honor import healer as honor_healer

    if (you is not _you() or cat is you or not _alive_in_clan(you) or not _alive_in_clan(cat)
            or let_decide.on(let_decide.MATES)):
        return False
    if honor_healer.on() and (honor_healer.is_healer(cat) or honor_healer.is_healer(you)):
        return False
    if not can_confess(cat, you) or not choices.can_offer():
        return False
    choices._offer({"kind": CONFESS, "cat": cat.ID})
    return True


# jealousy

def jealous_of(cat) -> list:
    return [j for j in data(cat)["jealous"] if Cat.fetch_cat(j["cat"])]


def is_jealous_of(cat, other) -> bool:
    return any(j["cat"] == other.ID for j in data(cat)["jealous"])


def _jealous_chance(cat) -> float:
    traits = _traits(cat)
    chance = JEALOUS_CHANCE
    if traits & set(JEALOUS_MORE):
        chance *= 2
    if traits & set(JEALOUS_LESS):
        chance *= 0.5
    return chance


def _maybe_jealous(cat, other, why, extra=None):
    if not on(JEALOUSY_SETTING) or cat is other or not _alive_in_clan(cat) or not _alive_in_clan(other):
        return
    d = data(cat)
    if is_jealous_of(cat, other) or len(d["jealous"]) >= JEALOUS_MAX or random() >= _jealous_chance(cat):
        return
    d["jealous"].append({"cat": other.ID, "why": why, "until": game.clan.age + randint(*JEALOUS_MOONS),
                         "extra": extra})
    # a best friend's new closest cat: the line names the friend
    _post("jealous_" + why, cat, Cat.fetch_cat(extra) if why == "friend" else other)


def _jealousy_over(cat, j) -> bool:
    other = Cat.fetch_cat(j["cat"])
    if not _alive_in_clan(other) or game.clan.age >= j["until"]:
        return True
    why = j["why"]
    if why == "mate":
        mate = Cat.fetch_cat(j.get("extra"))
        return not mate or mate.ID not in cat.mate or _stat(mate, other, "romance") <= CRUSH_AT
    if why == "mentor":
        return j.get("extra") != cat.mentor
    if why == "sibling":
        return not cat.status.rank.is_any_apprentice_rank()
    if why == "role":
        return _want_done(cat, {"kind": j.get("extra")})
    return False


def _jealousy_moon():
    for cat in _clanmates():
        d = data(cat)
        for j in list(d["jealous"]):
            other = Cat.fetch_cat(j["cat"])
            if _jealousy_over(cat, j):
                d["jealous"].remove(j)
                if _alive_in_clan(other):
                    _post("jealous_fades", cat, other)
                continue
            _nudge(cat, other, like=-randint(*JEALOUS_DROP))
            if j["why"] == "mate":
                mate = Cat.fetch_cat(j.get("extra"))
                if random() < MATE_EVENT:
                    _post("jealous_mate", cat, other)
                if mate and random() < BREAKUP:
                    cat.unset_mate(mate)
                    d["jealous"].remove(j)
                    _post("breakup", cat, mate)


def _mate_crushes():
    """a mate's crush on another cat"""
    rec = _record().setdefault("crushes", [])
    seen = set(rec)
    now = set()
    for cat in _clanmates():
        for mate_id in cat.mate:
            mate = Cat.fetch_cat(mate_id)
            if not _alive_in_clan(mate):
                continue
            for other_id, rel in mate.relationships.items():
                if rel.romance <= CRUSH_AT or other_id in mate.mate or other_id == cat.ID:
                    continue
                key = f"{cat.ID}|{mate.ID}|{other_id}"
                now.add(key)
                if key not in seen:
                    _maybe_jealous(cat, Cat.fetch_cat(other_id), "mate", mate.ID)
    _record()["crushes"] = sorted(now)


# changes since the last skip: new deputies, apprentices, warriors, deaths

def _snapshot() -> dict:
    cats = [c for c in Cat.all_cats_list if c.status.alive_in_player_clan or (c.dead and c.ID in game.clan.clan_cats)]
    return {
        "deputy": game.clan.deputy.ID if game.clan.deputy else None,
        "apps": {c.ID: list(c.apprentice) for c in cats if not c.dead and c.apprentice},
        "ranks": {c.ID: str(c.status.rank) for c in cats if not c.dead},
        "alive": [c.ID for c in cats if not c.dead],
    }


def _changes():
    rec = _record()
    old = rec.get("last")
    new = _snapshot()
    rec["last"] = new
    if not old:
        return
    clan = game.clan
    # a new deputy: the others were passed over
    if new["deputy"] and new["deputy"] != old.get("deputy"):
        deputy = Cat.fetch_cat(new["deputy"])
        _change_ambition(deputy, GOT_DEPUTY)
        for cat in _clanmates(exclude=deputy):
            if cat.moons > 12 and cat.status.rank not in (CatRank.ELDER, CatRank.LEADER) and _grown(cat):
                _change_ambition(cat, PASSED_OVER)
                data(cat)["passed_over"] = clan.age
                if want_of(cat) and want_of(cat)["kind"] == "deputy":
                    _maybe_jealous(cat, deputy, "role", "deputy")
    # new apprentices
    for mentor_id, apps in new["apps"].items():
        before = old.get("apps", {}).get(mentor_id, [])
        added = [a for a in apps if a not in before]
        if not added:
            continue
        mentor = Cat.fetch_cat(mentor_id)
        _change_ambition(mentor, GOT_APPRENTICE)
        for app_id in before:
            app = Cat.fetch_cat(app_id)
            if app and app_id in apps:
                for new_id in added:
                    _maybe_jealous(app, Cat.fetch_cat(new_id), "mentor", mentor_id)
        for cat in _clanmates(exclude=mentor):
            if cat.status.rank in (CatRank.WARRIOR, CatRank.MEDICINE_CAT) and not cat.apprentice \
                    and cat.moons > mentor.moons:
                _change_ambition(cat, YOUNGER_MENTOR)
                if want_of(cat) and want_of(cat)["kind"] == "apprentice":
                    _maybe_jealous(cat, mentor, "role", "apprentice")
    # a littermate made warrior first
    for cat_id, rank in new["ranks"].items():
        was = old.get("ranks", {}).get(cat_id)
        if not was or was == rank or rank not in (str(CatRank.WARRIOR), str(CatRank.MEDICINE_CAT),
                                                 str(CatRank.MEDIATOR)):
            continue
        cat = Cat.fetch_cat(cat_id)
        data(cat)["happy"] = clan.age
        for sib_id in cat.get_siblings():
            sib = Cat.fetch_cat(sib_id)
            if _alive_in_clan(sib) and sib.status.rank.is_any_apprentice_rank() and abs(sib.moons - cat.moons) <= 1:
                _maybe_jealous(sib, cat, "sibling")
    # deaths, for grieving
    died = [i for i in old.get("alive", []) if i not in new["alive"]]
    deaths = rec.setdefault("deaths", {})
    for cat_id in died:
        cat = Cat.fetch_cat(cat_id)
        if cat and cat.dead:
            deaths[cat_id] = clan.age
    for cat_id in [i for i, moon in deaths.items() if clan.age - moon > RECENT]:
        del deaths[cat_id]


# wants

def want_of(cat):
    return data(cat).get("want")


def _parents_and_mentor(cat) -> list:
    ids = list(cat.get_parents()) + ([cat.mentor] if cat.mentor else [])
    return [c for c in (Cat.fetch_cat(i) for i in ids) if _alive_in_clan(c)]


def _skill_paths(cat) -> set:
    return {s.path for s in (cat.skills.primary, cat.skills.secondary) if s}


def fitting_wants(cat) -> list:
    """(kind, target or None, weight) for every want that fits the cat now"""
    if not _alive_in_clan(cat) or cat.moons < WANT_FROM or not _grown(cat):
        return []
    traits = _traits(cat)
    rank = cat.status.rank
    out = []
    if rank in (CatRank.WARRIOR, CatRank.MEDICINE_CAT) and not cat.apprentice and cat.moons >= 12:
        out.append(("apprentice", None, 1 + (2 if traits & set(WARM) else 0)))
    if rank == CatRank.WARRIOR and ambition(cat) >= 40:
        out.append(("deputy", None, 2))
    if rank == CatRank.DEPUTY and ambition(cat) >= 40:
        out.append(("leader", None, 2))
    if cat.moons >= 12 and not cat.mate and not cat.no_mates and rank != CatRank.ELDER:
        out.append(("mate", None, 1 + (2 if traits & set(ROMANTIC) else 0)))
    if cat.mate and not cat.no_kits and 15 <= cat.moons < 100 and not any(
            (k := Cat.fetch_cat(i)) and not k.dead and k.moons < 12 for i in cat.get_children()):
        out.append(("kits", None, 1))
    mates = _clanmates(exclude=cat)
    friends = [c for c in mates if _stat(cat, c, "like") >= FRIEND_LIKE and _stat(c, cat, "like") < FRIEND_BACK]
    if friends:
        out.append(("friend", choice(friends), 1))
    elders = [c for c in _parents_and_mentor(cat) + ([game.clan.leader] if _alive_in_clan(game.clan.leader) else [])
              if c is not cat and _stat(c, cat, "respect") < RESPECT_DONE]
    if elders:
        out.append(("respect", choice(elders), 1))
    if traits & set(WANDERING) and not rank.is_baby():
        out.append(("world", None, 3))
    enemies = [c for c in mates if _stat(cat, c, "like") <= EVEN_AT]
    if enemies:
        out.append(("even", min(enemies, key=lambda c: _stat(cat, c, "like")), 1 + (3 if "vengeful" in traits else 0)))
    if rank.is_any_apprentice_rank():
        teachers = [c for c in mates if _grown(c) and not c.status.rank.is_any_apprentice_rank()
                    and _skill_paths(c) - _skill_paths(cat)]
        if teachers:
            out.append(("learn", choice(teachers), 1))
    from scripts import families, friends

    fell_out_with = friends.make_up_target(cat) or families.make_up_target(cat)
    if fell_out_with:
        out.append((friends.MAKE_UP, fell_out_with, 2))
    away = families.see_target(cat)
    if away:
        out.append((families.SEE, away, 1))
    look_up_to = families.respect_target(cat)
    if look_up_to:
        out.append(("respect", look_up_to, 3))
    if rank == CatRank.ELDER or traits & set(CALM):
        out.append(("peace", None, 3 if rank == CatRank.ELDER else 1))
    return out


def _new_want(cat, kind=None):
    wants = fitting_wants(cat)
    if kind:
        wants = [w for w in wants if w[0] == kind]
    if not wants:
        data(cat).pop("want", None)
        return
    if data(cat).get("mood") == LONELY:
        wants = [(k, t, w * (3 if k == "friend" else 1)) for k, t, w in wants]
    k, target, _w = weighted_choice(wants, [w for _k, _t, w in wants])[0]
    data(cat)["want"] = {"kind": k, "cat": target.ID if target else None, "since": game.clan.age}


def _want_done(cat, want) -> bool:
    kind = want["kind"]
    target = Cat.fetch_cat(want.get("cat"))
    rank = cat.status.rank
    if kind == "apprentice":
        return bool(cat.apprentice)
    if kind == "deputy":
        return rank in (CatRank.DEPUTY, CatRank.LEADER)
    if kind == "leader":
        return rank == CatRank.LEADER
    if kind == "mate":
        return bool(cat.mate)
    if kind == "kits":
        return any((k := Cat.fetch_cat(i)) and not k.dead and k.moons < 2 for i in cat.get_children())
    if kind == "friend":
        return bool(target) and _stat(target, cat, "like") >= FRIEND_DONE
    if kind == "respect":
        return bool(target) and _stat(target, cat, "respect") >= RESPECT_DONE
    if kind == "world":
        return want.get("done", False)
    if kind == "even":
        return want.get("done", False)
    if kind == "makeup":
        from scripts import families, friends

        return bool(target) and not friends.fell_out(cat, target) and not families.is_estranged(cat, target)
    if kind == "see":
        return want.get("done", False)
    if kind == "learn":
        return bool(target) and (cat.mentor == target.ID or bool(_skill_paths(target) & _skill_paths(cat)))
    return False


def _want_gone(cat, want) -> bool:
    """the want doesn't fit anymore (the other cat is gone, a new rank)"""
    target_id = want.get("cat")
    if want["kind"] == "see":
        from scripts import families

        return families.see_gone(want)
    if target_id and not _alive_in_clan(Cat.fetch_cat(target_id)):
        return True
    kinds = {k for k, _t, _w in fitting_wants(cat)}
    return want["kind"] not in kinds and not _want_done(cat, want)


def _helper(cat, want):
    kind = want["kind"]
    if want.get("cat"):
        return Cat.fetch_cat(want["cat"])
    if kind == "apprentice":
        leader = game.clan.leader
        return leader if _alive_in_clan(leader) and leader is not cat else None
    if kind in ("mate", "kits"):
        mates = [m for m in (Cat.fetch_cat(i) for i in cat.mate) if m and not m.dead]
        return mates[0] if mates else None
    return None


def _wants_moon():
    from scripts.honor.acts import RESTLESS

    clan = game.clan
    for cat in _clanmates():
        d = data(cat)
        want = d.get("want")
        if want and _want_done(cat, want):
            helper = _helper(cat, want)
            if helper and _alive_in_clan(helper):
                _nudge(cat, helper, like=DONE_LIKE)
                d["helped_by"] = helper.ID
            cat.temptation[RESTLESS] = max(0, cat.temptation.get(RESTLESS, 0) + DONE_RESTLESS)
            d["happy"] = clan.age
            d.pop("want")
            key = "done_" + want["kind"]
            if key in texts():
                _post(key, cat, helper)
            continue
        if not want or _want_gone(cat, want) or (want["kind"] == "peace" and clan.age - want["since"] >= WANT_MOONS) \
                or clan.age - want["since"] >= WANT_MOONS:
            _new_want(cat)
            continue
        if want["kind"] != "peace" and clan.age - want["since"] >= FRUSTRATED_AFTER:
            cat.temptation[RESTLESS] = min(100, cat.temptation.get(RESTLESS, 0) + FRUSTRATED_RESTLESS)
            key = "frustrated_" + want["kind"]
            if key in texts() and random() < FRUSTRATED_LINE:
                _post(key, cat)


def mentor_first(cats) -> list:
    """the fair picks for a mentor, the cats who want an apprentice first"""
    wanting = [c for c in cats if (w := want_of(c)) and w["kind"] == "apprentice"]
    return wanting or cats


def explored(cats):
    for cat in cats:
        want = want_of(cat)
        if want and want["kind"] == "world":
            want["done"] = True


def came_out(cat):
    """a misdeed came out: anyone who wanted to get even with this cat has it"""
    for other in _clanmates(exclude=cat):
        want = want_of(other)
        if want and want["kind"] == "even" and want.get("cat") == cat.ID:
            want["done"] = True


def _wants_romance():
    """cats who want a mate grow fond a little faster"""
    for cat in _clanmates():
        want = want_of(cat)
        if not want or want["kind"] != "mate":
            continue
        crush = max(_clanmates(exclude=cat), key=lambda c: _stat(cat, c, "romance"), default=None)
        if crush and _stat(cat, crush, "romance") > 0 and _stat(cat, crush, "like") > 20:
            _nudge(cat, crush, romance=1)


def can_change_want(cat) -> bool:
    d = data(cat)
    return (_alive_in_clan(cat) and len(fitting_wants(cat)) > 1
            and game.clan.age - d.get("changed", -99) >= CHANGE_EVERY)


def change_want(cat, kind, target_id=None):
    """the player picked this want for their cat"""
    data(cat)["changed"] = game.clan.age
    data(cat)["want"] = {"kind": kind, "cat": target_id, "since": game.clan.age}


def want_text(cat, want=None) -> str:
    want = want or want_of(cat)
    if not want:
        return ""
    target = Cat.fetch_cat(want.get("cat"))
    text = texts()["want_names"][want["kind"]]
    return text.replace("r_c", str(target.name)) if target else text


# moods

def _close(cat, other) -> bool:
    rel = _rel(cat, other)
    family = other.ID in set(cat.get_parents()) | set(cat.get_siblings()) | set(cat.get_children()) | set(cat.mate)
    return family or bool(rel) and (rel.like > CLOSE_AT or rel.comfort > CLOSE_AT)


def _grief_for(cat):
    from scripts import friends

    best = friends.grieving_for(cat)
    if best:
        return best
    from scripts import families

    away = families.grieving_for(cat)
    if away:
        return away
    for cat_id in _record().get("deaths", {}):
        dead = Cat.fetch_cat(cat_id)
        if dead and dead is not cat and _close(cat, dead):
            return dead
    return None


def _work_out_mood(cat):
    d = data(cat)
    age = game.clan.age
    dead = _grief_for(cat)
    if dead:
        return GRIEVING, dead.ID
    judged = any(age - moon <= RECENT for moon, _ in getattr(cat, "code_record", []) or [])
    passed = ambition(cat) >= RESENT_AT and age - d.get("passed_over", -99) <= RECENT
    if d["jealous"] or passed or judged:
        return BITTER, None
    from scripts import families

    # a parent worried about a hurt or sick kit
    if families.worried_about(cat):
        return RESTLESS, d.get("worried")
    want = d.get("want")
    # (not from restless temptation: most cats' sits high between misdeeds, so nearly everyone was restless)
    if want and want["kind"] != "peace" and age - want["since"] >= FRUSTRATED_AFTER:
        return RESTLESS, None
    from scripts import friends

    if not cat.mate and not friends.friends_of(cat) and not any(_stat(c, cat, "like") > LONELY_AT for c in _clanmates(exclude=cat)):
        return LONELY, None
    if age - d.get("happy", -99) <= RECENT:
        return HAPPY, None
    return CONTENT, None


def mood(cat) -> str:
    return data(cat).get("mood", CONTENT)


def _moods():
    from scripts.honor.acts import GRUDGE, RESTLESS as R

    scale = 1 / weekskip.WEEKS_IN_MOON if weekskip.on() else 1.0
    everyone = _clanmates()
    for cat in everyone:
        if not _grown(cat):
            continue
        d = data(cat)
        d["mood"], d["mood_cat"] = _work_out_mood(cat)
        m = d["mood"]
        others = [c for c in everyone if c is not cat]
        friends = [c for c in others if _stat(cat, c, "like") > CLOSE_AT]
        if m == GRIEVING:
            cat.temptation[R] = min(100, cat.temptation.get(R, 0) + MOOD_TEMPTATION)
            for friend in friends[:3]:
                _nudge(cat, friend, comfort=round(2 * scale) or 1)
        elif m == BITTER:
            cat.temptation[GRUDGE] = min(100, cat.temptation.get(GRUDGE, 0) + MOOD_TEMPTATION)
        elif m == RESTLESS:
            cat.temptation[R] = min(100, cat.temptation.get(R, 0) + MOOD_TEMPTATION)
        elif m in (LONELY, HAPPY):
            # lonely cats warm to others faster, happy ones are nicer to be around
            for other in sample(others, min(2, len(others))):
                _nudge(cat, other, like=1)


def lean(cat):
    """for relationship events: True for friendlier, False for prickly, None for neither"""
    m = mood(cat)
    return True if m == HAPPY else False if m == BITTER else None


def _mood_event():
    you = _you()
    if not _alive_in_clan(you) or not _grown(you) or random() >= MOOD_EVENT:
        return
    m = mood(you)
    if m == CONTENT:
        return
    other = Cat.fetch_cat(data(you).get("mood_cat"))
    _post("mood_" + m, you, other, force=True)


def shows(cat) -> bool:
    """the player sees this cat's feelings on the profile"""
    you = _you()
    return cat is you or (bool(you) and _stat(you, cat, "like") > SEE_AT)


def profile_lines(cat) -> str:
    if not game.clan or cat.dead or not cat.status.alive_in_player_clan or not shows(cat) or not _grown(cat):
        return ""
    t = texts()["profile"]
    out = t["mood"].replace("%{mood}", t["moods"][mood(cat)]) + "\n"
    if want_of(cat):
        out += t["want"].replace("%{want}", want_text(cat)) + "\n"
    jealous = [str(Cat.fetch_cat(j["cat"]).name) for j in jealous_of(cat)]
    if jealous:
        out += t["jealous"].replace("%{cats}", ", ".join(jealous)) + "\n"
    deputy = game.clan.deputy
    if (on(AMBITION_SETTING) and deputy and deputy is not cat and _alive_in_clan(deputy)
            and ambition(cat) >= RESENT_AT and cat.status.rank != CatRank.LEADER):
        out += t["resents"].replace("%{cat}", str(deputy.name)) + "\n"
    from scripts import friends

    out += friends.profile_lines(cat)
    from scripts import families

    out += families.profile_lines(cat)
    return out


# every skip

def on_skip(full_moon: bool):
    if not game.clan:
        return
    _changes()
    if full_moon:
        if on(AMBITION_SETTING):
            _ambition_moon()
            _asks()
        if on(JEALOUSY_SETTING):
            _mate_crushes()
            _jealousy_moon()
        else:
            for cat in _clanmates():
                data(cat)["jealous"] = []
        from scripts import friends

        friends.on_moon()
        from scripts import families

        families.on_moon()
        _wants_moon()
        _wants_romance()
    _moods()
    _mood_event()


# the player's choices (scripts/honor/choices.py hands these over)

def pending_gone(c) -> bool:
    if c["kind"] == CONFESS:
        cat = Cat.fetch_cat(c["cat"])
        return not _alive_in_clan(cat) or cat.ID in _you().mate
    cat, deputy = Cat.fetch_cat(c["cat"]), Cat.fetch_cat(c["deputy"])
    return not _can_be_deputy(cat) or not _alive_in_clan(deputy) or game.clan.deputy is not deputy \
        or game.clan.leader is not _you()


def window_text(c):
    if c["kind"] == CONFESS:
        cat = Cat.fetch_cat(c["cat"])
        part = texts()["confess_window"]
        prompt = _render(part["prompt"], cat, _you())
        return prompt, [(YES, _render(part["yes"], cat, _you())), (NO, _render(part["no"], cat, _you()))]
    cat, deputy = Cat.fetch_cat(c["cat"]), Cat.fetch_cat(c["deputy"])
    part = texts()["ask_window"]
    prompt = _render(part["prompt"], cat, deputy)
    return prompt, [(YES, _render(part["yes"], cat, deputy)), (NO, _render(part["no"], cat, deputy))]


def resolve_choice(c, option):
    from scripts.honor import choices

    if c["kind"] == CONFESS:
        from scripts.events_module.relationship.romantic_events import confess

        answer = None if option == choices.DECIDE else option == YES
        confess(Cat.fetch_cat(c["cat"]), _you(), answer, show_no=True)
        return option
    cat, deputy = Cat.fetch_cat(c["cat"]), Cat.fetch_cat(c["deputy"])
    if option == choices.DECIDE:
        option = _leader_says(_you(), cat, deputy)
    answer_ask(cat, deputy, option)
    return option
