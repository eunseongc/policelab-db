import os
import json

from django.conf import settings
from django.http import FileResponse
from graphene_file_upload.django import FileUploadGraphQLView
from .exceptions import APIError


class CustomGraphQLView(FileUploadGraphQLView):
    @staticmethod
    def format_error(error):
        if hasattr(error, 'original_error') and error.original_error:
            formatted = {'message': str(error.original_error)}
            if isinstance(error.original_error, APIError):
                formatted['code'] = error.original_error.code
            return formatted

        return FileUploadGraphQLView.format_error(error)


def download_apk(requests):
    with open(os.path.join(settings.APK_DIR, 'release.json'), 'r') as f:
        info = json.load(f)

    return FileResponse(open(os.path.join(settings.APK_DIR, info['apk']), 'rb'))
