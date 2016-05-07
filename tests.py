from django.test import TestCase
from django.contrib.auth import get_user_model

from django_fake_model import models as f

from state_machine.models import StateMachineModel
from state_machine.state_machine import State, ImproperlyConfigured, IllegalTransition, StateMachine


class CallableCalled(Exception):
    pass


class TestStateMachine(f.FakeModel, StateMachineModel):

    transitions = {
        # really fucking bad config to try all edge cases
        State(0, "initial"): {"success": State(1, "label1"), "fail": 2},
        1: {None: 2}
    }


class TestStateMachine2(f.FakeModel, StateMachineModel):

    transitions = {
        State(0, "initial"): {"success": 1}
    }


@TestStateMachine.fake_me
@TestStateMachine2.fake_me
class StateMachineTest(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create(email="test_user@localhost")

    def test_configuration_check(self):
        class TestStateMachineWrongConfig(StateMachineModel):
            pass

        with self.assertRaises(ImproperlyConfigured):
            TestStateMachineWrongConfig.get_initial_state()

        self.assertTrue(TestStateMachine.get_initial_state() == 0)

    def test_states(self):
        """states should be equal to their codes"""
        self.assertEqual(State(0), 0)
        self.assertEqual(0, State(0))
        self.assertEqual(State("moo", "this is a moo"), "moo")

        config = {
            State(0): 1,
            State(1): 2,
            State(2): State(3),
        }
        self.assertEqual(config[0], 1)
        self.assertEqual(
            set(config.keys()) - set(config.values()),
            {0}
        )

    def test_statemachine(self):
        self.assertEqual(TestStateMachine.get_initial_state(), 0)
        self.assertEqual(TestStateMachine.get_terminals(), [2])

        state_machine = TestStateMachine.objects.create(owner=self.user)
        self.assertEqual(state_machine.current_state, 0)
        state_machine.transition("success")
        self.assertEqual(state_machine.current_state, 1)
        self.assertEqual(state_machine.current_state.label, "label1")

        with self.assertRaises(IllegalTransition):
            state_machine.transition("success")

    def test_handlers(self):

        called = 0

        @TestStateMachine.handle(from_state=0)
        def handler(state_machine, *args):
            nonlocal called
            called = called + 1

        self.assertFalse(called)
        state_machine = TestStateMachine.objects.create(owner=self.user)
        state_machine.transition("success")
        self.assertEqual(called, 1)

        # does not call the handler
        state_machine.transition(None)
        self.assertEqual(called, 1)

        other_state_machine = TestStateMachine2.objects.create(owner=self.user)
        other_state_machine.transition("success")
        # other classes do not call the handlers
        self.assertEqual(called, 1)

    def test_subclassing(self):

        class SMSuper(StateMachine):
            transitions = {
                State(0, "initial"): {"success": 1}
            }

        class SMSub(SMSuper):
            pass

        called = 0

        @SMSuper.handle(from_state=0)
        def handler(state_machine, *args):
            nonlocal called
            called = called + 1

        self.assertFalse(called)
        state_machine_super = SMSuper()
        state_machine_super.transition("success")
        self.assertEqual(called, 1)
        state_machine_sub = SMSub()
        state_machine_sub.transition("success")
        self.assertEqual(called, 2)
