import json

import epyqlib.abstractcolumns
import epyqlib.pyqabstractitemmodel
import epyqlib.treenode

import pm.parameters

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


class Columns(epyqlib.abstractcolumns.AbstractColumns):
    _members = ['name']

Columns.indexes = Columns.indexes()


class Parameter(epyqlib.treenode.TreeNode):
    def __init__(self, parameter, parent=None):
        super().__init__(parent=parent)

        self.fields = Columns()

        self._parameter = None
        self.parameter = parameter

    @property
    def parameter(self):
        return self._parameter

    @parameter.setter
    def parameter(self, parameter):
        self._parameter = parameter

        self.fields.name = self.parameter.name


class Group(epyqlib.treenode.TreeNode):
    def __init__(self, group, parent=None):
        super().__init__(parent=parent)

        self.fields = Columns()

        self._group = None
        self.group = group

    @property
    def group(self):
        return self._group

    @group.setter
    def group(self, group):
        self._group = group

        self.fields.name = self.group.name


class Decoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        obj_type = obj.get('type', None)

        if isinstance(obj, list):
            return obj

        elif obj_type == 'parameter':
            obj.pop('type')
            parameter = pm.parameters.Parameter(**obj)
            return Parameter(parameter=parameter)

        elif obj_type == 'group':
            obj.pop('type')
            children = obj.pop('children')
            group = pm.parameters.Group(**obj)
            node = Group(group=group)

            for child in children:
                node.append_child(child)

            return node

        raise Exception('Unexpected object found: {}'.format(obj))


class Model(epyqlib.pyqabstractitemmodel.PyQAbstractItemModel):
    def __init__(self, root=None, parent=None):
        if root is None:
            root = pm.parameters.Group(name='root')
            root = Group(group=root)

        super().__init__(root=root, parent=parent)

        self.headers = Columns(
            name='Name'
        )

    @classmethod
    def from_json_string(cls, s):
        root = pm.parameters.Group(name='root')
        root = Group(group=root)

        children = json.loads(s, cls=Decoder)
        for child in children:
            root.append_child(child)

        return cls(root=root)
