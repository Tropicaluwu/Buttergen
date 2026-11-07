"""BUTTERGEN: special eye colors as a rare recessive gene, from Beetle's Eyes."""
from random import choice, random

import ujson

with open("resources/dicts/special_eyes.json", "r", encoding="utf-8") as read_file:
    EYES = ujson.loads(read_file.read())


def config():
    from scripts.game_structure import constants

    return constants.CONFIG.get("buttergen", {}).get("eyes", {})


def _eyes_of(genes):
    eyes = getattr(genes, "special_eyes", None)
    return eyes if isinstance(eyes, dict) else {}


def founder_eyes():
    """Special eye genes for a cat with no known parents"""
    eyes = {}
    if random() < config().get("show_chance", 0):
        eyes[choice(list(EYES))] = 2
    carrier_chance = config().get("carrier_chance", 0)
    for name in EYES:
        if name not in eyes and random() < carrier_chance:
            eyes[name] = 1
    return eyes


def _passes(copies):
    return copies >= 2 or (copies == 1 and random() < 0.5)


def kit_eyes(par1, par2):
    """Each parent passes one of their two copies, like any other gene"""
    parents = [_eyes_of(par) for par in (par1, par2)]
    eyes = {}
    for name in set(parents[0]) | set(parents[1]):
        copies = sum(1 for par in parents if _passes(par.get(name, 0)))
        if copies:
            eyes[name] = copies
    return eyes


def shown(genes):
    """The special eye color a cat has (two copies), or None"""
    names = sorted(name for name, copies in _eyes_of(genes).items() if copies >= 2 and name in EYES)
    return names[0] if names else None


def _sides(genes):
    """Which eyes show the special color: both, or for odd eyes the one that isn't blue"""
    if not shown(genes):
        return ()
    left, right = genes.lefteyetype, genes.righteyetype
    if left == right:
        return ("left", "right")
    if "blue" in left and "blue" not in right:
        return ("right",)
    return ("left",)


def eye_data(genes, side):
    """The colors (inner, outer, pupil) for that eye if it's special, or None"""
    if side in _sides(genes):
        return EYES[shown(genes)]
    return None


def eye_names(genes):
    """The names of the cat's eye colors, with the special one in"""
    special = shown(genes)
    sides = _sides(genes)
    left = EYES[special]["text"] if "left" in sides else genes.lefteye
    right = EYES[special]["text"] if "right" in sides else genes.righteye
    return left, right


def gene_list(genes):
    return [f"{name} ({copies}/2)" for name, copies in sorted(_eyes_of(genes).items())]


def match_parents(kit_genes, parent_genes):
    """Made up parents for your cat's birth get the copies your cat needed from them"""
    kit = _eyes_of(kit_genes)
    parents = [_eyes_of(genes) for genes in parent_genes]
    for genes, eyes in zip(parent_genes, parents):
        genes.special_eyes = eyes
    for name, copies in kit.items():
        have = [i for i, par in enumerate(parents) if par.get(name, 0)]
        for i, par in enumerate(parents):
            if len(have) >= min(copies, len(parents)):
                break
            if i not in have:
                par[name] = 1
                have.append(i)
