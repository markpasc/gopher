class Item(object):

    title, location, date, thumb = None, None, None, None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return '<%s "%s" %s>' % (type(self).__name__, self.title, self.location)


class Movie(Item):
    pass


class Episode(Item):
    episode_number, show_title = None, None
