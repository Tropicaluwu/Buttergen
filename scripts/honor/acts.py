"""BUTTERGEN: every act that follows or breaks the warrior code. Texts: events/honor_acts.json."""

from scripts.cat.enums import CatRank

R = CatRank
APPRENTICES = {R.APPRENTICE, R.MEDICINE_APPRENTICE, R.MEDIATOR_APPRENTICE, R.QUEEN_APPRENTICE}
# everyone from apprentice up but the leader (step 8 adds leaders to the shared acts by name)
EVERYONE = APPRENTICES | {R.WARRIOR, R.MEDICINE_CAT, R.MEDIATOR, R.QUEEN, R.DEPUTY, R.ELDER}
WORKING = EVERYONE - {R.ELDER}
WARRIORS = {R.WARRIOR, R.APPRENTICE, R.DEPUTY}
HEALERS = {R.MEDICINE_CAT, R.MEDICINE_APPRENTICE}
MEDIATORS = {R.MEDIATOR, R.MEDIATOR_APPRENTICE}
QUEENS = {R.QUEEN, R.QUEEN_APPRENTICE}
KITS = {R.KITTEN}
LEADER = {R.LEADER}

HUNGER, LONGING, GRUDGE, RESTLESS, DARK, DUTY = "hunger", "longing", "grudge", "restless", "dark", "duty"
CAUSES = (HUNGER, LONGING, GRUDGE, RESTLESS, DARK)


def act(kind, roles, causes, level=None, other=None, other_clan=False, full_moon=False, hungry=False):
    return {"kind": kind, "level": level, "roles": roles, "causes": causes, "other": other,
            "other_clan": other_clan, "full_moon": full_moon, "hungry": hungry}


def brk(level, roles, causes, **kw):
    return act("break", roles, causes, level=level, **kw)


def fol(roles, **kw):
    return act("follow", roles, (DUTY,), **kw)


ACTS = {
    # step 7: healers taking mates and having kits, with the toggle on. No roles: these come
    # from romance and births (scripts/honor/healer.py), never from temptation
    "healer_mate": brk("serious", frozenset(), ()),
    "healer_kits": brk("serious", frozenset(), ()),
    # everyone from apprentice up
    "eat_first": brk("minor", EVERYONE | LEADER, (HUNGER,)),
    "sneak_out": brk("minor", EVERYONE, (RESTLESS, LONGING)),
    "skip_duties": brk("minor", WORKING, (RESTLESS,)),
    "lie_leader": brk("serious", EVERYONE - {R.DEPUTY}, (GRUDGE, DARK), other="leader"),
    "gathering_fight": brk("serious", EVERYONE | LEADER, (GRUDGE,), other_clan=True, full_moon=True),
    "pass_secrets": brk("grave", EVERYONE, (DARK,), other_clan=True),
    "twoleg_food": brk("minor", EVERYONE, (HUNGER, RESTLESS)),
    "neglect_kit": brk("serious", EVERYONE, (GRUDGE, DARK), other_clan=True),
    "give_share": fol(EVERYONE, other="hungry"),
    "defend_clanmate": fol(EVERYONE, other="liked"),
    "help_kit": fol(EVERYONE, other_clan=True),
    # warriors, apprentices and the deputy
    "hunt_border": brk("serious", WARRIORS, (HUNGER,), other_clan=True),
    "let_trespasser": brk("minor", WARRIORS, (LONGING,), other_clan=True),
    "markers_lapse": brk("minor", WARRIORS, (RESTLESS,), other_clan=True),
    "renew_markers": fol(WARRIORS, other_clan=True),
    "feed_elders": fol(WARRIORS, other="elder"),
    "keep_vigil": fol(WARRIORS),
    "extra_patrol": fol(WARRIORS),
    # apprentices
    "disobey_mentor": brk("minor", APPRENTICES, (RESTLESS,), other="mentor"),
    "app_eat_first": brk("minor", {R.APPRENTICE}, (HUNGER,)),
    "practice": fol(APPRENTICES, other="mentor"),
    "help_healer": fol({R.APPRENTICE}, other="healer"),
    # kits
    "kit_sneak": act("mischief", KITS, (RESTLESS,)),
    "kit_border": act("mischief", KITS, (RESTLESS,), other_clan=True),
    # healers
    "hide_sign": brk("serious", HEALERS, (DARK, GRUDGE), other="leader"),
    "bend_sign": brk("grave", HEALERS, (DARK,), other="leader"),
    "favorite_herbs": brk("minor", HEALERS, (HUNGER, GRUDGE), other="liked"),
    "leave_den": brk("minor", HEALERS, (RESTLESS,), other="sick"),
    "honest_sign": fol(HEALERS, other="leader"),
    "sick_vigil": fol(HEALERS, other="sick"),
    "teach_apprentice": fol({R.MEDICINE_CAT}, other="apprentice"),
    "share_herbs": fol(HEALERS, other_clan=True),
    # mediators
    "twist_words": brk("minor", MEDIATORS, (GRUDGE,), other="clanmate"),
    "carry_messages": brk("serious", MEDIATORS, (LONGING,), other_clan=True),
    "settle_fairly": fol(MEDIATORS, other="clanmate"),
    # queens
    "kits_wander": brk("minor", QUEENS, (RESTLESS,)),
    "best_nest": brk("minor", QUEENS, (HUNGER, GRUDGE), other="queen"),
    "nurse_kit": fol(QUEENS, other="queen"),
    "watch_nursery": fol(QUEENS),
    # elders
    "spread_rumors": brk("minor", {R.ELDER}, (GRUDGE,), other="disliked"),
    "old_stories": fol({R.ELDER}),
    # deputy
    "unfair_patrols": brk("minor", {R.DEPUTY}, (GRUDGE,), other="disliked"),
    "hide_news": brk("serious", {R.DEPUTY}, (GRUDGE, DARK), other="leader"),
    "fair_patrols": fol({R.DEPUTY}),
    # step 8: leaders. favorite_off and spite have no roles: they happen inside a judgment
    # (scripts/honor/judgment.py), when the leader's feelings get the better of them
    "favorite_off": brk("serious", frozenset(), ()),
    "spite": brk("serious", frozenset(), ()),
    "ignore_sign": brk("serious", LEADER, (GRUDGE, DARK), other="healer"),
    "secret_meeting": brk("serious", LEADER, (LONGING,), other_clan=True),
    "claim_land": brk("serious", LEADER, (GRUDGE,), other_clan=True),
    "lead_dawn": fol(LEADER),
    "eat_last": fol(LEADER, hungry=True),
    "leader_vigil": fol(LEADER, other="dead"),
    # step 10: only from the player's patrols (scripts/honor/patrols.py), never from temptation
    "steal_kit": brk("grave", frozenset(), (), other_clan=True),
    "kill_kits": brk("grave", frozenset(), (), other_clan=True),
    "border_raid": brk("serious", frozenset(), (), other_clan=True),
    "mark_their_land": brk("minor", frozenset(), (), other_clan=True),
    "herb_border": brk("minor", frozenset(), (), other_clan=True),
    "break_shunning": brk("minor", frozenset(), ()),
}

# honor lost for breaking the code, by level
HONOR_LOSS = {"minor": (2, 4), "serious": (6, 10), "grave": (15, 25)}
# following the code
HONOR_GAIN = (1, 4)
REPUTATION_GAIN = (1, 2)
# a cat doesn't do the same act again within this many moons
COOLDOWN_MOONS = 6
