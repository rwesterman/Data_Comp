# This .py file holds all global variables so they can be used across modules within this project
# import queue
import logging
import multiprocessing

# A Queue to hold logging requests so they can be displayed in real time
# log_q = queue.Queue()
# log_q = multiprocessing.Queue()

# A flag that tells the logging loop to continue
loop_flag = True

dbglog = logging.getLogger(__name__)
stdout = logging.StreamHandler()
stdout.setLevel(logging.DEBUG)
dbglog.addHandler(stdout)
dbglog.setLevel(logging.DEBUG)