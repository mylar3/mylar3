#!/usr/bin/env python
""" stresstest.py:  A stress-tester for ConcurrentRotatingFileHandler

This utility spawns a bunch of processes that all try to concurrently write to
the same file. This is pretty much the worst-case scenario for my log handler.
Once all of the processes have completed writing to the log file, the output is
compared to see if any log messages have been lost.

In the future, I may also add in support for testing with each process having
multiple threads.


"""

__version__ = '$Id$'
__author__ = 'Lowell Alleman'


import os
import sys
from subprocess import call, Popen, STDOUT
from time import sleep

ROTATE_COUNT = 5000

# local lib; for testing
from cloghandler import ConcurrentRotatingFileHandler

class RotateLogStressTester:
    def __init__(self, sharedfile, uniquefile, name="LogStressTester", logger_delay=0):
        self.sharedfile = sharedfile
        self.uniquefile = uniquefile
        self.name = name
        self.writeLoops = 100000
        self.rotateSize = 128 * 1024
        self.rotateCount = ROTATE_COUNT
        self.random_sleep_mode = False
        self.debug = False
        self.logger_delay = logger_delay
    
    def getLogHandler(self, fn):
        """ Override this method if you want to test a different logging handler
        class. """
        return ConcurrentRotatingFileHandler(fn, 'a', self.rotateSize,
                                             self.rotateCount, delay=self.logger_delay,
                                             debug=self.debug)
        # To run the test with the standard library's RotatingFileHandler:
        # from logging.handlers import RotatingFileHandler
        # return RotatingFileHandler(fn, 'a', self.rotateSize, self.rotateCount)
    
    def start(self):
        from logging import getLogger, FileHandler, Formatter, DEBUG
        self.log = getLogger(self.name)
        self.log.setLevel(DEBUG)
        
        formatter = Formatter('%(asctime)s [%(process)d:%(threadName)s] %(levelname)-8s %(name)s:  %(message)s')
        # Unique log handler (single file)
        handler  = FileHandler(self.uniquefile, "w")
        handler.setLevel(DEBUG)
        handler.setFormatter(formatter)
        self.log.addHandler(handler)
        
        # If you suspect that the diff stuff isn't working, un comment the next
        # line.  You should see this show up once per-process.
        # self.log.info("Here is a line that should only be in the first output.")
        
        # Setup output used for testing
        handler = self.getLogHandler(self.sharedfile)
        handler.setLevel(DEBUG)
        handler.setFormatter(formatter)
        self.log.addHandler(handler)
        
        # If this ever becomes a real "Thread", then remove this line:
        self.run()
    
    def run(self):
        c = 0
        from random import choice, randint
        # Use a bunch of random quotes, numbers, and severity levels to mix it up a bit!
        msgs = ["I found %d puppies", "There are %d cats in your hatz",
                "my favorite number is %d", "I am %d years old.", "1 + 1 = %d",
                "%d/0 = DivideByZero", "blah!  %d thingies!", "8 15 16 23 48 %d",
                "the worlds largest prime number: %d", "%d happy meals!"]
        logfuncts = [self.log.debug, self.log.info, self.log.warn, self.log.error]
        
        self.log.info("Starting to write random log message.   Loop=%d", self.writeLoops)
        while c <= self.writeLoops:
            c += 1
            msg = choice(msgs)
            logfunc = choice(logfuncts)
            logfunc(msg, randint(0,99999999))
            
            if self.random_sleep_mode and c % 1000 == 0:
                # Sleep from 0-15 seconds
                s = randint(1,15)
                print("PID %d sleeping for %d seconds" % (os.getpid(), s))
                sleep(s)
            # break
        self.log.info("Done witting random log messages.")

def iter_lognames(logfile, count):
    """ Generator for log file names based on a rotation scheme """
    for i in range(count -1, 0, -1):
        yield "%s.%d" % (logfile, i)
    yield logfile

def iter_logs(iterable, missing_ok=False):
    """ Generator to extract log entries from shared log file. """
    for fn in iterable:
        if os.path.exists(fn):
            for line in open(fn):
                yield line
        elif not missing_ok:
            raise ValueError("Missing log file %s" % fn)

def combine_logs(combinedlog, iterable, mode="w"):
    """ write all lines (iterable) into a single log file. """
    fp = open(combinedlog, mode)
    for chunk in iterable:
        fp.write(chunk)
    fp.close()



from optparse import OptionParser
parser = OptionParser(usage="usage:  %prog",
                      version=__version__,
                      description="Stress test the cloghandler module.")
parser.add_option("--log-calls", metavar="NUM",
                  action="store", type="int", default=50000,
                  help="Number of logging entries to write to each log file.  "
                  "Default is %default")
parser.add_option("--random-sleep-mode",
                  action="store_true", default=False)
parser.add_option("--debug",
                  action="store_true", default=False)
parser.add_option("--logger-delay",
                  action="store_true", default=False,
                   help="Enable the 'delay' mode in the logger class. "
                  "This means that the log file will be opened on demand.") 


def main_client(args):
    (options, args) = parser.parse_args(args)
    if len(args) != 2:
        raise ValueError("Require 2 arguments.  We have %d args" % len(args))
    (shared, client) = args
    
    if os.path.isfile(client):
        sys.stderr.write("Already a client using output file %s\n" % client)
        sys.exit(1)
    tester = RotateLogStressTester(shared, client, logger_delay=options.logger_delay)
    tester.random_sleep_mode = options.random_sleep_mode
    tester.debug = options.debug
    tester.writeLoops = options.log_calls
    tester.start()
    print("We are done  pid=%d" % os.getpid())



class TestManager:
    class ChildProc(object):
        """ Very simple child container class."""
        __slots__ = [ "popen", "sharedfile", "clientfile" ]
        def __init__(self, **kwargs):
            self.update(**kwargs)
        def update(self, **kwargs):
            for key, val in kwargs.items():
                setattr(self, key, val)
    
    def __init__(self):
        self.tests = []
    
    def launchPopen(self, *args, **kwargs):
        proc = Popen(*args, **kwargs)
        cp = self.ChildProc(popen=proc)
        self.tests.append(cp)
        return cp
    
    def wait(self, check_interval=3):
        """ Wait for all child test processes to complete. """
        print("Waiting while children are out running and playing!")
        while True:
            sleep(check_interval)
            waiting = []
            for cp in self.tests:
                if cp.popen.poll() is None:
                    waiting.append(cp.popen.pid)
            if not waiting:
                break
            print("Waiting on %r " % waiting)
        print("All children have stopped.")
    
    def checkExitCodes(self):
        for cp in self.tests:
            if cp.popen.poll() != 0:
                return False
        return True



def unified_diff(a,b, out=sys.stdout):
    import difflib
    ai = open(a).readlines()
    bi = open(b).readlines()
    for line in difflib.unified_diff(ai, bi, a, b):
        out.write(line)



def main_runner(args):
    parser.add_option("--processes", metavar="NUM",
                      action="store", type="int", default=3,
                      help="Number of processes to spawn.  Default: %default")
    parser.add_option("--delay", metavar="secs",
                      action="store", type="float", default=2.5,
                      help="Wait SECS before spawning next processes.  "
                      "Default: %default")
    parser.add_option("-p", "--path", metavar="DIR",
                      action="store", default="test",
                      help="Path to a temporary directory.  Default: '%default'")
    
    
    this_script = args[0]
    (options, args) = parser.parse_args(args)
    options.path = os.path.abspath(options.path)
    if not os.path.isdir(options.path):
        os.makedirs(options.path)
    
    manager = TestManager()
    shared = os.path.join(options.path, "shared.log")
    for client_id in range(options.processes):
        client = os.path.join(options.path, "client.log_client%s.log" % client_id)
        cmdline = [ sys.executable, this_script, "client", shared, client,
                   "--log-calls=%d" % options.log_calls ]
        if options.random_sleep_mode:
            cmdline.append("--random-sleep-mode")
        if options.debug:
            cmdline.append("--debug")
        if options.logger_delay:
            cmdline.append("--logger-delay")
        
        child = manager.launchPopen(cmdline)
        child.update(sharedfile=shared, clientfile=client)
        sleep(options.delay)
    
    # Wait for all of the subprocesses to exit
    manager.wait()
    # Check children exit codes
    if not manager.checkExitCodes():
        sys.stderr.write("One or more of the child process has failed.\n"
                         "Aborting test.\n")
        sys.exit(2)
    
    client_combo = os.path.join(options.path, "client.log.combo")
    shared_combo = os.path.join(options.path, "shared.log.combo")
    
    # Combine all of the log files...
    client_files = [ child.clientfile for child in manager.tests ]
        
    if False:
        def sort_em(iterable):
            return iterable
    else:
       sort_em = sorted
    
    print("Writing out combined client logs...")
    combine_logs(client_combo, sort_em(iter_logs(client_files)))
    print("done.")
    
    print("Writing out combined shared logs...")
    shared_log_files = iter_lognames(shared, ROTATE_COUNT)
    log_lines = iter_logs(shared_log_files, missing_ok=True)
    combine_logs(shared_combo, sort_em(log_lines))
    print("done.")
    
    print("Running internal diff:  (If the next line is 'end of diff', then the stress test passed!)")
    unified_diff(client_combo, shared_combo)
    print("   --- end of diff ----")



if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1].lower() == "client":
            main_client(sys.argv[2:])
    else:
        main_runner(sys.argv)
