"""Tests for translucent popups and scroll fades (ui/polish.py)."""

import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QLabel, QScrollArea, QStyledItemDelegate,
    QVBoxLayout, QWidget,
)

from dnf_gui.ui.polish import add_scroll_fades, install_ui_polish


class TestPopups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        install_ui_polish()

    def test_combo_popup_becomes_translucent_when_shown(self):
        host = QWidget()
        combo = QComboBox()
        combo.addItems(["All updates", "Security updates"])
        QVBoxLayout(host).addWidget(combo)
        host.show()
        self.app.processEvents()
        popup = combo.view().window()
        self.assertIsNot(popup, host)
        self.assertTrue(popup.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertIs(type(combo.itemDelegate()), QStyledItemDelegate)
        host.close()

    def test_update_menu_is_translucent(self):
        from dnf_gui.ui.widgets.update_action_button import UpdateActionButton
        button = UpdateActionButton()
        self.assertTrue(button._menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))


class TestScrollFades(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_fades_follow_scroll_position(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        for i in range(60):
            layout.addWidget(QLabel(f"row {i}"))
        scroll.setWidget(content)
        scroll.resize(300, 200)
        scroll.show()
        self.app.processEvents()
        add_scroll_fades(scroll)
        top, bottom = scroll._dnf_gui_fades
        self.assertTrue(top.isHidden())       # at the top: nothing above
        self.assertFalse(bottom.isHidden())   # more rows below
        bar = scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.assertFalse(top.isHidden())
        self.assertTrue(bottom.isHidden())
        self.assertTrue(top.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        scroll.close()


if __name__ == "__main__":
    unittest.main()
