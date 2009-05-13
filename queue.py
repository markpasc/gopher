class Item(object):

    title, location, date, thumb = None, None, None, None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return '<Item "%s" %s>' % (self.title, self.location)
