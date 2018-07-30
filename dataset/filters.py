from django_filters import filters
from django_filters import FilterSet

from django.db.models import Q

from . import models


class DatasetModelFilter(FilterSet):
    """
    Filter for the base `DatasetModel` fields:
        - urn
        - title
        - short_description
        - abstract
        - method
        - doi_ids
        - sra_ids
        - pubmed_ids
        - keywords
        - contributor first name
        - contributor last name
        - contributor username
        - contributor display name
    """
    URN = 'urn'
    TITLE = 'title'
    DESCRIPTION = 'description'
    ABSTRACT = 'abstract'
    METHOD = 'method'
    DOI = 'doi'
    SRA = 'sra'
    PUBMED = 'pubmed'
    KEYWORD = 'keyword'
    FIRST_NAME = 'first_name'
    LAST_NAME = 'last_name'
    USERNAME = 'username'
    DISPLAY_NAME = 'display_name'
    
    class Meta:
        fields = (
            'title', 'description', 'abstract', 'method',
            'doi', 'sra', 'pubmed', 'first_name', 'last_name',
            'username', 'display_name',
        )
        
    urn = filters.CharFilter(
        field_name='urn', lookup_expr='iexact')
    title = filters.CharFilter(
        field_name='title', lookup_expr='icontains')
    description = filters.CharFilter(
        field_name='short_description', lookup_expr='icontains')
    abstract = filters.CharFilter(
        field_name='abstract_text', lookup_expr='icontains')
    method = filters.CharFilter(
        field_name='method_text', lookup_expr='icontains')
    doi = filters.CharFilter(
        field_name='doi_ids__identifier', lookup_expr='icontains')
    sra = filters.CharFilter(
        field_name='sra_ids__identifier', lookup_expr='icontains')
    pubmed = filters.CharFilter(
        field_name='pubmed_ids__identifier', lookup_expr='icontains')
    keyword = filters.CharFilter(
        field_name='keywords__text', lookup_expr='icontains')
    
    first_name = filters.CharFilter(
        method='filter_contributor', lookup_expr='iexact')
    last_name = filters.CharFilter(
        method='filter_contributor', lookup_expr='iexact')
    username = filters.CharFilter(
        method='filter_contributor', lookup_expr='iexact')
    display_name = filters.CharFilter(method='filter_contributor_display_name')
    
    @property
    def qs(self):
        qs = super().qs
        user = getattr(self.request, 'user', None)
        if not user:
            return qs.filter(private=False)
        if not user.is_authenticated:
            return qs.filter(private=False)
        return qs
    
    def filter_contributor(self, queryset, name, value):
        instances_pks = []
        if not queryset.count():
            return queryset
        model = queryset.first().__class__
        for instance in queryset.all():
            contributors = instance.contributors().filter(**{name:value})
            if contributors.count():
                instances_pks.append(instance.pk)
        return model.objects.filter(pk__in=set(instances_pks))
        
    def filter_contributor_display_name(self, queryset, name, value):
        instances_pks = []
        if not queryset.count():
            return queryset
        model = queryset.first().__class__
        for instance in queryset.all():
            matches = any(
                [value.lower() in c.profile.get_display_name().lower()
                 for c in instance.contributors()])
            if matches:
                instances_pks.append(instance.pk)
        return model.objects.filter(pk__in=set(instances_pks))
        
        
class ExperimentSetFilterModel(DatasetModelFilter):
    """
    Filter `ExperimentSets` based on the fields in `DatasetModelFilter`.
    """
    class Meta(DatasetModelFilter.Meta):
        model = models.experimentset.ExperimentSet


class ExperimentFilter(DatasetModelFilter):
    """
    Filter `Experiment` based on the fields in `DatasetModelFilter` plus
    additional fields on scoresets:
        - licence
        - target
        - species
        - genome
        - uniprot
        - ensembl
        - refseq
    """
    LICENCE = 'licence'
    TARGET = 'target'
    SPECIES = 'species'
    GENOME = 'genome'
    UNIPROT = 'uniprot'
    ENSEMBL = 'ensembl'
    REFSEQ = 'refseq'
    
    class Meta(DatasetModelFilter.Meta):
        model = models.experiment.Experiment
        fields = DatasetModelFilter.Meta.fields + (
            'licence', 'genome', 'target', 'species',
            'uniprot', 'ensembl', 'refseq'
        )

    licence = filters.CharFilter(method='filter_licence')
    genome = filters.CharFilter(method='filter_genome')
    target = filters.CharFilter(
        field_name='scoresets__target__name', lookup_expr='icontains'
    )
    species = filters.CharFilter(
        field_name='scoresets__target__reference_maps__genome__species_name',
        lookup_expr='icontains'
    )
    uniprot = filters.CharFilter(
        field_name='scoresets__target__uniprot_id__identifier',
        lookup_expr='iexact'
    )
    ensembl = filters.CharFilter(
        field_name='scoresets__target__ensembl_id__identifier',
        lookup_expr='iexact'
    )
    refseq = filters.CharFilter(
        field_name='scoresets__target__refseq_id__identifier',
        lookup_expr='iexact'
    )

    def filter_licence(self, queryset, name, value):
        q = Q(**{'scoresets__licence__short_name__icontains': value}) | \
            Q(**{'scoresets__licence__long_name__icontains': value})
        return queryset.filter(q)

    def filter_genome(self, queryset, name, value):
        genome_field = 'scoresets__target__reference_maps__genome'
        short_name = '{}__short_name__iexact'.format(genome_field)
        assembly_id = '{}__genome_id__identifier__iexact'.format(genome_field)
        q = Q(**{short_name: value}) | Q(**{assembly_id: value})
        return queryset.filter(q)
        
    
class ScoreSetFilter(DatasetModelFilter):
    """
    Filter `ScoreSet` based on the fields in `DatasetModelFilter` plus
    additional fields:
        - licence
        - target
        - species
        - genome
        - uniprot
        - ensembl
        - refseq
    """
    LICENCE = 'licence'
    TARGET = 'target'
    SPECIES = 'species'
    GENOME = 'genome'
    UNIPROT = 'uniprot'
    ENSEMBL = 'ensembl'
    REFSEQ = 'refseq'
    
    class Meta(DatasetModelFilter.Meta):
        model = models.scoreset.ScoreSet
        fields = DatasetModelFilter.Meta.fields + (
            'licence', 'genome', 'target', 'species',
            'uniprot', 'ensembl', 'refseq'
        )

    licence = filters.CharFilter(method='filter_licence')
    genome = filters.CharFilter(method='filter_genome')
    target = filters.CharFilter(
        field_name='target__name', lookup_expr='icontains'
    )
    species = filters.CharFilter(
        field_name='target__reference_maps__genome__species_name',
        lookup_expr='icontains'
    )
    uniprot = filters.CharFilter(
        field_name='target__uniprot_id__identifier',
        lookup_expr='iexact'
    )
    ensembl = filters.CharFilter(
        field_name='target__ensembl_id__identifier',
        lookup_expr='iexact'
    )
    refseq = filters.CharFilter(
        field_name='target__refseq_id__identifier',
        lookup_expr='iexact'
    )
    
    def filter_licence(self, queryset, name, value):
        q = Q(licence__short_name__icontains=value) | \
             Q(licence__long_name__icontains=value)
        return queryset.filter(q)
        
    def filter_genome(self, queryset, name, value):
        genome_field = 'target__reference_maps__genome'
        short_name = '{}__short_name__iexact'.format(genome_field)
        assembly_id = '{}__genome_id__identifier__iexact'.format(genome_field)
        q = Q(**{short_name: value}) | Q(**{assembly_id: value})
        return queryset.filter(q)