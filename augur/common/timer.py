import time


class Timer(object):
    def __init__(self, name):
        self.start_time = None
        self.timer_name = name
        self._splits = []

    def split(self, name):
        self._splits.append((name, time.clock()))

    def __enter__(self):
        self.start_time = time.clock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print "Timer: %s" % self.timer_name
        print "------"
        print "Start time: %f" % self.start_time
        last_time = self.start_time
        for split in self._splits:
            print ">> %s - %f (%f)" % (split[0], split[1], split[1] - last_time)
            last_time = split[1]
        print "######################################"
