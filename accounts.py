from datetime import datetime

import httplib2
from oauth.oauth import OAuthConsumer
from elementtree import ElementTree

from oauthclient import NetflixHttp
from queue import Item
import settings


class Account(object):

    def configure(self):
        pass

    def queue(self):
        return ()


class Netflix(Account):

    def http(self, access_token=None):
        h = NetflixHttp()
        h.consumer = OAuthConsumer(settings.NETFLIX_KEY, settings.NETFLIX_SECRET)
        if access_token is not None:
            h.add_credentials(h.consumer, access_token, domain="api.netflix.com")
        return h

    def configure(self):
        if hasattr(self, 'access_token'):
            return

        h = self.http()
        h.fetch_request_token()
        url = h.authorize_token()

        raw_input("Visit this URL to authorize your account:\n\n<%s>\n\nthen press Enter: "
            % url)

        self.access_token = h.fetch_access_token()

        # Confirm that the access token works.
        h = self.http(self.access_token)
        response, content = h.request("http://api.netflix.com/users/current")
        if response.status != 200:
            raise ValueError('Could not authorize Netflix account')

        # Find the real user info.
        culink = ElementTree.fromstring(content)
        userlink = culink.find('./link')
        userhref = userlink.get('href')

        # Look for the user name.
        response, content = h.request(userhref)
        if response.status != 200:
            raise ValueError('Could not fetch Netflix account')
        userdoc = ElementTree.fromstring(content)
        userid = userdoc.find('./user_id').text
        firstname = userdoc.find('./first_name').text
        lastname = userdoc.find('./last_name').text

        self.userid = userid
        self.name = ' '.join((firstname, lastname))

    def itemize_item(self, item):
        title = item.find('./title').get('regular')
        link = item.find('./link[@rel="alternate"]').get('href')
        thumb = item.find('./box_art').get('large')

        timestamp = item.find('./updated').text
        date = datetime.fromtimestamp(int(timestamp))

        return Item(title=title, location=link, date=date, thumb=thumb)

    def instant_queue(self):
        h = self.http(self.access_token)
        response, content = h.request("http://api.netflix.com/users/%s/queues/instant/available"
            % self.userid)
        if response.status != 200:
            raise ValueError('Could not fetch Netflix instant queue %s')

        queue = ElementTree.fromstring(content)
        items = queue.findall('.//queue_item')
        if items is None:
            return
        return [self.itemize_item(item) for item in items]

    def queue(self):
        return self.instant_queue()

    def __str__(self):
        return "Netflix: %s" % self.name


class Hulu(Account):

    def configure(self):
        self.name = raw_input('Enter your Hulu username: ')

        # Confirm that that name has a queue.
        h = httplib2.Http()
        url = 'http://www.hulu.com/feed/queue/%s' % self.name
        response, content = h.request(url, method="HEAD")

        if response.status != 200:
            raise ValueError('Could not find Hulu account %r' % self.name)

    def itemize_item(self, x):
        title = x.find('title').text
        link = x.find('link').text
        thumb = x.find('{http://search.yahoo.com/mrss/}thumbnail').get('url')

        date = x.find('pubDate').text
        # TODO: parse date?

        return Item(title=title, location=link, date=date, thumb=thumb)

    def queue(self):
        h = httplib2.Http()
        url = 'http://www.hulu.com/feed/queue/%s' % self.name
        response, content = h.request(url)

        if response.status != 200:
            raise ValueError('Could not fetch Hulu queue for %r' % self.name)

        feed = ElementTree.fromstring(content)
        items = feed.findall('.//item')
        return [self.itemize_item(x) for x in items]

    def __str__(self):
        return "Hulu: %s" % self.name


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
