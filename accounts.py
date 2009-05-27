from datetime import datetime
import email.utils
import re
import time

import httplib2
from oauth.oauth import OAuthConsumer
from elementtree import ElementTree

from oauthclient import NetflixHttp
from queue import Item, Movie, Episode
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
        userlink = culink.find('link')
        userhref = userlink.get('href')

        # Look for the user name.
        response, content = h.request(userhref)
        if response.status != 200:
            raise ValueError('Could not fetch Netflix account')
        userdoc = ElementTree.fromstring(content)
        userid = userdoc.find('user_id').text
        firstname = userdoc.find('first_name').text
        lastname = userdoc.find('last_name').text

        self.userid = userid
        self.name = ' '.join((firstname, lastname))

    def info_for_item(self, item, dateattr='updated', titleattr='regular'):
        title = item.find('title').get(titleattr)
        link = item.find('link[@rel="alternate"]').get('href')
        thumb = item.find('box_art').get('large')

        timestamp_el = item.find(dateattr)
        if timestamp_el is not None:
            timestamp = timestamp_el.text
            date = datetime.fromtimestamp(int(timestamp))
        else:
            date = datetime.fromtimestamp(0)

        return dict(title=title, location=link, date=date, thumb=thumb)

    def at_home_queue(self):
        h = self.http(self.access_token)
        response, content = h.request("http://api.netflix.com/users/%s/at_home"
            % self.userid)
        if response.status != 200:
            raise ValueError('Could not fetch Netflix at-home queue')

        athome = ElementTree.fromstring(content)
        items = athome.findall('at_home_item')
        if items is None:
            return list()

        return [Movie(**self.info_for_item(item, dateattr='estimated_arrival_date'))
            for item in items]

    def instant_queue(self):
        h = self.http(self.access_token)
        response, content = h.request("http://api.netflix.com/users/%s/queues/instant/available"
            % self.userid)
        if response.status != 200:
            raise ValueError('Could not fetch Netflix instant queue')

        queue = list()
        queuedoc = ElementTree.fromstring(content)
        items = queuedoc.findall('queue_item')
        if items is None:
            return queue

        for item in items:
            iteminfo = self.info_for_item(item)

            episodes = item.find('link[@rel="http://schemas.netflix.com/catalog/titles.programs"]')
            if episodes is None:
                queue.append(Movie(**iteminfo))
                continue

            proghref = episodes.get('href')
            response, content = h.request(proghref)
            if response.status != 200:
                raise ValueError('Could not fetch program list %s: %s %s'
                    % (proghref, response.status, response.reason))

            progdoc = ElementTree.fromstring(content)
            episodes = progdoc.findall('catalog_title')
            if episodes is None:
                continue  # ??
            for episode in episodes:
                info = self.info_for_item(episode, titleattr='episode_short')
                # Episodes don't have date info, so snarf it from the real queue item.
                info['date'] = iteminfo['date']
                queue.append(Episode(**info))

        return queue

    def queue(self):
        queue = self.at_home_queue()
        queue.extend(self.instant_queue())
        return queue

    def __str__(self):
        return "Netflix: %s" % self.name


class Hulu(Account):

    show_title_re = re.compile(r"""
        \A
        ([^:]+) : \s+                    # series name
        ([^(]+) \s+                      # episode name
        \( s(\d+) \s* \| \s* e(\d+) \)   # episode number
        \Z
    """, re.VERBOSE | re.MULTILINE | re.DOTALL)

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

        pubdate = x.find('pubDate').text
        timestruct = email.utils.parsedate(pubdate)
        timestamp = time.mktime(timestruct)
        date = datetime.fromtimestamp(timestamp)

        info = {'location': link, 'date': date, 'thumb': thumb}
        show_mo = re.match(self.show_title_re, title)
        if show_mo is None:
            itemclass = Movie
            info['title'] = title
        else:
            itemclass = Episode
            info.update({
                'episode_number': '%s.%s' % show_mo.group(3, 4),
                'show_title': show_mo.group(1),
                'title': show_mo.group(2),
            })

        return itemclass(**info)

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
