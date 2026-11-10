"""BUTTERGEN: honor step 10, the player's patrol choices count.

Each patrol outcome below is marked by hand: who did what, how bad it was, and whether the other
Clan saw. Outcome ids are the patrol's event_id plus _success0, _fail1, _antag_success0 and so on,
and _decline for turning the patrol down. Notes\\Buttergen honor step 10 for review.txt has the rules.
"""

from random import randint, random

from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank
from scripts.game_structure import game
from scripts.honor import core
from scripts.honor.acts import ACTS, COOLDOWN_MOONS, HONOR_GAIN, HONOR_LOSS, REPUTATION_GAIN

# rule d: turning a temptation down is worth half the usual gain
RESIST_GAIN = (1, 2)
# a little more for taking kits home to a hostile Clan
HOSTILE_HELP_EXTRA = 1


def brk(who, act, caught=False, level=None, top=False, followers=None, follower_level="minor",
        ordered=False, by="caught", kits=None):
    """who breaks the code. who is an abbreviation, a list (the first one named in the text) or
    "patrol" (every patrol cat but p_l). followers: True for the whole patrol, or a list of
    abbreviations. ordered: the patrol leader gave the order (an apprentice player's cat is spared).
    by: the text group when caught ("caught" by the other Clan, "out" in camp, "told" by a patient).
    kits: abbreviations of kits taken, to remember where they came from"""
    return {"kind": "break", "who": who, "act": act, "caught": caught, "level": level, "top": top,
            "followers": followers, "follower_level": follower_level, "ordered": ordered, "by": by,
            "kits": kits or []}


def resist(who, act):
    """rule d: turning it down"""
    return {"kind": "resist", "who": who, "act": act}


def stop(who, act):
    """rule e: stopping someone else"""
    return {"kind": "stop", "who": who, "act": act}


def gain(who, act, extra=0):
    """following the code, like taking lost kits home"""
    return {"kind": "gain", "who": who, "act": act, "extra": extra}


def _kit_patrol(pid, hostile=False, behind_back=True, ally_stop=False):
    help_extra = HOSTILE_HELP_EXTRA if hostile else 0
    out = {f"{pid}_success{i}": [gain("p_l", "help_kit", help_extra), gain("r_c0", "help_kit", help_extra)]
           for i in range(4)}
    out[f"{pid}_antag_success0"] = [brk("p_l", "kill_kits", top=True, followers=True,
                                        follower_level="serious", ordered=True)]
    out[f"{pid}_antag_success1"] = [brk("p_l", "steal_kit", followers=True, ordered=True,
                                        kits=["n_c0", "n_c1"])]
    if behind_back:
        out[f"{pid}_antag_success2"] = [brk("patrol", "steal_kit", kits=["n_c0", "n_c1"])]
    kill_fail = brk("p_l", "kill_kits", caught=True, followers=True, follower_level="serious", ordered=True)
    steal_fail = brk("p_l", "steal_kit", caught=True, followers=True, ordered=True)
    if hostile:
        out[f"{pid}_antag_fail0"] = [kill_fail]
        out[f"{pid}_antag_fail1"] = [kill_fail]
        out[f"{pid}_antag_fail2"] = [steal_fail]
    else:
        out[f"{pid}_antag_fail0"] = [kill_fail]
        out[f"{pid}_antag_fail1"] = [steal_fail]
    if ally_stop:
        out[f"{pid}_antag_fail2"] = [stop("r_c0", "steal_kit")]
    return out


def _eat(pid, who, resists, snacks, out_in_camp, secret=(), text_split=None):
    out = {f"{pid}_decline": [resist(who, "eat_first")]}
    for i in resists:
        out[f"{pid}_success{i}"] = [resist(who, "eat_first")]
    for i in snacks:
        out[f"{pid}_success{i}"] = [brk(who, "eat_first")]
    for i in out_in_camp:
        out[f"{pid}_fail{i}"] = [brk(who, "eat_first", caught=True, by="out")]
    for i in secret:
        out[f"{pid}_fail{i}"] = [brk(who, "eat_first")]
    if text_split:
        # one outcome with two texts that mean different things: picked by a word in the text
        i, words = text_split
        out[f"{pid}_success{i}"] = {"text": {words[0]: [resist(who, "eat_first")],
                                             words[1]: [brk(who, "eat_first")]}}
    return out


def _herbs(pid, taken, caught, safe=()):
    out = {f"{pid}_decline": [resist("p_l", "herb_border")]}
    for key in taken:
        out[f"{pid}_{key}"] = [brk("p_l", "herb_border")]
    for key in caught:
        out[f"{pid}_{key}"] = [brk("p_l", "herb_border", caught=True)]
    return out


RABBIT = "gen_bord_otherclan_rabbit1"
PATROLS = {
    # A. hunting across the border
    f"{RABBIT}_success0": [brk("r_c0", "hunt_border")],
    f"{RABBIT}_success1": [brk("r_c0", "hunt_border", level="minor")],
    f"{RABBIT}_success2": [brk("r_c0", "hunt_border", caught=True)],
    f"{RABBIT}_success3": [stop("s_c0", "hunt_border")],
    f"{RABBIT}_fail0": [brk("r_c0", "hunt_border", level="minor", caught=True)],
    f"{RABBIT}_fail1": [brk("s_c0", "hunt_border", caught=True)],
    f"{RABBIT}_fail2": [brk("r_c0", "hunt_border", caught=True)],
    f"{RABBIT}_antag_success0": [brk("r_c0", "hunt_border", caught=True, top=True)],
    f"{RABBIT}_antag_fail0": [brk("r_c0", "hunt_border", level="minor")],
    f"{RABBIT}_decline": [resist("r_c0", "hunt_border")],
    # C. the apprentice mission
    "gen_bord_appmission_success0": [brk("s_c0", "hunt_border", followers=["r_c1"], ordered=True)],
    "gen_bord_appmission_success1": [brk("s_c0", "hunt_border", level="minor"), resist("r_c1", "hunt_border")],
    "gen_bord_appmission_success2": [brk("p_l", "hunt_border", level="minor")],
    "gen_bord_appmission_fail0": [brk("p_l", "hunt_border", caught=True, followers=["r_c1"], ordered=True)],
    "gen_bord_appmission_fail1": [brk("r_c1", "hunt_border", level="minor", caught=True),
                                  brk("s_c0", "hunt_border")],
    "gen_bord_appmission_decline": [resist("p_l", "hunt_border")],
    # D. stealing a kit (fail1: p_l dies)
    "gen_bord_kitsteal1_success0": [brk("p_l", "steal_kit", kits=["n_c0"])],
    "gen_bord_kitsteal1_fail0": [brk("p_l", "steal_kit", caught=True)],
    "gen_bord_kitsteal1_decline": [resist("p_l", "steal_kit")],
    # I. a shunned healer treats a patient in secret
    "lg_medcat_shunned_J1_success0": [gain("p_l", "sick_vigil")],
    "lg_medcat_shunned_J1_fail0": [brk("p_l", "break_shunning", caught=True, by="told")],
}
# B. eating prey before the Clan (gen_train_sneakprey1 doesn't count, answer 2)
PATROLS.update(_eat("gen_hunt_sneakprey1", "s_c0", resists=[2], snacks=[1], out_in_camp=[0, 1, 2],
                    secret=[4], text_split=(0, ("resist", "snack"))))
PATROLS["gen_hunt_sneakprey1_fail3"] = [brk(["s_c0", "r_c0"], "eat_first", caught=True, by="out")]
PATROLS.update(_eat("dst_hunt_sneak", "r_c0", resists=[0], snacks=[1], out_in_camp=[0, 1]))
PATROLS.update(_eat("dst_hunt_sneakprey2", "p_l", resists=[0], snacks=[1], out_in_camp=[0]))
# E. another Clan's kits by the border (declining is nothing)
PATROLS.update(_kit_patrol("gen_bord_neutral_otherclankits1"))
PATROLS.update(_kit_patrol("gen_bord_allies_otherclankits1", ally_stop=True))
PATROLS.update(_kit_patrol("gen_bord_hostile_otherclankits1", hostile=True, behind_back=False))
# F. raiding the border (disaster1 antag_fail0: p_l dies)
for _pid in ("gen_bord_ambush_hostile_disaster1", "gen_bord_ambush_hostile_disaster2"):
    PATROLS[f"{_pid}_success0"] = [resist("p_l", "border_raid")]
    PATROLS[f"{_pid}_success2"] = [resist("s_c0", "border_raid")]
    PATROLS[f"{_pid}_antag_success0"] = [brk("p_l", "border_raid", caught=True, ordered=True)]
PATROLS["gen_bord_ambush_hostile_disaster2_antag_fail0"] = [
    brk("p_l", "border_raid", caught=True, followers=True, ordered=True)]
# G. paying back a trespass (declining doesn't count, answer 4)
for _pid in ("gen_bord_scent1", "gen_bord_scent2", "gen_bord_scent_allies1", "gen_bord_scent_allies2",
             "gen_bord_scent_hostile1", "gen_bord_scent_hostile2"):
    PATROLS[f"{_pid}_antag_success0"] = [brk("p_l", "mark_their_land", caught=True, ordered=True)]
# H. herbs across the border
PATROLS.update(_herbs("gen_otherclan_raspberrymed_solo", taken=["success0"], caught=["fail0", "fail1"]))
PATROLS.update(_herbs("gen_med_borderherb1", taken=["success0"], caught=[]))
PATROLS.update(_herbs("gen_med_borderherb3", taken=["success0"], caught=["fail0", "fail1"]))


def _you():
    return game.clan.your_cat


def _alive(cat) -> bool:
    return cat is not None and not cat.dead and core.has_honor(cat)


def _text_name(cat) -> str:
    return str(cat.name)


def _cat(abbr, cats: dict, text: str):
    if isinstance(abbr, list):
        for a in abbr:
            c = cats.get(a)
            if c and _text_name(c) in text:
                return c
        return cats.get(abbr[0])
    return cats.get(abbr)


def _capture(fn, *args, **kwargs) -> list:
    """runs an honor function that posts to the events, and takes its lines for the patrol
    screen instead (patrols happen between skips, so they don't go on the events page)"""
    before = list(game.cur_events_list)
    fn(*args, **kwargs)
    new = [e for e in game.cur_events_list if not any(e is b for b in before)]
    game.cur_events_list[:] = before
    return [e.text for e in new if getattr(e, "text", None)]


def _on_cooldown(cat, key) -> bool:
    done = cat.code_done.get(key)
    return done is not None and game.clan.age - done < COOLDOWN_MOONS


def _post(group, offender, act, other_clan, variant=None, witness_cat=None) -> list:
    from scripts.honor import witness

    return _capture(witness._post, group, offender, witness_cat, act, other_clan, variant)


def _break(spec, offender, patrol, cats, other_clan) -> list:
    """rule f: misdeeds always count, no cooldown"""
    from scripts.honor import witness

    act = spec["act"]
    level = spec["level"] or ACTS[act]["level"]
    low, high = HONOR_LOSS[level]
    core.change_honor(offender, -(high if spec["top"] else randint(low, high)))
    offender.code_done[act] = game.clan.age
    for cause in ACTS[act]["causes"]:
        offender.temptation[cause] = 0
    lines = []
    if spec["caught"]:
        group = spec["by"]
        lines += _capture(witness.report, offender, None, act, other_clan, group, naming=False,
                          level=spec["level"])
        return lines
    # not caught: the rest of the patrol saw it, and each decides (step 3), but the player's cat
    # never reports a choice the player made
    seen_by = [c for c in patrol.patrol_cats if c is not offender and _alive(c)
               and not (spec["who"] == "patrol" and c is cats.get("p_l"))]
    if not seen_by:
        return _post("patrol_alone", offender, act, other_clan)
    # border acts: the other Clan didn't see. Acts at home (eating prey): nobody else did
    lines += _post("patrol_secret" if ACTS[act]["other_clan"] else "patrol_secret_home", offender, act, other_clan)
    keepers, holder = [], None
    you = _you()
    for w in seen_by:
        what = "keep" if w is you else witness.decide(w, offender, act)
        if what == "report":
            lines += _capture(witness.report, offender, w, act, other_clan, "report", naming=False,
                              level=spec["level"])
            return lines
        keepers.append(w)
        if what == "hold" and holder is None:
            holder = w
    first = holder or keepers[0]
    lines += _capture(witness.add_secret, offender, first, act, other_clan, holder is not None, spec["level"])
    if game.clan.code_secrets:
        secret = game.clan.code_secrets[-1]
        secret["knowers"] = [c.ID for c in keepers]
    if holder is not None:
        witness._nudge(offender, holder, trust=-randint(6, 12), like=-randint(3, 6))
        if you in (offender, holder) or random() < witness.SHOW_OTHERS_QUIET:
            lines += _post("hold", offender, act, other_clan, witness_cat=holder)
    return lines


def _follower_loss(spec, cat, offenders, cats) -> bool:
    """rule b: a follower of an order, or the player's cat going along with it"""
    if cat in offenders or not _alive(cat):
        return False
    you = _you()
    leader = cats.get("p_l")
    if cat is you and spec["ordered"] and cat.status.rank == CatRank.APPRENTICE and leader is not you:
        return False  # answer 1: an apprentice following the patrol leader's order
    low, high = HONOR_LOSS[spec["follower_level"]]
    core.change_honor(cat, -randint(low, high))
    return True


def _run_break(spec, patrol, cats, text, other_clan) -> list:
    if spec["who"] == "patrol":
        offenders = [c for c in patrol.patrol_cats if c is not cats.get("p_l") and _alive(c)]
    else:
        c = _cat(spec["who"], cats, text)
        offenders = [c] if _alive(c) else []
    if not offenders:
        return []
    lines = []
    for offender in offenders:
        lines += _break(spec, offender, patrol, cats, other_clan)
    for abbr in spec["kits"]:
        kit = cats.get(abbr)
        if kit is not None:
            game.clan.code_stolen_kits.append({
                "kit": kit.ID, "from": other_clan.name if other_clan else None,
                "by": [c.ID for c in offenders], "moon": game.clan.age,
            })
    level = spec["level"] or ACTS[spec["act"]]["level"]
    you = _you()
    followers = spec["followers"]
    if followers is True:
        pool = list(patrol.patrol_cats)
    elif followers:
        pool = [cats.get(a) for a in followers if cats.get(a)]
    else:
        pool = []
    for cat in pool:
        _follower_loss(spec, cat, offenders, cats)
    # the player's cat on the patrol went along with something serious (answer 1)
    # (not when the patrol did it behind the leader's back and the leader is the player's cat)
    behind_back = spec["who"] == "patrol" and you is cats.get("p_l")
    if (level in ("serious", "grave") and you in patrol.patrol_cats and you not in offenders
            and you not in pool and _alive(you) and not behind_back):
        if _follower_loss(dict(spec, follower_level="minor"), you, offenders, cats):
            lines += _post("along", offenders[0], spec["act"], other_clan, variant="you_did")
    elif you in pool and you not in offenders and _alive(you) and level in ("serious", "grave"):
        if not (spec["ordered"] and you.status.rank == CatRank.APPRENTICE and cats.get("p_l") is not you):
            lines += _post("along", offenders[0], spec["act"], other_clan, variant="you_did")
    return lines


def _run_gain(spec, cats, text, other_clan) -> list:
    """rules d and e, and good deeds: these keep the usual cooldown (answer 7)"""
    cat = _cat(spec["who"], cats, text)
    if not _alive(cat):
        return []
    key = {"resist": "resist_", "stop": "stop_"}.get(spec["kind"], "") + spec["act"]
    if _on_cooldown(cat, key):
        return []
    cat.code_done[key] = game.clan.age
    if spec["kind"] == "resist":
        core.change_honor(cat, randint(*RESIST_GAIN))
        return _post("resist", cat, spec["act"], other_clan)
    core.change_honor(cat, randint(*HONOR_GAIN) + spec.get("extra", 0))
    core.change_reputation(cat, randint(*REPUTATION_GAIN))
    return []


def _specs(outcome_id, text):
    specs = PATROLS.get(outcome_id)
    if isinstance(specs, dict):
        for word, chosen in specs["text"].items():
            if word in text:
                return chosen
        return []
    return specs or []


def on_outcome(patrol, outcome_id: str, cats: dict, text: str) -> list:
    """after a patrol outcome runs. Returns honor lines for the patrol screen"""
    if not game.clan or not outcome_id:
        return []
    specs = _specs(outcome_id, text)
    if not specs:
        return []
    cats = dict(cats or {})
    for key, value in (patrol.involved_cats or {}).items():
        if isinstance(value, Cat):
            cats.setdefault(key, value)
    if "p_l" not in cats and patrol.patrol_cats:
        cats["p_l"] = patrol.patrol_cats[0]
    lines = []
    for spec in specs:
        if spec["kind"] == "break":
            lines += _run_break(spec, patrol, cats, text, patrol.other_clan)
        else:
            lines += _run_gain(spec, cats, text, patrol.other_clan)
    return lines


def on_decline(patrol) -> list:
    if patrol.patrol_event is None:
        return []
    return on_outcome(patrol, f"{patrol.patrol_event.event_id}_decline", {}, "")
