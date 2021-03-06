import json
from pandas.testing import assert_frame_equal

from django.core import mail
from django.test import TestCase, TransactionTestCase, RequestFactory, mock
from django.urls import reverse_lazy
from django.http import Http404
from django.core.exceptions import PermissionDenied

from reversion.models import Version

from mavedb import celery_app

from accounts.factories import UserFactory
from accounts.permissions import (
    assign_user_as_instance_viewer,
    assign_user_as_instance_editor,
    assign_user_as_instance_admin,
)

from core.utilities.tests import TestMessageMixin
from core.tasks import send_mail

from genome.factories import ReferenceGenomeFactory

from metadata.factories import (
    KeywordFactory,
    PubmedIdentifierFactory,
    DoiIdentifierFactory,
    SraIdentifierFactory,
    UniprotOffsetFactory,
    EnsemblOffsetFactory,
    RefseqOffsetFactory,
    UniprotIdentifierFactory,
    EnsemblIdentifierFactory,
    RefseqIdentifierFactory,
    EnsemblOffset,
    UniprotOffset,
    RefseqOffset,
)

from variant.factories import VariantFactory

from ..utilities import publish_dataset
import dataset.constants as constants
from ..tasks import create_variants
from ..forms.scoreset import ScoreSetForm
from ..factories import (
    ScoreSetFactory,
    ExperimentFactory,
    ScoreSetWithTargetFactory,
)
from ..models.scoreset import ScoreSet
from ..views.scoreset import (
    ScoreSetDetailView,
    ScoreSetCreateView,
    ScoreSetEditView,
)

from .utility import make_files


class TestScoreSetSetDetailView(TestCase, TestMessageMixin):
    """
    Test that experimentsets are displayed correctly to the public.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.template = "dataset/scoreset/scoreset.html"
        self.template_403 = "main/403.html"
        self.template_404 = "main/404.html"
        celery_app.conf.update(CELERY_TASK_ALWAYS_EAGER=True)

    def test_title_in_metadata_description_tag(self):
        obj = ScoreSetFactory()
        obj = publish_dataset(obj)
        response = self.client.get("/scoreset/{}/".format(obj.urn))
        self.assertEqual(response.status_code, 200)
        tag = '<meta name="description" content="{}">'.format(obj.title)
        self.assertContains(response, tag)

    def test_404_status_and_template_used_when_object_not_found(self):
        obj = ScoreSetFactory()
        urn = obj.urn
        obj.delete()
        response = self.client.get("/scoreset/{}/".format(urn))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, self.template_404)

    def test_uses_correct_template(self):
        obj = ScoreSetFactory()
        obj = publish_dataset(obj)
        obj.save()
        response = self.client.get("/scoreset/{}/".format(obj.urn))
        self.assertTemplateUsed(response, self.template)

    def test_private_instance_will_403_if_no_permission(self):
        user = UserFactory()
        obj = ScoreSetFactory(private=True)
        request = self.factory.get("/scoreset/{}/".format(obj.urn))
        request.user = user
        with self.assertRaises(PermissionDenied):
            ScoreSetDetailView.as_view()(request, urn=obj.urn)

    def test_403_uses_correct_template(self):
        obj = ScoreSetFactory(private=True)
        response = self.client.get("/scoreset/{}/".format(obj.urn))
        self.assertTemplateUsed(response, self.template_403)

    def test_private_experiment_rendered_if_user_can_view(self):
        user = UserFactory()
        obj = ScoreSetFactory()
        obj.add_viewers(user)
        request = self.factory.get("/scoreset/{}/".format(obj.urn))
        request.user = user
        response = ScoreSetDetailView.as_view()(request, urn=obj.urn)
        self.assertEqual(response.status_code, 200)

    def test_scores_get_ajax(self):
        scs = ScoreSetFactory(private=False)
        scs.dataset_columns = {
            constants.score_columns: ["score"],
            constants.count_columns: [],
        }
        scs.save()
        var = VariantFactory(
            scoreset=scs, data={constants.variant_score_data: {"score": 0}}
        )
        request = self.factory.get(
            "/scoreset/{}/".format(scs.urn),
            data={"type": "scores"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        request.user = UserFactory()
        response = ScoreSetDetailView.as_view()(request, urn=scs.urn)
        data = json.loads(response.content.decode())["data"]

        for i, value in enumerate(var.score_data):
            self.assertEqual(str(value), data[0][str(i)])

    def test_counts_get_ajax(self):
        scs = ScoreSetFactory(private=False)
        scs.dataset_columns = {
            constants.score_columns: ["score"],
            constants.count_columns: ["count"],
        }
        scs.save()
        var = VariantFactory(
            scoreset=scs,
            data={
                constants.variant_score_data: {"score": 1},
                constants.variant_count_data: {"count": 0},
            },
        )
        request = self.factory.get(
            "/scoreset/{}/".format(scs.urn),
            data={"type": "counts"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        request.user = UserFactory()
        response = ScoreSetDetailView.as_view()(request, urn=scs.urn)
        data = json.loads(response.content.decode())["data"]
        for i, value in enumerate(var.count_data):
            self.assertIn(str(value), data[0][str(i)])

    # --- MaveVis link visibility
    def test_disables_mavevis_if_private(self):
        scs_private = ScoreSetWithTargetFactory(private=True)
        scs_public = ScoreSetWithTargetFactory(private=False)
        v1 = VariantFactory(scoreset=scs_private)
        v2 = VariantFactory(scoreset=scs_public)

        self.assertTrue(scs_private.has_protein_variants)
        self.assertTrue(scs_public.has_protein_variants)
        self.assertTrue(scs_private.has_uniprot_metadata)
        self.assertTrue(scs_public.has_uniprot_metadata)

        self.assertTrue(scs_private.private)
        self.assertFalse(scs_public.private)

        request = self.factory.get("/scoreset/{}/".format(scs_private.urn))
        request.user = UserFactory()
        scs_private.add_viewers(request.user)
        response = ScoreSetDetailView.as_view()(request, urn=scs_private.urn)
        self.assertContains(
            response, "This button will activate once published"
        )

        request = self.factory.get("/scoreset/{}/".format(scs_public.urn))
        request.user = UserFactory()
        response = ScoreSetDetailView.as_view()(request, urn=scs_public.urn)
        self.assertNotContains(
            response, "This button will activate once published"
        )

    def test_disables_mavevis_if_not_protein_coding_variants(self):
        scs_protein = ScoreSetWithTargetFactory(private=False)
        scs_no_protein = ScoreSetWithTargetFactory(private=False)
        v1 = VariantFactory(scoreset=scs_protein)
        v2 = VariantFactory(scoreset=scs_no_protein, hgvs_pro=None)

        self.assertTrue(scs_protein.has_uniprot_metadata)
        self.assertTrue(scs_no_protein.has_uniprot_metadata)
        self.assertTrue(scs_protein.has_protein_variants)
        self.assertFalse(scs_no_protein.has_protein_variants)

        request = self.factory.get("/scoreset/{}/".format(scs_protein.urn))
        request.user = UserFactory()
        response = ScoreSetDetailView.as_view()(request, urn=scs_protein.urn)
        self.assertNotContains(response, "disabled")

        request = self.factory.get("/scoreset/{}/".format(scs_no_protein.urn))
        request.user = UserFactory()
        response = ScoreSetDetailView.as_view()(
            request, urn=scs_no_protein.urn
        )
        self.assertContains(response, "disabled")

    # def test_hides_mavevis_if_target_has_no_uniprot_id(self):
    #     scs_uniprot = ScoreSetWithTargetFactory(private=False)
    #     scs_no_uniprot = ScoreSetWithTargetFactory(private=False)
    #
    #     v1 = VariantFactory(scoreset=scs_uniprot)
    #     v2 = VariantFactory(scoreset=scs_no_uniprot)
    #     scs_no_uniprot.target.uniprot_id = None
    #     scs_no_uniprot.target.save()
    #
    #     self.assertTrue(scs_uniprot.has_protein_variants)
    #     self.assertTrue(scs_no_uniprot.has_protein_variants)
    #     self.assertTrue(scs_uniprot.has_uniprot_metadata)
    #     self.assertFalse(scs_no_uniprot.has_uniprot_metadata)
    #
    #     request = self.factory.get('/scoreset/{}/'.format(scs_no_uniprot.urn))
    #     request.user = UserFactory()
    #     response = ScoreSetDetailView.as_view()(request, urn=scs_no_uniprot.urn)
    #     self.assertContains(response, 'disabled')
    #
    #     request = self.factory.get('/scoreset/{}/'.format(scs_uniprot.urn))
    #     request.user = UserFactory()
    #     response = ScoreSetDetailView.as_view()(request, urn=scs_uniprot.urn)
    #     self.assertNotContains(response, 'disabled')

    # --- Next version links
    def test_next_version_not_shown_if_private_and_user_is_not_a_contributor(
        self
    ):
        scs = ScoreSetFactory(private=False)
        scs1 = ScoreSetFactory(private=True, replaces=scs)
        request = self.factory.get("/scoreset/{}/".format(scs.urn))
        request.user = UserFactory()
        response = ScoreSetDetailView.as_view()(request, urn=scs.urn)
        self.assertNotContains(response, scs1.urn)

    def test_next_version_shown_if_private_and_user_is_a_contributor(self):
        scs = ScoreSetFactory(private=False)
        scs1 = ScoreSetFactory(private=True, replaces=scs)
        scs2 = ScoreSetFactory(private=False, replaces=scs1)
        user = UserFactory()
        scs1.add_viewers(user)
        request = self.factory.get("/scoreset/{}/".format(scs.urn))
        request.user = user
        response = ScoreSetDetailView.as_view()(request, urn=scs.urn)
        self.assertContains(response, scs1.urn + " [Private]", count=1)

    def test_next_version_shown_if_public(self):
        scs = ScoreSetFactory(private=False)
        scs1 = ScoreSetFactory(private=False, replaces=scs)
        scs2 = ScoreSetFactory(private=False, replaces=scs1)
        request = self.factory.get("/scoreset/{}/".format(scs.urn))
        request.user = UserFactory()
        response = ScoreSetDetailView.as_view()(request, urn=scs.urn)
        self.assertContains(response, ">" + scs1.urn + "<", count=1)

    # --- Prev version links
    def test_prev_version_not_shown_if_private_and_user_is_not_a_contributor(
        self
    ):
        scs = ScoreSetFactory(private=True)
        scs1 = ScoreSetFactory(private=False, replaces=scs)
        request = self.factory.get("/scoreset/{}/".format(scs1.urn))
        request.user = UserFactory()
        response = ScoreSetDetailView.as_view()(request, urn=scs1.urn)
        self.assertNotContains(response, scs.urn)

    def test_prev_version_shown_if_private_and_user_is_a_contributor(self):
        scs = ScoreSetFactory(private=True)
        scs1 = ScoreSetFactory(private=False, replaces=scs)
        user = UserFactory()
        scs.add_viewers(user)
        request = self.factory.get("/scoreset/{}/".format(scs1.urn))
        request.user = user
        response = ScoreSetDetailView.as_view()(request, urn=scs1.urn)
        self.assertContains(response, scs.urn + " [Private]", count=1)

    def test_prev_version_shown_if_public(self):
        scs = ScoreSetFactory(private=False)
        scs1 = ScoreSetFactory(private=False, replaces=scs)
        request = self.factory.get("/scoreset/{}/".format(scs1.urn))
        request.user = UserFactory()
        response = ScoreSetDetailView.as_view()(request, urn=scs1.urn)
        self.assertContains(response, ">" + scs.urn + "<", count=1)

    # --- Current Version
    def test_curr_version_not_shown_if_private_and_user_is_not_a_contributor(
        self
    ):
        scs = ScoreSetFactory(private=False)
        scs1 = ScoreSetFactory(private=False, replaces=scs)
        scs2 = ScoreSetFactory(private=True, replaces=scs1)
        request = self.factory.get("/scoreset/{}/".format(scs.urn))
        request.user = UserFactory()
        response = ScoreSetDetailView.as_view()(request, urn=scs.urn)
        self.assertNotContains(response, scs2.urn)

    def test_curr_version_shown_if_private_and_user_is_a_contributor(self):
        scs = ScoreSetFactory(private=False)
        scs1 = ScoreSetFactory(private=False, replaces=scs)
        scs2 = ScoreSetFactory(private=True, replaces=scs1)
        user = UserFactory()
        scs2.add_viewers(user)
        request = self.factory.get("/scoreset/{}/".format(scs.urn))
        request.user = user
        response = ScoreSetDetailView.as_view()(request, urn=scs.urn)
        self.assertContains(response, scs2.urn + " [Private]", count=1)

    def test_curr_version_shown_if_public(self):
        scs = ScoreSetFactory(private=False)
        scs1 = ScoreSetFactory(private=False, replaces=scs)
        scs2 = ScoreSetFactory(private=False, replaces=scs1)
        request = self.factory.get("/scoreset/{}/".format(scs.urn))
        request.user = UserFactory()
        response = ScoreSetDetailView.as_view()(request, urn=scs.urn)
        self.assertContains(response, ">" + scs2.urn + "<", count=1)


class TestCreateNewScoreSetView(TransactionTestCase, TestMessageMixin):
    """
    Test that the submission process does not allow invalid data through,
    and properly handles model creation.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.path = reverse_lazy("dataset:scoreset_new")
        self.template = "dataset/scoreset/new_scoreset.html"
        self.ref = ReferenceGenomeFactory()

        score_file, count_file, meta_file = make_files()
        self.post_data = {
            "experiment": [""],
            "replaces": [""],
            "private": ["on"],
            "short_description": ["an entry"],
            "data_usage_policy": [""],
            "title": ["title"],
            "abstract_text": [""],
            "method_text": [""],
            "sra_ids": [""],
            "doi_ids": [""],
            "pubmed_ids": [""],
            "keywords": [""],
            "uniprot-identifier": [""],
            "uniprot-offset": [""],
            "ensembl-identifier": [""],
            "ensembl-offset": [""],
            "refseq-identifier": [""],
            "refseq-offset": [""],
            "submit": ["submit"],
            "genome": [self.ref.pk],
            "wt_sequence": ["atcg"],
            "name": ["BRCA1"],
            "category": ["Protein coding"],
        }
        self.files = {constants.variant_score_data: score_file}
        self.user = UserFactory()
        self.username = self.user.username
        self.unencrypted_password = "secret_key"
        self.user.set_password(self.unencrypted_password)
        self.user.save()
        self.client.logout()

    def test_redirect_to_login_not_logged_in(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 302)

    def test_correct_tamplate_when_logged_in(self):
        self.client.login(
            username=self.username, password=self.unencrypted_password
        )
        response = self.client.get(self.path)
        self.assertTemplateUsed(response, self.template)

    def test_redirects_to_profile_after_success(self):
        data = self.post_data.copy()
        exp1 = ExperimentFactory()
        assign_user_as_instance_admin(self.user, exp1)
        data["experiment"] = [exp1.pk]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetCreateView.as_view()(request)

        # Redirects to scoreset_detail
        self.assertEqual(response.status_code, 302)

    def test_creates_new_reversion_instance(self):
        data = self.post_data.copy()
        exp1 = ExperimentFactory()
        assign_user_as_instance_admin(self.user, exp1)
        data["experiment"] = [exp1.pk]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)

        self.assertEqual(Version.objects.count(), 0)
        response = ScoreSetCreateView.as_view()(request)
        self.assertEqual(Version.objects.count(), 1)

    def test_reference_map_created(self):
        data = self.post_data.copy()
        exp1 = ExperimentFactory()
        assign_user_as_instance_admin(self.user, exp1)
        data["experiment"] = [exp1.pk]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetCreateView.as_view()(request)

        # Redirects to scoreset_detail
        self.assertEqual(response.status_code, 302)

        scoreset = ScoreSet.objects.order_by("-urn").first()
        self.assertIsNotNone(scoreset.get_target())
        targetgene = scoreset.get_target()

        reference_map = targetgene.get_reference_maps().first()
        genome = reference_map.get_reference_genome()

        self.assertEqual(genome.get_short_name(), self.ref.get_short_name())
        self.assertEqual(
            genome.get_organism_name(), self.ref.get_organism_name()
        )

    def test_experiment_options_are_restricted_to_admin_instances(self):
        exp1 = ExperimentFactory()
        exp2 = ExperimentFactory()
        assign_user_as_instance_admin(self.user, exp1)
        assign_user_as_instance_viewer(self.user, exp2)
        request = self.factory.get("/scoreset/new/")
        request.user = self.user

        response = ScoreSetCreateView.as_view()(request)
        self.assertContains(response, "{} | {}".format(exp1.urn, exp1.title))
        self.assertNotContains(
            response, "{} | {}".format(exp2.urn, exp2.title)
        )

    def test_experiment_options_are_restricted_to_editor_instances(self):
        exp1 = ExperimentFactory()
        exp2 = ExperimentFactory()
        assign_user_as_instance_admin(self.user, exp1)
        assign_user_as_instance_viewer(self.user, exp2)
        request = self.factory.get("/scoreset/new/")
        request.user = self.user

        response = ScoreSetCreateView.as_view()(request)
        self.assertContains(response, "{} | {}".format(exp1.urn, exp1.title))
        self.assertNotContains(
            response, "{} | {}".format(exp2.urn, exp2.title)
        )

    def test_replaces_options_are_restricted_to_admin_instances(self):
        exp1 = ExperimentFactory()
        scs_1 = ScoreSetFactory(experiment=exp1, private=False)
        scs_2 = ScoreSetFactory(experiment=exp1, private=False)
        assign_user_as_instance_admin(self.user, scs_1)
        assign_user_as_instance_viewer(self.user, scs_2)

        request = self.factory.get("/scoreset/new/")
        request.user = self.user

        response = ScoreSetCreateView.as_view()(request)
        self.assertContains(response, "{} | {}".format(scs_1.urn, scs_1.title))
        self.assertNotContains(
            response, "{} | {}".format(scs_2.urn, scs_2.title)
        )

    def test_replaces_options_are_restricted_to_editor_instances(self):
        exp1 = ExperimentFactory()
        scs_1 = ScoreSetFactory(experiment=exp1, private=False)
        scs_2 = ScoreSetFactory(experiment=exp1, private=False)
        assign_user_as_instance_editor(self.user, scs_1)
        assign_user_as_instance_viewer(self.user, scs_2)

        request = self.factory.get("/scoreset/new/")
        request.user = self.user

        response = ScoreSetCreateView.as_view()(request)
        self.assertContains(response, "{} | {}".format(scs_1.urn, scs_1.title))
        self.assertNotContains(
            response, "{} | {}".format(scs_2.urn, scs_2.title)
        )

    def test_can_submit_and_create_scoreset_when_forms_are_valid(self):
        data = self.post_data.copy()
        scs1 = ScoreSetFactory(private=False)
        assign_user_as_instance_admin(self.user, scs1)
        assign_user_as_instance_admin(self.user, scs1.experiment)
        data["experiment"] = [scs1.parent.pk]
        data["replaces"] = [scs1.pk]
        data["keywords"] = ["protein", "kinase"]
        data["abstract_text"] = "Hello world"
        data["method_text"] = "foo bar"

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetCreateView.as_view()(request)

        # Redirects to profile
        self.assertEqual(response.status_code, 302)
        if ScoreSet.objects.all()[0].urn == scs1.urn:
            scoreset = ScoreSet.objects.all()[1]
        else:
            scoreset = ScoreSet.objects.all()[0]
        self.assertEqual(scoreset.experiment, scs1.parent)
        self.assertEqual(scoreset.replaces, scs1)
        self.assertEqual(scoreset.keywords.count(), 2)
        self.assertEqual(scoreset.abstract_text, "Hello world")
        self.assertEqual(scoreset.method_text, "foo bar")
        self.assertEqual(scoreset.method_text, "foo bar")
        self.assertEqual(scoreset.target.name, "BRCA1")
        self.assertEqual(scoreset.target.wt_sequence.sequence, "ATCG")

    def test_calls_create_variants(self):
        data = self.post_data.copy()
        exp = ExperimentFactory()
        assign_user_as_instance_admin(self.user, exp)
        data["experiment"] = [exp.pk]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)

        form_data = {k: v[0] for k, v in data.items()}
        form = ScoreSetForm(files=self.files, data=form_data, user=self.user)
        self.assertTrue(form.is_valid())

        with mock.patch(
            "dataset.views.scoreset.create_variants.apply_async"
        ) as create_mock:
            ScoreSetCreateView.as_view()(request)
            create_mock.assert_called_once()
            scores, counts, index = form.serialize_variants()
            expected = create_mock.call_args[1]["kwargs"]
            expected_socres = expected.pop("scores_records")
            expected_counts = expected.pop("counts_records")
            self.assertEqual(
                {
                    "user_pk": self.user.pk,
                    "scoreset_urn": ScoreSet.objects.first().urn,
                    "index": index,
                    "dataset_columns": form.dataset_columns,
                },
                expected,
            )
            assert_frame_equal(scores, expected_socres)
            assert_frame_equal(counts, expected_counts)

    def test_invalid_form_does_not_redirect(self):
        data = self.post_data.copy()
        data["experiment"] = ["wrong_pk"]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetCreateView.as_view()(request)

        self.assertEqual(ScoreSet.objects.count(), 0)
        self.assertEqual(response.status_code, 200)

    def test_scoreset_created_with_current_user_as_admin(self):
        data = self.post_data.copy()
        exp1 = ExperimentFactory()
        assign_user_as_instance_admin(self.user, exp1)
        data["experiment"] = [exp1.pk]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        _ = ScoreSetCreateView.as_view()(request)

        scs = ScoreSet.objects.all()[0]
        self.assertTrue(self.user in scs.administrators)

    def test_failed_submission_adds_extern_identifier_to_context(self):
        fs = [
            (SraIdentifierFactory, "sra_ids"),
            (PubmedIdentifierFactory, "pubmed_ids"),
            (DoiIdentifierFactory, "doi_ids"),
        ]
        for factory, field in fs:
            data = self.post_data.copy()
            instance = factory()
            data[field] = [instance.identifier]

            request = self.create_request(
                method="post", path=self.path, data=data
            )
            request.user = self.user
            response = ScoreSetCreateView.as_view()(request)

            self.assertContains(response, instance.identifier)

    def test_failed_submission_adds_new_extern_identifier_to_context(self):
        fs = [
            (SraIdentifierFactory, "sra_ids"),
            (PubmedIdentifierFactory, "pubmed_ids"),
            (DoiIdentifierFactory, "doi_ids"),
        ]
        for factory, field in fs:
            data = self.post_data.copy()
            instance = factory()
            value = instance.identifier
            data[field] = [value]
            instance.delete()

            request = self.create_request(
                method="post", path=self.path, data=data
            )
            request.user = self.user
            response = ScoreSetCreateView.as_view()(request)

            self.assertContains(response, instance.identifier)

    def test_failed_submission_adds_keywords_to_context(self):
        data = self.post_data.copy()
        kw = KeywordFactory()
        data["keywords"] = ["protein", kw.text]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        response = ScoreSetCreateView.as_view()(request)

        self.assertContains(response, "protein")
        self.assertContains(response, kw.text)

    def test_failed_submission_adds_uniprot_ids_to_context(self):
        data = self.post_data.copy()
        up = UniprotIdentifierFactory()
        data["uniprot-offset-identifier"] = ["P12345", up.identifier]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        response = ScoreSetCreateView.as_view()(request)

        self.assertContains(response, "P12345")
        self.assertContains(response, up.identifier)

    def test_failed_submission_adds_refseq_ids_to_context(self):
        data = self.post_data.copy()
        id_ = RefseqIdentifierFactory()
        data["ensembl-offset-identifier"] = ["RefSeq", id_.identifier]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        response = ScoreSetCreateView.as_view()(request)

        self.assertContains(response, "RefSeq")
        self.assertContains(response, id_.identifier)

    def test_failed_submission_adds_ensembl_ids_to_context(self):
        data = self.post_data.copy()
        id_ = EnsemblIdentifierFactory()
        data["refseq-offset-identifier"] = ["Ensembl", id_.identifier]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        response = ScoreSetCreateView.as_view()(request)

        self.assertContains(response, "Ensembl")
        self.assertContains(response, id_.identifier)

    def test_does_not_add_user_as_admin_to_selected_parent(self):
        data = self.post_data.copy()
        exp1 = ExperimentFactory()
        assign_user_as_instance_editor(self.user, exp1)
        data["experiment"] = [exp1.pk]
        data["publish"] = ["publish"]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        _ = ScoreSetCreateView.as_view()(request)

        scs = ScoreSet.objects.all()[0]
        self.assertNotIn(self.user, scs.parent.administrators)
        self.assertNotIn(self.user, scs.parent.parent.administrators)

    def test_ajax_submission_returns_json_response(self):
        data = self.post_data.copy()
        data["abstractText"] = "# Hello world"
        data["methodText"] = "## foo bar"
        data["markdown"] = [True]

        request = self.factory.get(
            path=self.path, data=data, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        request.user = self.user
        response = ScoreSetCreateView.as_view()(request)
        self.assertContains(response, "pandoc")

    def test_GET_experiment_param_locks_experiment_choice(self):
        exp1 = ExperimentFactory()
        exp2 = ExperimentFactory()
        assign_user_as_instance_editor(self.user, exp1)
        assign_user_as_instance_editor(self.user, exp2)

        request = self.factory.get(
            path=self.path + "/?experiment={}".format(exp1.urn)
        )
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetCreateView.as_view()(request)
        self.assertContains(response, exp1.urn)
        self.assertNotContains(response, exp2.urn)

    def test_GET_experiment_param_ignored_if_no_edit_permissions(self):
        exp1 = ExperimentFactory()
        exp2 = ExperimentFactory()
        assign_user_as_instance_editor(self.user, exp2)
        request = self.factory.get(
            path=self.path + "/?experiment={}".format(exp1.urn)
        )
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetCreateView.as_view()(request)
        self.assertNotContains(response, exp1.urn)
        self.assertContains(response, exp2.urn)

    def test_create_not_set_superusers_as_admins(self):
        su = UserFactory(is_superuser=True)
        ScoreSet.objects.all().delete()

        data = self.post_data.copy()
        exp1 = ExperimentFactory()
        assign_user_as_instance_admin(self.user, exp1)
        data["experiment"] = [exp1.pk]

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetCreateView.as_view()(request)

        # Redirects to scoreset_detail
        self.assertEqual(response.status_code, 302)

        scoreset = ScoreSet.objects.first()

        self.assertNotIn(su, scoreset.administrators)
        self.assertNotIn(su, scoreset.parent.administrators)
        self.assertNotIn(su, scoreset.parent.parent.administrators)

    def test_associates_new_uniprot_identifiers(self):
        data = self.post_data.copy()
        exp = ExperimentFactory(private=False)
        assign_user_as_instance_admin(self.user, exp)
        data["experiment"] = [exp.pk]

        obj = UniprotIdentifierFactory()
        identifier = obj.identifier
        data["uniprot-offset-identifier"] = identifier
        data["uniprot-offset-offset"] = 5
        obj.delete()

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetCreateView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        scoreset = ScoreSet.objects.order_by("-urn").first()
        self.assertEqual(
            scoreset.target.get_uniprot_offset_annotation().identifier.identifier,
            identifier,
        )
        self.assertEqual(
            scoreset.target.get_uniprot_offset_annotation().offset, 5
        )

    def test_associates_new_ensembl_identifiers(self):
        data = self.post_data.copy()
        exp = ExperimentFactory(private=False)
        assign_user_as_instance_admin(self.user, exp)
        data["experiment"] = [exp.pk]

        obj = EnsemblIdentifierFactory()
        identifier = obj.identifier
        data["ensembl-offset-identifier"] = identifier
        data["ensembl-offset-offset"] = 5
        obj.delete()

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetCreateView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        scoreset = ScoreSet.objects.order_by("-urn").first()
        self.assertEqual(
            scoreset.target.get_ensembl_offset_annotation().identifier.identifier,
            identifier,
        )
        self.assertEqual(
            scoreset.target.get_ensembl_offset_annotation().offset, 5
        )

    def test_associates_new_refseq_identifiers(self):
        data = self.post_data.copy()
        exp = ExperimentFactory(private=False)
        assign_user_as_instance_admin(self.user, exp)
        data["experiment"] = [exp.pk]

        obj = RefseqIdentifierFactory()
        identifier = obj.identifier
        data["refseq-offset-identifier"] = identifier
        data["refseq-offset-offset"] = 5
        obj.delete()

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetCreateView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        scoreset = ScoreSet.objects.order_by("-urn").first()
        self.assertEqual(
            scoreset.target.get_refseq_offset_annotation().identifier.identifier,
            identifier,
        )
        self.assertEqual(
            scoreset.target.get_refseq_offset_annotation().offset, 5
        )


class TestEditScoreSetView(TransactionTestCase, TestMessageMixin):
    """
    Test that the submission process does not allow invalid data through,
    and properly handles model creation.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.path = "/profile/edit/scoreset/{}/"
        self.template = "dataset/scoreset/update_scoreset.html"
        self.ref = ReferenceGenomeFactory()

        score_file, count_file, meta_file = make_files()
        self.post_data = {
            "experiment": [""],
            "replaces": [""],
            "private": ["on"],
            "short_description": "an entry",
            "data_usage_policy": "",
            "title": "title",
            "abstract_text": [""],
            "method_text": [""],
            "sra_ids": [""],
            "doi_ids": [""],
            "pubmed_ids": [""],
            "keywords": [""],
            "uniprot-identifier": [""],
            "uniprot-offset": [""],
            "ensembl-identifier": [""],
            "ensembl-offset": [""],
            "refseq-identifier": [""],
            "refseq-offset": [""],
            "submit": ["submit"],
            "genome": [self.ref.pk],
            "wt_sequence": "atcg",
            "name": "BRCA1",
            "category": ["Protein coding"],
            "publish": [""],
        }
        self.files = {constants.variant_score_data: score_file}
        self.user = UserFactory()
        self.username = self.user.username
        self.unencrypted_password = "secret_key"
        self.user.set_password(self.unencrypted_password)
        self.user.save()
        self.client.logout()

    def test_correct_tamplate_when_logged_in(self):
        scs = ScoreSetFactory()
        assign_user_as_instance_admin(self.user, scs)
        self.client.login(
            username=self.username, password=self.unencrypted_password
        )
        response = self.client.get(self.path.format(scs.urn))
        self.assertTemplateUsed(response, self.template)

    def test_requires_login(self):
        self.client.logout()
        obj = ScoreSetFactory()
        response = self.client.get(self.path.format(obj.urn))
        self.assertEqual(response.status_code, 302)

    def test_404_object_not_found(self):
        obj = ScoreSetFactory()
        urn = obj.urn
        request = self.factory.get(self.path.format(urn))
        request.user = self.user
        obj.delete()
        with self.assertRaises(Http404):
            ScoreSetEditView.as_view()(request, urn=urn)

    def test_redirect_to_profile_if_no_permission(self):
        scs = ScoreSetFactory()
        assign_user_as_instance_viewer(self.user, scs)

        path = self.path.format(scs.urn)
        request = self.create_request(method="get", path=path)
        request.user = self.user

        response = ScoreSetEditView.as_view()(request, urn=scs.urn)
        self.assertEqual(response.status_code, 302)

    def test_calls_create_variants_and_notifies_user(self):
        # Catch admin patch and prevent it being called
        data = self.post_data.copy()
        user = UserFactory(is_superuser=True)
        user.email = "admin@admin.com"
        user.save()

        scs = ScoreSetFactory()
        assign_user_as_instance_admin(self.user, scs)
        assign_user_as_instance_admin(self.user, scs.parent)
        data["publish"] = ["publish"]
        data["experiment"] = [scs.parent.pk]

        path = self.path.format(scs.urn)
        request = self.create_request(method="post", path=path, data=data)
        request.user = self.user
        request.FILES.update(self.files)

        with mock.patch(
            "dataset.views.scoreset.create_variants.apply_async"
        ) as create_mock:
            ScoreSetEditView.as_view()(request, urn=scs.urn)
            create_mock.assert_called_once()
            scs.refresh_from_db()
            self.assertEqual(scs.processing_state, constants.processing)

            with mock.patch(
                "core.tasks.send_mail.apply_async"
            ) as notify_patch:
                create_variants.apply(**create_mock.call_args[1])
                self.assertEqual(notify_patch.call_count, 1)
                send_mail.apply(**notify_patch.call_args[1])
                self.assertEqual(len(mail.outbox), 1)
                scs.refresh_from_db()
                self.assertEqual(scs.processing_state, constants.success)

    def test_published_instance_returns_edit_only_mode_form(self):
        scs = ScoreSetFactory(private=False)
        assign_user_as_instance_admin(self.user, scs)
        assign_user_as_instance_admin(self.user, scs.parent)

        path = self.path.format(scs.urn)
        request = self.create_request(method="get", path=path)
        request.user = self.user
        request.FILES.update(self.files)

        response = ScoreSetEditView.as_view()(request, urn=scs.urn)
        self.assertNotContains(response, "id_score_data")
        self.assertNotContains(response, "id_count_data")
        self.assertNotContains(response, "id_meta_data")

    def test_resubmit_blank_uniprot_id_deletes_offset_instance(self):
        data = self.post_data.copy()
        scs = ScoreSetWithTargetFactory()
        UniprotOffsetFactory(
            target=scs.target, identifier=scs.target.uniprot_id
        )
        self.assertIsNotNone(scs.target.uniprot_id)
        self.assertIsNotNone(scs.target.get_uniprot_offset_annotation())

        assign_user_as_instance_admin(self.user, scs)
        assign_user_as_instance_admin(self.user, scs.parent)
        data["experiment"] = [scs.parent.pk]

        path = self.path.format(scs.urn)
        request = self.create_request(method="post", path=path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetEditView.as_view()(request, urn=scs.urn)

        # Redirects to profile
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(scs.target.uniprot_id, 1)
        self.assertEqual(UniprotOffset.objects.count(), 0)

        scs = ScoreSet.objects.first()
        self.assertIsNone(scs.target.get_uniprot_offset_annotation())

    def test_resubmit_blank_refseq_id_deletes_offset_instance(self):
        data = self.post_data.copy()
        scs = ScoreSetWithTargetFactory()
        RefseqOffsetFactory(target=scs.target, identifier=scs.target.refseq_id)
        self.assertIsNotNone(scs.target.refseq_id)
        self.assertIsNotNone(scs.target.get_refseq_offset_annotation())

        assign_user_as_instance_admin(self.user, scs)
        assign_user_as_instance_admin(self.user, scs.parent)
        data["experiment"] = [scs.parent.pk]

        path = self.path.format(scs.urn)
        request = self.create_request(method="post", path=path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetEditView.as_view()(request, urn=scs.urn)

        # Redirects to profile
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(scs.target.refseq_id, 1)
        self.assertEqual(RefseqOffset.objects.count(), 0)

        scs = ScoreSet.objects.first()
        self.assertIsNone(scs.target.get_refseq_offset_annotation())

    def test_resubmit_blank_ensembl_id_deletes_offset_instance(self):
        data = self.post_data.copy()
        scs = ScoreSetWithTargetFactory()
        EnsemblOffsetFactory(
            target=scs.target, identifier=scs.target.ensembl_id
        )

        self.assertIsNotNone(scs.target.ensembl_id)
        self.assertIsNotNone(scs.target.get_ensembl_offset_annotation())

        assign_user_as_instance_admin(self.user, scs)
        assign_user_as_instance_admin(self.user, scs.parent)
        data["experiment"] = [scs.parent.pk]

        path = self.path.format(scs.urn)
        request = self.create_request(method="post", path=path, data=data)
        request.user = self.user
        request.FILES.update(self.files)
        response = ScoreSetEditView.as_view()(request, urn=scs.urn)

        # Redirects to profile
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(scs.target.ensembl_id, 1)
        self.assertEqual(EnsemblOffset.objects.count(), 0)

        scs = ScoreSet.objects.first()
        self.assertIsNone(scs.target.get_ensembl_offset_annotation())

    def test_cannot_edit_processing_scoreset(self):
        scs = ScoreSetWithTargetFactory()
        scs.processing_state = constants.processing
        scs.save()
        path = self.path.format(scs.urn)
        assign_user_as_instance_admin(self.user, scs)
        self.client.login(
            username=self.user.username, password=self.user._password
        )
        response = self.client.get(path)
        self.assertEqual(response.status_code, 302)

    def test_creates_new_reversion_instance(self):
        instance = ScoreSetWithTargetFactory()
        data = self.post_data.copy()
        data["experiment"] = [instance.parent.pk]

        assign_user_as_instance_admin(self.user, instance)
        assign_user_as_instance_admin(self.user, instance.parent)

        request = self.create_request(method="post", path=self.path, data=data)
        request.user = self.user
        request.FILES.update(self.files)

        self.assertEqual(Version.objects.count(), 0)
        ScoreSetEditView.as_view()(request, urn=instance.urn)
        self.assertEqual(Version.objects.count(), 1)
