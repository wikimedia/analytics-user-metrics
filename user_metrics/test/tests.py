"""
    Test user metrics methods.  This file contains method definitions to be
    invoked by nose_.  The testing framework focuses on ensuring that
    UserMetric and API functionality functions correctly.

    .. _nose: https://nose.readthedocs.org/en/latest/
"""

__author__ = "ryan faulkner"
__email__ = "rfaulkner@wikimedia.org"
__date__ = "02/14/2012"
__license__ = "GPL (version 2 or later)"

from user_metrics.metrics import edit_count


# User Metric tests
# =================


def test_blocks():
    assert False  # TODO: implement your test here


def test_namespace_of_edits():
    assert False  # TODO: implement your test here


def test_time_to_threshold():
    assert False  # TODO: implement your test here


def test_edit_rate():
    assert False  # TODO: implement your test here


def test_edit_count():
    """ Test the edit count metric results """
    results = {
        '13234584': 18,
        '13234503': 2,
        '13234565': 0,
        '13234585': 2,
        '13234556': 6,
        }
    e = edit_count.EditCount(t=10000)

    # Check edit counts against
    index = 0
    for res in e.process(results.keys()):
        assert res[1] == results[str(res[0])]
        index += 1


def test_live_account():
    assert False  # TODO: implement your test here


def test_threshold():
    assert False  # TODO: implement your test here


def test_survival():
    assert False  # TODO: implement your test here


def test_bytes_added():
    assert False  # TODO: implement your test here


def test_revert_rate():
    assert False  # TODO: implement your test here


def test_user():
    assert False  # TODO: implement your test here


# Query call tests
# ================


def test_get_user_reg_from_logging():
    assert False  # TODO: implement your test here


# ETL tests
# =========


def test_connect_to_dbs():
    assert False  # TODO: implement your test here


# API tests
# =========


def test_cohort_parse():
    assert False  # TODO: implement your test here


# Utilities tests
# ===============


def test_recordtype():
    assert False  # TODO: implement your test here