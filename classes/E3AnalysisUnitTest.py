"""
    Unit Testing Framework for E3 Analytics
"""

__author__ = "Ryan Faulkner"
__date__ = "September 18, 2012"
__license__ = "GPL (version 2 or later)"

import sys
import unittest
import classes.DataLoader as DL
import classes.Metrics as M

class TestSequenceFunctions(unittest.TestCase):
    """
        Some Sample tests to ensure that the unit testing module is functioning properly
    """
    def setUp(self):
        self.seq = range(10)

    def test_shuffle(self):
        # make sure the shuffled sequence does not lose any elements
        random.shuffle(self.seq)
        self.seq.sort()
        self.assertEqual(self.seq, range(10))

        # should raise an exception for an immutable sequence
        self.assertRaises(TypeError, random.shuffle, (1,2,3))

    def test_choice(self):
        element = random.choice(self.seq)
        self.assertTrue(element in self.seq)

    def test_sample(self):
        with self.assertRaises(ValueError):
            random.sample(self.seq, 20)
        for element in random.sample(self.seq, 5):
            self.assertTrue(element in self.seq)


class TestTimeToThreshold(unittest.TestCase):
    """
        Class that defines unit tests across the TimeToThreshold Metrics class
    """

    def setUp(self):
        self.uid = 13234584 # Renklauf
        self.ttt = M.TimeToThreshold(M.TimeToThreshold.EDIT_COUNT_THRESHOLD, first_edit=1, threshold_edit=2)

    def test_time_diff_greater_than_a_day(self):
        """
            Ensure that the time to threshold when exceeding one day reports the correct value
        """

        self.assertEqual(self.ttt.process(self.uid), 1441)


def main():
    # Execute desired unit tests
    unittest.main()


# Call Main
if __name__ == "__main__":
    sys.exit(main([]))