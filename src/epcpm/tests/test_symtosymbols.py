import decimal
import io
import json
import textwrap

import pytest

import epyqlib.tests.common

import epcpm.symbolmodel
import epcpm.symtoproject


@pytest.fixture
def sym_file():
    return io.BytesIO(textwrap.dedent('''\
    FormatVersion=5.0 // Do not edit this line!
    Title="canmatrix-Export"
    
    {SEND}
    
    [ParameterQuery]
    ID=1DEFF741h
    Type=Extended
    DLC=8
    Mux=TestMux 0,14 0 
    Var=TestParam unsigned 14,2 /f:0.01  /min:0.01  /max:0.2 /p:2 /d:0.02
    
    {SENDRECEIVE}
    
    [ParameterResponse]
    ID=1DEF41F7h
    Type=Extended
    DLC=8
    Mux=TestMux 0,14 0 
    Var=TestParam unsigned 14,2 /f:0.01  /min:0.01  /max:0.2 /p:2 /d:0.02
    ''').encode('utf-8'))


@pytest.fixture
def hierarchy_file():
    return io.StringIO(json.dumps({
        'children': [
            {
                'name': 'Test Group',
                'children': [
                    [
                        "TestMux",
                        "TestParam"
                    ]
                ]
            }
        ]
    }))


@pytest.fixture
def empty_hierarchy_file():
    return io.StringIO('{"children": []}')


def test_load_can_file():
    parameter_root, symbol_root = epcpm.symtoproject.load_can_path(
        epyqlib.tests.common.symbol_files['customer'],
        epyqlib.tests.common.hierarchy_files['customer'],
    )

    assert isinstance(parameter_root, epcpm.parametermodel.Root)
    assert isinstance(symbol_root, epcpm.symbolmodel.Root)


def test_only_one_parameter_per_query_response_pair(
        sym_file,
        empty_hierarchy_file,
):
    parameter_root, symbol_root = epcpm.symtoproject.load_can_file(
        can_file=sym_file,
        file_type='sym',
        parameter_hierarchy_file=empty_hierarchy_file,
    )

    parameters = next(
        node
        for node in parameter_root.children
        if node.name == 'Parameters'
    )

    assert len(parameters.children[0].children) == 1


def test_accurate_decimal(sym_file, hierarchy_file):
    parameter_root, symbol_root = epcpm.symtoproject.load_can_file(
        can_file=sym_file,
        file_type='sym',
        parameter_hierarchy_file=hierarchy_file,
    )

    parameters = next(
        node
        for node in parameter_root.children
        if node.name == 'Parameters'
    )

    test_group = next(
        node
        for node in parameters.children
        if node.name == 'Test Group'
    )

    test_parameter = next(
        node
        for node in test_group.children
        if node.name.endswith('Test Param')
    )

    # TODO: default is probably in wrong scaling
    # assert isinstance(test_parameter.default, decimal.Decimal)
    # assert test_parameter.default == decimal.Decimal('0.02')

    assert isinstance(test_parameter.minimum, decimal.Decimal)
    assert test_parameter.minimum == decimal.Decimal('0.01')
