

from django.conf import settings
from django.conf.urls import include, url

from ecommerce.megauni.payment.vnpay import views as vnpay


VNPAY_URLS = [
    url(r'^ipn/$', vnpay.VNPayIPNView.as_view(), name='vnpay-ipn'),
    url(r'^return/$', vnpay.VNPayReturnView.as_view(), name='vnpay-return'),
]

urlpatterns = [
    url(r'^vnpay/', include((VNPAY_URLS, 'vnpay'))),
]
