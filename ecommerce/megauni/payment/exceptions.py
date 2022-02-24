"""Exceptions and error messages used by payment processors."""


from django.utils.translation import ugettext_lazy as _
from oscar.apps.payment.exceptions import GatewayError


class InvalidAmountError(GatewayError):
    """The amount of the payment processor's response is invalid."""
