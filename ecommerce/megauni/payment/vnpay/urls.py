

from django.conf import settings
from django.conf.urls import include, url

from ecommerce.megauni.payment.vnpay import views as vnpay


urlpatterns = [
    url(r'^ipn/$', vnpay.VNPayIPNView.as_view(), name='ipn'),
    url(r'^return/$', vnpay.VNPayReturnView.as_view(), name='return'),
]
