from django.test import TestCase, RequestFactory

from accounts.factories import UserFactory

from ..utilities import publish_dataset
from ..factories import ExperimentFactory, ExperimentSetFactory
from ..forms.experiment import ExperimentForm, ErrorMessages
from ..models.experiment import Experiment
from ..models.experimentset import ExperimentSet


class TestExperimentForm(TestCase):
    """
    Test that the `ExperimentForm` object is able to raise the appropriate
    `ValidationError` on fields such as experimentset.
    """

    def setUp(self):
        self.user = UserFactory()
        self.factory = RequestFactory()

    def make_form_data(self, create_experimentset=False):
        """
        Makes sample test input for instantiating the form to simulate
        POST data from a view.

        Parameters
        ----------
        create_experimentset : bool
            If False, experimentset is set to None
        """
        data = {"short_description": "experiment", "title": "title"}
        if create_experimentset:
            exps = ExperimentSetFactory()
            exps.add_administrators(self.user)
            data["experimentset"] = exps.pk
        return data

    def test_can_create_form_and_save_new_instance(self):
        form = ExperimentForm(user=self.user, data=self.make_form_data())
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(Experiment.objects.count(), 1)
        self.assertEqual(ExperimentSet.objects.count(), 1)

    def test_not_valid_experimentset_not_found(self):
        data = self.make_form_data()
        data["experimentset"] = "blah"
        form = ExperimentForm(user=self.user, data=data)
        self.assertFalse(form.is_valid())

    def test_admin_experimentset_appear_in_options(self):
        obj1 = ExperimentSetFactory()
        obj2 = ExperimentSetFactory()
        _ = ExperimentSetFactory()

        obj1.add_administrators(self.user)
        obj2.add_viewers(self.user)

        form = ExperimentForm(user=self.user)
        self.assertEqual(form.fields["experimentset"].queryset.count(), 1)
        self.assertIn(obj1, form.fields["experimentset"].queryset)

    def test_editor_experimentset_appear_in_options(self):
        obj1 = ExperimentSetFactory()
        obj2 = ExperimentSetFactory()
        _ = ExperimentSetFactory()

        obj1.add_editors(self.user)
        obj2.add_viewers(self.user)

        form = ExperimentForm(user=self.user)
        self.assertEqual(form.fields["experimentset"].queryset.count(), 1)
        self.assertIn(obj1, form.fields["experimentset"].queryset)

    def test_from_request_modifies_existing_instance(self):
        exp = ExperimentFactory()
        exp.add_administrators(self.user)
        exp.parent.add_administrators(self.user)

        data = self.make_form_data(create_experimentset=True)
        request = self.factory.post("/path/", data=data)
        request.user = self.user

        form = ExperimentForm.from_request(request, exp)
        instance = form.save(commit=True)
        self.assertEqual(instance.experimentset.pk, data["experimentset"])
        self.assertEqual(instance.get_title(), data["title"])
        self.assertEqual(instance.get_description(), data["short_description"])

    def test_invalid_change_experimentset_public_experiment(self):
        obj = ExperimentFactory()
        obj.parent.add_administrators(self.user)
        obj.add_administrators(self.user)
        obj = publish_dataset(obj)

        # Make the data, which also sets the selected experiment
        data = self.make_form_data(create_experimentset=True)
        form = ExperimentForm(data=data, user=self.user, instance=obj)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            ErrorMessages.ExperimentSet.public_experiment,
            form.errors["experimentset"][0],
        )

    def test_experimentset_options_frozen_when_passing_instance(self):
        data = self.make_form_data(create_experimentset=False)

        exp = ExperimentSetFactory()
        exp.add_administrators(self.user)

        # Should not appear since locked to above
        exp2 = ExperimentSetFactory()
        exp2.add_administrators(self.user)

        form = ExperimentForm(data=data, experimentset=exp, user=self.user)
        self.assertIn(exp, form.fields["experimentset"].queryset)
        self.assertNotIn(exp2, form.fields["experimentset"].queryset)
