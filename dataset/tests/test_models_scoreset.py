import datetime

from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.db import transaction
from django.shortcuts import reverse

from core.utilities import base_url

from genome.models import TargetGene

from main.models import Licence

from variant.factories import VariantFactory

from dataset import constants

from ..models.scoreset import default_dataset, ScoreSet, assign_public_urn
from ..factories import ScoreSetFactory, ScoreSetWithTargetFactory
from ..utilities import publish_dataset


class TestScoreSet(TestCase):
    """
    The purpose of this unit test is to test that the database model
    :py:class:`ScoreSet`, representing an experiment with associated
    :py:class:`Variant` objects. We will test correctness of creation,
    validation, uniqueness, queries and that the appropriate errors are raised.
    """
    def test_new_is_assigned_all_permission_groups(self):
        self.assertEqual(Group.objects.count(), 0)
        _ = ScoreSetFactory()
        self.assertEqual(Group.objects.count(), 9)

    def test_deleted_deletes_all_permission_groups(self):
        obj = ScoreSetFactory()
        self.assertEqual(Group.objects.count(), 9)
        obj.delete()
        self.assertEqual(Group.objects.count(), 6)

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
        scs = ScoreSet()
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
        scs.save()

        self.assertEqual(scs.dataset_columns, default_dataset())
        self.assertEqual(scs.variants.count(), 0)
        self.assertEqual(scs.last_child_value, 0)

    def test_can_traverse_public_replaced_by_tree(self):
        scs_1 = ScoreSetFactory(private=False)
        scs_2 = ScoreSetFactory(
            private=False, experiment=scs_1.experiment, replaces=scs_1)
        scs_3 = ScoreSetFactory(
            private=True, experiment=scs_2.experiment, replaces=scs_2)
        self.assertEqual(scs_1.current_public_version, scs_2)
        self.assertEqual(scs_2.current_public_version, scs_2)

    def test_next_public_version_returns_none_if_next_is_private(self):
        scs_1 = ScoreSetFactory(private=False)
        scs_2 = ScoreSetFactory(
            private=True, experiment=scs_1.experiment, replaces=scs_1)
        self.assertEqual(scs_1.next_public_version, None)
        self.assertEqual(scs_2.next_public_version, None)

    def test_next_public_version_returns_next_if_next_is_public(self):
        scs_1 = ScoreSetFactory(private=False)
        scs_2 = ScoreSetFactory(
            private=False, experiment=scs_1.experiment, replaces=scs_1)
        self.assertEqual(scs_1.next_public_version, scs_2)

    def test_previous_public_version_returns_none_if_previous_is_private(self):
        scs_1 = ScoreSetFactory(private=True)
        scs_2 = ScoreSetFactory(experiment=scs_1.experiment, replaces=scs_1)
        self.assertEqual(scs_1.previous_public_version, None)
        self.assertEqual(scs_2.previous_public_version, None)

    def test_previous_public_version_returns_previous_if_previous_is_public(self):
        scs_1 = ScoreSetFactory(private=False)
        scs_2 = ScoreSetFactory(
            private=True, experiment=scs_1.experiment, replaces=scs_1)
        scs_3 = ScoreSetFactory(experiment=scs_2.experiment, replaces=scs_2)
        self.assertEqual(scs_3.previous_public_version, scs_1)
        self.assertEqual(scs_2.previous_public_version, scs_1)

    def test_delete_cascades_to_target(self):
        scs = ScoreSetWithTargetFactory()
        self.assertEqual(TargetGene.objects.count(), 1)
        scs.delete()
        self.assertEqual(TargetGene.objects.count(), 0)

    def test_delete_does_not_delete_licence(self):
        scs = ScoreSetFactory()
        self.assertEqual(Licence.objects.count(), 1)
        scs.delete()
        self.assertEqual(Licence.objects.count(), 1)

    def test_delete_replaces_sets_field_to_none(self):
        scs_1 = ScoreSetFactory()
        scs_2 = ScoreSetFactory(replaces=scs_1)
        self.assertIsNotNone(scs_2.replaces)
        scs_1.delete()
        scs_2.refresh_from_db()
        self.assertIsNone(scs_2.replaces)

    def test_can_get_url(self):
        obj = ScoreSetFactory()
        self.assertEqual(
            obj.get_url(),
            base_url() + reverse('dataset:scoreset_detail', args=(obj.urn,))
        )
        
    def test_primary_column_is_nt_when_nt_is_present(self):
        obj = ScoreSetFactory()
        VariantFactory(scoreset=obj, hgvs_nt='a')
        VariantFactory(scoreset=obj)
        self.assertEqual(obj.primary_hgvs_column, constants.hgvs_nt_column)
        
    def test_primary_column_is_pro_when_nt_is_not_present(self):
        obj = ScoreSetFactory()
        VariantFactory(scoreset=obj, hgvs_nt=None)
        self.assertEqual(obj.primary_hgvs_column, constants.hgvs_pro_column)
        
    # def test_wt_is_first_when_sorted(self):
    #     obj = ScoreSetFactory()
    #     v1 = VariantFactory(scoreset=obj, hgvs_nt='c.[9A>T;99G>T]')
    #     v2 = VariantFactory(scoreset=obj, hgvs_nt='_wt')
    #     self.assertEqual(obj.children.order_by(
    #         '{}'.format(obj.primary_hgvs_column)).first(), v2
    #     )


class TestAssignPublicUrn(TestCase):
    def test_assign_public_urn_twice_doesnt_change_urn(self):
        exp = ScoreSetFactory()
        publish_dataset(exp)
        exp.refresh_from_db()
        old_urn = exp.urn
        self.assertTrue(exp.has_public_urn)

        exp = ScoreSet.objects.first()
        assign_public_urn(exp)
        exp.refresh_from_db()
        new_urn = exp.urn

        self.assertTrue(exp.has_public_urn)
        self.assertEqual(new_urn, old_urn)

    def test_assigns_sequential_urns(self):
        instance1 = ScoreSetFactory()
        instance2 = ScoreSetFactory()
        instance2.experiment = instance1.experiment
        instance2.experiment.experimentset = instance1.experiment.experimentset
        instance2.save()
        assign_public_urn(instance2)
        self.assertIn('-1', instance2.urn)
        assign_public_urn(instance1)
        self.assertIn('-2', instance1.urn)
