#!/usr/bin/env python3
# vim: set ts=4 sw=4 et sts=4 ai:

def _check_state(fsm, current_state, state_str):
    if not hasattr(fsm, "_rencoding"):
        fsm._rencoding = {}
        for s, n in fsm.encoding.items():
            fsm._rencoding[n] = s

    if current_state == fsm.encoding[state_str]:
        return True, ""
    else:
        return False, """\
FSM was in state {} not {}
""".format(fsm._rencoding[current_state], state_str)


class CheckFailure(Exception):
    pass


def check_state(fsm, state_str):
    """Check if the FSM is in a given state.
    
    >>> if (yield check_state(fsm, "START")):
    ...    print("Yay!")
    >>> 
    """
    c, msg = _check_state(fsm, (yield fsm.state), state_str)
    if not c:
        raise CheckFailure(msg)


def assert_state(fsm, state_str):
    """Assert the FSM is in a given state.
    
    >>> yield from assert_state(fsm, "START"))
    Traceback (most recent call last):
        ...
    AssertionError: FSM was in state DETECT_SDA not DETECT_SCL
    >>> 
    """
    c, msg = _check_state(fsm, (yield fsm.state), state_str)
    assert c, msg
