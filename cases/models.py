from django.contrib.gis.db import models
from django.conf import settings

import os


def qrcode_directory_path(instance, filename):
    path = 'case/{0}/qrcode/{1}'.format(instance.id, filename)
    return os.path.join(settings.MEDIA_ROOT_PREFIX, path)


def video_directory_path(instance, filename):
    path = 'case/{0}/video/{1}'.format(instance.case.id, filename)
    return os.path.join(settings.MEDIA_ROOT_PREFIX, path)


class Case(models.Model):
    class Meta:
        verbose_name_plural = 'cases'

    # 사건 이름
    name = models.CharField(max_length=255)

    # 사건 고유 토큰 (QR 코드 �:w�성시)
    token = models.CharField(max_length=255, unique=True)

    # 사건 개요
    text = models.TextField(blank=True, null=True)

    # 사건 만료 여부
    is_expired = models.BooleanField(default=False)

    # 사건 생성 날짜
    created_at = models.DateTimeField(auto_now_add=True)

    # qrcode
    qrcode = models.FileField(upload_to=qrcode_directory_path)

    # 사건 발생 위치
    loc = models.CharField(max_length=300, null=True)

    # time information of 
    case_date = models.DateTimeField('case occured')

    # 사건과 관련된 사용자
    members = models.ManyToManyField(
        'accounts.User',
        related_name='cases',
        blank=True,
    )

    def __str__(self):
        return self.name


class Video(models.Model):

    # upload 파일 위치
    upload = models.FileField(upload_to=video_directory_path)

    # 영상 이름
    name = models.CharField(max_length=300)

    # 영상 길이
    length = models.IntegerField(default=0)

    # 영상 날짜
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # 영상 크기
    size = models.IntegerField(default=0)

    # 영상 메타 데이터
    meta = models.CharField(max_length=300, blank=True)

    # 영상 촬영 위치
    location = models.PointField(blank=True, null=True)

    # time information of video
    rec_date = models.DateTimeField('date recorded')    

    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='videos',
    )

    def __str__(self):
        return self.name


class Bookmark(models.Model):
    # 북마크 시간
    sec = models.FloatField(default=0)

    # 북마크 코드
    code = models.IntegerField(default=0)

    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name='bookmarks',
    )

    def __str__(self):
        return str(self.code)
