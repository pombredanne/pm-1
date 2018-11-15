import collections
import contextlib
import functools
import io
import logging
import os
import pathlib

import attr
import graham
import pycparser.c_ast
import pycparser.c_generator
import PyQt5.QtCore
from PyQt5 import QtCore, QtGui, QtWidgets
import PyQt5.uic

import epyqlib.attrsmodel
import epyqlib.pm.parametermodel
import epyqlib.pm.valuesetmodel
import epyqlib.utils.qt

import epcpm.parameterstoc
import epcpm.project
import epcpm.canmodel
import epcpm.cantosym
import epcpm.symtoproject

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


@attr.s
class ModelView:
    view = attr.ib()
    # filename = attr.ib()
    types = attr.ib()
    extras = attr.ib(default=attr.Factory(collections.OrderedDict))
    model = attr.ib(default=None)
    proxy = attr.ib(default=None)
    selection = attr.ib(default=None)


class Window:
    def __init__(self, title, ui_file, icon_path):
        logging.debug('Working directory: {}'.format(os.getcwd()))
        logging.debug('Loading UI from: {}'.format(ui_file))

        self.ui = PyQt5.uic.loadUi(pathlib.Path(
            pathlib.Path(__file__).parents[0],
            ui_file,
        ))

        self.ui.action_new_project.triggered.connect(
            lambda _: self.open_project(),
        )
        self.ui.action_open_project.triggered.connect(
            lambda _: self.open_project_from_dialog(),
        )
        self.ui.action_save_project.triggered.connect(
            lambda _: self.save_project(),
        )
        self.ui.action_save_as_project.triggered.connect(
            lambda _: self.save_as_project(),
        )

        self.ui.action_new_value_set.triggered.connect(
            lambda _: self.new_value_set(),
        )
        self.ui.action_open_value_set.triggered.connect(
            lambda _: self.open_value_set_from_dialog(),
        )
        self.ui.action_save_value_set.triggered.connect(
            lambda _: self.save_value_set(),
        )
        self.ui.action_save_as_value_set.triggered.connect(
            lambda _: self.save_as_value_set(),
        )

        self.ui.action_import_sym.triggered.connect(self.import_sym)
        self.ui.action_export_sym.triggered.connect(self.generate_symbol_file)

        self.ui.action_about.triggered.connect(self.about_dialog)

        self.ui.setWindowTitle(title)

        logging.debug('Loading icon from: {}'.format(icon_path))
        self.ui.setWindowIcon(QtGui.QIcon(str(pathlib.Path(
            pathlib.Path(__file__).parents[0],
            icon_path,
        ))))

        self.project_filters = [
            ('Parameter Project', ['pmp']),
            ('All Files', ['*'])
        ]

        self.data_filters = [
            ('JSON', ['json']),
            ('All Files', ['*'])
        ]
        self.hierarchy_filters = self.data_filters

        self.can_filters = [
            ('CAN Symbols', ['sym']),
            ('All Files', ['*'])
        ]

        self.view_models = {}

        self.uuid_notifier = epcpm.canmodel.ReferencedUuidNotifier()
        self.uuid_notifier.changed.connect(self.can_uuid_changed)

        self.project = None
        self.value_set = None

        self.set_title()

    def set_title(self, detail=None):
        title = 'Parameter Manager v{}'.format(epcpm.__version__)

        if detail is not None:
            title = ' - '.join((title, detail))

        self.ui.setWindowTitle(title)

    def set_model(self, name, view_model):
        self.view_models[name] = view_model

        view_model.proxy = QtCore.QSortFilterProxyModel()
        view_model.proxy.setSortCaseSensitivity(QtCore.Qt.CaseInsensitive)
        view_model.proxy.setSourceModel(view_model.model.model)
        view_model.view.setModel(view_model.proxy)
        view_model.view.setItemDelegate(epyqlib.attrsmodel.create_delegate())

        view_model.selection = view_model.view.selectionModel()

        with contextlib.suppress(TypeError):
            view_model.selection.selectionChanged.disconnect()

        view_model.selection.selectionChanged.connect(
            self.selection_changed)

    def open_project_from_dialog(self):
        filename = epyqlib.utils.qt.file_dialog(
            self.project_filters,
            parent=self.ui,
        )

        if filename is None:
            return

        self.open_project(filename=filename)

    def import_sym(self):
        sym_path = epyqlib.utils.qt.file_dialog(
            filters=self.can_filters,
            parent=self.ui,
        )

        if sym_path is None:
            return

        hierarchy_path = epyqlib.utils.qt.file_dialog(
            filters=self.hierarchy_filters,
            parent=self.ui,
            caption='Open Parameter Hierarchy',
        )

        if hierarchy_path is None:
            return

        with open(sym_path, 'rb') as sym, open(hierarchy_path) as hierarchy:
            parameters_root, can_root = epcpm.symtoproject.load_can_file(
                can_file=sym,
                file_type=str(pathlib.Path(sym.name).suffix[1:]),
                parameter_hierarchy_file=hierarchy,
                add_tables=True,
            )

        project = epcpm.project.Project()

        project.models.parameters = epyqlib.attrsmodel.Model(
            root=parameters_root,
            columns=epyqlib.pm.parametermodel.columns,
        )
        project.models.can = epyqlib.attrsmodel.Model(
            root=can_root,
            columns=epcpm.canmodel.columns,
        )

        epcpm.project._post_load(project)

        self.open_project(project=project)

    def open_project(self, filename=None, project=None):
        if project is not None:
            self.project = project
        else:
            if filename is None:
                self.project = epcpm.project.create_blank()
            else:
                self.project = epcpm.project.loadp(filename)

        model_views = epcpm.project.Models()

        model_views.parameters = ModelView(
            view=self.ui.parameter_view,
            types=epyqlib.pm.parametermodel.types,
            extras=collections.OrderedDict((
                ('Generate code...', self.generate_code),
            )),
        )

        model_views.can = ModelView(
            view=self.ui.can_view,
            types=epcpm.canmodel.types,
        )

        self.uuid_notifier.disconnect_view()

        i = zip(model_views.items(), self.project.models.values())
        for (name, model_view), model in i:
            view = model_view.view

            view.setSelectionBehavior(view.SelectRows)
            view.setSelectionMode(view.SingleSelection)
            view.setDropIndicatorShown(True)
            view.setDragEnabled(True)
            view.setAcceptDrops(True)

            if model is None:
                model_view.model = epyqlib.attrsmodel.Model(
                    root=model_view.root_factory(),
                    columns=model_view.columns,
                )
            else:
                model_view.model = model

            model.update_nodes()

            self.set_model(name=name, view_model=model_view)
            view.collapseAll()
            column_count = (
                model_view.model.model.columnCount(QtCore.QModelIndex())
            )
            for i in range(column_count):
                view.resizeColumnToContents(i)

            view.setContextMenuPolicy(
                QtCore.Qt.CustomContextMenu)
            m = functools.partial(
                self.context_menu,
                view_model=model_view
            )

            with contextlib.suppress(TypeError):
                view.customContextMenuRequested.disconnect()

            view.customContextMenuRequested.connect(m)

        self.uuid_notifier.set_view(self.ui.can_view)

        return

    def save_project(self):
        self.project.save(parent=self.ui)

    def save_as_project(self):
        project = attr.evolve(self.project)
        project.filename = None
        # TODO: this is still going to mutate the same object as the
        #       original project is referencing
        project.paths.set_all(None)

        project.save(parent=self.ui)
        self.project = project

    def new_value_set(self):
        parameters = self.view_models.get('parameters')
        if parameters is not None:
            parameters = parameters.model

        value_set = epyqlib.pm.valuesetmodel.create_blank(
            parameter_model=parameters,
        )

        human_names = QtWidgets.QMessageBox.question(
            self.ui,
            'Humanized Names',
            'Use humanized names in new value set?',
            buttons=(
                QtWidgets.QMessageBox.Yes
                | QtWidgets.QMessageBox.No
            ),
            defaultButton=QtWidgets.QMessageBox.Yes,
        ) == QtWidgets.QMessageBox.Yes

        only_parameters = QtWidgets.QMessageBox.question(
            self.ui,
            'Only Parameters',
            'Only include parameters group in new value set?',
            buttons=(
                QtWidgets.QMessageBox.Yes
                | QtWidgets.QMessageBox.No
            ),
            defaultButton=QtWidgets.QMessageBox.No,
        ) == QtWidgets.QMessageBox.Yes

        calculate_unspecified_min_max = QtWidgets.QMessageBox.question(
            self.ui,
            'Calculate Unspecified',
            (
                'Calculate unspecified minimum And maximum values from '
                'symbol ranges?'
            ),
            buttons=(
                QtWidgets.QMessageBox.Yes
                | QtWidgets.QMessageBox.No
            ),
            defaultButton=QtWidgets.QMessageBox.No,
        ) == QtWidgets.QMessageBox.Yes

        base_node = None
        if only_parameters:
            base_node, = [
                node
                for node in value_set.parameter_model.root.children
                if node.name == 'Parameters'
            ]

        epyqlib.pm.valuesetmodel.copy_parameter_data(
            value_set=value_set,
            human_names=human_names,
            base_node=base_node,
            calculate_unspecified_min_max=calculate_unspecified_min_max,
            can_root=self.view_models.get('can').model.root,
        )

        self.set_active_value_set(value_set)

    def set_active_value_set(self, value_set):
        self.value_set = value_set

        view = self.ui.value_set_view
        model = self.value_set.model

        model_view = ModelView(
            view=view,
            model=model,
            types=epyqlib.pm.valuesetmodel.types,
        )

        view.setSelectionBehavior(view.SelectRows)
        view.setSelectionMode(view.SingleSelection)
        view.setDropIndicatorShown(True)
        view.setDragEnabled(True)
        view.setAcceptDrops(True)

        self.set_model(name='value_set', view_model=model_view)
        view.expandAll()

    def open_value_set_from_dialog(self):
        path = epyqlib.utils.qt.file_dialog(
            attr.fields(epyqlib.pm.valuesetmodel.ValueSet).filters.default,
            parent=self.ui,
        )

        if path is None:
            return

        value_set = epyqlib.pm.valuesetmodel.loadp(path)

        self.set_active_value_set(value_set)

    def save_value_set(self):
        self.value_set.save(parent=self.ui)

    def save_as_value_set(self):
        value_set = attr.evolve(self.value_set)
        value_set.path = None

        value_set.save(parent=self.ui)
        self.value_set = value_set

    def context_menu(self, position, view_model):
        view = view_model.view
        view_index = view.indexAt(position)
        index_is_valid = view_index.isValid()
        index = view.model().mapToSource(view_index)

        model = view_model.model
        node = model.node_from_index(index)

        menu = QtWidgets.QMenu(parent=view)

        addable_types = node.addable_types()
        actions = {
            menu.addAction('Add {}'.format(name)): t
            for name, t in addable_types.items()
        }
        if len(actions) == 0:
            no_addable_child_types = menu.addAction('No addable child types')
            no_addable_child_types.setDisabled(True)

        menu.addSeparator()

        delete = menu.addAction('Delete')
        delete.setEnabled(node.can_delete())

        update = menu.addAction('Update')
        update.setEnabled(hasattr(node, 'update'))

        menu.addSeparator()

        extra_actions = {
            menu.addAction(name): function
            for name, function in view_model.extras.items()
        }

        if len(extra_actions) > 0:
            menu.addSeparator()

        expand_tree = menu.addAction('Expand Tree')
        expand_tree.setEnabled(index_is_valid)
        expand_all = menu.addAction('Expand All')
        menu.addSeparator()
        collapse_tree = menu.addAction('Collapse Tree')
        collapse_tree.setEnabled(index_is_valid)
        collapse_all = menu.addAction('Collapse All')

        action = menu.exec(
            view.viewport().mapToGlobal(position)
        )

        if action is not None:
            extra = extra_actions.get(action)
            if extra is not None:
                extra(node)
            elif action is delete:
                node.tree_parent.remove_child(child=node)
            elif action is update:
                node.update()
            elif action is expand_tree:
                epyqlib.utils.qt.set_expanded_tree(
                    view=view,
                    index=view_index,
                    expanded=True,
                )
            elif action is expand_all:
                view.expandAll()
            elif action is collapse_tree:
                epyqlib.utils.qt.set_expanded_tree(
                    view=view,
                    index=view_index,
                    expanded=False,
                )
            elif action is collapse_all:
                view.collapseAll()
            else:
                new_node = actions[action]()
                node.append_child(new_node)
                new_index = model.index_from_node(new_node)
                view_index = epyqlib.utils.qt.resolve_index_from_model(
                    model=model.model,
                    view=view,
                    index=new_index,
                )
                view.setCurrentIndex(view_index)

    def generate_code(self, node):
        builder = epcpm.parameterstoc.builders.wrap(node)
        ast = pycparser.c_ast.FileAST(builder.definition())
        generator = pycparser.c_generator.CGenerator()
        s = generator.visit(ast)
        epyqlib.utils.qt.dialog(
            parent=self.ui,
            message=s,
            modal=False,
        )

    def generate_symbol_file(self):
        finder = self.view_models['can'].model.node_from_uuid
        access_levels, = self.project.models.parameters.root.nodes_by_filter(
            filter=(
                lambda node: isinstance(
                    node,
                    epyqlib.pm.parametermodel.AccessLevels
                )
            ),
        )
        builder = epcpm.cantosym.builders.wrap(
            wrapped=self.view_models['can'].model.root,
            access_levels=access_levels,
            parameter_uuid_finder=finder,
            parameter_model=self.view_models['parameters'].model,
        )

        epyqlib.utils.qt.dialog(
            parent=self.ui,
            message=builder.gen(),
            modal=False,
            save_filters=(
                ('CAN Symbols', ['sym']),
                ('All Files', ['*'])
            ),
            save_caption='Save CAN Symbols',
        )

    def selection_changed(self, selected, deselected):
        pass

    def can_uuid_changed(self, uuid):
        view_model = self.view_models['parameters']
        model = view_model.model
        view = view_model.view

        try:
            node = model.node_from_uuid(uuid)
        except epyqlib.attrsmodel.NotFoundError:
            return

        index = model.index_from_node(node)
        index = epyqlib.utils.qt.resolve_index_from_model(
            model=model.model,
            view=view,
            index=index,
        )

        view.setCurrentIndex(index)
        view.selectionModel().select(
            index,
            QtCore.QItemSelectionModel.ClearAndSelect,
        )

    def about_dialog(self):
        message = [
            __copyright__,
            __license__,
            f'Version Tag: {epcpm.__version_tag__}',
            f'Commit SHA: {epcpm.__sha__}',
            f'Build Tag: {epcpm.__build_tag__}',
        ]

        message = '\n'.join(message)

        epyqlib.utils.qt.dialog(
            parent=self.ui,
            title='About',
            message=message,
        )
