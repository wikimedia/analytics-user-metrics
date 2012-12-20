
"""
    This module contains methods that provide functionality for aggregating metrics data
"""

__author__ = "ryan faulkner"
__date__ = "12/12/2012"
__license__ = "GPL (version 2 or later)"

import src.metrics.threshold as th
import src.metrics.revert_rate as rr
from itertools import izip

def decorator_builder(header):
    """ Decorator method to annotate aggregation methods to ensure the correct data model is exposed by """
    def eval_data_model(f):
        def wrapper(metric):
            if hasattr(metric,'header'):
                header_arg = metric.header()
                if all(header_arg[i] == header[i] for i in range(len(header)-1)):
                    return f(metric)
            else:
                raise AggregatorException('This aggregator (%s) does not operate on this data type.' % f.__name__)
        return wrapper
    return eval_data_model

@decorator_builder(th.Threshold.header())
def threshold_editors_agg(metric):
    """ Computes the fraction of editors reaching a threshold """
    total=0
    pos=0
    for r in metric.__iter__():
        try:
            if r[1]: pos+=1
            total+=1
        except IndexError: continue
        except TypeError: continue
    if total:
        return total, pos, float(pos) / total
    else:
        return total, pos, 0.0

@decorator_builder(rr.RevertRate.header())
def reverted_revs_agg(metric):
    """ Computes revert metrics on a user set """
    total_revs = 0
    weighted_rate = 0.0
    total_editors = 0
    reverted_editors = 0
    for r in metric.__iter__():
        try:
            reverted_revs = int(r[2])
            total_editors += 1
            if reverted_revs: reverted_editors += 1
            total_revs += reverted_revs
            weighted_rate += reverted_revs * float(r[1])
        except IndexError: continue
        except TypeError: continue
    if total_revs:
        weighted_rate /= total_revs
    else:
        weighted_rate = 0.0
    return total_revs, weighted_rate, total_editors, reverted_editors

def list_summation(l, key_index):
    """
        Sums the elements of list keyed on `key_index`.  The elements must be summable (i.e. e1 + e2 is allowed
        for all e1 and e2).

        e.g.
        >>> l = [[2,1],[1,4],[2,2]]
        >>> list_summation(l,0)
        [[1,4], [2,3]]
    """
    d=dict()
    for i in l:
        summables = i[:key_index] + i[key_index+1:]
        if d.has_key(i[key_index]):
            d[i[key_index]] = map(sum, izip(summables,d[i[key_index]]))
        else:
            d[i[key_index]] = summables
    return [d[k][:key_index] + [k] + d[k][key_index:] for k in d]

class AggregatorException(Exception): pass

