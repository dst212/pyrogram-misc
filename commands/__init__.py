import glob
import importlib
import os

__dict__ = {}
items = {}


def _():
    for i in glob.glob(os.path.join(__path__[0], "[!_]*")):
        if os.path.isfile(i) and i.endswith(".py"):
            i = os.path.basename(i[:-3])
        elif os.path.isdir(i):
            i = os.path.basename(i)
        else:
            continue

        items[i] = importlib.import_module(f"{__name__}.{i}")
        __dict__[i] = items[i]


_()
