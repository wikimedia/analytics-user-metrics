
"""
    The engine for the metrics API which stores definitions an backend API
    operations.  This module defines the communication between API requests
    and UserMetric objects, how and where request responses are stored, and
    how cohorts are parsed from API request URLs.



    Cohort request parsing
    ~~~~~~~~~~~~~~~~~~~~~~

    This set of methods allows boolean expressions of cohort IDs to be
    synthesized and interpreted in the portion of the URL path that is
    bound to the user cohort name.  This set of methods, invoked at the top
    level via ``parse_cohorts`` takes an expression of the form::

        http://metrics-api.wikimedia.org/cohorts/1&2~3~4/bytes_added

    The portion of the path ``1&2~3~4``, resolves to the boolean expression
    "1 AND 2 OR 3 OR 4".  The cohorts that correspond to the numeric ID values
    in ``usertags_meta`` are resolved to sets of user ID longs which are then
    operated on with union and intersect operations to yield a custom user
    list.  The power of this functionality lies in that it allows subsets of
    users to be selected based on prior conditions that includes them in a
    given cohort.

    Method Definitions
    ~~~~~~~~~~~~~~~~~~
"""

__author__ = "ryan faulkner"
__email__ = "rfaulkner@wikimedia.org"
__date__ = "january 11 2012"
__license__ = "GPL (version 2 or later)"

from re import search
from user_metrics.config import settings, logging
from user_metrics.api import MetricsAPIError, query_mod
from datetime import datetime
import user_metrics.etl.data_loader as dl


#
# Define remaining constants
# ==========================
# @TODO break these out into separate modules

# Regex that matches a MediaWiki user ID
MW_UID_REGEX = r'^[0-9]{5}[0-9]*$'
MW_UNAME_REGEX = r'[a-zA-Z_\.\+ ]'

# Datetime string format to be used throughout the API
DATETIME_STR_FORMAT = "%Y-%m-%d %H:%M:%S"

# The default value for non-assigned and valid values in the query string
DEFAULT_QUERY_VAL = 'present'

# DELIMETER FOR RESPONSE IN BROKER
RESPONSE_DELIMETER = '<&>'

# Timeout in seconds to wait for data on the queue.  This should be long
# enough to ensure that the full response can be received
RESPONSE_TIMEOUT = 10.0
RESQUEST_TIMEOUT = 10.0

# MODULE CONSTANTS
#
# 1. Determines maximum block size of (multiprocessing.)queue item
# 2. Number of maximum concurrently running jobs
# 3. Time to block on waiting for a new request to appear in the queue
MAX_BLOCK_SIZE = 5000
MAX_CONCURRENT_JOBS = 2


#
# Cohort parsing methods
#
# ======================

# This regex must be matched to parse cohorts
COHORT_REGEX = r'^([0-9]+[&~])*[0-9]+$'

COHORT_OP_AND = '&'
COHORT_OP_OR = '~'
# COHORT_OP_NOT = '^'


def parse_cohorts(expression):
    """
        Defines and parses boolean expressions of cohorts and returns a list
        of user ids corresponding to the expression argument.

            Parameters:
                - **expression**: str. Boolean expression built of
                    cohort labels.

            Return:
                - List(str).  user ids corresponding to cohort expression.
    """

    # match expression
    if not search(COHORT_REGEX, expression):
        raise MetricsAPIError()

    # parse expression
    return parse(expression)


def parse(expression):
    """ Top level parsing. Splits expression by OR then sub-expressions by
        AND. returns a generator of ids included in the evaluated expression
    """
    user_ids_seen = set()
    for sub_exp_1 in expression.split(COHORT_OP_OR):
        for user_id in intersect_ids(sub_exp_1.split(COHORT_OP_AND)):
            if not user_ids_seen.__contains__(user_id):
                user_ids_seen.add(user_id)
                yield user_id


def intersect_ids(cohort_id_list):

    user_ids = dict()
    # only a single cohort id in the expression - return all users of this
    # cohort
    if len(cohort_id_list) == 1:
        for id in query_mod.get_cohort_users(cohort_id_list[0]):
            yield id
    else:
        for cid in cohort_id_list:
            for id in query_mod.get_cohort_users(cid):
                if id in user_ids:
                    user_ids[id] += 1
                else:
                    user_ids[id] = 1
                    # Executes only in the case that there was more than one
                    # cohort id in the expression
        for key in user_ids:
            if user_ids[key] > 1:
                yield key


def get_cohort_refresh_datetime(utm_id):
    """
        Get the latest refresh datetime of a cohort.  Returns current time
        formatted as a string if the field is not found.
    """

    # @TODO MOVE DB REFS INTO QUERY MODULE
    conn = dl.Connector(instance=settings.__cohort_data_instance__)
    query = """ SELECT utm_touched FROM usertags_meta WHERE utm_id = %s """
    conn._cur_.execute(query, int(utm_id))

    utm_touched = None
    try:
        utm_touched = conn._cur_.fetchone()[0]
    except ValueError:
        pass

    # Ensure the field was retrieved
    if not utm_touched:
        logging.error(__name__ + '::Missing utm_touched for cohort %s.' %
                                 str(utm_id))
        utm_touched = datetime.now()

    del conn
    return utm_touched.strftime(DATETIME_STR_FORMAT)


def pack_response_for_broker(request, data):
    """
    Packs up response data for broker
    """
    return str(''.join([request, RESPONSE_DELIMETER, data]))


def unpack_response_for_broker(value):
    """
    unpacks up response data from broker
    """
    return value.split(RESPONSE_DELIMETER)
