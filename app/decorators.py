from functools import wraps, update_wrapper
from .exceptions import AuthError


def login_required(func):
    @wraps(func)
    def wrap(info, *args, **kwargs):
        if not info.context.user.is_authenticated:
            raise AuthError()
        return func(info, *args, **kwargs)
    return wrap


# method_decorator that supports decorators with arguments
# https://code.djangoproject.com/ticket/13879
def method_decorator(decorator):
    """Converts a function decorator into a method decorator.

    This works properly for both: decorators with arguments and without them.
    The Django's version of this function just supports decorators
    with no arguments."""

    # For simple decorators, like @login_required, without arguments
    def _dec(func):
        def _wrapper(self, *args, **kwargs):
            def bound_func(*args2, **kwargs2):
                return func(self, *args2, **kwargs2)
            return decorator(bound_func)(*args, **kwargs)
        return wraps(func)(_wrapper)

    # Called everytime
    def _args(*argsx, **kwargsx):
        # Detect a simple decorator and call _dec for it
        if len(argsx) == 1 and callable(argsx[0]) and not kwargsx:
            return _dec(argsx[0])

        # Used for decorators with arguments, like @permission_required('something')  # noqa
        def _dec2(func):
            def _wrapper(self, *args, **kwargs):
                def bound_func(*args2, **kwargs2):
                    return func(self, *args2, **kwargs2)
                return decorator(*argsx, **kwargsx)(bound_func)(*args, **kwargs)  # noqa
            return wraps(func)(_wrapper)
        return _dec2

    update_wrapper(_args, decorator)
    # Change the name to aid debugging.
    _args.__name__ = 'method_decorator(%s)' % decorator.__name__
    return _args
