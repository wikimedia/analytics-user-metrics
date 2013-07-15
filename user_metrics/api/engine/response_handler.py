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
from user_metrics.api.engine.request_meta import rebuild_unpacked_request
from user_metrics.api.engine.data import set_data, build_key_signature

# Timeout in seconds to wait for data on the queue.  This should be long
# enough to ensure that the full response can be received
RESPONSE_TIMEOUT = 0.1


# API RESPONSE HANDLER
# ####################


def process_response():
    """ Pulls responses off of the queue. """

    log_name = '{0} :: {1}'.format(__name__, process_response.__name__)
    logging.debug(log_name  + ' - STARTING...')

    while 1:

        # Read request from the broker target
        res_item = umapi_broker_context.pop(RESPONSE_BROKER_TARGET)
        request_meta = rebuild_unpacked_request(res_item)
        key_sig = build_key_signature(request_meta, hash_result=True)

        # Add result to cache once completed
        # TODO - umapi_broker_context.add(target, key_sig, res_item)

        logging.debug(log_name + ' - Setting data for {0}'.format(
            str(request_meta)))
        set_data(stream, request_meta)

    logging.debug(log_name + ' - SHUTTING DOWN...')
