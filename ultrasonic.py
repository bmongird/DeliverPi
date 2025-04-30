""" Fairly simple ultrasonic detection script. Not really much to it.
"""

import json
import logging
import sys
import threading
import time
import zmq
sys.path.append('/home/pi/TurboPi/')
import HiwonderSDK.Sonar as Sonar

logging.basicConfig(filename="logs.txt", level=logging.DEBUG, format=f'[ULTRASONIC] %(asctime)s - %(levelname)s - %(message)s')

HWSONAR = Sonar.Sonar()

# open communication with the controller
context = zmq.Context()
dealer_socket = context.socket(zmq.DEALER)
dealer_socket.identity = b"ultrasonic"
dealer_socket.connect("tcp://localhost:5575")

is_blocked = False
_is_running = False
time_blocked = 0

def msg():
    global _is_running
    while(True):
        empty, request = dealer_socket.recv_multipart()
        request = json.loads(request)
        logging.debug(f"Received request: {request}")
        
        if request["command"] == "check":
            dealer_socket.send_multipart([b"", "ONLINE".encode()])
        elif request["command"] == "start":
            _is_running = True
            logging.info(f"Starting ultrasonic detection")
            # maybe send back an acknowledge?
        elif request["command"] == "stop":
            _is_running = False
            dealer_socket.send_multipart([b"", "STOPPED".encode()]) # informing controller that we successfully stopped
        elif request["command"] == "resume":
            _is_running = True
            logging.info(f"Resuming ultrasonic detection")

msg_thread = threading.Thread(target=msg)
msg_thread.daemon = True
msg_thread.start()

while True:
    if _is_running:
        dist = 0
        for i in range(0,5):
            # this loop is to get an average because the sonar can be wonky sometimes
            tmp_dist = HWSONAR.getDistance() / 10.0 # 获取超声波传感器距离数据(get ultrasonic sensor distance data)
            dist += tmp_dist
            time.sleep(0.01)
        dist /= 5
        
        if time_blocked >= 10:
            # we've been blocked for a while, notify controller
            time_blocked = 0
            dealer_socket.send_multipart([b"", "blocked_timeout".encode()])
            time.sleep(1)
            
        if dist <= 10.0:
            if is_blocked == False:
                dealer_socket.send_multipart([b"", "path_blocked".encode()])
                is_blocked = True
            time_blocked += 0.1
            time.sleep(0.1)
        else:
            if is_blocked == True:
                dealer_socket.send_multipart([b"", "path_unblocked".encode()])
            is_blocked = False
            time.sleep(0.1)
    else:
        is_blocked = False
        time_blocked = 0