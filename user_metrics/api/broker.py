"""
This module defines the interface between API modules.
"""


__author__ = {
    "ryan faulkner": "rfaulkner@wikimedia.org"
}
__date__ = "2013-07-06"
__license__ = "GPL (version 2 or later)"


import json
import os


class Broker(object):
    """
    Base class for broker
    """

    def __init__(self, **kwargs):
        raise NotImplementedError()

    def compose(self):
        raise NotImplementedError()

    def add(self, target, key, value):
        """
        Add a key/value pair to the broker
        """
        raise NotImplementedError()

    def remove(self, target, key):
        """
        Remove a key/value pair to the broker
        """
        raise NotImplementedError()

    def get(self, target, key):
        """
        Retrieve a key/value pair to the broker
        """
        raise NotImplementedError()


class FileBroker(Broker):
    """
    Implements a broker that uses a flat file as a broker
    """

    def __init__(self, **kwargs):
        super(FileBroker, self).__init__(**kwargs)

    def compose(self):
        pass

    def add(self, target, key, value):
        """
        Adds key/value pair
        """
        if os.path.isfile(target):
            mode = 'a'
        else:
            mode = 'w'

        with open(target, mode) as f:
            f.write(json.dumps({key: value}) + '\n')

    def remove(self, target, key):
        """
        Remove element with the given key
        """
        with open(target, 'r') as f:
            lines = f.read().split('\n')
            for idx, line in enumerate(lines):
                item = json.loads(line)
                if item['key'] == key:
                    del lines[idx]
                    break
        with open(target, 'w') as f:
            for line in lines:
                f.write(line)

    def get(self, target, key):
        pass
