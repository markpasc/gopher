

class Account(object):

    def configure(self):
        pass


class Netflix(Account):
    pass


class Hulu(Account):
    pass


services = {
    'netflix': Netflix,
    'hulu':    Hulu,
}


def account_for_service(service):
    try:
        service_class = services[service.lower()]
    except KeyError:
        raise ValueError('No such service %r' % service)

    return service_class
