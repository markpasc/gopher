import httplib2
from oauth.oauth import OAuthConsumer

from oauthclient import NetflixHttp
import settings


class Account(object):

    def configure(self):
        pass


class Netflix(Account):

    def configure(self):
        if hasattr(self, 'access_token'):
            return

        h = NetflixHttp()
        h.consumer = OAuthConsumer(settings.NETFLIX_KEY, settings.NETFLIX_SECRET)
        h.fetch_request_token()
        url = h.authorize_token()

        raw_input("Visit this URL to authorize your account:\n\n<%s>\n\nthen press Enter: "
            % url)

        self.access_token = h.fetch_access_token()

        # Confirm that the access token works.
        h.add_credentials(h.consumer, self.access_token, domain="api.netflix.com")
        response, content = h.request("http://api.netflix.com/users/current")

        if response.status != 200:
            raise ValueError('Could not authorize Netflix account')


class Hulu(Account):

    def configure(self):
        self.name = raw_input('Enter your Hulu username: ')

        # Confirm that that name has a queue.
        h = httplib2.Http()
        url = 'http://www.hulu.com/feed/queue/%s' % self.name
        response, content = h.request(url, method="HEAD")

        if response.status != 200:
            raise ValueError('Could not find Hulu account %r' % self.name)


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
