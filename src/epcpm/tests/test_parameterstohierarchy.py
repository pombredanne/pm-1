import epyqlib.pm.parametermodel

import epcpm.parameterstohierarchy
import epcpm.canmodel


def test_():
    parameter_root = epyqlib.pm.parametermodel.Root()

    parameters = epyqlib.pm.parametermodel.Group(name='Parameters')
    parameter_root.append_child(parameters)

    group = epyqlib.pm.parametermodel.Group(name='Group A')
    parameters.append_child(group)

    parameter_aa = epyqlib.pm.parametermodel.Parameter(name='Parameter AA')
    group.append_child(parameter_aa)
    parameter_ab = epyqlib.pm.parametermodel.Parameter(name='Parameter AB')
    group.append_child(parameter_ab)

    parameter_a = epyqlib.pm.parametermodel.Parameter(name='Parameter A')
    parameters.append_child(parameter_a)

    can_root = epcpm.canmodel.Root()

    multiplexed_message = epcpm.canmodel.MultiplexedMessage()
    can_root.append_child(multiplexed_message)

    multiplexer_a = epcpm.canmodel.Multiplexer(name='Multiplexer A')
    multiplexed_message.append_child(multiplexer_a)

    signal_aa = epcpm.canmodel.Signal(
        name='Signal PAA',
        parameter_uuid=parameter_aa.uuid,
    )
    multiplexer_a.append_child(signal_aa)

    multiplexer_b = epcpm.canmodel.Multiplexer(name='Multiplexer B')
    multiplexed_message.append_child(multiplexer_b)

    signal_ab = epcpm.canmodel.Signal(
        name='Signal PAB',
        parameter_uuid=parameter_ab.uuid,
    )
    multiplexer_b.append_child(signal_ab)

    signal_a = epcpm.canmodel.Signal(
        name='Signal PA',
        parameter_uuid=parameter_a.uuid,
    )
    multiplexer_b.append_child(signal_a)

    expected = {
        'children': [
            {
                'name': 'Group A',
                'children': [
                    [
                        'MultiplexerA',
                        'SignalPAA',
                    ],
                    [
                        'MultiplexerB',
                        'SignalPAB',
                    ],
                ]
            },
            [
                'MultiplexerB',
                'SignalPA',
            ],
        ]
    }

    builder = epcpm.parameterstohierarchy.builders.wrap(
        wrapped=parameter_root,
        can_root=can_root,
    )

    assert builder.gen(json_output=False) == expected