"""Venue adapters are loaded lazily so parser tests do not require HTTP extras."""

__all__ = ["TeatroRealAdapter", "WienerStaatsoperAdapter", "MunichBayerischeStaatsoperAdapter"]


def __getattr__(name):
    modules = {
        "TeatroRealAdapter": (".teatro_real", "TeatroRealAdapter"),
        "WienerStaatsoperAdapter": (".wiener_staatsoper", "WienerStaatsoperAdapter"),
        "MunichBayerischeStaatsoperAdapter": (".munich_bayerische_staatsoper", "MunichBayerischeStaatsoperAdapter"),
    }
    if name not in modules:
        raise AttributeError(name)
    from importlib import import_module
    module, symbol = modules[name]
    value = getattr(import_module(module, __name__), symbol)
    globals()[name] = value
    return value
