"""Provides a StateMachine class, subclass and define transitions to use

class MyStateMachine(StateMachine):
    transitions = {
        "initial": {
            "success": "accepted",
            "fail": "denied"
        },
        "accepted": {"fail": "denied"}
    }

# To define callbacks for transitions use:

@MyStateMachine.handle(to_state="denied")
def send_failure_notice(state_machine, *args):
    'send mail to state_machine.owner'

state_machine = MyStateMachine()
state_machine.transition("fail") # sends an email
state_machine.transition("fail") # raises IllegalTransition


How to define Transitions:
    transitions = {
        <state>: {
            <symbol>: <state>
        }
    }

    <state>: <state_code> | <State instance>
    <state_code>: any Python object except None
        (must be a string if you subclass `StateMachineModel`)
    <State instance>: an instance of `State` -> a state code with additional information,
        such as a human readable label
        State(code, label=None, *, is_initial=None, is_terminal=None)
    <symbol>: any Python object

    if no states are explicitly marked as initial, we try to deduce them
    the state machine must have exactly one initial state
"""
from state_machine.helpers import classproperty

from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class IllegalTransition(Exception):
    pass


class ImproperlyConfigured(Exception):
    pass


class State:
    """State objects compare equal to their code

    this way we don't need users to always create State instances when doing anything
    with state_machine - they can use state_codes instead
    """
    def __init__(self, code, label=None, *, is_initial=None, is_terminal=None):
        self.code = code
        self.label = label
        self.is_initial = is_initial
        self.is_terminal = is_terminal

    def merge_data(self, other):
        if self != other:
            raise ValueError("trying to merge data of inequal states")

        for attr in ["label", "is_initial", "is_terminal"]:
            if getattr(self, attr) != getattr(other, attr) and getattr(other, attr) is not None:
                if getattr(self, attr) is None:
                    setattr(self, attr, getattr(other, attr))
                else:
                    raise ImproperlyConfigured(
                        "multiple states with same code and different {}".format(attr))

    def __eq__(self, other):
        if isinstance(other, State):
            return self.code == other.code
        else:
            return self.code == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.code)

    def __repr__(self):
        return "State({}, {})".format(repr(self.code), repr(self.label))

    def __str__(self):
        return "{} ({})".format(self.label, self.code)


class StateMachine:
    current_state_code = None

    ANY = object()
    # handlers need to be defined per class
    handlers = defaultdict(set)
    _states = None

    transitions = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.current_state_code is None:
            self.current_state = self.get_initial_state()

    def transition(self, symbol=None):
        """transition into the next state according to the given symbol

        raises IllegalTransition if that doesn't make sense

        returns the results of all registered handlers
        """
        try:
            next_state = self.get_next(symbol)
        except KeyError:
            raise IllegalTransition((self.current_state, symbol))
        if not self.allow_transition(self.current_state, symbol, next_state):
            raise IllegalTransition((self.current_state, symbol))
        current_state = self.current_state
        self.current_state = next_state
        self.save()
        return self.call_handlers(current_state, symbol, next_state)

    def allow_transition(self, from_state, symbol, next_state):
        return True

    def get_next(self, symbol):
        """given a symbol, return the next state

        if you subclass this class and change how to configure transitions, you'll
        probably want to override this
        """
        return self.transitions[self.current_state][symbol]

    @classproperty
    def states(cls):
        """get all states from cls.transitions configuration

        if a state appears multiple times, we merge their data
        If no initial or terminal states are defined, we try to deduce them

        raises `ImproperlyConfigured` if:
            there are multiple states with the same code but conflicting additional data,
            or there is not exactly 1 initial state,

        returns a Mapping of state_codes to State instances

        is cached per class

        if you subclass this class and change how to configure transitions, you'll
        probably want to override this
        This function should then still return a Mapping of state_codes to State
        instances, the instances need to have the maximum amount of data available.
        Particularly, initial and terminal states need to be marked.
        """
        if not cls._states:
            right_side = [
                val
                for _, transitions in cls.transitions.items()
                for val in transitions.values()
            ]
            states = right_side + list(cls.transitions.keys())
            cls._states = {}
            # gather most complete information available
            for state in states:
                if not isinstance(state, State):
                    state = State(state)
                if state.code not in cls._states:
                    cls._states[state.code] = state
                else:
                    cls._states[state.code].merge_data(state)

            # make sure initals and terminals are marked
            initials = [s for s in cls._states.values() if s.is_initial]
            terminals = [s for s in cls._states.values() if s.is_terminal]
            if len(initials) == 0:
                initials = cls.deduce_initial_states()
            if len(initials) != 1:
                raise ImproperlyConfigured(
                    "Must define exactly 1 initial state. Use "
                    "`State(code, is_initial=True)` "
                    "in transitions to explicitly mark a state as initial.")
            if len(terminals) == 0:
                terminals = cls.deduce_terminal_states()
            for state in initials:
                cls._states[state].is_initial = True
            for state in terminals:
                cls._states[state].is_terminal = True

        return cls._states

    @property
    def current_state(self):
        """self.current_state_code as a State instance"""
        try:
            return self.states[self.current_state_code]
        # TODO: we might not want to catch this
        except KeyError:
            return None

    @current_state.setter
    def current_state(self, state):
        self.current_state_code = self.states[state].code

    @classmethod
    def get_initial_state(cls):
        for state in cls.states.values():
            if state.is_initial:
                return state

    @classmethod
    def get_terminals(cls):
        terminals = []
        for state in cls.states.values():
            if state.is_terminal:
                terminals.append(state)
        return terminals

    @classmethod
    def deduce_initial_states(cls):
        """return states of cls.transitions that appear only on the left side of a transition"""
        right_side = {
            val
            for _, transitions in cls.transitions.items()
            for val in transitions.values()
        }
        return set(cls.transitions.keys()) - right_side

    @classmethod
    def deduce_terminal_states(cls):
        """return states of cls.transitions that appear only on the right side of a transition"""
        right_side = {
            val
            for _, transitions in cls.transitions.items()
            for val in transitions.values()
        }
        return right_side - set(cls.transitions.keys())

    def save(self, *args, **kwargs):
        if hasattr(super(), "save"):
            return super().save(*args, **kwargs)

    @classmethod
    def get_handlers(cls):
        """merge handlers defined on subclasses with those defined on superclasses"""
        if hasattr(super(), "get_handlers"):
            # NOTE: this might get weird if super() is not a state_machine, but happens
            # to define handlers...
            handlers = super().get_handlers().copy()
        else:
            handlers = {}
        handlers.update(cls.handlers)
        return handlers

    def call_handlers(self, from_state, symbol, to_state):
        """call handlers registered for the given combination of from_state, symbol, to_state

        returns a list of (handler, return value or exceptions) from called
        handlers
        a handler throwing an exception does not prevent others from running
        """
        args = from_state, symbol, to_state
        results = []
        for rule, handlers in self.get_handlers().items():
            matches = all(condition == arg or condition is StateMachine.ANY
                          for condition, arg
                          in zip(rule, args))
            if (matches):
                for handler in handlers:
                    try:
                        results.append((
                            handler,
                            handler(self, from_state, symbol, to_state)
                        ))
                    except Exception as e:
                        logger.error("error in state_machine transition callback")
                        logger.error(handler, e)
                        results.append((handler, e))
        return results

    @classmethod
    def handle(cls, from_state=ANY, symbol=ANY, to_state=ANY):
        """decorator to register callables that will be notified whenever a specific transition occurs

        define any combination of from_state, symbol, to_state
        to specify which transitions to get notified of
        """
        def decorator(fun):
            if "handlers" not in cls.__dict__:
                # create `handlers` on the current class
                # don't stuff all handlers into `StateMachine`'s dict
                cls.handlers = defaultdict(set)
            cls.handlers[(from_state, symbol, to_state)].add(fun)
            return fun
        return decorator
