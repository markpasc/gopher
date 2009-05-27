#!/usr/bin/env python

import logging
from optparse import OptionParser
import pickle
import sys

import accounts


class Command(object):

    def configure_logging(self, verbose):
        levels = {
            -2: logging.CRITICAL,
            -1: logging.ERROR,
             0: logging.WARNING,
             1: logging.INFO,
             2: logging.DEBUG,
        }

        verbose = min(2, max(-2, verbose))
        level = levels[verbose]

        logging.basicConfig(level=level)
        logging.info('Logging at level %s', logging.getLevelName(level))

    def add_options(self, parser):
        pass

    def parse_args(self, argv=None):
        if argv is None:
            argv = sys.argv

        parser = OptionParser()
        self.parser = parser
        parser.add_option('-v', '--verbose', dest='verbose', action='count',
                          default=0, help="print more to console")
        parser.add_option('-q', '--quiet', dest='quiet', action='count',
                          default=0, help="print less to console")
        self.add_options(parser)
        opts, args = parser.parse_args()

        self.configure_logging(opts.verbose - opts.quiet)
        return opts, args

    def main(self, argv=None):
        self.parse_args(argv)
        return 0


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


class Gopher(Command):

    def add_account(self, option, opt, value, parser):
        parser.values.command = 'add'
        setattr(parser.values, option.dest, value)

    def add_options(self, parser):
        parser.add_option('-p', '--person', dest='name',
            help="person to act as")
        parser.add_option('--add', action='callback', dest='account',
            type='string', callback=self.add_account,
            help="add an account", metavar='SERVICE')
        parser.add_option('--accounts', action='store_const', dest='command',
            const='accounts', help="list all of a person's accounts")
        parser.add_option('--queue', action='store_const', dest='command',
            const='queue', help="compile and print a person's queue")

    def main(self, argv=None):
        opt, arg = self.parse_args(argv)

        if opt.name is None:
            self.parser.error("Person parameter is required")

        p = Person.get(opt.name)

        if opt.command is None:
            print "No command was specified; one of --add or --accounts is required"
            return 1

        if opt.command == 'add':
            p.add_account(opt.account)
            p.save()
        elif opt.command == 'accounts':
            print "## Accounts ##"
            for x in p.accounts.values():
                print x
        elif opt.command == 'queue':
            queue = list()
            for servicename, account in p.accounts.iteritems():
                queue.extend(account.queue())
            print "## Queue ##"
            for x in queue:
                print x

        return 0


if __name__ == '__main__':
    sys.exit(Gopher().main())
