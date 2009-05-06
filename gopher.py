#!/usr/bin/env python

import sys
import logging
from optparse import OptionParser


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


if __name__ == '__main__':
    sys.exit(Command().main())
