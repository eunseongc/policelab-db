import os

from datetime import datetime
from django.contrib.gis.db import models
from django.conf import settings

from app.storage import OverwriteStorage


def qrcode_directory_path(instance, filename):
    path = 'case/{0}/qrcode/{1}'.format(instance.id, filename)
    return os.path.join(settings.MEDIA_ROOT_PREFIX, path)


def video_directory_path(instance, filename):
    path = 'case/{0}/video/{1}/{2}'.format(
        instance.case.id,
        instance.id,
        filename,
    )
    return os.path.join(settings.MEDIA_ROOT_PREFIX, path)


def image_directory_path(instance, filename):
    path = 'case/{0}/video/{1}/image/{2}/{3}'.format(
        instance.video.case.id,
        instance.video.id,
        instance.id,
        filename,
    )
    return os.path.join(settings.MEDIA_ROOT_PREFIX, path)


class Case(models.Model):
    class Meta:
        verbose_name_plural = 'cases'

    # Case name
    name = models.CharField(max_length=255)

    # Token for each case (Provided when QR code is generated)
    token = models.CharField(max_length=255, unique=True)

    # Case overview
    text = models.TextField(blank=True, null=True)

    # Case expiration status
    is_expired = models.BooleanField(default=False)

    # Case creation date
    created_at = models.DateTimeField(auto_now_add=True)

    # QR code
    qrcode = models.FileField(upload_to=qrcode_directory_path)

    # Case location
    loc = models.CharField(max_length=300, null=True)

    # Time information of the case
    case_date = models.DateTimeField('case occured', blank=True, null=True)

    # Members related to the case
    members = models.ManyToManyField(
        'accounts.User',
        related_name='cases',
        blank=True,
    )

    def __str__(self):
        return self.name


class Video(models.Model):

    # Directory to upload file
    upload = models.FileField(upload_to=video_directory_path)

    # Video name
    name = models.CharField(max_length=300)

    # Video length
    length = models.IntegerField(default=0)

    # Upload date
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Video size
    size = models.IntegerField(default=0)

    # Meta data of the video
    meta = models.CharField(max_length=300, blank=True)

    # Location where the video is recorded
    location = models.PointField(blank=True, null=True)

    # Time information of the video
    rec_date = models.DateTimeField(default=datetime.now)

    # Whether video is preprocessed or not
    is_preprocessed = models.BooleanField(default=False)

    # Video thumbnail
    thumbnail = models.ImageField(storage=OverwriteStorage(),
                                  upload_to=video_directory_path)

    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='videos',
    )

    def __str__(self):
        return self.name


class Bookmark(models.Model):
    # Bookmark time
    sec = models.FloatField(default=0)

    # Bookmark code
    code = models.IntegerField(default=0)

    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name='bookmarks',
    )

    def __str__(self):
        return str(self.code)


class Image(models.Model):
    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name='images',
    )

    original = models.ImageField(upload_to=image_directory_path)
    query_feature = models.FileField(upload_to=image_directory_path)
    improvement = models.ImageField(
        storage=OverwriteStorage(),
        upload_to=image_directory_path,
        blank=True,
        null=True,
    )
