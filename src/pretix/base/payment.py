from collections import OrderedDict
from decimal import Decimal
from django import forms

from django.forms import Form
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _
from pretix.base.forms import SettingsForm
from pretix.base.models import Order

from pretix.base.settings import SettingsSandbox


class BasePaymentProvider:
    """
    This is the base class for all payment providers.
    """

    def __init__(self, event):
        self.event = event
        self.settings = SettingsSandbox('payment', self.identifier, event)

    def __str__(self):
        return self.identifier

    @property
    def is_enabled(self) -> bool:
        """
        Returns, whether or whether not this payment provider is enabled.
        By default, this is determined by the value of the ``_enabled`` setting.
        """
        return self.settings.get('_enabled', as_type=bool)

    def calculate_fee(self, price: Decimal) -> Decimal:
        """
        Calculate the fee for this payment provider which will be added to
        final price before fees (but after taxes). It should include any taxes.
        The default implementation makes use of the setting ``_fee_abs`` for an
        absolute fee and ``_fee_percent`` for a percentage.

        :param price: The total value without the payment method fee, after taxes.
        """
        fee_abs = self.settings.get('_fee_abs', as_type=Decimal, default=0)
        fee_percent = self.settings.get('_fee_percent', as_type=Decimal, default=0)
        return Decimal(price * fee_percent / 100 + fee_abs)

    @property
    def verbose_name(self) -> str:
        """
        A human-readable name for this payment provider. This should
        be short but self-explaining. Good examples include 'Bank transfer'
        and 'Credit card via Stripe'.
        """
        raise NotImplementedError()  # NOQA

    @property
    def identifier(self) -> str:
        """
        A short and unique identifier for this payment provider.
        This should only contain lowercase letters and in most
        cases will be the same as your packagename.
        """
        raise NotImplementedError()  # NOQA

    @property
    def settings_form_fields(self) -> dict:
        """
        When the event's administrator administrator visits the event configuration
        page, this method is called to return the configuration fields available.

        It should therefore return a dictionary where the keys should be (unprefixed)
        settings keys and the values should be corresponding Django form fields.

        The default implementation returns the appropriate fields for the ``_enabled``,
        ``_fee_abs`` and ``_fee_percent`` settings mentioned above.

        We suggest that you return an ``OrderedDict`` object instead of a dictionary
        and make use of the default implementation. Your implementation could look
        like this::

            @property
            def settings_form_fields(self):
                return OrderedDict(
                    list(super().settings_form_fields.items()) + [
                        ('bank_details',
                         forms.CharField(
                             widget=forms.Textarea,
                             label=_('Bank account details'),
                             required=False
                         ))
                    ]
                )
        """
        return OrderedDict([
            ('_enabled',
             forms.ChoiceField(
                 label=_('Enable payment method'),
                 required=False,
                 choices=SettingsForm.BOOL_CHOICES,
             )),
            ('_fee_abs',
             forms.DecimalField(
                 label=_('Additional fee'),
                 help_text=_('Absolute value'),
                 required=False
             )),
            ('_fee_percent',
             forms.DecimalField(
                 label=_('Additional fee'),
                 help_text=_('Percentage'),
                 required=False
             )),
        ])

    @property
    def checkout_form_fields(self) -> dict:
        """
        This is used by the default implementation of :py:meth:`checkout_form`.
        It should return an object similar to :py:attr:`settings_form_fields`.

        The default implementation returns an empty dictionary.
        """
        return {}

    def checkout_form(self, request: HttpRequest) -> Form:
        """
        This is called by the default implementation of :py:meth:`checkout_form_render`
        to obtain the form that is displayed to the user during the checkout
        process. The default implementation constructs the form using
        :py:attr:`checkout_form_fields` and sets appropriate prefixes for the form
        and all fields and fills the form with data form the user's session.
        """
        form = Form(
            data=(request.POST if request.method == 'POST' else None),
            prefix='payment_%s' % self.identifier,
            initial={
                k.replace('payment_%s_' % self.identifier, ''): v
                for k, v in request.session.items()
                if k.startswith('payment_%s_' % self.identifier)
            }
        )
        form.fields = self.checkout_form_fields
        return form

    def checkout_form_render(self, request: HttpRequest) -> str:
        """
        When the user selects this provider as his prefered payment method,
        he will be shown the HTML you return from this method.

        The default implementation will call :py:meth:`checkout_form`
        and render the returned form. If your payment method doesn't require
        the user to fill out form fields, you should just return a paragraph
        of explainatory text.
        """
        form = self.checkout_form(request)
        template = get_template('pretixpresale/event/checkout_payment_form_default.html')
        ctx = {'request': request, 'form': form}
        return template.render(ctx)

    def checkout_confirm_render(self, request) -> str:
        """
        If the user successfully filled in his payment data, he will be redirected
        to a confirmation page which lists all details of his order for a final review.
        This method should return the HTML which should be displayed inside the
        'Payment' box on this page.

        In most cases, this should include a short summary of the user's input and
        a short explaination on how the payment process will continue.
        """
        raise NotImplementedError()  # NOQA

    def checkout_prepare(self, request: HttpRequest, cart: dict) -> "bool|str":
        """
        Will be called after the user selected this provider as his payment method.
        If you provided a form to the user to enter payment data, this method should
        at least store the user's input into his session.

        This method should return ``False``, if the user's input was invalid, ``True``
        if the input was valid and the frontend should continue with default behaviour
        or a string containing an URL, if the user should be redirected somewhere else.

        On errors, you should use Django's message framework to display an error message
        to the user (or the normal form validation error messages).

        The default implementation stores the input into the form returned by
        :py:meth:`checkout_form` in the user's session.

        If your payment method requires you to redirect the user to an external provider,
        this might be the place to do so.

        .. IMPORTANT:: If this is called, the user has not yet confirmed his or her order.
           You may NOT do anything which actually moves money.

        :param cart: This dictionary contains at least the following keys:

            positions:
               A list of ``CartPosition`` objects that are annotated with the special
               attributes ``count`` and ``total`` because multiple objects of the
               same content are grouped into one.

            raw:
                The raw list of ``CartPosition`` objects in the users cart

            total:
                The overall total *including* the fee for the payment method.

            payment_fee:
                The fee for the payment method.
        """
        form = self.checkout_form(request)
        if form.is_valid():
            for k, v in form.cleaned_data.items():
                request.session['payment_%s_%s' % (self.identifier, k)] = v
            return True
        else:
            return False

    def checkout_is_valid_session(self, request: HttpRequest) -> bool:
        """
        This is called at the time the user tries to place the order. It should return
        ``True``, if the user's session is valid and all data your payment provider requires
        in future steps is present.
        """
        raise NotImplementedError()  # NOQA

    def checkout_perform(self, request: HttpRequest, order: Order) -> str:
        """
        After the user confirmed his purchase, this method will be called to complete
        the payment process. This is the place to actually move the money, if applicable.
        If you need any speical  behaviour,  you can return a string
        containing an URL the user will be redirected to. If you are done with your process
        you should return the user to the order's detail page.

        If the payment is completed, you should call ``order.mark_paid(provider, info)``
        with ``provider`` being your :py:attr:`identifier` and ``info`` being any string
        you might want to store for later usage. Please note, that if you want to store
        something inside ``order.payment_info``, please do a ``order = order.clone()`` before
        modifying or saving the order object.

        The default implementation just returns ``None`` and therefore leaves the
        order unpaid. The user will be redirected to the order's detail page by default.

        On errors, you should use Django's message framework to display an error message
        to the user.

        :param order: The order object
        """
        return None

    def order_pending_mail_render(self, order: Order) -> str:
        """
        After the user submitted his order, he or she will receive a confirmation
        e-mail. You can return a string from this method if you want to add additional
        information to this e-mail.

        :param order: The order object
        """
        return ""

    def order_pending_render(self, request: HttpRequest, order: Order) -> str:
        """
        If the user visits a detail page of an order which has not yet been paid but
        this payment method was selected during checkout, this method will be called
        to provide HTML content for the 'payment' box on the page.

        It should contain instructions on how to continue with the payment process,
        either in form of text or buttons/links/etc.

        :param order: The order object
        """
        raise NotImplementedError()  # NOQA

    def order_paid_render(self, request: HttpRequest, order: Order) -> str:
        """
        Will be called if the user views the detail page of an paid order which is
        associated with this payment provider.

        It should return HTML code which should be displayed to the user or None,
        if there is nothing to say (like the default implementation does).

        :param order: The order object
        """
        return None

    def order_control_render(self, request: HttpRequest, order: Order) -> str:
        """
        Will be called if the *event administrator* views the detail page of an order
        which is associated with this payment provider.

        It should return HTML code containing information regarding the current payment
        status and, if applicable, next steps.

        The default implementation returns the verbose name of the payment provider.

        :param order: The order object
        """
        return _('Payment provider: %s' % self.verbose_name)
