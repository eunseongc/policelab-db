import os

import graphene
import qrcode

from io import BytesIO

from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.core.files.base import ContentFile, File
from django.contrib.gis.geos import Point

from graphql_relay import from_global_id

from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphene_file_upload.scalars import Upload
from graphene_subscriptions.events import UPDATED, CREATED

from app.decorators import login_required, method_decorator
from app.exceptions import InvalidInputError

from .models import Case, Video
from .types import LocationType, LocationInput
from .tasks import create_gallery
from .utils import generate_thumbnail


class CaseNode(DjangoObjectType):
    class Meta:
        model = Case
        interfaces = (graphene.relay.Node, )
        filter_fields = ['token']

    def resolve_qrcode(self, *args, **kwargs):
        return settings.SERVER_URL_PREFIX + str(self.qrcode)


class VideoNode(DjangoObjectType):
    location = graphene.Field(LocationType)

    class Meta:
        model = Video
        interfaces = (graphene.relay.Node, )
        filter_fields = []
        exclude_fields = ['location']

    def resolve_upload(self, *args, **kwargs):
        return settings.SERVER_URL_PREFIX + str(self.upload)

    def resolve_thumbnail(self, *args, **kwargs):
        return settings.SERVER_URL_PREFIX + str(self.thumbnail)

    def resolve_location(self, *args, **kwargs):
        if self.location:
            return LocationType(latitude=self.location.y,
                                longitude=self.location.x)
        return None


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

        qr_img = qrcode.make(settings.WEB_URL_PREFIX +
                             'case/upload/{}'.format(token))

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
        location = graphene.Field(LocationInput)
        upload = Upload()

    def mutate_and_get_payload(self, info, **input):
        try:
            case = Case.objects.get(token=input.get('token'))
        except Case.DoesNotExist:
            raise InvalidInputError(message=_('invalid token'))

        if case.is_expired:
            raise InvalidInputError(message=_('token is expired'))

        video = Video(case=case)
        video.upload = File(input.get('upload'), name=input.get('upload').name)

        location = input.get('location')

        if location:
            point = Point(location.longitude, location.latitude, srid=4326)
            video.location = point

        thumbnail_name = 'thumbnail.jpg'
        in_filename = os.path.join(settings.MEDIA_ROOT, str(video.upload))
        out_filename = os.path.join(os.path.dirname(in_filename),
                                    thumbnail_name)

        generate_thumbnail(in_filename, out_filename, 0, 512)

        video.thumbnail = File(open(out_filename, 'rb'), name=thumbnail_name)

        video.save()

        create_gallery.delay(video.id)

        return UploadVideo(video=video)


class Mutation:
    create_case = CreateCase.Field()
    upload_video = UploadVideo.Field()


class Subscription:
    case_video = graphene.Field(CaseNode, id=graphene.ID(required=True))

    @method_decorator(login_required)
    def resolve_case_video(root, info, **input):
        _id = int(from_global_id(input.get('id'))[1])

        return root.filter(
            lambda event: event.operation in [UPDATED, CREATED] and isinstance(
                event.instance, Video) and event.instance.case.id == _id).map(
                    lambda _: Case.objects.get(id=_id))
