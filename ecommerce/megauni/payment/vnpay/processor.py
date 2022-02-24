""" VNPay payment processing. """


import logging
from decimal import Decimal
from datetime import datetime
from urllib.parse import urljoin

from django.utils.translation import get_language
from django.urls import reverse
from ecommerce.extensions.checkout.mixins import Order
from ecommerce.extensions.payment.exceptions import ExcessivePaymentForOrderError, InvalidSignatureError, RedundantPaymentNotificationError
from oscar.core.loading import get_model

from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse
from ecommerce.extensions.payment.utils import get_basket_program_uuid

from ecommerce.megauni.payment.exceptions import InvalidAmountError
from ecommerce.megauni.payment.vnpay.client import vnpay

logger = logging.getLogger(__name__)


PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class VNPay(BasePaymentProcessor):

    NAME = 'vnpay'
    TITLE = 'VNPay'

    @property
    def cancel_url(self):
        return get_ecommerce_url(self.configuration['cancel_checkout_path'])

    @property
    def error_url(self):
        return get_ecommerce_url(self.configuration['error_path'])

    def __init__(self, site):
        super(VNPay, self).__init__(site)

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        """ Get the transaction parameters for the processor. """
        order_type = 'program'
        order_id = basket.order_number
        amount = basket.total_incl_tax * 100
        currency = basket.currency
        order_desc = "program_id:{}".format(get_basket_program_uuid(basket))
        bank_code = None
        language = get_language()
        ipaddr = get_client_ip(request)

        # Build URL Payment
        vnp = vnpay()
        vnp.requestData['vnp_Version'] = self.configuration['version']
        vnp.requestData['vnp_Command'] = 'pay'
        vnp.requestData['vnp_TmnCode'] = self.configuration['tmn_code']
        vnp.requestData['vnp_Amount'] = amount.to_integral_exact()
        vnp.requestData['vnp_CurrCode'] = currency
        vnp.requestData['vnp_TxnRef'] = order_id
        vnp.requestData['vnp_OrderInfo'] = order_desc
        vnp.requestData['vnp_OrderType'] = order_type

        # Check language, default: vn
        if language and language != '':
            vnp.requestData['vnp_Locale'] = language
        else:
            vnp.requestData['vnp_Locale'] = 'vn'
        
        # Check bank_code, if bank_code is empty, customer will be selected bank on VNPAY
        if bank_code and bank_code != "":
            vnp.requestData['vnp_BankCode'] = bank_code

        vnp.requestData['vnp_CreateDate'] = datetime.now().strftime('%Y%m%d%H%M%S')  # 20150410063022
        vnp.requestData['vnp_IpAddr'] = ipaddr
        vnp.requestData['vnp_ReturnUrl'] = urljoin(get_ecommerce_url(), reverse('vnpay:return'))

        vnpay_payment_url = vnp.get_payment_url(self.configuration['payment_url'], self.configuration['hash_secret_key'])
        
        parameters = {
            'payment_page_url': vnpay_payment_url,
        }

        return parameters

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        raise NotImplementedError

    def handle_processor_response(self, response, basket=None):
        vnp = vnpay()
        vnp.responseData = response

        if not vnp.validate_response(self.configuration['hash_secret_key']):
            raise InvalidSignatureError

        order_number = response.get('vnp_TxnRef')
        transaction_id = response.get('vnp_TransactionNo')
        total = Decimal(response.get('vnp_Amount')) / 100
        currency = 'VND' # response.get('vnp_CurrCode')
        card_type = response.get('vnp_CardType')

        label = 'VNPay (%s)' % card_type
        
        if basket is not None and basket.total_incl_tax != total:
            raise InvalidAmountError

        if Order.objects.filter(number=order_number).exists():
            if PaymentProcessorResponse.objects.filter(processor_name=self.NAME, transaction_id=transaction_id).exists():
                raise RedundantPaymentNotificationError
            raise ExcessivePaymentForOrderError

        self.record_processor_response(response, transaction_id=transaction_id, basket=basket)

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=label,
            card_type=card_type,
        )
