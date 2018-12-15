import os
import pathlib

import attr
import epyqlib.utils.qt
import PyQt5.uic


Ui, UiBase = PyQt5.uic.loadUiType(
    pathlib.Path(__file__).with_suffix('.ui'),
)


all_files_filter = ('All Files', ['*'])


@attr.s
class ImportPaths:
    can = attr.ib()
    hierarchy = attr.ib()
    spreadsheet = attr.ib()
    smdx = attr.ib()


@attr.s
class Dialog(UiBase):
    ui = attr.ib(factory=Ui)
    paths_result = attr.ib(default=None)
    _parent = attr.ib(default=None)

    def __attrs_post_init__(self):
        super().__init__(self._parent)

        self.ui.setupUi(self)

        self.ui.buttons.accepted.connect(self.accept)
        self.ui.buttons.rejected.connect(self.reject)

        self.ui.pick_can.clicked.connect(self.pick_can)
        self.ui.pick_hierarchy.clicked.connect(self.pick_hierarchy)
        self.ui.pick_spreadsheet.clicked.connect(self.pick_spreadsheet)
        self.ui.pick_smdx.clicked.connect(self.pick_smdx)
        self.ui.remove_smdx.clicked.connect(self.remove_smdx)

    def accept(self):
        self.paths_result = ImportPaths(
            can=self.ui.can.text(),
            hierarchy=self.ui.hierarchy.text(),
            spreadsheet=self.ui.spreadsheet.text(),
            smdx=self.smdx_paths(),
        )
        super().accept()

    def smdx_paths(self):
        return [
            self.ui.smdx_list.item(index).text()
            for index in range(self.ui.smdx_list.count())
        ]

    def remove_smdx(self):
        selected_items = self.ui.smdx_list.selectedItems()

        for item in reversed(selected_items):
            self.ui.smdx_list.takeItem(self.ui.smdx_list.row(item))

    def pick_can(self):
        filters = (
            ('PEAK PCAN Symbol File', ['sym']),
            all_files_filter,
        )

        self.file_dialog(
            target=self.ui.can,
            filters=filters,
            multiple=False,
        )

    def pick_hierarchy(self):
        filters = (
            ('Parameter Hierarchy', ['json']),
            all_files_filter,
        )

        self.file_dialog(
            target=self.ui.hierarchy,
            filters=filters,
            multiple=False,
        )

    def pick_spreadsheet(self):
        filters = (
            ('SunSpec Spreadsheet', ['xls']),
            all_files_filter,
        )

        self.file_dialog(
            target=self.ui.spreadsheet,
            filters=filters,
            multiple=False,
        )

    def pick_smdx(self):
        filters = (
            ('SunSpec SMDX', ['xml']),
            all_files_filter,
        )

        paths = self.file_dialog(
            target=None,
            filters=filters,
            multiple=True,
        )

        existing_items = set(self.smdx_paths())

        for path in paths:
            path = os.fspath(path)

            if path not in existing_items:
                self.ui.smdx_list.addItem(path)

    def file_dialog(self, target, filters, multiple):
        path = epyqlib.utils.qt.file_dialog(
            filters=filters,
            parent=self,
            path_factory=pathlib.Path,
            multiple=multiple,
        )

        if path is None:
            return

        if target is not None:
            target.setText(os.fspath(path))

        return path


@attr.s
class Main:
    application = attr.ib()
    dialog = attr.ib(factory=Dialog)

    def show_dialog(self):
        self.dialog.accepted.connect(self.dialog_accepted)
        self.dialog.open()

    def dialog_accepted(self):
        print(self.dialog.paths_result)
        self.application.quit()

    def one_call(self):
        if self.dialog.exec():
            print(self.dialog.paths_result)
        self.application.quit()


def main():
    from PyQt5 import QtCore
    from PyQt5 import QtWidgets

    app = QtWidgets.QApplication([])

    main = Main(application=app)
    QtCore.QTimer.singleShot(0, main.one_call)
    app.exec()


if __name__ == '__main__':
    main()
