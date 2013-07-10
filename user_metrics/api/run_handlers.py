#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
This module handle the exescution of the job handler components of the User
metrics API.  This piece consists of three components:

    Job Controller:
        Schedules incoming requests for execution.

    Response Handler:
        Synthesizes responses from completed jobs.

    Request Notification Callback:
        Handles sending notifications on job status.
"""

__author__ = {
    "ryan faulkner": "rfaulkner@wikimedia.org"
}
__date__ = "2013-07-05"
__license__ = "GPL (version 2 or later)"

import multiprocessing as mp
from user_metrics.api.engine.request_manager import api_request_queue,\
    req_notification_queue_out, req_notification_queue_in, api_response_queue
from user_metrics.api.engine.response_handler import process_responses
from user_metrics.api.engine.request_manager import job_control, \
    requests_notification_callback
from user_metrics.utils import terminate_process_with_checks
from user_metrics.config import logging

job_controller_proc = None
response_controller_proc = None
rm_callback_proc = None


def setup_controller(req_queue, res_queue, msg_queue_in, msg_queue_out):
    """
        Sets up the process that handles API jobs
    """
    job_controller_proc = mp.Process(target=job_control,
                                     args=(req_queue, res_queue))
    response_controller_proc = mp.Process(target=process_responses,
                                          args=(res_queue,
                                                msg_queue_in))
    rm_callback_proc = mp.Process(target=requests_notification_callback,
                                  args=(msg_queue_in,
                                        msg_queue_out))
    job_controller_proc.start()
    response_controller_proc.start()
    rm_callback_proc.start()


def teardown():
    """ When the instance is deleted store the pickled data and shutdown
        the job controller """

    # Shutdown API handlers gracefully
    try:
        terminate_process_with_checks(job_controller_proc)
        terminate_process_with_checks(response_controller_proc)
        terminate_process_with_checks(rm_callback_proc)

    except Exception:
        logging.error(__name__ + ' :: Could not shut down callbacks.')


if __name__ == '__main__':
    setup_controller(api_request_queue,
        api_response_queue,
        req_notification_queue_in,
        req_notification_queue_out)
