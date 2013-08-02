"""
    This module implements the request manager functionality.

    Job Queue and Processing
    ^^^^^^^^^^^^^^^^^^^^^^^^

    As requests are issued via http to the API a process queue will store all
    active jobs. Processes will be created and assume one of the following
    states throughout their existence: ::

        * 'pending' - The request has yet to be begin being processed
        * 'running' - The request is being processed
        * 'success' - The request has finished processing and is exposed at
            the url
        * 'failure' - The result has finished processing but dailed to expose
            results

    When a process a request is received and a job is created to service that
    request it enters the 'pending' state. If the job returns without
    exception it enters the 'success' state, otherwise it enters the 'failure'
    state.  The job remains in either of these states until it is cleared
    from the process queue.

    Response Data
    ^^^^^^^^^^^^^

    As requests are made to the API the data generated and formatted as JSON.
    The definition of is as follows: ::

        {   header : header_list,
            cohort_expr : cohort_gen_timestamp : metric : timeseries :
            aggregator : start : end : [ metric_param : ]* : data
        }

    Where each component is defined: ::

        header_str := list(str), list of header values
        cohort_expr := str, cohort ID expression
        cohort_gen_timestamp := str, cohort generation timestamp (earliest of
            all cohorts in expression)
        metric := str, user metric handle
        timeseries := boolean, indicates if this is a timeseries
        aggregator := str, aggregator used
        start := str, start datetime of request
        end := str, end datetime of request
        metric_param := -, optional metric parameters
        data := list(tuple), set of data points

    Request data is mapped to a query via metric objects and hashed in the
    dictionary `api_data`.

    Request Flow Management
    ^^^^^^^^^^^^^^^^^^^^^^^

    This portion of the module defines a set of methods useful in handling
    series of metrics objects to build more complex results.  This generally
    involves creating one or more UserMetric derived objects with passed
    parameters to service a request.  The primary entry point is the
    ``process_data_request`` method. This method coordinates requests for
    three different top-level request types:

    - **Raw requests**.  Output is a set of datapoints that consist of the
      user IDs accompanied by metric results.
    - **Aggregate requests**.  Output is an aggregate of all user results based
      on the type of aggregaion as defined in the aggregator module.
    - **Time series requests**.  Outputs a time series list of data.  For this
      type of request a start and end time must be defined along with an
      interval length.  Further an aggregator must be provided which operates
      on each time interval.

    Also defined are metric types for which requests may be made with
    ``metric_dict``, and the types of aggregators that may be called on metrics
    ``aggregator_dict``, and also the meta data around how many threads may be
    used to process metrics ``USER_THREADS`` and ``REVISION_THREADS``.

"""

__author__ = {
    "ryan faulkner": "rfaulkner@wikimedia.org"
}
__date__ = "2013-03-05"
__license__ = "GPL (version 2 or later)"

from user_metrics.config import logging, settings
from user_metrics.api import MetricsAPIError, error_codes, query_mod, \
    REQUEST_BROKER_TARGET, umapi_broker_context,\
    RESPONSE_BROKER_TARGET, PROCESS_BROKER_TARGET
from user_metrics.api.engine import pack_response_for_broker
from user_metrics.api.engine.data import get_users
from user_metrics.api.engine.request_meta import build_request_obj
from user_metrics.metrics.users import MediaWikiUser
from user_metrics.metrics.user_metric import UserMetricError

from multiprocessing import Process, Queue
from collections import namedtuple
from os import getpid
from sys import getsizeof
import time
from hashlib import sha1

# API JOB HANDLER
# ###############

# MODULE CONSTANTS
#
# 1. Determines maximum block size of queue item
# 2. Number of maximum concurrently running jobs
# 3. Time to block on waiting for a new request to appear in the queue
MAX_BLOCK_SIZE = 5000
MAX_CONCURRENT_JOBS = 1
QUEUE_WAIT = 5
RESQUEST_TIMEOUT = 1.0

# Defines the job item type used to temporarily store job progress
job_item_type = namedtuple('JobItem', 'id process request queue')


def job_control():
    """
        Controls the execution of user metrics requests

        Parameters
        ~~~~~~~~~~

        request_queue : multiprocessing.Queue
           Queues incoming API requests.

    """

    # Store executed and pending jobs respectively
    job_queue = list()

    # Global job ID number
    job_id = 0

    # Tallies the number of concurrently running jobs
    concurrent_jobs = 0

    log_name = '{0} :: {1}'.format(__name__, job_control.__name__)

    logging.debug('{0} - STARTING...'.format(log_name))

    while 1:

        time.sleep(RESQUEST_TIMEOUT)

        # Request Queue Processing
        # ------------------------

        logging.debug(log_name + ' - POLLING REQUESTS...')
        if concurrent_jobs <= MAX_CONCURRENT_JOBS:

            # Pop from request target
            req_item = umapi_broker_context.pop(REQUEST_BROKER_TARGET)

            # Push to process target
            url_hash = sha1(req_item.encode('utf-8')).hexdigest()
            umapi_broker_context.add(PROCESS_BROKER_TARGET, url_hash, req_item)
        else:
            continue

        if not req_item:
            continue

        logging.debug(log_name + ' :: PULLING item from request queue -> '
                                 '\n\t{0}'
                      .format(req_item))

        # Process complete jobs
        # ---------------------

        for job_item in job_queue:

            if not job_item.queue.empty():

                # Pull data off of the queue and add it to response queue
                data = ''
                while not job_item.queue.empty():
                    data += job_item.queue.get(True)

                # Remove from process target
                url_hash = sha1(job_item.request.encode('utf-8')).hexdigest()
                umapi_broker_context.remove(PROCESS_BROKER_TARGET, url_hash)

                # Add to response target
                umapi_broker_context.add(RESPONSE_BROKER_TARGET, url_hash,
                                         pack_response_for_broker(
                                             job_item.request, data))

                del job_queue[job_queue.index(job_item)]
                concurrent_jobs -= 1
                logging.debug(log_name + ' :: RUN -> RESPONSE - Job ID {0}'
                                         '\n\tConcurrent jobs = {1}'
                              .format(str(job_item.id), concurrent_jobs))

        # Process request
        # ---------------

        req_q = Queue()
        proc = Process(target=process_metrics, args=(req_q, req_item))
        proc.start()

        job_item = job_item_type(job_id, proc, req_item, req_q)
        job_queue.append(job_item)

        concurrent_jobs += 1
        job_id += 1

        logging.debug(log_name + ' :: WAIT -> RUN - Job ID {0}'
                                 '\n\tConcurrent jobs = {1}, REQ = {2}'
                      .format(str(job_id), concurrent_jobs, req_item))

    logging.debug('{0} - FINISHING.'.format(log_name))


def process_metrics(p, request):
    """
        Worker process for requests, forked from the job controller.  This
        method handles:

            * Filtering cohort type: "regular" cohort, single user, user group
            * Secondary validation
            *
    """

    log_name = '{0} :: {1}'.format(__name__, process_metrics.__name__)

    logging.info(log_name + ' - START JOB'
                            '\n\t{0} -  PID = {2})'.
                 format(request, getpid()))

    err_msg = __name__ + ' :: Request failed.'
    users = list()

    try:
        request_obj = build_request_obj(request)
    except MetricsAPIError as e:
        # TODO - flag job as failed
        return

    # obtain user list - handle the case where a lone user ID is passed
    # !! The username should already be validated
    if request_obj.is_user:
        uid = MediaWikiUser.is_user_name(request_obj.cohort_expr,
                                         request_obj.project)
        if uid:
            valid = True
            users = [uid]
        else:
            valid = False
            err_msg = error_codes[3]

    # The "all" user group.  All users within a time period.
    elif request_obj.cohort_expr == 'all':
        users = MediaWikiUser(query_type=1)

        try:
            users = [u for u in users.get_users(
                request_obj.start, request_obj.end,
                project=request_obj.project)]
            valid = True
        except Exception:
            valid = False
            err_msg = error_codes[5]

    # "TYPICAL" COHORT PROCESSING
    else:
        users = get_users(request_obj.cohort_expr)

        # Default project is what is stored in usertags_meta
        project = query_mod.get_cohort_project_by_meta(
            request_obj.cohort_expr)
        if project:
            request_obj.project = project
        logging.debug(__name__ + ' :: Using default project from '
                                 'usertags_meta {0}.'.format(project))

        valid = True
        err_msg = ''

    if valid:
        # process request
        results = process_data_request(request_obj, users)
        results = str(results)
        response_size = getsizeof(results, None)

        if response_size > MAX_BLOCK_SIZE:
            index = 0

            # Dump the data in pieces - block until it is picked up
            while index < response_size:
                p.put(results[index:index+MAX_BLOCK_SIZE], block=True)
                index += MAX_BLOCK_SIZE
        else:
            p.put(results, block=True)

        logging.info(log_name + ' - END JOB'
                                '\n\tCOHORT = {0}- METRIC = {1} -  PID = {2})'.
                     format(request_obj.cohort_expr, request_obj.metric,
                            getpid()))

    else:
        p.put(err_msg, block=True)
        logging.info(log_name + ' - END JOB - FAILED.'
                                '\n\tCOHORT = {0}- METRIC = {1} -  PID = {2})'.
                     format(request_obj.cohort_expr, request_obj.metric,
                            getpid()))

# REQUEST FLOW HANDLER
# ###################

from dateutil.parser import parse as date_parse
from copy import deepcopy

from user_metrics.etl.data_loader import DataLoader
import user_metrics.metrics.user_metric as um
import user_metrics.etl.time_series_process_methods as tspm
from user_metrics.api.engine.request_meta import ParameterMapping
from user_metrics.api.engine.response_meta import format_response
from user_metrics.api.engine import DATETIME_STR_FORMAT
from user_metrics.api.engine.request_meta import get_agg_key, \
    get_aggregator_type, request_types

INTERVALS_PER_THREAD = 10
MAX_THREADS = 5

USER_THREADS = settings.__user_thread_max__
REVISION_THREADS = settings.__rev_thread_max__
DEFAULT_INERVAL_LENGTH = 24

# create shorthand method refs
to_string = DataLoader().cast_elems_to_string


def process_data_request(request_meta, users):
    """
        Main entry point of the module, prepares results for a given request.
        Coordinates a request based on the following parameters::

            metric_handle (string) - determines the type of metric object to
            build.  Keys metric_dict.

            users (list) - list of user IDs.

            **kwargs - Keyword arguments may contain a variety of variables.
            Most notably, "aggregator" if the request requires aggregation,
            "time_series" flag indicating a time series request.  The
            remaining kwargs specify metric object parameters.
    """

    # Set interval length in hours if not present
    if not request_meta.slice:
        request_meta.slice = DEFAULT_INERVAL_LENGTH
    else:
        request_meta.slice = float(request_meta.slice)

    # Get the aggregator key
    agg_key = get_agg_key(request_meta.aggregator, request_meta.metric) if \
        request_meta.aggregator else None

    args = ParameterMapping.map(request_meta)

    # Initialize the results
    results, metric_class, metric_obj = format_response(request_meta)

    start = metric_obj.datetime_start
    end = metric_obj.datetime_end

    if results['type'] == request_types.time_series:

        # Get aggregator
        try:
            aggregator_func = get_aggregator_type(agg_key)
        except MetricsAPIError as e:
            results['data'] = 'Request failed. ' + e.message
            return results

        # Determine intervals and thread allocation
        total_intervals = (date_parse(end) - date_parse(start)).\
            total_seconds() / (3600 * request_meta.slice)
        time_threads = max(1, int(total_intervals / INTERVALS_PER_THREAD))
        time_threads = min(MAX_THREADS, time_threads)

        logging.info(__name__ + ' :: Initiating time series for %(metric)s\n'
                                '\tAGGREGATOR = %(agg)s\n'
                                '\tFROM: %(start)s,\tTO: %(end)s.' %
                                {
                                    'metric': metric_class.__name__,
                                    'agg': request_meta.aggregator,
                                    'start': str(start),
                                    'end': str(end),
                                })
        metric_threads = '"k_" : {0}, "kr_" : {1}'.format(USER_THREADS,
                         REVISION_THREADS)
        metric_threads = '{' + metric_threads + '}'

        new_kwargs = deepcopy(args)

        del new_kwargs['slice']
        del new_kwargs['aggregator']
        del new_kwargs['datetime_start']
        del new_kwargs['datetime_end']

        out = tspm.build_time_series(start,
                                     end,
                                     request_meta.slice,
                                     metric_class,
                                     aggregator_func,
                                     users,
                                     kt_=time_threads,
                                     metric_threads=metric_threads,
                                     log=True,
                                     **new_kwargs)

        results['header'] = ['timestamp'] + \
            getattr(aggregator_func, um.METRIC_AGG_METHOD_HEAD)
        for row in out:
            timestamp = date_parse(row[0][:19]).strftime(
                DATETIME_STR_FORMAT)
            results['data'][timestamp] = row[3:]

    elif results['type'] == request_types.aggregator:

        # Get aggregator
        try:
            aggregator_func = get_aggregator_type(agg_key)
        except MetricsAPIError as e:
            results['data'] = 'Request failed. ' + e.message
            return results

        logging.info(__name__ + ' :: Initiating aggregator for %(metric)s\n'
                                '\AGGREGATOR = %(agg)s\n'
                                '\tFROM: %(start)s,\tTO: %(end)s.' %
                                {
                                    'metric': metric_class.__name__,
                                    'agg': request_meta.aggregator,
                                    'start': str(start),
                                    'end': str(end),
                                })

        try:
            metric_obj.process(users,
                               k_=USER_THREADS,
                               kr_=REVISION_THREADS,
                               log_=True,
                               **args)
        except UserMetricError as e:
            logging.error(__name__ + ' :: Metrics call failed: ' + str(e))
            results['data'] = str(e)
            return results

        r = um.aggregator(aggregator_func, metric_obj, metric_obj.header())
        results['header'] = to_string(r.header)
        results['data'] = r.data[1:]

    elif results['type'] == request_types.raw:

        logging.info(__name__ + ':: Initiating raw request for %(metric)s\n'
                                '\tFROM: %(start)s,\tTO: %(end)s.' %
                                {
                                    'metric': metric_class.__name__,
                                    'start': str(start),
                                    'end': str(end),
                                })
        try:
            metric_obj.process(users,
                               k_=USER_THREADS,
                               kr_=REVISION_THREADS,
                               log_=True,
                               **args)
        except UserMetricError as e:
            logging.error(__name__ + ' :: Metrics call failed: ' + str(e))
            results['data'] = str(e)
            return results

        for m in metric_obj.__iter__():
            results['data'][m[0]] = m[1:]

    return results
