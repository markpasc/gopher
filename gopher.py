#!/usr/bin/env python

import logging
import pickle
import sys

import optfunc

import accounts


class Person(object):

    def __init__(self, name):
        self.name = name

    @classmethod
    def get(self, name):
        try:
            f = open('%s.person' % name, 'rb')
        except IOError:
            # No such file?
            logging.info('Created new person %s', name)
            return Person(name)

        p = pickle.load(f)
        logging.info('Loaded person %s', name)
        return p

    def add_account(self, service):
        if not hasattr(self, 'accounts'):
            self.accounts = {}

        account = accounts.account_for_service(service)()
        account.configure()
        self.accounts[service] = account

    def save(self):
        f = open('%s.person' % self.name, 'wb')
        pickle.dump(self, f)
        logging.info('Saved person %s', self.name)


@optfunc.arghelp('person', 'person to whom to add the account')
@optfunc.arghelp('service', 'kind of account to add')
def add(person, service):
    """Add an account."""
    p = Person.get(person)
    p.add_account(service)
    p.save()


@optfunc.arghelp('person', 'person whose accounts to list')
def accounts(person):
    """List all of a person's accounts."""
    p = Person.get(person)
    print "## Accounts ##"
    for x in p.accounts.values():
        print x


@optfunc.arghelp('person', 'person whose queue to show')
def queue(person):
    """Compile and print a person's queue."""
    queue = list()
    for servicename, account in p.accounts.iteritems():
        queue.extend(account.queue())
    print "## Queue ##"
    for x in sorted(queue, key=lambda x: x.date):
        print x


if __name__ == '__main__':
    optfunc.run((add, accounts, queue))
