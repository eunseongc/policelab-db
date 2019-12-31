from django.utils.translation import gettext_lazy as _


class APIError(Exception):
    @property
    def code(self):
        raise NotImplementedError('code is not implemented')


class AlreadyExistedError(APIError):
    def __init__(self, message=_('already existed'), code=409):
        super().__init__(message)
        self._code = code

    @property
    def code(self):
        return self._code


class InvalidInputError(APIError):
    def __init__(self, message=_('invalid input'), code=400):
        super().__init__(message)
        self._code = code

    @property
    def code(self):
        return self._code


class AuthError(APIError):
    def __init__(self, message=_('login required'), code=401):
        super().__init__(message)
        self._code = code

    @property
    def code(self):
        return self._code
