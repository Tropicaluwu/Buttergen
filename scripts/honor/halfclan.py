"""BUTTERGEN: Other Clans step 3. Kits with a parent outside the player's Clan (another Clan's cat, or a
kittypet, loner or rogue), the secrets about them, and cats learning where they were really born.
Texts: events/honor_halfclan.json."""

from random import choice, choices as weighted_choice, randint, random, shuffle

from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank, CatSocial
from scripts.clan_package.settings import get_clan_setting
from scripts.config import get_config
from scripts.events_module import weekskip
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.honor import code, core, heart
from scripts.honor.acts import HONOR_LOSS

CLAN_ACT, OUTSIDE_ACT, STEAL_ACT = "heart_kits", "outside_kits", "steal_kit"
ACTS = (CLAN_ACT, OUTSIDE_ACT)
RARE = "birth secrets rare"

HERE, THERE, BROUGHT, TRUTH = "half_here", "half_there", "half_brought", "half_truth"
KINDS = (HERE, THERE, BROUGHT, TRUTH)
KEEP, TAKE, TELL, LEAVE, BRING = "keep", "take", "tell", "leave", "bring"
QUIET, CONFRONT, FIND = "quiet", "confront", "find"
# what the Clan is told
MATE, SILENT, FOUND, TOLD = "mate", "silent", "found", "told"

# pairs across borders have kits half as often (the kit roll is 1 in chance)
KIT_CHANCE_FACTOR = 2
WEIGHTS_HERE = {KEEP: 60, TAKE: 15, TELL: 25}
WEIGHTS_THERE = {LEAVE: 70, BRING: 20, TELL: 10}
AGREE_CLAN, AGREE_OUTSIDER, AGREE_TRUST = 0.4, 0.6, 0.2
GUESS_AT_BIRTH = {SILENT: 0.10, MATE: 0.06, FOUND: 0.04}
GUESS_EACH_MOON, GUESS_UNDER = 0.02, 12
LIE_POINTS, TOLD_POINTS = 1, -1
SEES_HALF, SEES_HALF_LIKE = 1 / 5, 5
TEASE_YOUNG, TEASE_GROWN, TEASE_HONOR = 1 / 6, 1 / 20, 30
TEASE_LIKE, STEPS_IN, STEPS_IN_LIKE = (2, 4), 1 / 3, 10
LEARN_FROM, LEARN, LEARN_RARE = 12, 1 / 20, 1 / 60
LEARN_YOUNG = 6
REMEMBERS_FROM = 3
DEATHBED = 0.4
OVERHEARD = 1 / 3
FAMILY_LIKE = (5, 10)
SWITCH_BONUS = 20

# (cat ID, act) --> the moon it last came out, for thefts that come out before they're recorded
_out_now = {}


def texts() -> dict:
    return load_lang_resource("events/honor_halfclan.json")


def _you():
    return game.clan.your_cat if game.clan else None


def _alive_in_clan(cat) -> bool:
    return bool(cat) and not cat.dead and cat.status.alive_in_player_clan


def record() -> dict:
    rec = getattr(game.clan, "code_kits", None)
    if not isinstance(rec, dict):
        rec = game.clan.code_kits = {}
    for key, empty in (("litters", []), ("seek", []), ("bonus", {}), ("next", 1)):
        rec.setdefault(key, empty)
    return rec


def _group(cat):
    """the group a cat lives in, or lived in before they died"""
    return cat.status.get_last_living_group() if cat.dead else cat.status.group_ID


def _clan(cat):
    """the OtherClan a cat lives in (or lived in), or None"""
    group = _group(cat) if cat else None
    return next((c for c in game.clan.all_other_clans if c.group_ID == group), None)


def _clan_named(name):
    from scripts.honor.witness import _clan_by_name

    return _clan_by_name(name) if name else None


def _kits(litter) -> list:
    return [k for k in (Cat.fetch_cat(i) for i in litter["kits"]) if k and not k.dead]


def _home_kits(litter) -> list:
    return [k for k in _kits(litter) if k.status.alive_in_player_clan]


def _cats(litter):
    return Cat.fetch_cat(litter["home"]), Cat.fetch_cat(litter["away"])


def _act(litter) -> str:
    return CLAN_ACT if litter["clan"] else OUTSIDE_ACT


def _key(litter, key) -> str:
    return key if litter["clan"] else key + "_outsider"


def _render(text, main_cat, other=None, other_clan=None):
    return event_text_adjust(Cat, text, main_cat=main_cat, random_cat=other, clan=game.clan,
                             other_clan=other_clan)


def _post(key, main_cat, other=None, other_clan=None, top=None):
    text = texts()[key]
    text = _render(choice(text) if isinstance(text, list) else text, main_cat, other, other_clan)
    event = EventInformation(text, ["relation"], [c.ID for c in (main_cat, other) if c])
    if top or (top is None and _you() in (main_cat, other)):
        game.cur_events_list.insert(0, event)
    else:
        game.cur_events_list.append(event)
    return text


def _quietly(key, main_cat, other=None, other_clan=None):
    """about other cats, only some of these show"""
    if _you() in (main_cat, other) or random() < heart.OTHERS_SHOWN:
        _post(key, main_cat, other, other_clan)


def _scale() -> float:
    return 1 / weekskip.WEEKS_IN_MOON if weekskip.on() else 1.0


def _nudge(cat_from, cat_to, **stats):
    from scripts.honor.temptation import nudge

    nudge(cat_from, cat_to, **stats)


# births

def outside_parent(cat) -> bool:
    """from outside the player's Clan, and never lost or exiled from it"""
    home = game.clan.group_ID
    if not cat or _group(cat) == home:
        return False
    return not (cat.status.is_lost(home) or cat.status.is_exiled(home))


def kit_chance(chance, cat, second_parent):
    parents = [p for p in (second_parent or []) if isinstance(p, Cat)]
    return chance * KIT_CHANCE_FACTOR if any(heart.pair_of(cat, p) for p in parents) else chance


def public_mates(cat, mates) -> list:
    """the mates a birth or pregnancy event may name"""
    return [m for m in mates if not (isinstance(m, Cat) and heart.is_secret(heart.pair_of(cat, m)))]


def _clan_mates(cat, exclude=()) -> list:
    """living mates in the cat's own Clan"""
    mates = [Cat.fetch_cat(m) for m in cat.mate]
    return [m for m in mates if m and not m.dead and m not in exclude
            and m.status.group_ID == cat.status.group_ID and not m.status.is_lost()]


def birth_text(cat, other_parents, events):
    """the birth line when the other parent lives outside the cat's Clan: (line, the mate it names or
    None), or None for every other birth"""
    if not game.clan or cat.status.is_outsider:
        return None
    others = [c for c in other_parents or [] if isinstance(c, Cat) and c is not cat]
    home = _group(cat)
    away = [c for c in others if _group(c) != home
            and not (c.status.is_lost(home) or c.status.is_exiled(home))]
    if not away or len(away) < len(others):
        return None
    pair = heart.pair_of(cat, away[0])
    if pair and not heart.is_secret(pair):
        return texts()["birth"], None
    mates = _clan_mates(cat)
    if mates:
        return choice(events["birth"]["two_parents"]), choice(mates)
    if cat is _you():
        return texts()["birth"], None
    return choice(events["birth"]["unmated_parent"]), None


def _known(home, away) -> bool:
    """the Clan already knows about these two"""
    pair = heart.pair_of(home, away)
    if pair and not heart.is_secret(pair):
        return True
    return any(lit["out"] and lit["home"] == home.ID and lit["away"] == away.ID for lit in record()["litters"])


def _lose_honor(home, away):
    """once for each mate: secret mates lost it when they became mates"""
    if any(lit["home"] == home.ID and lit["away"] == away.ID for lit in record()["litters"]):
        return
    pair = heart.pair_of(home, away)
    if pair and not pair.pop("from_litter", False):
        return
    core.change_honor(home, -randint(*HONOR_LOSS["serious"]))


def _new(home, away, kits, **extra):
    rec = record()
    clan = _clan(away)
    litter = {"id": rec["next"], "home": home.ID, "away": away.ID, "kits": [k.ID for k in kits],
              "clan": clan.name if clan else None, "social": str(away.status.social),
              "moon": game.clan.age, "story": SILENT, "out": False, "open": False, "healer": False,
              "hidden": False, "wait": None, "learned": [], "sees": [], "true": kits[0].backstory}
    litter.update(extra)
    rec["next"] += 1
    rec["litters"].append(litter)
    return litter


def _tidy_family(kits):
    """only cats who live with the kits raise them"""
    for kit in kits:
        raised_by = [Cat.fetch_cat(p) for p in kit.adoptive_parents or []]
        kit.adoptive_parents = [p.ID for p in raised_by if p and _group(p) == kit.status.group_ID]
    _refresh_family()


def _refresh_family():
    from scripts.cat_relations.inheritance2 import inheritance_db

    inheritance_db.load_inheritances(Cat)


def _made_up_clan(away, kits) -> bool:
    """single Clan mode's half-Clan litters have no real Clan behind them"""
    return _clan(away) is None and any(str(k.backstory).startswith("halfclan") for k in kits)


def after_birth(bearer, others, kits, hidden=False, surrogate=False):
    """every birth ends up here. Kits with a parent outside the player's Clan break the code"""
    if not game.clan or surrogate:
        return
    others = [c for c in others or [] if isinstance(c, Cat) and c is not bearer]
    if _group(bearer) == game.clan.group_ID:
        home, aways, where = bearer, [c for c in others if outside_parent(c)], HERE
    elif outside_parent(bearer):
        home = next((c for c in others if _alive_in_clan(c)), None)
        aways, where = [bearer], THERE
    else:
        return
    if not home or not aways:
        return
    away = aways[0]
    both = {home.ID, away.ID}
    mine = [k for k in kits if not k.dead and both <= {k.parent1, k.parent2, k.parent3}]
    if not mine or _made_up_clan(away, mine):
        return
    _tidy_family(mine)
    _born(home, away, mine, where, hidden)


def after_brought(home, aways, kits) -> bool:
    """a cat of the player's Clan came home with kits born outside. True if this posts the event"""
    if not game.clan or not _alive_in_clan(home):
        return False
    aways = [c for c in aways or [] if isinstance(c, Cat) and outside_parent(c)]
    living = [k for k in kits if not k.dead]
    if not aways or not living or _made_up_clan(aways[0], living):
        return False
    if not code.counts(CLAN_ACT if _clan(aways[0]) else OUTSIDE_ACT):
        return False
    _tidy_family(living)
    return _born(home, aways[0], living, BROUGHT)


def _born(home, away, kits, where, hidden=False) -> bool:
    from scripts.honor import healer

    if not code.counts(CLAN_ACT if _clan(away) else OUTSIDE_ACT):
        return False
    known = _known(home, away)
    _lose_honor(home, away)
    if known:
        # everyone knows already: nothing to hide, and no second judgment
        if where != THERE:
            _mark_out(_new(home, away, kits, story=TOLD, open=True))
        return False
    if home.dead:
        # nobody knows the truth anymore
        return False
    litter = _new(home, away, kits, hidden=bool(hidden))
    if where == HERE and healer.on() and healer.is_healer(home):
        # a healer's kits have their own choice and judgment
        litter["healer"] = True
        return False
    if home is _you():
        litter["wait"] = where
        offer_waiting()
    else:
        resolve_litter(litter, where, _decide_litter(litter, where))
    return True


def offer_waiting():
    """the player's choice about a litter, this moon or when the one that's waiting is made"""
    from scripts.honor import choices

    if not game.clan:
        return
    for litter in list(record()["litters"]):
        if not litter["wait"]:
            continue
        home, away = _cats(litter)
        if home is not _you() or not _alive_in_clan(home) or away is None or not _kits(litter):
            _wait_over(litter)
        elif choices.can_offer():
            choices._offer({"kind": litter["wait"], "cat": away.ID, "kits": [k.ID for k in _kits(litter)],
                            "litter": litter["id"]})
            return


def _wait_over(litter):
    """nobody can choose anymore"""
    where, litter["wait"] = litter["wait"], None
    home, _away = _cats(litter)
    if where == THERE or not home or not _kits(litter):
        record()["litters"].remove(litter)
    elif where == BROUGHT:
        _say_found(litter)
    else:
        litter["story"] = _story(litter)


def _by_id(litter_id):
    return next((lit for lit in record()["litters"] if lit["id"] == litter_id), None)


def _story(litter) -> str:
    home, away = _cats(litter)
    if _clan_mates(home, exclude=(away,)):
        return MATE
    return FOUND if litter["hidden"] else SILENT


def _reachable(litter) -> bool:
    _home, away = _cats(litter)
    return away is not None and not away.dead and not away.status.is_lost() and outside_parent(away)


def _options(litter, where) -> list:
    if where == HERE:
        return [KEEP, TAKE, TELL] if _reachable(litter) else [KEEP, TELL]
    return [LEAVE, BRING, TELL] if where == THERE else [BRING, TELL]


def _decide_litter(litter, where) -> str:
    home, away = _cats(litter)
    law = home.personality.lawfulness / 16
    romance = min(1.0, max(0, heart._stat(home, away, "romance")) / 100)
    weights = dict(WEIGHTS_HERE if where == HERE else WEIGHTS_THERE)
    weights[TELL] *= 0.5 + law
    for key in (KEEP, LEAVE):
        if key in weights:
            weights[key] *= 1 + romance / 2
    options = _options(litter, where)
    return weighted_choice(options, [weights[o] for o in options])[0]


def resolve_litter(litter, where, option):
    home, away = _cats(litter)
    clan = _clan(away)
    litter["wait"] = None
    if where == THERE:
        if option == LEAVE:
            _quietly(_key(litter, "stay"), home, away, clan)
        elif not _reachable(litter) or not _agrees(home, away):
            _quietly("refused", home, away, clan)
        else:
            _move(_kits(litter), home)
            litter["true"] = "halfclan2" if litter["clan"] else "outsider_roots2"
            for kit in _kits(litter):
                kit.backstory = litter["true"]
            if _known(home, away):
                # it came out while the choice waited
                option = TELL
        if not _home_kits(litter):
            record()["litters"].remove(litter)
            return
    if option == TELL:
        _tell(litter)
    elif where in (THERE, BROUGHT):
        _say_found(litter)
        _guess(litter, GUESS_AT_BIRTH[FOUND])
    elif option == TAKE and _reachable(litter):
        kits = _kits(litter)
        _move(kits, away)
        if where == HERE and home is not _you():
            _hide_birth_line(home, kits)
        _quietly(_key(litter, "taken"), home, away, clan)
        record()["litters"].remove(litter)
    else:
        litter["story"] = _story(litter)
        if litter["story"] == FOUND:
            _say_found(litter)
        elif home is _you():
            mates = _clan_mates(home, exclude=(away,))
            _post(litter["story"], home, mates[0] if mates else None, clan, top=True)
        _guess(litter, GUESS_AT_BIRTH[litter["story"]])


def _hide_birth_line(home, kits):
    """the birth line said home was raising the kits, but they went to the other parent: home tells
    the Clan a story instead (lines about one kit only for one kit)"""
    lines = load_lang_resource("conditions/pregnancy.json")["birth"]["otherclan_mother"]
    if len(kits) > 1:
        lines = [line for line in lines if "single kit" not in line]
    for event in reversed(game.cur_events_list):
        if "birth_death" in event.types and home.ID in event.cats_involved:
            event.text = _render(choice(lines), home)
            event.cat_dict = {"m_c": home}
            return


def _agrees(home, away) -> bool:
    chance = AGREE_CLAN if _clan(away) else AGREE_OUTSIDER
    return random() < chance + (AGREE_TRUST if heart._stat(away, home, "trust") > 50 else 0)


def _say_found(litter):
    home, _away = _cats(litter)
    litter["story"] = FOUND
    backstory = choice(("abandoned1", "abandoned2", "abandoned3", "abandoned4"))
    for kit in _kits(litter):
        kit.backstory = backstory
    _post("found", home)


def _move(kits, parent):
    """the kits go to live with this parent"""
    from scripts.cat.names import Name
    from scripts.cat_relations.cat_handle_funcs import create_relationships_new_cat
    from scripts.events_module.consequences import change_relationship_values

    into_clan = parent.status.group is not None and parent.status.group.is_any_clan_group()
    for kit in kits:
        was_outsider = kit.status.is_outsider
        kit.status.generate_new_status(
            age=kit.age,
            social=CatSocial.CLANCAT if into_clan else parent.status.social,
            group_ID=parent.status.group_ID,
        )
        if was_outsider and into_clan:
            kit.name = Name(kit)
        elif not was_outsider and not into_clan and kit.status.social != CatSocial.CLANCAT:
            # a kittypet, loner or rogue parent gives them a name like theirs, not a Clan name
            kit.name.find_outsider_name(kit.status.social)
        game.clan.add_cat(kit)
        create_relationships_new_cat(kit)
        change_relationship_values(cats_from=[parent], cats_to=[kit],
                                   **get_config("new_cat.parent_buff.parent_to_kit"))
        change_relationship_values(cats_from=[kit], cats_to=[parent],
                                   **get_config("new_cat.parent_buff.kit_to_parent"))
        kit.assign_thought()
    _tidy_family(kits)


# secrets coming out

def _guess(litter, chance):
    """someone may guess, and decides what to do with it like any witness"""
    from scripts.honor import witness

    home, _away = _cats(litter)
    if _alive_in_clan(home) and not litter["out"]:
        witness.after_break(home, _act(litter), _clan_named(litter["clan"]), chance=chance)


def has_secret(cat, act) -> bool:
    return bool(cat) and any(lit["home"] == cat.ID and not lit["out"] and _act(lit) == act
                             for lit in record()["litters"])


def _adjust_points(cat, points):
    for entry in game.clan.code_judgments:
        if entry["cat"] == cat.ID:
            entry["extra"] = entry.get("extra", 0) + points


def _tell(litter):
    home, away = _cats(litter)
    litter["story"], litter["open"] = TOLD, True
    _post(_key(litter, "told"), home, away, _clan(away))
    if _expose(litter):
        _adjust_points(home, TOLD_POINTS)


def _expose(litter) -> bool:
    """the whole Clan finds out. True if it's judged (not when the mate already was)"""
    from scripts.honor import witness

    home, away = _cats(litter)
    if litter["out"]:
        return False
    if not _alive_in_clan(home) or away is None or _known(home, away):
        _mark_out(litter)
        return False
    core.change_reputation(home, -randint(*witness.REPUTATION_LOSS["serious"]))
    witness.came_out(home, _act(litter), _clan_named(litter["clan"]))
    return True


def _mark_out(litter):
    litter["out"] = True
    litter["wait"] = None
    kits = _home_kits(litter)
    if litter["story"] == FOUND:
        for kit in _kits(litter):
            kit.backstory = litter["true"]
    if not kits:
        return
    family = {litter["home"], litter["away"], *litter["kits"]}
    for kit in kits:
        family.update(kit.get_parents())
        family.update(kit.get_siblings())
    for cat_id in game.clan.clan_cats:
        cat = Cat.fetch_cat(cat_id)
        if cat is _you() or not _alive_in_clan(cat) or cat.status.rank == CatRank.NEWBORN or cat.ID in family:
            continue
        if random() < SEES_HALF:
            litter["sees"].append(cat.ID)
            for kit in kits:
                _nudge(cat, kit, like=-SEES_HALF_LIKE)


def _mate_learns(litter):
    """the Clan mate who thought the kits were theirs"""
    from scripts.events_module.pregnancy.handle_already_pregnant import _check_should_claim_affair_kits

    home, away = _cats(litter)
    if not _alive_in_clan(home) or heart.pair_of(home, away) is None:
        return
    mates = _clan_mates(home, exclude=(away,))
    if not mates:
        return
    for mate in mates:
        if not _check_should_claim_affair_kits(mate, home):
            for kit in _kits(litter):
                if mate.ID in (kit.adoptive_parents or []):
                    kit.adoptive_parents.remove(mate.ID)
    heart.affair_known(home, _clan(away), mates)
    _refresh_family()


def came_out(cat, key, other_clan=None):
    """called for every misdeed that comes out (witness.came_out)"""
    from scripts.honor import healer

    if key == STEAL_ACT:
        _out_now[(cat.ID, key)] = game.clan.age
        for theft in game.clan.code_stolen_kits:
            if cat.ID in theft["by"]:
                theft["out"] = True
        return
    litters = [lit for lit in record()["litters"]
               if lit["home"] == cat.ID and not lit["out"] and lit["wait"] != THERE]
    if key in healer.HEALER_ACTS:
        litters = [lit for lit in litters if lit["healer"]]
    elif key in (heart.ACT, CLAN_ACT):
        litters = [lit for lit in litters if lit["clan"]]
    elif key == OUTSIDE_ACT:
        litters = [lit for lit in litters if not lit["clan"]]
    else:
        return
    if not litters:
        return
    for act in {_act(lit) for lit in litters}:
        game.clan.code_secrets = [s for s in game.clan.code_secrets
                                  if s["offender"] != cat.ID or s["act"] != act]
    pair_secret = key == CLAN_ACT and any(heart.is_secret(heart.pair_of(*_cats(lit))) for lit in litters)
    for litter in litters:
        home, away = _cats(litter)
        if key == heart.ACT:
            _post(_key(litter, "out"), home, away, _clan_named(litter["clan"]))
        _mark_out(litter)
        _mate_learns(litter)
        if key == CLAN_ACT and not heart.pair_of(home, away):
            _other_clan_hears(litter)
    if (key not in healer.HEALER_ACTS and code.follows("code honesty")
            and any(lit["story"] in (MATE, FOUND) for lit in litters)):
        _adjust_points(cat, LIE_POINTS)
    if pair_secret:
        # the mate is out with the kits, as one misdeed
        heart.came_out(cat)


def _other_clan_hears(litter):
    home, away = _cats(litter)
    clan = _clan_named(litter["clan"])
    if not away or clan is None:
        return
    game.clan.set_relations(game.clan, clan, None, -1)
    if away.dead:
        return
    from scripts.honor.leader import is_leader

    _post("news", home, away, clan)
    if not is_leader(away):
        _post("judged_there", home, away, clan)
        core.change_reputation(away, -randint(3, 6))


# growing up half-Clan

def _tease():
    kits = [(lit, k) for lit in record()["litters"] if lit["out"] and lit["sees"] for k in _home_kits(lit)
            if k.status.rank != CatRank.NEWBORN]
    shuffle(kits)
    for litter, kit in kits:
        young = kit.status.rank.is_baby() or kit.status.rank.is_any_apprentice_rank()
        chance = TEASE_YOUNG if young else TEASE_GROWN
        if kit.honor > TEASE_HONOR:
            chance /= 2
        teasers = [c for c in (Cat.fetch_cat(i) for i in litter["sees"]) if _alive_in_clan(c)]
        if not teasers or random() >= chance * _scale():
            continue
        teaser = choice(teasers)
        _nudge(kit, teaser, like=-randint(*TEASE_LIKE))
        clan = _clan_named(litter["clan"])
        friends = [c for c in (Cat.fetch_cat(i) for i in game.clan.clan_cats)
                   if _alive_in_clan(c) and c not in (kit, teaser) and c.ID not in litter["sees"]
                   and c.status.rank != CatRank.NEWBORN and heart._stat(c, kit, "like") > STEPS_IN_LIKE]
        if clan and friends and random() < STEPS_IN:
            _nudge(kit, choice(friends), like=randint(*TEASE_LIKE))
            _post("steps_in", kit, teaser, clan)
        elif clan:
            _post("tease", kit, teaser, clan)
        else:
            _post("tease_kittypet" if litter["social"] == CatSocial.KITTYPET else "tease_wild", kit, teaser)
        return


# learning the truth

def _hider(source):
    """the cat who hid the truth, or took the kit"""
    if "by" in source:
        return next((c for c in (Cat.fetch_cat(i) for i in source["by"]) if c), None)
    return Cat.fetch_cat(source["home"])


def _source_clan(source):
    return _clan_named(source["from"] if "by" in source else source["clan"])


def remembers(theft, kit) -> bool:
    """old enough to remember when they were taken"""
    return kit.moons - (game.clan.age - theft["moon"]) >= REMEMBERS_FROM


def _sources() -> list:
    """(source, kit) for every cat in the Clan who doesn't know where they come from"""
    found = []
    for litter in record()["litters"]:
        if not litter["open"] and not litter["wait"]:
            found += [(litter, k) for k in _home_kits(litter) if k.ID not in litter["learned"]]
    for theft in game.clan.code_stolen_kits:
        kit = Cat.fetch_cat(theft["kit"])
        if _alive_in_clan(kit) and not theft.get("learned") and not remembers(theft, kit):
            found.append((theft, kit))
    return found


def _knowers(source) -> int:
    hider = _hider(source)
    act = STEAL_ACT if "by" in source else _act(source)
    ids = {i for s in game.clan.code_secrets if hider and s["offender"] == hider.ID and s["act"] == act
           for i in s["knowers"]}
    return sum(1 for i in ids if _alive_in_clan(Cat.fetch_cat(i)))


def _how(source, kit) -> str:
    """the line that tells it, or "" if nobody can right now"""
    if "by" in source:
        return "learn_stolen"
    ways = []
    if _alive_in_clan(_hider(source)):
        ways.append("learn_parent")
    elders = [c for c in (Cat.fetch_cat(i) for i in game.clan.clan_cats)
              if _alive_in_clan(c) and c is not kit and c.status.rank == CatRank.ELDER
              and c.ID not in (source["home"], source["away"])]
    if len(elders) >= 2:
        ways.append("learn_overheard")
    return _key(source, choice(ways)) if ways else ""


def _can_ask() -> bool:
    from scripts.honor import choices

    return choices.can_offer()


def _learn_rolls():
    chance = LEARN_RARE if get_clan_setting(RARE, default=False) else LEARN
    for source, kit in _sources():
        if kit is _you() and not _can_ask():
            continue
        if source.get("out"):
            # everyone else knows already
            if kit.moons >= LEARN_YOUNG:
                _learn(source, kit, "learn_stolen" if "by" in source else "")
            continue
        if kit.moons < LEARN_FROM:
            continue
        if random() < chance * (2 if _knowers(source) >= 2 else 1) * _scale():
            how = _how(source, kit)
            if how:
                _learn(source, kit, how)


def _deathbeds():
    sources = [s for s in record()["litters"] if not s["open"]] + game.clan.code_stolen_kits
    for source in sources:
        hider = _hider(source)
        if source.get("deathbed") or hider is None or not hider.dead:
            continue
        source["deathbed"] = True
        if source.get("out") or _group(hider) != game.clan.group_ID or random() >= DEATHBED:
            continue
        told = False
        for other, kit in _sources():
            if other is not source or kit.moons < LEARN_YOUNG or (kit is _you() and not _can_ask()):
                continue
            _learn(source, kit, "" if told else "learn_deathbed")
            told = True


def _learn(source, kit, line):
    from scripts.honor import choices

    source.setdefault("learned", []).append(kit.ID)
    hider = _hider(source)
    if line:
        _post(line, kit, hider, _source_clan(source))
    if kit is _you():
        choices._offer({"kind": TRUTH, "cat": hider.ID if hider else None, "kit": kit.ID,
                        "theft": "by" in source, "litter": source.get("id")})
    else:
        resolve_truth(source, kit, _decide_truth(source, kit))


def _truth_options(source) -> list:
    options = [QUIET]
    if _alive_in_clan(_hider(source)):
        options.append(CONFRONT)
    if heart.on() and _source_clan(source) is not None:
        options.append(FIND)
    return options


def _decide_truth(source, kit) -> str:
    p = kit.personality
    weights = {QUIET: 50 * (0.5 + p.lawfulness / 16), CONFRONT: 35 * (0.5 + p.aggression / 16),
               FIND: 15 * (0.5 + p.sociability / 16)}
    options = _truth_options(source)
    return weighted_choice(options, [weights[o] for o in options])[0]


def resolve_truth(source, kit, option):
    hider, clan = _hider(source), _source_clan(source)
    if option == CONFRONT and _alive_in_clan(hider):
        _nudge(kit, hider, like=-randint(10, 20), trust=-randint(15, 25))
        _quietly("confront", kit, hider, clan)
        if not source.get("out") and random() < OVERHEARD:
            _overheard(source)
    elif option == FIND and clan is not None:
        record()["seek"].append({"kit": kit.ID, "group": clan.group_ID, "moon": game.clan.age})
        record()["bonus"][kit.ID] = clan.group_ID
    elif not source.get("out"):
        if hider and not hider.dead:
            _nudge(kit, hider, trust=-randint(8, 12))
        _quietly("quiet", kit, None, clan)


def _overheard(source):
    from scripts.honor import witness

    if "by" not in source:
        home, away = _cats(source)
        _post(_key(source, "out"), home, away, _clan_named(source["clan"]))
        _expose(source)
        return
    source["out"] = True
    thief = _hider(source)
    if code.counts(STEAL_ACT):
        game.clan.code_secrets = [s for s in game.clan.code_secrets
                                  if s["offender"] != thief.ID or s["act"] != STEAL_ACT]
        witness.report(thief, None, STEAL_ACT, _source_clan(source), "out")


def _meet_family():
    """the Gathering after a cat decides to look for their birth family"""
    from scripts import outsiders
    from scripts.honor import switching

    rec = record()
    for entry in list(rec["seek"]):
        if entry["moon"] >= game.clan.age:
            continue
        rec["seek"].remove(entry)
        kit = Cat.fetch_cat(entry["kit"])
        if not _alive_in_clan(kit):
            continue
        kin = switching._kin(kit)
        family = [c for c in switching.cats_in(entry["group"]) if c.ID in kin]
        _quietly("find" if family else "too_late", kit, None, switching.clan_of_group(entry["group"]))
        for cat in family:
            like = randint(*FAMILY_LIKE)
            if kit is _you():
                outsiders.meet(cat, "gathering", like)
            else:
                _nudge(kit, cat, like=like)
                _nudge(cat, kit, like=like)


def switch_bonus(cat, target) -> int:
    """a cat who looked for their birth family is taken in there more easily"""
    return SWITCH_BONUS if record()["bonus"].get(cat.ID) == target else 0


def theft_is_out(offenders) -> bool:
    """a theft can come out right away, before its kits are written down"""
    return any(_out_now.get((c.ID, STEAL_ACT)) == game.clan.age for c in offenders)


# every skip

def on_skip(full_moon: bool):
    rec = record()
    rec["litters"] = [lit for lit in rec["litters"] if lit["wait"] or _kits(lit)]
    if full_moon:
        _meet_family()
        for litter in list(rec["litters"]):
            if litter["out"] or litter["healer"] or litter["wait"]:
                continue
            if any(k.moons < GUESS_UNDER for k in _home_kits(litter)):
                _guess(litter, GUESS_EACH_MOON)
    _tease()
    _deathbeds()
    _learn_rolls()


# the player's choices (scripts/honor/choices.py hands these over)

def _truth_source(c):
    if c["theft"]:
        return next((t for t in game.clan.code_stolen_kits if t["kit"] == c["kit"]), None)
    return _by_id(c["litter"])


def pending_gone(c) -> bool:
    you = _you()
    if c["kind"] == TRUTH:
        return you.ID != c["kit"] or _truth_source(c) is None
    litter = _by_id(c["litter"])
    return litter is None or not litter["wait"] or litter["home"] != you.ID or not _kits(litter)


def window_text(c):
    from scripts.honor.leader import is_leader

    you, t = _you(), texts()
    if c["kind"] == TRUTH:
        source = _truth_source(c)
        hider, clan, part = _hider(source), _source_clan(source), t["truth"]
        options = []
        for key in _truth_options(source):
            label = part["let_it_be"] if key == QUIET and source.get("out") else part["options"][key]
            options.append((key, _render(label, you, hider, clan)))
        return _render(part["prompt"], you, hider, clan), options
    litter = _by_id(c["litter"])
    _home, away = _cats(litter)
    clan = _clan_named(litter["clan"])
    part = t["here" if c["kind"] == HERE else "there"]
    prompt = _render(part["prompt" if clan else "prompt_outsider"], you, away, clan)
    options = []
    for key in _options(litter, c["kind"]):
        label = part["tell_leader"] if key == TELL and is_leader(you) else part["options"][key]
        options.append((key, _render(label, you, away, clan)))
    return prompt, options


def resolve_choice(c, option):
    from scripts.honor import choices

    you = _you()
    if c["kind"] == TRUTH:
        source = _truth_source(c)
        if option == choices.DECIDE:
            option = _decide_truth(source, you)
        resolve_truth(source, you, option)
        return option
    litter = _by_id(c["litter"])
    if option == choices.DECIDE:
        option = _decide_litter(litter, c["kind"])
    resolve_litter(litter, c["kind"], option)
    return option
