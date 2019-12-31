import graphene
from graphene_django import DjangoObjectType


class CountableConnection(graphene.Connection):
    total_count = graphene.Int()

    class Meta:
        abstract = True

    @staticmethod
    def resolve_total_count(root, *args, **kwargs):
        return root.length


# https://github.com/graphql-python/graphene-django/issues/162#issuecomment-297977519
# Expose count field in ConnectionField
class CountingObjectType(DjangoObjectType):

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass_with_meta__(cls, **options):
        connection = CountableConnection.create_type(
            '{}Connection'.format(cls.__name__), node=cls,
        )

        super().__init_subclass_with_meta__(connection=connection, **options)
