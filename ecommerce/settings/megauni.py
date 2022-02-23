from ecommerce.settings.production import *


# PAYMENT PROCESSING
PAYMENT_PROCESSORS = (
    "ecommerce.megauni.payment.vnpay.processor.VNPay",
)


# Add here custom payment processor urls. For instance:
# EXTRA_PAYMENT_PROCESSOR_URLS = {
#   "mycustompaymentprocessor": "ecommerce.payment.processors.mycustompaymentprocessor.urls"
# }
EXTRA_PAYMENT_PROCESSOR_URLS = {
    "vnpay": "ecommerce.megauni.payment.vnpay.urls",
}
# END URL CONFIGURATION
