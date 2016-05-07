from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core import checks

from state_machine.state_machine import (
    StateMachine, ImproperlyConfigured)


class StateMachineModel(models.Model, StateMachine):
    """declare transitions, constraints and actions, saves current_state_code to DB

    saves the current_state_code as a CharField, which means state_codes need to
    be strings for this to work(!!)

    inherits most functionality from StateMachine,
    for further information on its configuration have a look in
    state_machine/state_machine.py
    """
    owner_type = models.ForeignKey(ContentType)
    owner_id = models.PositiveIntegerField()
    owner = GenericForeignKey('owner_type', 'owner_id')
    # CharField means current_state_code is always coerced to a string (or None)
    # allow null, because we want the inital value
    #   (=after creation, before initialization) to be None
    current_state_code = models.CharField(max_length=50, null=True)

    class Meta:
        abstract = True

    @classmethod
    def check(cls, **kwargs):
        errors = super().check(**kwargs)
        try:
            cls.states
        except ImproperlyConfigured as e:
            errors.append(
                checks.Error(
                    e.message,
                    hint=None,
                    obj=cls,
                    id='StateMachine.ImproperlyConfigured',
                )
            )
        return errors

    def __str__(self):
        return "{} - {}".format(self.owner, self.current_state)
