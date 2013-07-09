"""
This module defines the interface between API modules.
"""


__author__ = {
    "ryan faulkner": "rfaulkner@wikimedia.org"
}
__date__ = "2013-07-06"
__license__ = "GPL (version 2 or later)"


class Broker(object):
    """
    Base class for broker
    """

    def __init__(self, **kwargs):
        raise NotImplementedError()

    def compose(self):
        raise NotImplementedError()

    def add(self, target, key, value):
        raise NotImplementedError()

    def remove(self, target, key):
        raise NotImplementedError()

    def get(self, target, key):
        raise NotImplementedError()
