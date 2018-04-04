import datetime

from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from main.models import Licence
import dataset.constants as constants
from variant.factories import VariantFactory

from ..factories import ScoreSetFactory


class TestScoreSet(TestCase):
    """
    The purpose of this unit test is to test that the database model
    :py:class:`ScoreSet`, representing an experiment with associated
    :py:class:`Variant` objects. We will test correctness of creation,
    validation, uniqueness, queries and that the appropriate errors are raised.
    """
    def test_publish_updates_published_and_last_edit_dates(self):
        scs = ScoreSetFactory()
        scs.publish()
        self.assertEqual(scs.publish_date, datetime.date.today())
        self.assertEqual(scs.last_edit_date, datetime.date.today())

    def test_publish_updates_private_to_false(self):
        scs = ScoreSetFactory()
        scs.publish()
        self.assertFalse(scs.private)

    def test_new_is_assigned_all_permission_groups(self):
        self.assertEqual(Group.objects.count(), 0)
        _ = ScoreSetFactory()
        self.assertEqual(Group.objects.count(), 9)

    def test_deleted_deletes_all_permission_groups(self):
        obj = ScoreSetFactory()
        self.assertEqual(Group.objects.count(), 9)
        obj.delete()
        self.assertEqual(Group.objects.count(), 6)

    def test_autoassign_does_not_reassign_deleted_urn(self):
        obj = ScoreSetFactory()
        previous = obj.urn
        obj.delete()
        obj = ScoreSetFactory()
        self.assertGreater(obj.urn, previous)

    def test_cannot_create_with_duplicate_urn(self):
        obj = ScoreSetFactory()
        with self.assertRaises(IntegrityError):
            ScoreSetFactory(urn=obj.urn)

    def test_cannot_save_without_experiment(self):
        with self.assertRaises(IntegrityError):
            ScoreSetFactory(experiment=None)

    def test_gets_cc4_licence_by_default(self):
        obj = ScoreSetFactory()
        self.assertEqual(obj.licence, Licence.get_default())

    def test_scoreset_not_approved_and_private_by_default(self):
        scs = ScoreSetFactory()
        self.assertFalse(scs.approved)
        self.assertTrue(scs.private)

    def test_cannot_delete_scoreset_with_variants(self):
        scs = ScoreSetFactory()
        _ = VariantFactory(scoreset=scs)
        with self.assertRaises(ProtectedError):
            scs.delete()

    def test_can_traverse_replaced_by_tree(self):
        scs_1 = ScoreSetFactory()
        scs_2 = ScoreSetFactory(experiment=scs_1.experiment, replaces=scs_1)
        scs_3 = ScoreSetFactory(experiment=scs_2.experiment, replaces=scs_2)
        self.assertEqual(scs_1.current_version, scs_3)
        self.assertEqual(scs_1.next_version, scs_2)
        self.assertEqual(scs_2.previous_version, scs_1)

    def test_has_replacement_returns_false_if_no_relationship_set(self):
        scs = ScoreSetFactory()
        self.assertFalse(scs.has_replacement)

    def test_replaces_returns_false_if_no_relationship_set(self):
        scs = ScoreSetFactory()
        self.assertFalse(scs.replaces)

    def test_has_replacement_returns_true_if_relationship_set(self):
        scs_1 = ScoreSetFactory()
        _ = ScoreSetFactory(experiment=scs_1.experiment, replaces=scs_1)
        self.assertTrue(scs_1.has_replacement)

    def test_replaces_returns_true_if_relationship_set(self):
        scs_1 = ScoreSetFactory()
        scs_2 = ScoreSetFactory(experiment=scs_1.experiment, replaces=scs_1)
        self.assertTrue(scs_2.replaces)

    def test_has_variants(self):
        scs = ScoreSetFactory()
        self.assertFalse(scs.has_variants)
        _ = VariantFactory(scoreset=scs)
        self.assertTrue(scs.has_variants)

    def test_delete_variants_resets_dataset_columns(self):
        scs = ScoreSetFactory()
        _ = VariantFactory(scoreset=scs)
        scs.delete_variants()
        expected = dict({
            constants.score_columns: [constants.required_score_column],
            constants.count_columns: [],
            constants.metadata_columns: []
        })
        self.assertEqual(scs.dataset_columns, expected)
        self.assertEqual(scs.variants.count(), 0)
