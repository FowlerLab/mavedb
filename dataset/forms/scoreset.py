import json
from collections import OrderedDict

from django import forms as forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import ugettext

from dataset import constants as constants
from main.models import Licence
from variant.models import Variant
from variant.validators import (
    validate_variant_rows, validate_scoreset_columns_match_variant
)
from ..forms.base import DatasetModelForm
from ..models.experiment import Experiment
from ..models.scoreset import ScoreSet
from ..validators import (
    validate_scoreset_score_data_input,
    validate_csv_extension, validate_json_extension,
    validate_scoreset_count_data_input,
    validate_scoreset_json,
)


class ScoreSetForm(DatasetModelForm):
    """
    This form is presented on the create new scoreset view. It contains
    all the validation logic required to ensure that a score dataset and
    counts dataset are parsed into valid Variant objects that are associated
    with the created scoreset. It also defines additional validation for
    the `replaces` field in scoreset to make sure that the selected
    `ScoreSet` is a member of the selected `Experiment` instance.
    """
    class Meta(DatasetModelForm.Meta):
        model = ScoreSet
        fields = DatasetModelForm.Meta.fields + (
            'experiment',
            'licence',
            'replaces',
        )

    score_data = forms.FileField(
        required=False, label="Variant score data",
        validators=[validate_scoreset_score_data_input, validate_csv_extension],
        widget=forms.widgets.FileInput(attrs={"accept": "csv"})
    )
    count_data = forms.FileField(
        required=False, label="Variant count data",
        validators=[validate_scoreset_count_data_input, validate_csv_extension],
        widget=forms.widgets.FileInput(attrs={"accept": "csv"})
    )
    meta_data = forms.FileField(
        required=False, label="Variant metadata",
        validators=[validate_json_extension],
        widget=forms.widgets.FileInput(attrs={"accept": "json"})
    )

    def __init__(self, *args, **kwargs):
        self.field_order = ('experiment', 'replaces', 'licence',) + \
                           self.FIELD_ORDER + \
                           ('score_data', 'count_data', 'meta_data',)
        # If an experiment is passed in we can used to it to seed initial
        # replaces and m2m field selections.
        if 'experiment' in kwargs:
            self.experiment = kwargs.pop('experiment')
        else:
            self.experiment = None
        super().__init__(*args, **kwargs)

        if self.instance.pk is not None:
            self.dataset_columns = self.instance.dataset_columns.copy()
        else:
            # This will be used later after score/count files have been read in
            # to store the headers.
            self.dataset_columns = {
                constants.score_columns: [],
                constants.count_columns: [],
            }

        self.fields['experiment'] = forms.ModelChoiceField(
            queryset=None, required=True, widget=forms.Select(
                attrs={"class": "form-control"}))
        self.fields['replaces'] = forms.ModelChoiceField(
            queryset=ScoreSet.objects.none(), required=False,
            widget=forms.Select(
                attrs={"class": "form-control"}))
        self.fields['licence'] = forms.ModelChoiceField(
            queryset=Licence.objects.all(), required=False,
            widget=forms.Select(
                attrs={"class": "form-control "}))

        self.fields["replaces"].required = False
        self.set_replaces_options()
        self.set_experiment_options()

        self.fields["licence"].required = False
        if not self.fields["licence"].initial:
            self.fields["licence"].initial = Licence.get_default()
        self.fields["licence"].empty_label = 'Default'

    def clean_licence(self):
        licence = self.cleaned_data.get("licence", None)
        if not licence:
            licence = Licence.get_default()
        return licence

    def clean_replaces(self):
        scoreset = self.cleaned_data.get("replaces", None)
        experiment = self.cleaned_data.get("experiment", None)
        if scoreset is not None and experiment is not None:
            if scoreset not in experiment.scoresets.all():
                raise ValidationError(
                    ugettext(
                        "Replaces field selection must be a member of the "
                        "selected experiment."
                    ))
        return scoreset

    def clean_score_data(self):
        score_file = self.cleaned_data.get("score_data", None)
        if not score_file:
            return {}
        # Don't need to wrap this in a try/catch as the form
        # will catch any Validation errors automagically.
        #   Valdator must check the following:
        #       Header has hgvs and at least one other column
        #       Number of rows does not match header
        #       Datatypes of rows match
        #       HGVS string is a valid hgvs string
        #       Hgvs appears more than once in rows
        header, hgvs_score_map = validate_variant_rows(score_file)
        self.dataset_columns[constants.score_columns] = header
        return hgvs_score_map

    def clean_count_data(self):
        count_file = self.cleaned_data.get("count_data", None)
        if not count_file:
            self.dataset_columns[constants.count_columns] = []
            return {}
        header, hgvs_count_map = validate_variant_rows(count_file)
        self.dataset_columns[constants.count_columns] = header
        return hgvs_count_map

    def clean_meta_data(self):
        meta_file = self.cleaned_data.get("meta_data", None)
        if meta_file is None:
            return {}
        try:
            dict_ = json.load(meta_file)
            return dict_
        except ValueError as error:
            raise ValidationError(
                "Incorrectly formatted json file: {}".format(error)
            )

    @staticmethod
    def _fill_in_missing(hgvs_keys, mapping):
        # This function has side-effects - it creates new keys in the default
        # dict `mapping`.
        for key in hgvs_keys:
            _ = mapping[key]
        return mapping

    def clean(self):
        if self.errors:
            # There are errors, maybe from the `clean_<field_name>` methods.
            # End here and run the parent method to quickly return the form.
            return super().clean()

        cleaned_data = super().clean()

        # Ensure the user is not attempting to change an experiment that
        # has already been set
        parent = cleaned_data.get('experiment', None)
        if 'experiment' in self.fields and self.instance.pk is not None:
            if self.instance.parent != parent:
                self.add_error(
                    None if 'experiment' not in self.fields else 'experiment',
                    "MaveDB does not currently support changing a "
                    "previously assigned Experiment."
                )
                return cleaned_data

        # Indicates that a new scoreset is being created
        scores_required = self.instance.pk is None

        hgvs_score_map = cleaned_data.get("score_data", {})
        hgvs_count_map = cleaned_data.get("count_data", {})
        meta_data = cleaned_data.get("meta_data", {})

        has_score_data = len(hgvs_score_map) > 0
        has_count_data = len(hgvs_count_map) > 0
        has_meta_data = len(meta_data) > 0

        if has_meta_data:
            self.instance.extra_metadata = meta_data

        # In edit mode, we have relaxed the requirement of uploading a score
        # dataset since one already exists.
        if scores_required and not has_score_data:
            self.add_error(
                None if 'score_data' not in self.fields else 'score_data',
                "You must upload a non-empty scores data file."
            )
            return cleaned_data

        # In edit mode if a user tries to submit a new count dataset without
        # an accompanying score dataset, this error will be thrown. We could
        # relax this but there is the potential that the user might upload
        # a new count dataset and forget to upload a new score dataset.
        if has_count_data and not has_score_data:
            self.add_error(
                None if 'score_data' not in self.fields else 'score_data',
                "You must upload an accompanying score data file when "
                "uploading a new count data file or replacing an "
                "existing one."
            )
            return cleaned_data

        if has_count_data:
            # Cross-populate the hgvs_score_map with every hgvs in counts
            # but not in scores.
            self._fill_in_missing(hgvs_count_map.keys(), hgvs_score_map)
        if has_count_data:
            # hgvs_score_map now contains all variants. We can then fill in the
            # missing hgvs values in the other maps.
            self._fill_in_missing(hgvs_score_map.keys(), hgvs_count_map)

        # Re-build the variants if any new files have been processed.
        # If has_count_data is true then has_score_data should also be true.
        # The reverse is not always true.
        if has_score_data:
            validate_scoreset_json(self.dataset_columns)
            variants = OrderedDict()

            for hgvs in hgvs_score_map.keys():
                scores_json = hgvs_score_map[hgvs]
                counts_json = hgvs_count_map[hgvs] if has_count_data else {}
                data = {
                    constants.variant_score_data: scores_json,
                    constants.variant_count_data: counts_json,
                }
                validate_scoreset_columns_match_variant(
                    self.dataset_columns, data)
                variant = Variant(hgvs=hgvs, data=data)
                variants[hgvs] = variant

            cleaned_data["variants"] = variants
        return cleaned_data

    @transaction.atomic
    def _save_m2m(self):
        variants = self.get_variants()
        if variants:  # No variants if in edit mode and no new files uploaded.
            self.instance.delete_variants()
            variant_kwargs_list = [
                {'hgvs': v.hgvs, 'data': v.data} for _, v in variants.items()]
            Variant.bulk_create(self.instance, variant_kwargs_list)
        super()._save_m2m()

    @transaction.atomic
    def save(self, commit=True):
        super().save(commit=commit)
        self.instance.dataset_columns = self.dataset_columns
        self.instance.save()
        return self.instance

    def get_variants(self):
        return self.cleaned_data.get('variants', {})

    def set_replaces_options(self):
        if 'replaces' in self.fields:
            admin_instances = self.user.profile.administrator_scoresets()
            editor_instances = self.user.profile.editor_scoresets()
            choices = set(
                [i.pk for i in admin_instances.union(editor_instances)]
            )
            if self.experiment is not None:
                choices &= set(
                    [i.pk for i in self.experiment.scoresets.all()]
                )
            scoresets_qs = ScoreSet.objects.filter(
                pk__in=choices).order_by("urn")
            self.fields["replaces"].queryset = scoresets_qs

    def set_experiment_options(self):
        if 'experiment' in self.fields:
            admin_instances = self.user.profile.administrator_experiments()
            editor_instances = self.user.profile.editor_experiments()
            choices = set(
                [i.pk for i in admin_instances.union(editor_instances)]
            )
            experiment_qs = Experiment.objects.filter(
                pk__in=choices).order_by("urn")
            self.fields["experiment"].queryset = experiment_qs
            if self.experiment is not None:
                choices_qs = Experiment.objects.filter(
                    pk__in=[self.experiment.pk]).order_by("urn")
                self.fields["experiment"].queryset = choices_qs
                self.fields["experiment"].initial = self.experiment

    @classmethod
    def from_request(cls, request, instance=None, prefix=None, initial=None):
        form = super().from_request(request, instance, prefix, initial)
        form.set_replaces_options()
        if 'experiment' in form.fields and instance is not None:
            choices_qs = Experiment.objects.filter(
                pk__in=[instance.experiment.pk]).order_by("urn")
            form.fields["experiment"].queryset = choices_qs
            form.fields["experiment"].initial = instance.experiment

        return form


class ScoreSetEditForm(ScoreSetForm):
    """
    Subset of the `ScoreSetForm`, which freezes all fields except `private`,
    `doi_id`, `keywords`, `abstract` and `method_desc`. Only these fields
    are editable.
    """
    class Meta(ScoreSetForm.Meta):
        model = ScoreSet

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.edit_mode = True
        self.fields.pop('experiment')
        self.fields.pop('score_data')
        self.fields.pop('count_data')
        self.fields.pop('meta_data')
        self.fields.pop('licence')
        self.fields.pop('replaces')
