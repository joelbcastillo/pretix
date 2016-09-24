import datetime
from decimal import Decimal

from django.utils.timezone import now
from tests.base import SoupTest, extract_form_fields

from pretix.base.models import (
    Event, EventPermission, Item, ItemCategory, ItemVariation, Order,
    OrderPosition, Organizer, OrganizerPermission, Question, QuestionAnswer,
    Quota, User,
)


class ItemFormTest(SoupTest):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        self.orga1 = Organizer.objects.create(name='CCC', slug='ccc')
        self.orga2 = Organizer.objects.create(name='MRM', slug='mrm')
        self.event1 = Event.objects.create(
            organizer=self.orga1, name='30C3', slug='30c3',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
        )
        OrganizerPermission.objects.create(organizer=self.orga1, user=self.user)
        EventPermission.objects.create(event=self.event1, user=self.user, can_change_items=True,
                                       can_change_settings=True)
        self.client.login(email='dummy@dummy.dummy', password='dummy')


class CategoriesTest(ItemFormTest):

    def test_create(self):
        doc = self.get_doc('/control/event/%s/%s/categories/add' % (self.orga1.slug, self.event1.slug))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name_0'] = 'Entry tickets'
        doc = self.post_doc('/control/event/%s/%s/categories/add' % (self.orga1.slug, self.event1.slug), form_data)
        assert doc.select(".alert-success")
        self.assertIn("Entry tickets", doc.select("#page-wrapper table")[0].text)

    def test_update(self):
        c = ItemCategory.objects.create(event=self.event1, name="Entry tickets")
        doc = self.get_doc('/control/event/%s/%s/categories/%s/' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name_0'] = 'T-Shirts'
        doc = self.post_doc('/control/event/%s/%s/categories/%s/' % (self.orga1.slug, self.event1.slug, c.id),
                            form_data)
        assert doc.select(".alert-success")
        self.assertIn("T-Shirts", doc.select("#page-wrapper table")[0].text)
        self.assertNotIn("Entry tickets", doc.select("#page-wrapper table")[0].text)
        assert str(ItemCategory.objects.get(id=c.id).name) == 'T-Shirts'

    def test_sort(self):
        c1 = ItemCategory.objects.create(event=self.event1, name="Entry tickets", position=0)
        ItemCategory.objects.create(event=self.event1, name="T-Shirts", position=1)
        doc = self.get_doc('/control/event/%s/%s/categories/' % (self.orga1.slug, self.event1.slug))
        self.assertIn("Entry tickets", doc.select("table > tbody > tr")[0].text)
        self.assertIn("T-Shirts", doc.select("table > tbody > tr")[1].text)

        self.client.get('/control/event/%s/%s/categories/%s/down' % (self.orga1.slug, self.event1.slug, c1.id))
        doc = self.get_doc('/control/event/%s/%s/categories/' % (self.orga1.slug, self.event1.slug))
        self.assertIn("Entry tickets", doc.select("table > tbody > tr")[1].text)
        self.assertIn("T-Shirts", doc.select("table > tbody > tr")[0].text)

        self.client.get('/control/event/%s/%s/categories/%s/up' % (self.orga1.slug, self.event1.slug, c1.id))
        doc = self.get_doc('/control/event/%s/%s/categories/' % (self.orga1.slug, self.event1.slug))
        self.assertIn("Entry tickets", doc.select("table > tbody > tr")[0].text)
        self.assertIn("T-Shirts", doc.select("table > tbody > tr")[1].text)

    def test_delete(self):
        c = ItemCategory.objects.create(event=self.event1, name="Entry tickets")
        doc = self.get_doc('/control/event/%s/%s/categories/%s/delete' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        doc = self.post_doc('/control/event/%s/%s/categories/%s/delete' % (self.orga1.slug, self.event1.slug, c.id),
                            form_data)
        assert doc.select(".alert-success")
        self.assertNotIn("Entry tickets", doc.select("#page-wrapper")[0].text)
        assert not ItemCategory.objects.filter(id=c.id).exists()


class QuestionsTest(ItemFormTest):

    def test_create(self):
        doc = self.get_doc('/control/event/%s/%s/questions/add' % (self.orga1.slug, self.event1.slug))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['question_0'] = 'What is your shoe size?'
        form_data['type'] = 'N'
        doc = self.post_doc('/control/event/%s/%s/questions/add' % (self.orga1.slug, self.event1.slug), form_data)
        assert doc.select(".alert-success")
        self.assertIn("shoe size", doc.select("#page-wrapper table")[0].text)

    def test_update_choices(self):
        c = Question.objects.create(event=self.event1, question="What country are you from?", type="C", required=True)
        o1 = c.options.create(answer='Germany')
        doc = self.get_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['form-TOTAL_FORMS'] = '1'
        form_data['form-INITIAL_FORMS'] = '1'
        form_data['form-MIN_NUM_FORMS'] = '0'
        form_data['form-MAX_NUM_FORMS'] = '1'
        form_data['form-0-id'] = o1.pk
        form_data['form-0-answer_0'] = 'England'
        self.post_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id),
                      form_data)
        c.refresh_from_db()
        assert c.options.exists()
        assert str(c.options.first().answer) == 'England'

    def test_delete_choices(self):
        c = Question.objects.create(event=self.event1, question="What country are you from?", type="C", required=True)
        o1 = c.options.create(answer='Germany')
        doc = self.get_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['form-TOTAL_FORMS'] = '1'
        form_data['form-INITIAL_FORMS'] = '1'
        form_data['form-MIN_NUM_FORMS'] = '0'
        form_data['form-MAX_NUM_FORMS'] = '1'
        form_data['form-0-id'] = o1.pk
        form_data['form-0-answer_0'] = 'England'
        form_data['form-0-DELETE'] = 'yes'
        self.post_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id),
                      form_data)
        c.refresh_from_db()
        assert not c.options.exists()

    def test_add_choices(self):
        c = Question.objects.create(event=self.event1, question="What country are you from?", type="N", required=True)
        doc = self.get_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['type'] = 'C'
        form_data['form-TOTAL_FORMS'] = '1'
        form_data['form-INITIAL_FORMS'] = '0'
        form_data['form-MIN_NUM_FORMS'] = '0'
        form_data['form-MAX_NUM_FORMS'] = '1'
        form_data['form-0-id'] = ''
        form_data['form-0-answer_0'] = 'Germany'
        self.post_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id),
                      form_data)
        c = Question.objects.get(id=c.id)
        assert c.options.exists()
        assert str(c.options.first().answer) == 'Germany'

    def test_update(self):
        c = Question.objects.create(event=self.event1, question="What is your shoe size?", type="N", required=True)
        doc = self.get_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['question_0'] = 'How old are you?'
        doc = self.post_doc('/control/event/%s/%s/questions/%s/change' % (self.orga1.slug, self.event1.slug, c.id),
                            form_data)
        self.assertIn("How old", doc.select("#page-wrapper table")[0].text)
        self.assertNotIn("shoe size", doc.select("#page-wrapper table")[0].text)
        c = Question.objects.get(id=c.id)
        self.assertTrue(c.required)
        assert str(Question.objects.get(id=c.id).question) == 'How old are you?'

    def test_sort(self):
        q1 = Question.objects.create(event=self.event1, question="Vegetarian?", type="N", required=True, position=0)
        Question.objects.create(event=self.event1, question="Food allergies?", position=1)
        doc = self.get_doc('/control/event/%s/%s/questions/' % (self.orga1.slug, self.event1.slug))
        self.assertIn("Vegetarian?", doc.select("table > tbody > tr")[0].text)
        self.assertIn("Food allergies?", doc.select("table > tbody > tr")[1].text)

        self.client.get('/control/event/%s/%s/questions/%s/down' % (self.orga1.slug, self.event1.slug, q1.id))
        doc = self.get_doc('/control/event/%s/%s/questions/' % (self.orga1.slug, self.event1.slug))
        self.assertIn("Vegetarian?", doc.select("table > tbody > tr")[1].text)
        self.assertIn("Food allergies?", doc.select("table > tbody > tr")[0].text)

        self.client.get('/control/event/%s/%s/questions/%s/up' % (self.orga1.slug, self.event1.slug, q1.id))
        doc = self.get_doc('/control/event/%s/%s/questions/' % (self.orga1.slug, self.event1.slug))
        self.assertIn("Vegetarian?", doc.select("table > tbody > tr")[0].text)
        self.assertIn("Food allergies?", doc.select("table > tbody > tr")[1].text)

    def test_delete(self):
        c = Question.objects.create(event=self.event1, question="What is your shoe size?", type="N", required=True)
        doc = self.get_doc('/control/event/%s/%s/questions/%s/delete' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        doc = self.post_doc('/control/event/%s/%s/questions/%s/delete' % (self.orga1.slug, self.event1.slug, c.id),
                            form_data)
        assert doc.select(".alert-success")
        self.assertNotIn("shoe size", doc.select("#page-wrapper")[0].text)
        assert not Question.objects.filter(id=c.id).exists()

    def test_question_view(self):
        c = Question.objects.create(event=self.event1, question="What is your shoe size?", type="N", required=True)

        item1 = Item.objects.create(event=self.event1, name="Standard", default_price=0, position=1)
        o = Order.objects.create(code='FOO', event=self.event1, email='dummy@dummy.test',
                                 status=Order.STATUS_PENDING, datetime=now(),
                                 expires=now() + datetime.timedelta(days=10),
                                 total=14, payment_provider='banktransfer', locale='en')
        op = OrderPosition.objects.create(order=o, item=item1, variation=None, price=Decimal("14"),
                                          attendee_name="Peter")
        op.answers.create(question=c, answer='42')
        op = OrderPosition.objects.create(order=o, item=item1, variation=None, price=Decimal("14"),
                                          attendee_name="Michael")
        op.answers.create(question=c, answer='42')
        op = OrderPosition.objects.create(order=o, item=item1, variation=None, price=Decimal("14"),
                                          attendee_name="Petra")
        op.answers.create(question=c, answer='39')

        doc = self.get_doc('/control/event/%s/%s/questions/%s/' % (self.orga1.slug, self.event1.slug, c.id))
        tbl = doc.select('.container-fluid table.table-bordered tbody')[0]
        assert tbl.select('tr')[0].select('td')[0].text.strip() == '42'
        assert tbl.select('tr')[0].select('td')[1].text.strip() == '2'
        assert tbl.select('tr')[1].select('td')[0].text.strip() == '39'
        assert tbl.select('tr')[1].select('td')[1].text.strip() == '1'

        doc = self.get_doc('/control/event/%s/%s/questions/%s/?status=p' % (self.orga1.slug, self.event1.slug, c.id))
        assert not doc.select('.container-fluid table.table-bordered tbody')

        o.status = Order.STATUS_PAID
        o.save()
        doc = self.get_doc('/control/event/%s/%s/questions/%s/?status=p' % (self.orga1.slug, self.event1.slug, c.id))
        tbl = doc.select('.container-fluid table.table-bordered tbody')[0]
        assert tbl.select('tr')[0].select('td')[0].text.strip() == '42'


class QuotaTest(ItemFormTest):

    def test_create(self):
        doc = self.get_doc('/control/event/%s/%s/quotas/add' % (self.orga1.slug, self.event1.slug))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name'] = 'Full house'
        form_data['size'] = '500'
        doc = self.post_doc('/control/event/%s/%s/quotas/add' % (self.orga1.slug, self.event1.slug), form_data)
        assert doc.select(".alert-success")
        self.assertIn("Full house", doc.select("#page-wrapper table")[0].text)

    def test_update(self):
        c = Quota.objects.create(event=self.event1, name="Full house", size=500)
        item1 = Item.objects.create(event=self.event1, name="Standard", default_price=0)
        item2 = Item.objects.create(event=self.event1, name="Business", default_price=0)
        ItemVariation.objects.create(item=item2, value="Silver")
        ItemVariation.objects.create(item=item2, value="Gold")
        doc = self.get_doc('/control/event/%s/%s/quotas/%s/change' % (self.orga1.slug, self.event1.slug, c.id))
        doc.select('[name=item_%s]' % item1.id)[0]['checked'] = 'checked'
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['size'] = '350'
        doc = self.post_doc('/control/event/%s/%s/quotas/%s/change' % (self.orga1.slug, self.event1.slug, c.id),
                            form_data)
        self.assertIn("350", doc.select("#page-wrapper table")[0].text)
        self.assertNotIn("500", doc.select("#page-wrapper table")[0].text)
        assert Quota.objects.get(id=c.id).size == 350
        assert item1 in Quota.objects.get(id=c.id).items.all()

    def test_delete(self):
        c = Quota.objects.create(event=self.event1, name="Full house", size=500)
        doc = self.get_doc('/control/event/%s/%s/quotas/%s/delete' % (self.orga1.slug, self.event1.slug, c.id))
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        doc = self.post_doc('/control/event/%s/%s/quotas/%s/delete' % (self.orga1.slug, self.event1.slug, c.id),
                            form_data)
        assert doc.select(".alert-success")
        self.assertNotIn("Full house", doc.select("#page-wrapper")[0].text)
        assert not Quota.objects.filter(id=c.id).exists()


class ItemsTest(ItemFormTest):

    def setUp(self):
        super().setUp()
        self.item1 = Item.objects.create(event=self.event1, name="Standard", default_price=0, position=1)
        self.item2 = Item.objects.create(event=self.event1, name="Business", default_price=0, position=2)
        self.var1 = ItemVariation.objects.create(item=self.item2, value="Silver")
        self.var2 = ItemVariation.objects.create(item=self.item2, value="Gold")

    def test_move(self):
        self.client.post('/control/event/%s/%s/items/%s/down' % (self.orga1.slug, self.event1.slug, self.item1.id),)
        self.item1.refresh_from_db()
        self.item2.refresh_from_db()
        assert self.item1.position > self.item2.position
        self.client.post('/control/event/%s/%s/items/%s/up' % (self.orga1.slug, self.event1.slug, self.item1.id),)
        self.item1.refresh_from_db()
        self.item2.refresh_from_db()
        assert self.item1.position < self.item2.position

    def test_create(self):
        self.client.post('/control/event/%s/%s/items/add' % (self.orga1.slug, self.event1.slug), {
            'name_0': 'T-Shirt',
            'default_price': '23.00',
            'tax_rate': '19.00'
        })
        resp = self.client.get('/control/event/%s/%s/items/' % (self.orga1.slug, self.event1.slug))
        assert 'T-Shirt' in resp.rendered_content

    def test_update(self):
        self.client.post('/control/event/%s/%s/items/%d/' % (self.orga1.slug, self.event1.slug, self.item1.id), {
            'name_0': 'Standard',
            'default_price': '23.00',
            'tax_rate': '19.00',
            'active': 'yes',
            'allow_cancel': 'yes'
        })
        self.item1.refresh_from_db()
        assert self.item1.default_price == Decimal('23.00')

    def test_update_variations(self):
        self.client.post('/control/event/%s/%s/items/%d/variations' % (self.orga1.slug, self.event1.slug, self.item2.id), {
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '2',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(self.var1.pk),
            'form-0-value_0': 'Bronze',
            'form-0-active': 'yes',
            'form-1-id': str(self.var2.pk),
            'form-1-value_0': 'Gold',
            'form-1-active': 'yes',
            'name_0': 'form-TOTAL_FORMS',
            'default_price': '23.00',
            'tax_rate': '19.00',
            'active': 'yes',
            'allow_cancel': 'yes'
        })
        self.var1.refresh_from_db()
        assert str(self.var1.value) == 'Bronze'

    def test_delete_variation(self):
        self.client.post('/control/event/%s/%s/items/%d/variations' % (self.orga1.slug, self.event1.slug, self.item2.id), {
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '2',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(self.var1.pk),
            'form-0-value_0': 'Bronze',
            'form-0-active': 'yes',
            'form-1-id': str(self.var2.pk),
            'form-1-value_0': 'Gold',
            'form-1-active': 'yes',
            'form-1-DELETE': 'yes',
            'name_0': 'form-TOTAL_FORMS',
            'default_price': '23.00',
            'tax_rate': '19.00',
            'active': 'yes',
            'allow_cancel': 'yes'
        })
        assert not self.item2.variations.filter(pk=self.var2.pk).exists()

    def test_delete(self):
        self.client.post('/control/event/%s/%s/items/%d/delete' % (self.orga1.slug, self.event1.slug, self.item1.id),
                         {})
        assert not self.event1.items.filter(pk=self.item1.pk).exists()
        self.client.post('/control/event/%s/%s/items/%d/delete' % (self.orga1.slug, self.event1.slug, self.item2.id),
                         {})
        assert not self.event1.items.filter(pk=self.item2.pk).exists()

    def test_delete_ordered(self):
        o = Order.objects.create(
            code='FOO', event=self.event1, email='dummy@dummy.test',
            status=Order.STATUS_PENDING,
            datetime=now(), expires=now() + datetime.timedelta(days=10),
            total=14, payment_provider='banktransfer', locale='en'
        )
        OrderPosition.objects.create(
            order=o,
            item=self.item1,
            variation=None,
            price=Decimal("14"),
            attendee_name="Peter"
        )
        self.client.post('/control/event/%s/%s/items/%d/delete' % (self.orga1.slug, self.event1.slug, self.item1.id),
                         {})
        assert self.event1.items.filter(pk=self.item1.pk).exists()
        self.item1.refresh_from_db()
        assert not self.item1.active
