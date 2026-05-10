import importlib
import pkgutil

from .base import TrendAdapter

_TOOLS: dict[str, TrendAdapter] = {}
_DISCOVERED = False


def _discover():
    global _TOOLS, _DISCOVERED
    if _DISCOVERED:
        return
    _DISCOVERED = True
    for _, name, _ in pkgutil.iter_modules(__path__):
        if name.startswith("_") or name == "base":
            continue
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except Exception:
            continue
        for obj_name in dir(module):
            obj = getattr(module, obj_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, TrendAdapter)
                and obj is not TrendAdapter
            ):
                try:
                    instance = obj()
                    if instance.is_available():
                        _TOOLS[instance.name] = instance
                except Exception:
                    pass


def get_tools() -> list[TrendAdapter]:
    _discover()
    return list(_TOOLS.values())


def get_tool(name: str) -> TrendAdapter | None:
    _discover()
    return _TOOLS.get(name)
