'''toolkit_gui.panels.preview_panel - bounded data preview of the currently
selected variable (see variables_panel.py), polled from the gui_bridge.
Renders tables as a scrollable grid capped at 250x250 cells (see
tedtoolkit.tables.snapshot), with a truncation hint if the real data exceeds
that. QTableWidget provides horizontal/vertical scrollbars natively.
'''

from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class PreviewPanel(QWidget):
    def __init__(self, bridge_client, parent=None):
        super().__init__(parent)
        self._bridge_client = bridge_client
        self._current_name = None
        self._hint_label = QLabel('No variable selected.', self)
        self._hint_label.setWordWrap(True)
        self._table = QTableWidget(self)
        self._table.setVisible(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._hint_label)
        layout.addWidget(self._table)

    def clear(self):
        self._current_name = None
        self._hint_label.setText('No variable selected.')
        self._hint_label.setVisible(True)
        self._table.setVisible(False)
        self._table.clear()
        self._table.setRowCount(0)
        self._table.setColumnCount(0)

    def show_variable(self, name):
        self._current_name = name
        self.refresh()

    def refresh(self):
        '''Re-fetch the currently selected variable's preview (called on the
        same poll tick as the Variables panel, so a table's content stays in
        sync while a long-running command is still filling it in).'''
        if self._current_name is None:
            return
        try:
            resp = self._bridge_client.get_var_preview(self._current_name)
        except (ConnectionError, OSError):
            return
        if not resp.get('ok'):
            self._show_message(f"Could not preview '{self._current_name}': {resp.get('error')}")
            return
        result = resp['result']
        if result['kind'] == 'table':
            self._render_table(result)
        else:
            self._show_message(result['preview'])

    def _show_message(self, text):
        self._hint_label.setText(text)
        self._hint_label.setVisible(True)
        self._table.setVisible(False)

    def _render_table(self, result):
        hint_parts = []
        if result['truncated_rows']:
            hint_parts.append(f"showing {len(result['rows'])} of {result['row_count']} rows")
        if result['truncated_cols']:
            hint_parts.append(f"showing {len(result['column_labels'])} of {result['col_count']} columns")
        if hint_parts:
            self._hint_label.setText('Truncated for display: ' + ', '.join(hint_parts))
            self._hint_label.setVisible(True)
        else:
            self._hint_label.setVisible(False)
        self._table.setVisible(True)
        rows = result['rows']
        col_count = len(result['column_labels'])
        self._table.setRowCount(len(rows))
        self._table.setColumnCount(col_count)
        self._table.setHorizontalHeaderLabels(result['column_labels'])
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                self._table.setItem(row_index, col_index, QTableWidgetItem(value))
