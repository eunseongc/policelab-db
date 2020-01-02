from django.db import models


def video_directory_path(instance, filename):
    return 'case/{0}/{1}'.format(instance.case.id, filename)


class Case(models.Model):
    class Meta:
        verbose_name_plural = 'cases'

    # 사건 이름
    name = models.CharField(max_length=255)

    # 사건 고유 토큰 (QR 코드 생성시)
    token = models.CharField(max_length=255, unique=True)

    # 사건 개요
    text = models.TextField(blank=True, null=True)

    # 사건 만료 여부
    is_expired = models.BooleanField(default=False)

    # 사건 생성 날짜
    created_at = models.DateTimeField(auto_now_add=True)

    # 사건과 관련된 사용자
    members = models.ManyToManyField(
        'accounts.User',
        related_name='cases',
        blank=True,
    )


class Video(models.Model):

    # upload 파일 위치
    upload = models.FileField(upload_to=video_directory_path)

    # public file link url
    link = models.CharField(max_length=255)

    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='videos',
    )
