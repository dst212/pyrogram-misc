import glob
import importlib
import logging
import os

log = logging.getLogger(__name__)
__dict__ = {}
items = {}


def import_all():
    for i in glob.glob(os.path.join(__path__[0], "[!_]*")):
        if os.path.isfile(i) and i.endswith(".py"):
            i = os.path.basename(i[:-3])
        elif os.path.isdir(i):
            i = os.path.basename(i)
        else:
            continue

        items[i] = importlib.import_module(f"{__name__}.{i}")
        __dict__[i] = items[i]


def init(name, *args, **kwargs):
    log.info(f"Importing /{name}...")
    __dict__[name] = importlib.import_module(f"{__name__}.{name}").init(*args, **kwargs)
    return __dict__[name]
