"""BUTTERGEN: genes for white and tortie patches, from Simple Dark Patches and Mink's Torties."""
from random import random

GENES = ("dark_white", "white_shape_torties", "tortie_shape_white")
MUSTACHES = ("mustache", "MUSTACHE")


def config():
    from scripts.game_structure import constants

    return constants.CONFIG.get("buttergen", {}).get("patch_genes", {})


def _genes_of(genes):
    found = getattr(genes, "patch_genes", None)
    return found if isinstance(found, dict) else {}


def copies(genes, name):
    return _genes_of(genes).get(name, 0)


def set_copies(genes, name, amount):
    found = dict(_genes_of(genes))
    found[name] = amount
    genes.patch_genes = {key: value for key, value in found.items() if value}


def _shape_copies(chance):
    return sum(1 for _ in range(2) if random() < chance)


def _dark_copies(show_chance):
    roll = random()
    if roll < show_chance:
        return 2
    return 1 if roll < show_chance + config().get("dark_carrier_chance", 0) else 0


def founder_genes(new_look=True):
    """Patch genes for a cat with no known parents. Cats from older saves pass new_look=False,
    so they don't suddenly turn dark."""
    found = {
        "dark_white": _dark_copies(config().get("dark_show_chance", 0) if new_look else 0),
        "white_shape_torties": _shape_copies(config().get("white_shape_torties_chance", 0)),
        "tortie_shape_white": _shape_copies(config().get("tortie_shape_white_chance", 0)),
    }
    return {name: amount for name, amount in found.items() if amount}


def _passes(amount):
    return amount >= 2 or (amount == 1 and random() < 0.5)


def kit_genes(par1, par2):
    """Each parent passes one of their two copies, like any other gene"""
    found = {}
    for name in GENES:
        amount = sum(1 for par in (par1, par2) if _passes(copies(par, name)))
        if amount:
            found[name] = amount
    return found


def dark_shown(genes, pattern=None):
    """If the cat's white patches are dark. pattern is the white pattern if it isn't set on genes yet"""
    amount = copies(genes, "dark_white")
    white = genes.white_pattern if pattern is None else pattern
    # a solid white coat isn't patches
    if not isinstance(white, list) or "FULLWHITE" in white:
        return False
    return amount >= 2 or (amount == 1 and any(name in white for name in MUSTACHES))


def match_parents(kit_genes_, parent_genes):
    """Made up parents for your cat's birth get the copies your cat needed from them"""
    for name in GENES:
        have = [par for par in parent_genes if copies(par, name)]
        for par in parent_genes:
            if len(have) >= min(copies(kit_genes_, name), len(parent_genes)):
                break
            if par not in have:
                set_copies(par, name, 1)
                have.append(par)
