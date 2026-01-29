"""
Frozen firmware games package.

For frozen modules, we must explicitly list submodules in __all__
since os.listdir() doesn't work on the virtual .frozen filesystem.
"""

# List all game modules that should be discovered
__all__ = [
    "reaction_solo_game",
    "flashy",
]
