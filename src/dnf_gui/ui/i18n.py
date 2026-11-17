"""KDE-style translation functions for QML.

Kirigami Addons call ``i18n()``, ``i18nc()``, ``i18nd()``... which a C++
KDE app gets from KI18n's ``KLocalizedContext``. PyQt has no KI18n, so this
object, set as the root context object, provides the same names. The app
is English-only, so they just fill in ``%1``, ``%2``... arguments.
"""

from __future__ import annotations

import re

from PyQt6.QtCore import QObject, pyqtSlot

_ARG = re.compile(r"%(\d+)")


def _fill(text: str, args) -> str:
    values = [str(a) for a in args]
    return _ARG.sub(lambda m: values[int(m.group(1)) - 1]
                    if 0 < int(m.group(1)) <= len(values) else m.group(0), text)


def _overloads(name: str, fixed: int):
    """pyqtSlot overloads taking ``fixed`` strings plus 0..5 arguments."""
    def decorate(fn):
        for extra in range(5, -1, -1):
            fn = pyqtSlot(*([str] * fixed + ["QVariant"] * extra), name=name,
                          result=str)(fn)
        return fn
    return decorate


class LocalizedContext(QObject):
    @_overloads("i18n", 1)
    def i18n(self, text, *args):
        return _fill(text, args)

    @_overloads("i18nc", 2)
    def i18nc(self, _context, text, *args):
        return _fill(text, args)

    @_overloads("i18nd", 2)
    def i18nd(self, _domain, text, *args):
        return _fill(text, args)

    @_overloads("i18ndc", 3)
    def i18ndc(self, _domain, _context, text, *args):
        return _fill(text, args)

    @_overloads("i18np", 2)
    def i18np(self, singular, plural, *args):
        n = int(args[0]) if args else 1
        return _fill(singular if n == 1 else plural, args)

    @_overloads("i18ndp", 3)
    def i18ndp(self, _domain, singular, plural, *args):
        n = int(args[0]) if args else 1
        return _fill(singular if n == 1 else plural, args)
