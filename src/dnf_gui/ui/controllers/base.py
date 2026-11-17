"""Small building blocks shared by the QML-facing controllers.

Every QObject handed to QML is created here in Python, parented to its
controller and kept on an attribute, so QML never owns (or garbage
collects) it. Worker signals only reach controller slots, which run on the
GUI thread; QML reads properties.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from PyQt6.QtCore import (
    QAbstractListModel, QByteArray, QModelIndex, QObject, QSortFilterProxyModel,
    Qt, pyqtProperty, pyqtSignal, pyqtSlot,
)


def state_property(type_, name: str, signal):
    """A read-only QML property backed by ``self._state[name]``.

    All properties of a controller share one ``changed`` signal; the
    controllers are small enough that re-evaluating every binding on any
    change costs nothing measurable.
    """
    def getter(self):
        return self._state[name]
    return pyqtProperty(type_, getter, notify=signal)


class StateObject(QObject):
    """QObject with a ``_state`` dict.

    PyQt requires a property's notify signal to be defined in the same
    class, so each subclass declares ``changed = pyqtSignal()`` and its
    properties with :func:`declare` / :func:`state_property`.
    """

    _defaults: dict[str, Any] = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = dict(self._defaults)

    def _set(self, **values) -> None:
        dirty = False
        for key, value in values.items():
            if key not in self._state:
                raise KeyError(key)
            if self._state[key] != value:
                self._state[key] = value
                dirty = True
        if dirty:
            self.changed.emit()


def declare(namespace: dict, changed, spec: dict) -> None:
    """In a class body: ``declare(locals(), changed, {"name": type, ...})``."""
    for name, type_ in spec.items():
        namespace[name] = state_property(type_, name, changed)


class RowModel(QAbstractListModel):
    """A list of dicts exposed to QML with one role per key."""

    countChanged = pyqtSignal()

    def __init__(self, roles: Iterable[str], parent=None):
        super().__init__(parent)
        self._keys = list(roles)
        self._role_ids = {Qt.ItemDataRole.UserRole + 1 + i: key
                          for i, key in enumerate(self._keys)}
        self._rows: list[dict] = []

    def roleNames(self):
        return {role: QByteArray(key.encode()) for role, key in self._role_ids.items()}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return row.get(self._keys[0])
        key = self._role_ids.get(role)
        return row.get(key) if key else None

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = [dict(r) for r in rows]
        self.endResetModel()
        self.countChanged.emit()

    def rows(self) -> list[dict]:
        return [dict(r) for r in self._rows]

    def find(self, key: str, value) -> dict | None:
        return next((dict(r) for r in self._rows if r.get(key) == value), None)

    @pyqtProperty(int, notify=countChanged)
    def count(self) -> int:
        return len(self._rows)

    @pyqtSlot(int, result="QVariantMap")
    def get(self, row: int) -> dict:
        return dict(self._rows[row]) if 0 <= row < len(self._rows) else {}


class FilterModel(QSortFilterProxyModel):
    """Text + category filter over a :class:`RowModel`, keeping source order.

    The source is already sorted by section, so ``ListView`` sections stay
    contiguous; filtered-out rows don't exist for keyboard navigation or
    screen readers.
    """

    filterChanged = pyqtSignal()
    countChanged = pyqtSignal()

    def __init__(self, source: RowModel, text_keys: Iterable[str],
                 category: Callable[[dict, str], bool] | None = None, parent=None):
        super().__init__(parent)
        self._source = source
        self._text_keys = list(text_keys)
        self._category_fn = category
        self._query = ""
        self._category = "all"
        self.setSourceModel(source)
        self.rowsInserted.connect(self.countChanged)
        self.rowsRemoved.connect(self.countChanged)
        self.modelReset.connect(self.countChanged)
        self.layoutChanged.connect(self.countChanged)

    def filterAcceptsRow(self, source_row, source_parent):
        row = self._source._rows[source_row]
        if self._category != "all" and self._category_fn is not None:
            if not self._category_fn(row, self._category):
                return False
        if not self._query:
            return True
        return any(self._query in str(row.get(k, "")).lower() for k in self._text_keys)

    def _get_query(self) -> str:
        return self._query

    def _set_query(self, text: str) -> None:
        text = (text or "").strip().lower()
        if text != self._query:
            self._query = text
            self.invalidateFilter()
            self.filterChanged.emit()
            self.countChanged.emit()

    query = pyqtProperty(str, _get_query, _set_query, notify=filterChanged)

    def _get_category(self) -> str:
        return self._category

    def _set_category(self, value: str) -> None:
        value = value or "all"
        if value != self._category:
            self._category = value
            self.invalidateFilter()
            self.filterChanged.emit()
            self.countChanged.emit()

    category = pyqtProperty(str, _get_category, _set_category, notify=filterChanged)

    @pyqtProperty(int, notify=countChanged)
    def count(self) -> int:
        return self.rowCount()

    @pyqtSlot(int, result="QVariantMap")
    def get(self, row: int) -> dict:
        index = self.mapToSource(self.index(row, 0))
        return self._source.get(index.row()) if index.isValid() else {}
