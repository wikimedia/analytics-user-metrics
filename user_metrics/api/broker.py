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
from user_metrics.config import logging


class Broker(object):
    """
    Base class for broker
    """

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

    def update(self, target, key, value):
        """
        Remove a key/value pair to the broker
        """
        raise NotImplementedError()

    def get(self, target, key):
        """
        Retrieve a key/value pair to the broker
        """
        raise NotImplementedError()

    def get_keys(self, target):
        """
        Retrieve all keys in the broker
        """
        raise NotImplementedError()

    def get_all_items(self, target):
        """
        Retrieve all values in the target
        """
        raise NotImplementedError()

    def pop(self, target):
        """
        Pop the first item off of the queue
        """
        raise NotImplementedError()

    def is_item(self, target, key):
        """
        Return boolean indicating whether a key is in target
        """
        raise NotImplementedError()


class FileBroker(Broker):
    """
    Implements a broker that uses a flat file as a broker

    !! Operations are O(n), consider storing keys in heap
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
        try:
            with open(target, 'r') as f:
                lines = f.read().split('\n')
                for idx, line in enumerate(lines):
                    item = json.loads(line)
                    if item.keys()[0] == key:
                        del lines[idx]
                        break
        except IOError:
            lines = []
            with open(target, 'w'):
                pass

        with open(target, 'w') as f:
            for line in lines:
                f.write(line)

    def update(self, target, key, value):
        """
        Update element with the given key
        """
        try:
            with open(target, 'r') as f:
                lines = f.read().split('\n')
                for idx, line in enumerate(lines):
                    item = json.loads(line)
                    if item.keys()[0] == key:
                        lines[idx] = json.dumps({key: value}) + '\n'
                        break
        except IOError:
            lines = []
            with open(target, 'w'):
                pass

        with open(target, 'w') as f:
            for line in lines:
                f.write(line)

    def get(self, target, key):
        """
        Retrieve a value with the given key
        """
        try:
            with open(target, 'r') as f:
                lines = f.read().split('\n')
                for idx, line in enumerate(lines):
                    item = json.loads(line)
                    if item.keys()[0] == key:
                        return item[key]
        except IOError:
            with open(target, 'w'):
                pass

            return None

    def get_keys(self, target):
        """
        Retrieve all keys in the broker target
        """
        items = self.get_all_items(target)
        return [item.keys()[0] for item in items]

    def get_all_items(self, target):
        """
        Retrieve all values in the target
        """
        all_keys = list()
        try:
            with open(target, 'r') as f:
                lines = f.read().split('\n')
                for idx, line in enumerate(lines):
                    try:
                        item = json.loads(line)
                    except Exception:
                        logging.error(__name__ + ' :: Could not parse JSON '
                                                 'from: {0}'.format(line))
                        continue
                    all_keys.append(item)
        except IOError:
            with open(target, 'w'):
                pass
        return all_keys

    def pop(self, target):
        """
        Pop the top value from the list
        """
        try:
            with open(target, 'r') as f:
                contents = f.read()
                if contents:
                    lines = contents.split('\n')
                    if len(lines):
                        try:
                            item = json.loads(lines[0])
                            key = item.keys()[0]
                        except (KeyError, ValueError):
                            logging.error(__name__ + ' :: FileBroker.pop - '
                                                     'Could not parse key.')
                            return None
                        self.remove(target, key)
                        return item[key]
        except IOError:
            with open(target, 'w'):
                pass
        return None

    def is_item(self, target, key):
        """
        Return boolean indicating whether a key is in target
        """
        return key in self.get_keys(target)
