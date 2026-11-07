"""BUTTERGEN: switching Clans by a task, the warrior code's way (honor step 9)."""

from random import choice, randint, random

from scripts.cat.cats import Cat
from scripts.cat.enums import CatAge, CatRank, CatStanding
from scripts.clan_package import cotc
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.honor import core

RANKS = (CatRank.WARRIOR, CatRank.MEDICINE_CAT)
# the ask chance per Gathering is the pull score times this, at most ASK_CAP
ASK_PER_POINT = 0.008
ASK_CAP = 0.25
ACCEPT_BASE, ACCEPT_LOW, ACCEPT_HIGH = 50, 5, 90
TASK_BASE, TASK_SKILL = 40, 40
EFFORT = {"all": 15, "enough": -15}
REFUSED_WAIT, FAILED_WAIT, MOVED_WAIT = 12, 6, 12
FOLLOW_BONUS = 40
FOLLOW_BASE, FOLLOW_CAP = 0.25, 0.75
FIGHT_HURT = 0.3
HURTS = ("claw_wound", "bite_wound", "scrapes", "bruises")
TASKS_WARRIOR = ("hunt", "fight", "kit", "loyalty")
TASKS_HEALER = ("sick", "kit", "loyalty")
TASK_SKILLS = {"hunt": ("HUNTER",), "fight": ("FIGHTER", "GUARDIAN"), "sick": ("HEALER",),
               "kit": ("TRACKER", "SENSE")}


def texts() -> dict:
    return load_lang_resource("events/honor_switch.json")


def _you():
    return game.clan.your_cat if game.clan else None


def on() -> bool:
    return bool(game.clan) and game.clan.clancount == "multiclan"


def record() -> dict:
    rec = getattr(game.clan, "code_switch", None)
    if not isinstance(rec, dict):
        rec = game.clan.code_switch = {}
    for key, empty in (("skips", 0), ("asks", []), ("tasks", []), ("waits", {})):
        rec.setdefault(key, empty)
    return rec


def _like(cat_from, cat_to, stat="like") -> int:
    rel = cat_from.relationships.get(cat_to.ID) if cat_from and cat_to else None
    return getattr(rel, stat) if rel else 0


# who's where

def home_group():
    return game.clan.group_ID


def clan_of_group(group_ID):
    if group_ID == game.clan.group_ID:
        return game.clan
    return next((c for c in game.clan.all_other_clans if c.group_ID == group_ID), None)


def cats_in(group_ID) -> list:
    return [c for c in Cat.all_cats_list
            if not c.dead and c.status.group_ID == group_ID and not c.status.is_lost()]


def leader_of(group_ID):
    from scripts.honor.exile import _leader_of

    clan = clan_of_group(group_ID)
    return _leader_of(clan) if clan else None


def eligible(cat) -> bool:
    """a warrior or healer in good standing, in your Clan or another one"""
    if not cat or cat.dead or cat.status.rank not in RANKS:
        return False
    group = cat.status.group
    if not group or not group.is_any_clan_group() or cat.status.is_lost():
        return False
    if cat.status.is_shunned() or cat.status.is_exiled():
        return False
    from scripts.honor.judgment import sentence

    return sentence(cat) is None


def busy(cat) -> bool:
    rec = record()
    return any(a["cat"] == cat.ID for a in rec["asks"]) or any(t["cat"] == cat.ID for t in rec["tasks"])


def wait_for(cat, group_ID) -> int:
    waits = record()["waits"].get(cat.ID, {})
    until = max(waits.get("any", 0), waits.get(group_ID, 0))
    return max(0, until - game.clan.age)


def targets(cat) -> list:
    """the Clans this cat could ask: from your Clan any other, from another Clan only yours"""
    if cat.status.group_ID == home_group():
        return [c.group_ID for c in game.clan.all_other_clans if leader_of(c.group_ID)]
    return [home_group()] if leader_of(home_group()) else []


# the pull

def _kin(cat) -> set:
    return set(cat.get_parents()) | set(cat.get_siblings()) | set(cat.get_children())


def pull(cat, target) -> float:
    there = cats_in(target)
    home = [c for c in cats_in(cat.status.group_ID) if c is not cat]
    there_ids = {c.ID for c in there}
    kin = _kin(cat)
    score = 0.0
    # pulls them away
    if any(m in there_ids for m in cat.mate):
        score += 8
    elif any(_like(cat, c, "romance") > 30 for c in there):
        score += 5
    score += 2 * min(2, len(kin & there_ids))
    score += 1.5 * min(3, sum(1 for c in there if _like(cat, c) > 30))
    # pushes them out (only your Clan tracks honor)
    if cat.status.group_ID == home_group():
        leader = game.clan.leader
        if cat.reputation < -20:
            score += 3
        if leader and leader is not cat and _like(cat, leader) < -30:
            score += 3
        if leader and leader is not cat and leader.clan_trust <= -40:
            score += 3
    score += max(0, 8 - cat.personality.lawfulness) / 8 * 1.5
    # keeps them home
    home_ids = {c.ID for c in home}
    if any(m in home_ids for m in cat.mate):
        score -= 4
    if any(c.ID in cat.get_children() and c.moons < 12 for c in home):
        score -= 4
    if cat.apprentice:
        score -= 2
    score -= 0.5 * min(3, len(kin & home_ids))
    score -= 0.25 * min(3, sum(1 for c in home if _like(cat, c) > 30))
    score -= cat.personality.lawfulness / 16
    return score


# asking

def accept_chance(cat, target, bonus=0) -> int:
    from scripts.honor.exile import _ties

    clan = clan_of_group(target)
    leader = leader_of(target)
    chance = ACCEPT_BASE + bonus
    if leader is not None:
        chance += 10 * round((leader.personality.lawfulness - 8) / 8)
    chance += _ties(cat, clan)
    other = clan if clan is not game.clan else clan_of_group(cat.status.group_ID)
    if other is not None and other is not game.clan:
        label = game.clan.get_relations(game.clan, other, get_label=True)
        chance += {"ally": 10, "hostile": -10}.get(label, 0)
    if cat.status.rank == CatRank.MEDICINE_CAT:
        healers = [c for c in cats_in(target) if c.status.rank == CatRank.MEDICINE_CAT]
        if len(healers) < 2:
            chance += 15
    if cat.age in (CatAge.YOUNG_ADULT, CatAge.ADULT):
        chance += 5
    skill = cat.skills.primary
    if skill and getattr(skill, "tier", 0) >= 2:
        chance += 5
    if cat.status.group_ID == home_group():
        chance += max(-10, min(10, cat.reputation // 5))
    return max(ACCEPT_LOW, min(ACCEPT_HIGH, chance))


def fitting_tasks(cat) -> tuple:
    return TASKS_HEALER if cat.status.rank == CatRank.MEDICINE_CAT else TASKS_WARRIOR


def ask(cat, target, bonus=0, follow=None):
    """the cat asks at the Gathering. Returns True if it was settled now (not waiting on your choice)"""
    if not eligible(cat) or target not in targets(cat):
        return True
    leader = leader_of(target)
    _post("ask_in" if target == home_group() else "ask", cat, leader, target)
    from scripts.honor import choices

    if leader is _you():
        if choices.can_offer():
            choices.offer_switch_ask(cat, target, bonus, follow)
            return False
        option = decide_ask(cat, target, bonus)
    else:
        option = decide_ask(cat, target, bonus)
    answer(cat, target, option)
    return True


def decide_ask(cat, target, bonus=0) -> str:
    if random() * 100 < accept_chance(cat, target, bonus):
        return "task_" + choice(fitting_tasks(cat))
    return "refuse"


def answer(cat, target, option):
    """option: "refuse" or "task_<task>" """
    leader = leader_of(target)
    if option == "refuse" or not option.startswith("task_"):
        refused(cat, target)
        return
    task = option[len("task_"):]
    rec = record()
    rec["tasks"].append({"cat": cat.ID, "from": cat.status.group_ID, "to": target, "task": task,
                         "start": rec["skips"], "effort": None, "told": None})
    _post("task_" + task + ("_in" if target == home_group() else ""), cat, leader, target)
    if cat is _you():
        from scripts.honor import choices

        if choices.can_offer():
            if task == "loyalty":
                choices.offer_switch_loyalty(cat, target)
            else:
                choices.offer_switch_effort(cat, target, task)


def _wait(cat, group_ID, moons):
    waits = record()["waits"].setdefault(cat.ID, {})
    waits[group_ID] = max(waits.get(group_ID, 0), game.clan.age + moons)


def _came_home_cost(cat):
    from scripts.honor.temptation import nudge

    leader = leader_of(cat.status.group_ID)
    if leader and leader is not cat:
        nudge(leader, cat, like=-randint(3, 6))
    if cat.status.group_ID == home_group() and core.has_honor(cat):
        core.change_reputation(cat, -randint(2, 4))


def refused(cat, target):
    _came_home_cost(cat)
    _wait(cat, target, REFUSED_WAIT)
    _post("refused_in" if target == home_group() else "refused", cat, leader_of(target), target)


# the task

def _skill_bonus(cat, task) -> int:
    if task == "loyalty":
        return int(max(0, cat.honor) * TASK_SKILL / 100)
    paths = TASK_SKILLS.get(task, ())
    best = 0
    for skill in (cat.skills.primary, cat.skills.secondary):
        if skill and skill.path.name in paths:
            best = max(best, (skill.tier + 1) * 10)
    return min(TASK_SKILL, best)


def task_chance(cat, task, effort=None) -> int:
    return max(5, min(95, TASK_BASE + _skill_bonus(cat, task) + EFFORT.get(effort, 0)))


def decide_effort(cat) -> str:
    return "all" if random() < 0.4 + cat.personality.lawfulness / 16 * 0.4 else "enough"


def decide_told(cat) -> str:
    keep = 0.5 + max(0, cat.honor) / 200 + cat.personality.lawfulness / 16 * 0.3
    if random() < keep:
        return "refuse"
    return "little" if random() < 0.7 else "all"


def settle(task):
    """at the full moon after the task began"""
    cat = Cat.fetch_cat(task["cat"])
    target = task["to"]
    if not eligible(cat) or cat.status.group_ID != task["from"] or not leader_of(target):
        return
    kind = task["task"]
    if kind == "loyalty":
        told = task.get("told") or (decide_told(cat) if cat is _you() else None)
        if told is None:
            told = "refuse" if random() * 100 < task_chance(cat, kind) else "all"
        success = told == "refuse"
        if not success:
            _told(cat, target, told)
        else:
            _post("loyalty_pass", cat, leader_of(target), target)
    else:
        effort = task.get("effort") or (decide_effort(cat) if cat is _you() else None)
        success = random() * 100 < task_chance(cat, kind, effort)
        if kind == "fight" and effort != "enough" and random() < FIGHT_HURT:
            from scripts.cat.conditions.gain_conditions import gain_temporary_condition

            gain_temporary_condition(cat, choice(HURTS))
    if success:
        move(cat, target)
    else:
        _came_home_cost(cat)
        record()["waits"].setdefault(cat.ID, {})["any"] = game.clan.age + FAILED_WAIT
        _post("failed_in" if target == home_group() else "failed", cat, leader_of(target), target)


def _told(cat, target, how):
    """a cat from your Clan who answers the loyalty test breaks the code: passing secrets"""
    if cat.status.group_ID != home_group():
        return
    clan = clan_of_group(target)
    if how == "little":
        from scripts.honor import witness
        from scripts.honor.acts import HONOR_LOSS

        core.change_honor(cat, -randint(*HONOR_LOSS["minor"]))
        witness.after_break(cat, "pass_secrets", clan, level="minor")
        _post("loyalty_little", cat, leader_of(target), target)
    else:
        from scripts.honor import temptation

        temptation.do_act(cat, "pass_secrets", None, clan)


# switching

def move(cat, target):
    from scripts.honor.temptation import nudge

    old = cat.status.group_ID
    old_leader = leader_of(old)
    if old_leader and old_leader is not cat:
        nudge(old_leader, cat, like=-randint(3, 6))
    for other in cats_in(old):
        if other is not cat and _like(other, cat) > 30:
            nudge(other, cat, like=-randint(1, 3))
    other_clan = clan_of_group(target if target != home_group() else old)
    if other_clan is not None and other_clan is not game.clan:
        cotc.change_clan_relations(game.clan, other_clan, -1)
    core.change_honor(cat, randint(2, 4))
    if old == home_group() and cat.status.rank == CatRank.MEDICINE_CAT:
        game.clan.remove_med_cat(cat)
    cat.history.add_beginning(False)
    cat.status._modify_group(cat.status.rank, CatStanding.LEFT, target)  # pylint: disable=protected-access
    for app in cat.apprentice.copy():
        apprentice = Cat.fetch_cat(app)
        if apprentice:
            apprentice.update_mentor()
    cat.update_mentor()
    game.clan.add_cat(cat)
    # a cat who just switched settles in before asking anywhere again
    record()["waits"].setdefault(cat.ID, {})["any"] = game.clan.age + MOVED_WAIT
    if target == home_group():
        cat.reputation = 0
        if cat.status.rank == CatRank.MEDICINE_CAT:
            game.clan.new_medicine_cat(cat)
    _post("done_in" if target == home_group() else "done", cat, leader_of(target), target, origin=old)
    _tell_you(cat, old, target)
    _mates_follow(cat, old, target)


def _tell_you(cat, old, target):
    you = _you()
    if not you or you is cat or you.dead or you.status.group_ID != old:
        return
    close = cat.ID in you.mate or cat.ID in _kin(you) or _like(you, cat) > 30
    if close:
        _post("you_lose", you, cat, target)


def follow_chance(mate, cat) -> float:
    chance = min(FOLLOW_CAP, FOLLOW_BASE + max(0, _like(mate, cat, "romance")) / 400)
    young_kits = [k for k in (Cat.fetch_cat(i) for i in mate.get_children())
                  if k and not k.dead and k.moons < 6 and k.status.group_ID == mate.status.group_ID]
    if young_kits or mate.apprentice:
        chance /= 2
    return chance


def _mates_follow(cat, old, target):
    from scripts.honor import choices

    for mate_id in list(cat.mate):
        mate = Cat.fetch_cat(mate_id)
        if not mate or mate.status.group_ID != old or not eligible(mate) or busy(mate):
            continue
        if mate is _you():
            if choices.can_offer():
                choices.offer_switch_follow(cat, target)
                continue
            follows = random() < follow_chance(mate, cat)
        else:
            follows = random() < follow_chance(mate, cat)
        resolve_follow(mate, cat, target, follows)


def resolve_follow(mate, cat, target, follows):
    inbound = "_in" if target == home_group() else ""
    if follows:
        record()["asks"].append({"cat": mate.ID, "to": target, "bonus": FOLLOW_BONUS, "follow": cat.ID})
        _post("follow" + inbound, mate, cat, target)
    else:
        _post("stay" + inbound, mate, cat, target)


# your cat asking

def you_can_ask() -> bool:
    you = _you()
    return (on() and eligible(you) and you.status.group_ID == home_group() and not busy(you)
            and any(not wait_for(you, t) for t in targets(you)))


def queue_your_ask(target):
    you = _you()
    if not you_can_ask() or wait_for(you, target) or target not in targets(you):
        return None
    record()["asks"].append({"cat": you.ID, "to": target, "bonus": 0, "follow": None})
    return _post("queued", you, leader_of(target), target)


# every skip

def on_skip(full_moon: bool):
    if not on():
        return
    rec = record()
    rec["skips"] += 1
    if not full_moon:
        return
    # asks that were waiting before this Gathering (your cat's, and mates who chose to follow last
    # moon). Mates who decide to follow at this Gathering ask at the next one
    waiting, rec["asks"] = rec["asks"], []
    # tasks that began at an earlier full moon end now
    due = [t for t in rec["tasks"] if t["start"] < rec["skips"]]
    rec["tasks"] = [t for t in rec["tasks"] if t not in due]
    for task in due:
        settle(task)
    for entry in waiting:
        cat = Cat.fetch_cat(entry["cat"])
        if cat:
            ask(cat, entry["to"], entry.get("bonus", 0), entry.get("follow"))
    # new asks
    you = _you()
    candidates = [c for c in Cat.all_cats_list if c is not you and eligible(c) and not busy(c)]
    # at most one new ask a Gathering, so a Clan with many ties abroad doesn't flood the events
    for cat in sorted(candidates, key=lambda c: random()):
        options = [t for t in targets(cat) if not wait_for(cat, t)]
        if not options:
            continue
        scored = max(((pull(cat, t), t) for t in options), key=lambda x: x[0])
        if scored[0] > 0 and random() < min(ASK_CAP, scored[0] * ASK_PER_POINT):
            ask(cat, scored[1])
            break


# your cat's choices (scripts/honor/choices.py hands these over)

def resolve_choice(c, option):
    from scripts.honor import choices

    cat = Cat.fetch_cat(c["cat"])
    if c["kind"] == choices.SWITCH_ASK:
        if option == choices.DECIDE:
            option = decide_ask(cat, c["to"], c.get("bonus", 0))
        answer(cat, c["to"], option)
    elif c["kind"] == choices.SWITCH_EFFORT:
        task = _task_for(cat)
        if task:
            task["effort"] = decide_effort(cat) if option == choices.DECIDE else option
            _post("effort_" + task["effort"], cat, leader_of(c["to"]), c["to"])
    elif c["kind"] == choices.SWITCH_LOYALTY:
        task = _task_for(cat)
        if task:
            task["told"] = decide_told(cat) if option == choices.DECIDE else option
    elif c["kind"] == choices.SWITCH_FOLLOW:
        you = _you()
        follows = random() < follow_chance(you, cat) if option == choices.DECIDE else option == "follow"
        resolve_follow(you, cat, c["to"], follows)
    return option


def _task_for(cat):
    return next((t for t in record()["tasks"] if t["cat"] == cat.ID), None)


def window_text(c, render, decide_label):
    """(prompt, [(option, label), ...]) for one of step 9's choices"""
    from scripts.honor import choices

    t = texts()["choices"]
    cat = Cat.fetch_cat(c["cat"])
    target = c["to"]
    oc = clan_of_group(target if target != home_group() else cat.status.group_ID)
    leader = leader_of(target)
    if c["kind"] == choices.SWITCH_ASK:
        part = t["ask"]
        options = [("task_" + task, part["tasks"][task]) for task in fitting_tasks(cat)]
        options.append(("refuse", part["refuse"]))
        prompt = part["prompt"]
    elif c["kind"] == choices.SWITCH_EFFORT:
        part = t["effort"]
        options = list(zip(("all", "enough"), part["options"]))
        prompt = part["prompt_" + c["task"]]
    elif c["kind"] == choices.SWITCH_LOYALTY:
        part = t["loyalty"]
        options = list(zip(("refuse", "little", "all"), part["options"]))
        prompt = part["prompt"]
    else:
        part = t["follow"]
        options = list(zip(("follow", "stay"), part["options"]))
        prompt = part["prompt"]
    return render(prompt, cat, leader, oc), [(o, render(label, cat, leader, oc)) for o, label in options]


# text

def _post(key, cat, other, target, origin=None):
    """origin: the Clan the cat came from, when they've already moved"""
    lines = texts()[key]
    you = _you()
    involved = you in (cat, other)
    if isinstance(lines, dict):
        # "you": your cat is the one switching, "r_you": your cat is the leader or the mate (r_c)
        if cat is you and "you" in lines:
            lines = lines["you"]
        elif other is you and other is not None and "r_you" in lines:
            lines = lines["r_you"]
        else:
            lines = lines.get("others", [])
    if not lines:
        return ""
    # o_c_n is always the Clan that isn't yours
    oc = clan_of_group(target if target != home_group() else (origin or cat.status.group_ID))
    if oc is game.clan:
        oc = None
    text = event_text_adjust(Cat, choice(lines), main_cat=cat, random_cat=other, clan=game.clan, other_clan=oc)
    event = EventInformation(text, ["misc"], [c.ID for c in (cat, other) if c])
    if involved:
        game.cur_events_list.insert(0, event)
    else:
        game.cur_events_list.append(event)
    return text
