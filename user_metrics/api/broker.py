"""
This module defines the interface between API modules.
"""


__author__ = {
    "ryan faulkner": "rfaulkner@wikimedia.org"
}
__date__ = "2013-07-06"
__license__ = "GPL (version 2 or later)"

class Broker:

    def __init__(self):
        pass

    def compose(self):
        pass

    def add(self, target, key, value):
        pass

    def remove(self, target, key):
        pass

    def get(self, target, key):
        pass
