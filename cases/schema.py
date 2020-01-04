import graphene
import qrcode

from io import BytesIO

from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.core.files.base import ContentFile

from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphene_file_upload.scalars import Upload

from app.decorators import login_required, method_decorator
from app.exceptions import InvalidInputError

from .models import Case, Video


class CaseNode(DjangoObjectType):
    class Meta:
        model = Case
        interfaces = (graphene.relay.Node, )
        filter_fields = ['token']

    def resolve_qrcode(self, *args, **kwargs):
        return settings.SERVER_URL_PREFIX + str(self.qrcode)


class VideoNode(DjangoObjectType):
    class Meta:
        model = Video
        interfaces = (graphene.relay.Node, )
        filter_fields = []

    def resolve_upload(self, *args, **kwargs):
        return settings.SERVER_URL_PREFIX + str(self.upload)


class Query:
    case = graphene.Field(CaseNode, token=graphene.String(required=True))
    videos = DjangoFilterConnectionField(VideoNode)

    def resolve_case(self, info, **input):
        try:
            case = Case.objects.get(token=input.get('token'))
            return case
        except Case.DoesNotExist:
            return None


class CreateCase(graphene.relay.ClientIDMutation):
    case = graphene.Field(CaseNode)

    class Input:
        name = graphene.String(required=True)
        text = graphene.String(required=True)

    @method_decorator(login_required)
    def mutate_and_get_payload(self, info, **input):
        name = input.get('name')
        text = input.get('text')
        token = get_random_string(length=16)

        qr_img = qrcode.make(settings.WEB_URL_PREFIX + 'case/{}'.format(token))

        f = BytesIO()
        qr_img.save(f, format='png')

        case = Case.objects.create(
            name=name,
            text=text,
            token=token,
        )

        case.qrcode.save(token + '.png', ContentFile(f.getvalue()))
        case.members.set([info.context.user])

        f.close()

        return CreateCase(case=case)


class UploadVideo(graphene.relay.ClientIDMutation):
    video = graphene.Field(VideoNode, required=True)

    class Input:
        token = graphene.String(required=True)
        upload = Upload()

    def mutate_and_get_payload(self, info, **input):
        try:
            case = Case.objects.get(token=input.get('token'))
        except Case.DoesNotExist:
            raise InvalidInputError(message=_('invalid token'))

        if case.is_expired:
            raise InvalidInputError(message=_('token is expired'))

        video = Video.objects.create(case=case)
        video.upload.save(input.get('upload').name, input.get('upload'))

        return UploadVideo(video=video)


class Mutation:
    create_case = CreateCase.Field()
    upload_video = UploadVideo.Field()
