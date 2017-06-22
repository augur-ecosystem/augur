import time
import logging
import sys


class Timer(object):
    def __init__(self, name):
        self.logger = logging.getLogger("timer")
        self.start_time = None
        self.timer_name = name
        self._splits = []

    def split(self, name):
        self._splits.append((name, time.clock()))

    def __enter__(self):
        self.start_time = time.clock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.info("Timer: %s" % self.timer_name)
        current_time = time.clock()
        total_time = current_time - self.start_time

        if len(self._splits) > 0:
            last_time = self.start_time
            self.logger.info("   Splits:")
            for split in self._splits:
                self.logger.info("     %s - %f" % (split[0], split[1] - last_time))
                last_time = split[1]

        self.logger.info("  Total ticks: %f" % total_time)
