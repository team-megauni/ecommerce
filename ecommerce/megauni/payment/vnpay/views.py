""" Views for interacting with the payment processor. """


import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http.response import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import View
from ecommerce.extensions.payment.exceptions import ExcessivePaymentForOrderError, InvalidSignatureError, RedundantPaymentNotificationError
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import PaymentError
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url

from ecommerce.megauni.payment.vnpay import processor as VNPay  

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class VNPayIPNView(EdxOrderPlacementMixin, View):

    @property
    def payment_processor(self):
        return VNPay(self.request.site)

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super(VNPayIPNView, self).dispatch(request, *args, **kwargs)

    def _get_basket(self, order_number):
        try:
            basket_id = OrderNumberGenerator().basket_id(order_number)
            basket = Basket.open.get(id=basket_id)

            basket.strategy = strategy.Default()

            Applicator().apply(basket, basket.owner, self.request)

            basket_add_organization_attribute(basket, self.request.GET)
            return basket
        except ObjectDoesNotExist:
            logger.warning(u"Basket with ID [%s] not found.", basket_id)
            return None
        except Exception:
            logger.exception(u"Unexpected error during basket retrieval while executing VNPay payment.")
            return None

    def get(self, request):
        payment_response = request.GET.dict()
        order_number = payment_response.get('vnp_TxnRef')

        basket = self._get_basket(order_number)

        if not basket:
            return JsonResponse({'RspCode': '01', 'Message': u"Basket not found"})

        try:
            with transaction.atomic():
                try:
                    self.handle_payment(payment_response, basket)
                except InvalidSignatureError:
                    return JsonResponse({'RspCode': '97', 'Message': u"Invalid signature"})
                except RedundantPaymentNotificationError:
                    return JsonResponse({'RspCode': '02', 'Message': u"Order Already Update"})
                except ExcessivePaymentForOrderError:
                    return JsonResponse({'RspCode': '99', 'Message': u"Invalid request"})
                except PaymentError:
                    return JsonResponse({'RspCode': '99', 'Message': u"Invalid request"})
        except:  # pylint: disable=bare-except
            logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
            return JsonResponse({'RspCode': '99', 'Message': u"System error"})
        
        try:
            order = self.create_order(request, basket)
        except Exception:  # pylint: disable=broad-except
            # any errors here will be logged in the create_order method. If we wanted any
            # Paypal specific logging for this error, we would do that here.
            return JsonResponse({'RspCode': '99', 'Message': u"System error"})
        
        try:
            self.handle_post_order(order)
        except Exception:  # pylint: disable=broad-except
            self.log_order_placement_exception(basket.order_number, basket.id)

        return JsonResponse({'RspCode': '00', 'Message': u"Confirm Success"})


class VNPayReturnView(EdxOrderPlacementMixin, View):

    @property
    def payment_processor(self):
        return VNPay(self.request.site)

    def get(self, request):
        payment_response = request.GET.dict()
        order_number = payment_response.get('vnp_TxnRef')

        basket_id = OrderNumberGenerator().basket_id(order_number)
        basket = Basket.submitted.get(id=basket_id)

        if not basket:
            return redirect(self.payment_processor.error_url)

        receipt_url = get_receipt_page_url(
            order_number=basket.order_number,
            site_configuration=basket.site.siteconfiguration,
            disable_back_button=True,
        )

        return redirect(receipt_url)
