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
from user_metrics.api.engine import unpack_response_for_broker, \
    RESPONSE_TIMEOUT
from user_metrics.api.engine.request_meta import build_request_obj
from user_metrics.api.engine.data import set_data

import time


# API RESPONSE HANDLER
# ####################


def process_response():
    """ Pulls responses off of the queue. """

    log_name = '{0} :: {1}'.format(__name__, process_response.__name__)
    logging.debug(log_name  + ' - STARTING...')

    while 1:

        time.sleep(RESPONSE_TIMEOUT)

        # Handle any responses as they enter the queue
        # logging.debug(log_name  + ' - POLLING RESPONSES...')
        res_item = umapi_broker_context.pop(RESPONSE_BROKER_TARGET)
        if not res_item:
            continue

        req, data = unpack_response_for_broker(res_item)
        request_meta = build_request_obj(req)

        # Add result to cache once completed
        logging.debug(log_name + ' - Setting data for {0}'.format(
            str(request_meta)))
        set_data(data, request_meta)

    logging.debug(log_name + ' - SHUTTING DOWN...')
