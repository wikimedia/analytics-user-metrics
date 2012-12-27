
"""
    This module contains methods that provide functionality for aggregating metrics data
"""

__author__ = "ryan faulkner"
__date__ = "12/12/2012"
__license__ = "GPL (version 2 or later)"

from itertools import izip
from numpy import array

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


def identity(x):
    """ The identity aggregator - returns whatever was put in """
    return x

def list_sum_indices(l, indices):
    """
        Sums the elements of list indicated by numeric list `indices`.  The elements must be summable (i.e. e1 + e2 is allowed
        for all e1 and e2).

        Returns: <list of summed elements>

        e.g.
        >>> l = [['1',1,50],['2',4,1],['3',2,6]]
        >>> list_sum_indices(l,[1,2])
        [7, 57]
    """
    return list(reduce(lambda x,y: x+y, [array([elem.__getitem__(i) for i in indices]) for elem in l]))

def list_sum_by_group(l, group_index):
    """
        Sums the elements of list keyed on `key_index`.  The elements must be summable (i.e. e1 + e2 is allowed
        for all e1 and e2).  All elements outside of key are summed on matching keys.

        Returns: <list of summed and keyed elements>

        e.g.
        >>> l = [[2,1],[1,4],[2,2]]
        >>> list_sum_by_group(l,0)
        [[1,4], [2,3]]
    """
    d=dict()
    for i in l:
        summables = i[:group_index] + i[group_index+1:]
        if d.has_key(i[group_index]):
            d[i[group_index]] = map(sum, izip(summables,d[i[group_index]]))
        else:
            d[i[group_index]] = summables
    return [d[k][:group_index] + [k] + d[k][group_index:] for k in d]


def list_average_by_group(l, group_index):
    """
        Computes the average of the elements of list keyed on `key_index`.  The elements must be summable
        (i.e. e1 + e2 is allowed for all e1 and e2).  All elements outside of key are summed on matching keys.
        This duplicates the code of `list_sum_by_group` since it needs to compute counts in the loop also.

        Returns: <list of averaged and keyed elements>

        e.g.
        >>> l = [[2,1],[1,4],[2,2]]
        >>> list_average(l,0)
        [[1, 4.0], [2, 1.5]]
    """
    d=dict()
    counts=dict()
    for i in l:
        summables = i[:group_index] + i[group_index+1:]
        if d.has_key(i[group_index]):
            d[i[group_index]] = map(sum, izip(summables,d[i[group_index]]))
            counts[i[group_index]] += 1
        else:
            d[i[group_index]] = summables
            counts[i[group_index]] = 1
    for k in counts: d[k] = list(array(d[k]) / float(counts[k]))     # use numpy array perform list operation
    return [d[k][:group_index] + [k] + d[k][group_index:] for k in d]

class AggregatorException(Exception): pass

