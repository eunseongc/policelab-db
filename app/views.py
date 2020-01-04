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
