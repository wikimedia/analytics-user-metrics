"""
    This module handles API functionality involved in extracting custom data
    for API specific requests along with ETL and data storage operations.

    Data Storage and Retrieval
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    This portion of the API engine is concerned with extracting and storing
    data at runtime to service API requests.  This includes all of the
    interaction with the ``usertags`` and ``usertags_meta`` SQL tables that
    define user cohorts.  The following methods are involved with extracting
    this data::

        get_users(cohort_expr)
        get_cohort_id(utm_name)

    The other portion of data storage and retrieval is concerned with providing
    functionality that enables responses to be cached.  Request responses are
    currently cached in the ``api_data`` OrderedDict_ defined in the run
    module.  This object stores responses in a nested fashion using URL request
    variables and their corresponding values.  For example, the url
    ``http://metrics-api.wikimedia.org/cohorts/e3_ob2b/revert_rate?t=10000``
    maps to::

        api_data['cohort_expr <==> e3_ob2b']['metric <==> revert_rate']
        ['start <==> xx']['start <==> yy']['t <==> 10000']

    The list of key values for a given request is referred to as it's "key
    signature".  The order of parameters is perserved.

    The ``get_data`` method requires a reference to ``api_data``. Given this
    reference and a RequestMeta object the method attempts to find an entry
    for the request if one exists.  The ``set_data`` method does much the
    same operation but performs storage into the hash reference passed.
    The method ``get_url_from_keys`` builds URLs from nested hash references
    using the key list and ``build_key_tree`` recursively builds a tree
    representation of all of the key paths in the hash reference.

    .. _OrderedDict: http://docs.python.org/2/library/collections.html

"""

__author__ = {
    "ryan faulkner": "rfaulkner@wikimedia.org"
}
__date__ = "2012-01-11"
__license__ = "GPL (version 2 or later)"


from re import search
from collections import OrderedDict
from hashlib import sha1
import cPickle
import os

from user_metrics.config import logging, settings
from user_metrics.api.engine import COHORT_REGEX, parse_cohorts
from user_metrics.api.engine.request_meta import REQUEST_META_QUERY_STR,\
    REQUEST_META_BASE, build_request_obj
from user_metrics.api import MetricsAPIError, query_mod


# This is used to separate key meta and key strings for hash table data
# e.g. "metric <==> blocks"
HASH_KEY_DELIMETER = "--"


def get_users(cohort_expr):
    """ get users from cohort """

    if search(COHORT_REGEX, cohort_expr):
        logging.info(__name__ + ' :: Processing cohort by expression.')
        users = [user for user in parse_cohorts(cohort_expr)]
    else:
        logging.info(__name__ + ' :: Processing cohort by tag name.')
        try:
            id = query_mod.get_cohort_id(cohort_expr)
            users = [u for u in query_mod.get_cohort_users(id)]
        except (IndexError, TypeError,
                query_mod.UMQueryCallError) as e:
            logging.error(__name__ + ' :: Could not retrieve users '
                                     'for cohort {0}: {1}'.
                format(cohort_expr, str(e)))
            return []
    return users


def get_data(request, hash_result=True):
    """
        Extract data from the global hash given a request object.  If an item
        is successfully recovered data is returned
    """

    request_obj = build_request_obj(request)
    hash_table_ref = read_pickle_data()

    # Traverse the hash key structure to find data
    # @TODO rather than iterate through REQUEST_META_BASE &
    #   REQUEST_META_QUERY_STR look only at existing attributes

    logging.debug(__name__ + " - Attempting to pull data for request " \
                             "COHORT {0}, METRIC {1}".
                  format(request_obj.cohort_expr, request_obj.metric))

    key_sig = build_key_signature(request_obj, hash_result=hash_result)
    item = find_item(hash_table_ref, key_sig)

    if item:
        # item[0] will be a stringified structure that
        # is initialized, see set_data.
        try:
            return eval(item[0])
        except SyntaxError:
            logging.error(__name__ + ' :: Failed to retrieve {0}'.
                          format(key_sig))
            return None
    else:
        return None


def set_data(data, request_meta, hash_result=True):
    """
        Given request meta-data and a dataset create a key path in the global
        hash to store the data
    """
    hash_table_ref = read_pickle_data()

    key_sig = build_key_signature(request_meta, hash_result=hash_result)
    logging.debug(__name__ + " :: Adding data to hash @ key signature = {0}".
                  format(str(key_sig)))
    if hash_result:
        key_sig_full = build_key_signature(request_meta, hash_result=False)
        hash_table_ref[key_sig] = (data, key_sig_full)
    else:
        last_item = key_sig[-1]
        for item in key_sig:
            if item == last_item:
                hash_table_ref[last_item] = data
            else:
                hash_table_ref[item] = OrderedDict()
            hash_table_ref = hash_table_ref[item]
    write_pickle_data(hash_table_ref)


def find_item(hash_table_ref, key_sig):
    """
        For each key in the key signature add a nested key to the hash.

        Parameters
        ~~~~~~~~~~
    """
    if not hasattr(key_sig, '__iter___'):
        key_sig = [key_sig]

    last_item = key_sig[len(key_sig) - 1]
    for key in key_sig:
        if key != last_item:
            if hasattr(hash_table_ref, 'keys') and key in hash_table_ref:
                hash_table_ref = hash_table_ref[key]
            else:
                # Item not found
                return None
        else:
            if hasattr(hash_table_ref, 'keys') and \
                key in hash_table_ref:
                    return hash_table_ref[key]
            # Item not found
            return None


def build_key_signature(request_meta, hash_result=False):
    """
        Given a RequestMeta object contruct a hashkey.

        Parameters
        ~~~~~~~~~~

            request_meta : RequestMeta
                Stores request data.
    """
    key_sig = list()

    # Build the key signature -- These keys must exist
    for key_name in REQUEST_META_BASE:
        key = getattr(request_meta, key_name)
        if key:
            key_sig.append(key_name + HASH_KEY_DELIMETER + key)
        else:
            logging.error(__name__ + ' :: Request must include %s. '
                                     'Cannot set data %s.' %
                                     (key_name, str(request_meta)))
            return ''
    # These keys may optionally exist
    for key_name in REQUEST_META_QUERY_STR:
        if hasattr(request_meta, key_name):
            key = getattr(request_meta, key_name)
            if key:
                key_sig.append(key_name + HASH_KEY_DELIMETER + str(key))

    if hash_result:
        return sha1(str(key_sig).encode('utf-8')).hexdigest()
    else:
        return key_sig


def get_url_from_keys(keys, path_root):
    """ Compose a url from a set of keys """
    query_str = ''
    for key in keys:
        parts = key.split(HASH_KEY_DELIMETER)
        if parts[0] in REQUEST_META_BASE:
            path_root += parts[1] + '/'
        elif parts[0] in REQUEST_META_QUERY_STR:
            query_str += parts[0] + '=' + parts[1] + '&'

    if not path_root:
        raise MetricsAPIError()
    if query_str:
        url = path_root[:-1] + '?' + query_str[:-1]
    else:
        url = path_root
    return url


def read_pickle_data():
    try:
        with open(os.path.join(settings.__data_file_dir__,
                  'api_data.pkl'), 'rb') as pkl_file:
            return cPickle.load(pkl_file)
    except IOError:
        with open(os.path.join(settings.__data_file_dir__,
                  'api_data.pkl'), 'wb') as pkl_file:
            data = OrderedDict()
            cPickle.dump(data, pkl_file)
            return data

def write_pickle_data(obj):
    with open(os.path.join(settings.__data_file_dir__,
              'api_data.pkl'), 'wb') as pkl_file:
        cPickle.dump(obj, pkl_file)