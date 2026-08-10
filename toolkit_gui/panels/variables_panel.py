'''toolkit_gui.panels.variables_panel - live list of a session's working
variables, polled from its gui_bridge. Single-selection only, matching the
requirement that at most one variable is inspected at a time.
'''

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget


class VariablesPanel(QWidget):
    variable_selected = Signal(str)
    selection_cleared = Signal()

    def __init__(self, bridge_client, parent=None):
        super().__init__(parent)
        self._bridge_client = bridge_client
        self._list = QListWidget(self)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list)

    def refresh(self):
        '''Poll the bridge for the current variable list and update the
        widget, preserving the current selection by name if it still exists.'''
        selected_name = self.selected_variable_name()
        try:
            resp = self._bridge_client.list_vars()
        except (ConnectionError, OSError):
            return
        if not resp.get('ok'):
            return
        self._list.blockSignals(True)
        self._list.clear()
        for item in resp['result']:
            list_item = QListWidgetItem(f"{item['name']}  ({item['type']})")
            list_item.setData(Qt.UserRole, item['name'])
            self._list.addItem(list_item)
            if item['name'] == selected_name:
                list_item.setSelected(True)
        self._list.blockSignals(False)

    def selected_variable_name(self):
        items = self._list.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.UserRole)

    def _on_selection_changed(self):
        name = self.selected_variable_name()
        if name is None:
            self.selection_cleared.emit()
        else:
            self.variable_selected.emit(name)
