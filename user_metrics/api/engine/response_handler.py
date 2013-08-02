"""
    Handles API responses.
"""

__author__ = {
    "ryan faulkner": "rfaulkner@wikimedia.org"
}
__date__ = "2013-03-14"
__license__ = "GPL (version 2 or later)"

from user_metrics.api import RESPONSE_BROKER_TARGET, umapi_broker_context
from user_metrics.config import logging
from user_metrics.api.engine import unpack_response_for_broker
from user_metrics.api.engine.request_meta import build_request_obj
from user_metrics.api.engine.data import set_data, build_key_signature

import time

# Timeout in seconds to wait for data on the queue.  This should be long
# enough to ensure that the full response can be received
RESPONSE_TIMEOUT = 1.0


# API RESPONSE HANDLER
# ####################


def process_response():
    """ Pulls responses off of the queue. """

    log_name = '{0} :: {1}'.format(__name__, process_response.__name__)
    logging.debug(log_name  + ' - STARTING...')

    while 1:

        time.sleep(RESPONSE_TIMEOUT)

        # Read request from the broker target
        logging.debug(log_name  + ' - POLLING RESPONSES...')
        res_item = umapi_broker_context.pop(RESPONSE_BROKER_TARGET)
        if not res_item:
            continue

        request, data = unpack_response_for_broker(res_item)
        request_obj = build_request_obj(request)

        # Add result to cache once completed
        # TODO - umapi_broker_context.add(target, key_sig, res_item)

        logging.debug(log_name + ' - Setting data for {0}'.format(
            str(request_obj)))
        set_data(data, request_obj)

    logging.debug(log_name + ' - SHUTTING DOWN...')
