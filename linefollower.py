import json
import logging
import sys

import zmq
sys.path.append('/home/pi/TurboPi/')
import cv2
import time
import math
import signal
import Camera
import threading
import numpy as np
import yaml_handle
import HiwonderSDK.mecanum as mecanum
import HiwonderSDK.FourInfrared as infrared

car = mecanum.MecanumChassis()
line = infrared.FourInfrared()
_is_running = True

context = zmq.Context()
dealer_socket = context.socket(zmq.DEALER)
dealer_socket.identity = b"linefollower"
dealer_socket.connect("tcp://localhost:5575")

response_received = False
ignore_aisle = False

def msg():
    while True:
        empty, request = dealer_socket.recv_multipart() # removing the prepended filter
        request = json.loads(request)
        logging.debug(f"Received request: {request}")
        
        if request["command"] == "check":
            dealer_socket.send_multipart([b"", "ONLINE".encode()])
        elif request["command"] == "start":
            _is_running = True
            logging.info(f"Starting line following")
            # maybe send back an acknowledge?
        elif request["command"] == "stop":
            _is_running = False
            car.set_velocity(0,90,0)
            dealer_socket.send_multipart([b"", "STOPPED".encode()]) # informing controller that we successfully stopped
        elif request["command"] == "resume":
            _is_running = True
            logging.info(f"Resuming linefollower")
        elif request["command"] == "enter":
            #continue down aisle
            ignore_aisle = False
            response_received = True
            pass
        elif request["command"] == "ignore":
            ignore_aisle = True
            response_received = True
            # ignore aisle

msg_thread = threading.Thread(target=msg)
msg_thread.daemon = True
msg_thread.start()

def turn(direction: int):
    """Function to control vehicle aisle turning

    :param direction: 0 for left, 1 for right
    """
    turning = True
    yaw = -0.2 if direction == 0 else 0.2
    time.sleep(0.3)
    car.set_velocity(0,90, yaw)
    while turning:
        sensor1, sensor2, sensor3, sensor4 = line.readData()
        if direction == 0 and sensor1:
            turning = False
        elif direction == 1 and sensor4:
            turning = False
            
car_speed = 20

while True:
    while _is_running:
        sensor1, sensor2, sensor3, sensor4 = line.readData() # 读取4路循传感器数据(read 4-channel sensor data)
        match sensor1, sensor2, sensor3, sensor4:
            case False, False, False, False:
                car.set_velocity(0,90,0)
            case False, False, False, True:
                car.set_velocity(10, 90, 0.2)
            case False, False, True, False:
                car.set_velocity(car_speed, 90, 0.03)
            case False, False, True, True:
                car.set_velocity(car_speed, 90, 0.1)
            case False, True, False, False:
                car.set_velocity(car_speed, 90, -0.03)
            case False, True, False, True:
                #invalid state
                car.set_velocity(0,90,0)
            case False, True, True, False:
                car.set_velocity(car_speed,90,0)
            case False, True, True, True:
                turn(1)
            case True, False, False, False:
                car.set_velocity(10, 90, -0.2)
            case True, False, False, True:
                #invalid state
                car.set_velocity(0,90,0)
            case True, False, True, False:
                #invalid state
                car.set_velocity(0,90,0)
            case True, False, True, True:
                #invalid state
                car.set_velocity(0,90,0)
            case True, True, False, False:
                car.set_velocity(car_speed, 90, -0.2)
            case True, True, False, True:
                #invalid state
                car.set_velocity(0,90,0)
            case True, True, True, False:
                # NOTE: Special case because this means we've reached an aisle. Check if we should continue.
                car.set_velocity(0,90,0)
                dealer_socket.send_multipart([b"", "aisle_reached".encode()])
                while not response_received:
                    time.sleep(0.01)
                if ignore_aisle:
                    car.set_velocity(car_speed,90,0)
                    # give enough time to clear the aisle
                    time.sleep(0.8)
                else:
                    turn(0)
            case True, True, True, True:
                #invalid state
                car.set_velocity(0,90,0)
            case _:
                car.set_velocity(0,90,0)
        time.sleep(0.02)