from django.core.signals import request_finished, request_started


class DjangoDBManagementMiddleware:
    """
    A simple WSGI middleware that manually manages opening/closing db connections.

    Django normally does that as part of its own middleware chain, but we're using Trac's middleware
    so we must do this by hand.
    This hopefully prevents open connections from piling up.
    """

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        request_started.send(sender=self.__class__)
        try:
            for data in self.application(environ, start_response):
                yield data
        finally:
            request_finished.send(sender=self.__class__)
