from django import forms as forms
from django.db import transaction
from django.forms.models import BaseModelFormSet, inlineformset_factory, BaseInlineFormSet
from django.forms import modelformset_factory
from django.core.exceptions import ValidationError

from nested_formset import nestedformset_factory

from core.utilities import is_null

from .validators import (
    validate_interval_start_lteq_end,
    validate_wildtype_sequence,
    validate_gene_name,
    validate_at_least_one_map,
    validate_map_has_unique_reference_genome,
    validate_one_primary_map
)

from .models import (
    TargetGene,
    ReferenceMap,
    ReferenceGenome,
    GenomicInterval,
    WildTypeSequence,
)


# TargetGene
# ------------------------------------------------------------------------ #
class TargetGeneForm(forms.ModelForm):
    """
    Form for validating the fields required to instantiate the following:

        - :class:`WildTypeSequence`
        - :class:`TargetGene`

    The wildtype sequence will be created from `wt_sequence` and then
    associated with the :class:`TargetGene` instance that will be created
    upon saving.
    """
    class Meta:
        model = TargetGene
        fields = ('name', )

    wt_sequence = forms.CharField(
        label='Target wild-type sequence',
        required=True,
        widget=forms.Textarea(),
        validators=[validate_wildtype_sequence],
        error_messages={
            'required':
                'You must supply a wild-type sequence for your target.'
        },
    )
    target = forms.ModelChoiceField(
        label='Existing target', required=False,
        queryset=None,
        widget=forms.Select(
            attrs={"class": "form-control"})
    )

    def __init__(self, *args, **kwargs):
        self.field_order = ('target', 'name', 'wt_sequence')
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)

        instance = kwargs.get('instance', None)
        self.wt_sequence = None
        if instance and instance.get_wt_sequence():
            self.fields['wt_sequence'].initial = \
                instance.get_wt_sequence().get_sequence()

        self.set_target_gene_options()

        self.fields['name'].label = 'Target name'
        self.fields['name'].validators = [validate_gene_name]
        self.fields['name'].widget = forms.TextInput()
        self.fields['name'].error_messages.update(
            {'required': 'You must supply a name for your target.'})

    def clean_wt_sequence(self):
        sequence = self.cleaned_data.get('wt_sequence', None)
        if sequence is None:
            raise ValidationError("Sequence cannot be empty.")
        self.wt_sequence = sequence
        return sequence

    def set_target_gene_options(self):
        if 'target' in self.fields:
            choices = set()
            targets = TargetGene.objects.all()
            user_scoresets = self.user.profile.contributor_scoresets()
            for target in targets:
                scoreset = target.scoreset
                if scoreset.private and scoreset in user_scoresets:
                    choices.add(target.pk)
                elif not scoreset.private:
                    choices.add(target.pk)

            targets_qs = TargetGene.objects.filter(
                pk__in=choices).order_by("name")
            self.fields["target"].queryset = targets_qs
            self.fields["target"].choices = \
                [("", self.fields["target"].empty_label)] + [
                (t.pk, t.get_unique_name()) for t in targets_qs.all()
            ]
            self.fields["target"].initial = ""

    @transaction.atomic
    def save(self, commit=True):
        if not self.is_valid():
            raise ValidationError("Cannot save with invalid data.")

        if self.instance.get_wt_sequence() is not None:
            if isinstance(self.wt_sequence, str):
                self.instance.get_wt_sequence().sequence = self.wt_sequence

        if commit:
            if self.instance.get_wt_sequence() is None:
                self.instance.set_wt_sequence(
                    WildTypeSequence.objects.create(sequence=self.wt_sequence)
                )
            self.instance.get_wt_sequence().save()
            return super().save(commit=True)

        return super().save(commit=False)

    def clean(self):
        cleaned_data = super().clean()
        if not self.errors:
            wt_sequence = cleaned_data.get('wt_sequence', None)
            if not wt_sequence:
                raise ValidationError("You must supply a wild-type sequence.")
            self.wt_sequence = wt_sequence
        return cleaned_data


# GenomicInterval
# ------------------------------------------------------------------------ #
class GenomicIntervalForm(forms.ModelForm):
    """
    Form for validating interval input and instantiating a valid instance.
    """

    class Meta:
        model = GenomicInterval
        fields = ('start', 'end', 'chromosome', 'strand',)

    def __init__(self, *args, **kwargs):
        self.field_order = ('start', 'end', 'chromosome', 'strand')
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True

    def clean_start(self):
        start = self.cleaned_data.get('start', None)
        if is_null(start):
            raise ValidationError("A valid start coordinate is required.")
        return start

    def clean_end(self):
        end = self.cleaned_data.get('end', None)
        if is_null(end):
            raise ValidationError("An valid end coordinate is required.")
        return end

    def clean_chromosome(self):
        value = self.cleaned_data.get('chromosome', None)
        if is_null(value):
            raise ValidationError("A valid chromosome is required.")
        return value

    def clean_strand(self):
        value = self.cleaned_data.get('strand', None)
        if is_null(value):
            raise ValidationError("A valid strand is required.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data
        else:
            start = cleaned_data.get('start', None)
            end = cleaned_data.get('end', None)
            validate_interval_start_lteq_end(start, end)
            return cleaned_data

    def form_is_blank(self):
        start = self.cleaned_data.get("start")
        end = self.cleaned_data.get("end")
        chr_ = self.cleaned_data.get("chromosome")
        strand = self.cleaned_data.get("strand")
        return all([is_null(elem) for elem in [start, end, chr_, strand]])


class BaseGenomicIntervalFormSet(BaseInlineFormSet):
    """
    Formset which will validate multiple intervals against each other
    to ensure uniqueness.
    """
    model = GenomicInterval
    form_prefix = "genomic_interval_form"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'queryset' in kwargs:
            self.queryset = kwargs['queryset']
        else:
            self.queryset = GenomicInterval.objects.none()

    def has_errors(self):
        for form in self.forms:
            # These are not triggering for empty forms. Do them manually.
            form.full_clean()
            form.clean_start()
            form.clean_end()
            form.clean_chromosome()
            form.clean_strand()
        if self.non_form_errors():
            return True
        elif isinstance(self.errors, list):
            return any(self.errors)
        else:
            return bool(self.errors)

    def clean(self):
        if self.has_errors():
            return

        field_values = set()
        for form in self.forms:
            start = form.cleaned_data['start']
            end = form.cleaned_data['end']
            chromosome = form.cleaned_data['chromosome']
            strand = form.cleaned_data['strand']
            value = (start, end, str(chromosome).lower(), str(strand).lower())
            if value in field_values:
                raise ValidationError(
                    "You can not specify the same interval twice.")
            else:
                field_values.add(value)

    def save(self, reference_map=None, commit=True):
        if self.has_errors():
            return super().save(commit)
        if reference_map is not None:
            if reference_map.pk is None:
                raise ValueError(
                    "ReferenceMap must be saved before it can "
                    "be assigned as a related object."
                )
            for form in self.forms:
                form.instance.reference_map = reference_map

        for form in self.forms:
            if form.instance.pk is None and reference_map is None:
                raise ValueError(
                    "Cannot save a GenomicInterval without a "
                    "ReferenceMap instance."
                )

        return super().save(commit)


def create_genomic_interval_formset(extra=2, min_num=1,
                                    can_delete=False):
    return modelformset_factory(
        model=GenomicInterval,
        form=GenomicIntervalForm,
        formset=BaseGenomicIntervalFormSet,
        extra=extra,
        min_num=min_num,
        validate_min=True,
        can_delete=can_delete,
        fields=GenomicIntervalForm.Meta.fields,
    )


def create_inline_genomic_interval_formset(extra=2, min_num=1,
                                           can_delete=False):
    return inlineformset_factory(
        parent_model=ReferenceMap,
        model=GenomicInterval,
        form=GenomicIntervalForm,
        formset=BaseGenomicIntervalFormSet,
        extra=extra,
        min_num=min_num,
        validate_min=True,
        can_delete=can_delete,
        fields=GenomicIntervalForm.Meta.fields,
    )


# ReferenceMap
# ------------------------------------------------------------------------ #
class ReferenceMapForm(forms.ModelForm):
    """
    The reference_map form

    Parameters
    ----------
    annotations : `tuple`
        A tuple of annotations to validate the instance this form will create
        against. Useful for validating all annotations specify unique
        references.

    intervals : `tuple`
        A tuple of valid intervals to associate with the reference_map.
    """
    class Meta:
        model = ReferenceMap
        fields = ('is_primary', 'genome',)

    def __init__(self, *args, **kwargs):
        self.field_order = ('is_primary', 'genome',)
        super().__init__(*args, **kwargs)

        genome_field = self.fields['genome']
        genome_field.requried = True
        genome_field.queryset = ReferenceGenome.objects.all()
        genome_field.choices = \
            [("", genome_field.empty_label)] + [
                (r.pk, r.display_name()) for r in ReferenceGenome.objects.all()
            ]
        genome_field.initial = ""
        is_primary_field = self.fields['is_primary']

    def dummy_instance(self):
        if self.errors:
            return None
        return ReferenceMap(
            genome=self.cleaned_data.get('genome'),
            is_primary=self.cleaned_data.get('is_primary'),
        )

    def clean_genome(self):
        genome = self.cleaned_data.get('genome', None)
        if not genome:
            raise ValidationError("You must select a valid reference genome.")
        return genome


class PimraryReferenceMapForm(ReferenceMapForm):
    """
    Same as `ReferenceMapForm` except `is_primary` is popped and always
    sets as True.
    """
    def __init__(self, *args, **kwargs):
        super(PimraryReferenceMapForm, self).__init__(*args, **kwargs)
        self.fields.pop('is_primary')

    def clean_is_primary(self):
        return True


class BaseReferenceMapFormSet(BaseInlineFormSet):
    """
    Formset for handling the validation of :class:`ReferenceMap` instances
    against each other.
    """
    model = ReferenceMap

    def has_errors(self):
        if isinstance(self.errors, list):
            return any(len(dict_) for dict_ in self.errors)
        else:
            return bool(self.errors)

    def clean(self):
        if not self.has_errors():
            maps = [form.dummy_instance() for form in self.forms]
            validate_at_least_one_map(maps)
            validate_map_has_unique_reference_genome(maps)
            validate_one_primary_map(maps)

    def add_fields(self, form, index):
        super().add_fields(form, index)
        # save the formset in the 'nested' property
        print(form.prefix)
        form.nested = self.nested_formset_class(
            instance=form.instance,
            data=form.data if form.is_bound else None,
            files=form.files if form.is_bound else None,
            prefix='%s-%s' % (
                form.prefix,
                self.nested_formset_class.get_default_prefix()
            )
        )


def create_reference_map_interval_nested_formset(outer_kwargs, inner_kwargs):

    GenomicIntervalFormSet = create_inline_genomic_interval_formset(
        **inner_kwargs
    )
    NestedFormSet = inlineformset_factory(
        parent_model=TargetGene, model=ReferenceMap,
        form=ReferenceMapForm, formset=BaseReferenceMapFormSet,
        fields=ReferenceMapForm.Meta.fields, validate_min=True,
        **outer_kwargs
    )
    NestedFormSet.nested_formset_class = GenomicIntervalFormSet
    return NestedFormSet


# Mangement forms
# -------------------------------------------------------------------------- #
class ReferenceMapManagementForm(forms.Form):

    target = forms.ModelChoiceField(
        label='Existing target', required=False,
        queryset=None,
        widget=forms.Select()
    )