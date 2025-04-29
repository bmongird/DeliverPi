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

logging.basicConfig(filename="logs.txt", level=logging.DEBUG, format=f'[LINE FOLLOWER] %(asctime)s - %(levelname)s - %(message)s')


car = mecanum.MecanumChassis()
line = infrared.FourInfrared()
_is_running = False

context = zmq.Context()
dealer_socket = context.socket(zmq.DEALER)
dealer_socket.identity = b"linefollower"
dealer_socket.connect("tcp://localhost:5575")

aisle_var = None
turn_direction = 0

aisle_condition = threading.Condition()


def turn(direction: int, timesleep: float = 0.3, speed: int = 0):
    """Function to control vehicle aisle turning

    :param direction: 0 for left, 1 for right
    """
    global _is_running
    was_running = _is_running
    _is_running = False
    turning = True
    yaw = -0.2 if direction == 0 else 0.2
    car.set_velocity(speed,90, yaw)
    time.sleep(timesleep)
    while turning:
        sensor1, sensor2, sensor3, sensor4 = line.readData()
        if direction == 0 and sensor1:
            turning = False
        elif direction == 1 and sensor4:
            turning = False
    car.set_velocity(0,90,0)
    print(f"was_running val: {was_running}")
    _is_running = was_running
            
            
def msg():
    global aisle_var
    global _is_running
    global turn_direction
    while True:
        empty, request = dealer_socket.recv_multipart() # removing the prepended filter
        request = json.loads(request)
        logging.debug(f"Received request: {request}")
        print(f"LINEFOLLOWER: Received request {request}")
        
        if request["command"] == "check":
            dealer_socket.send_multipart([b"", "ONLINE".encode()])
        elif request["command"] == "start":
            _is_running = True
            logging.info("At start. Initiating turn")
            if "param" in request:
                if request["param"] == 180:
                    turn(0)
                elif request["param"] == 90:
                    turn(1)
                # elif request["param"] == "reverse":
            logging.info(f"Starting line following")
            # maybe send back an acknowledge?
        elif request["command"] == "turn":
            direction = 1 if request["direction"] else 0
            turn(direction)
        elif request["command"] == "stop":
            _is_running = False
            car.set_velocity(0,90,0)
            dealer_socket.send_multipart([b"", "STOPPED".encode()]) # informing controller that we successfully stopped
        elif request["command"] == "resume":
            _is_running = True
            logging.info(f"Resuming linefollower")
        elif request["command"] == "end":
            aisle_var = None
            with aisle_condition:
                aisle_var = "end"
                aisle_condition.notify()
        elif request["command"] == "enter":
            aisle_var = None
            #continue down aisle
            with aisle_condition:
                aisle_var = "enter"
                print("secured condition var in msg")
                turn_direction = 1 if "direction" in request else 0 #TODO: make direction mandatory in the request
                aisle_condition.notify()
        elif request["command"] == "ignore":
            aisle_var = None
            with aisle_condition:
                aisle_var = "ignore"
                aisle_condition.notify()
            # ignore aisle

msg_thread = threading.Thread(target=msg)
msg_thread.daemon = True
msg_thread.start()

car_speed = 30

car.set_velocity(0,90,0)

no_line_count = 0

while True:
    while _is_running:
        # Averaging sensor data
        # s = [0,0,0,0]
        # sensor1, sensor2, sensor3, sensor4 = [False, False, False, False]
        # for i in range(0,3):
        #     sensor1, sensor2, sensor3, sensor4 = line.readData() # 读取4路循传感器数据(read 4-channel sensor data)
        #     j = 0
        #     for sensor in [sensor1,sensor2,sensor3,sensor4]:
        #         if sensor:
        #             s[j] += 1
        #         j +=1
        # j = 0
        # for sensor in [sensor1, sensor2, sensor3, sensor4]:
        #     if s[j] >= 2:
        #         sensor = True
        #     else:
        #         sensor = False
        #     j +=1
        sensor1, sensor2, sensor3, sensor4 = line.readData()
        match sensor1, sensor2, sensor3, sensor4:
            case False, False, False, False:
                # no_line_count += 1
                looping = True
                count = 0
                while looping:
                    count += 1
                    sensor1, sensor2, sensor3, sensor4 = line.readData()
                    if sensor1 == False and sensor2 == False and sensor3 == False and sensor4 == False:
                        no_line_count += 1
                        time.sleep(0.1)
                    if no_line_count == 10:# should be looping here
                        no_line_count = 0
                        car.set_velocity(0,90,-.1)
                        dealer_socket.send_multipart([b"", "no_line".encode()])
                    if count == 10:
                        looping = False
                no_line_count = 0
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
                car.set_velocity(0,90,0)
                aisle_var = None
                dealer_socket.send_multipart([b"", "intersection_reached".encode()])
                with aisle_condition:
                    while aisle_var == None:
                        aisle_condition.wait()
                    if aisle_var == "ignore":
                        logging.debug("Ignoring aisle")
                        car.set_velocity(car_speed,90,0)
                        # give enough time to clear the aisle
                        time.sleep(0.8)
                    elif aisle_var == "enter":
                        logging.debug("Entering aisle")
                        turn(turn_direction, 0.5, 4)
                        dealer_socket.send_multipart([b"", "aisle_entered".encode()])
                    elif aisle_var == "end":
                        turn(0, 1.5)
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
                aisle_var = None
                dealer_socket.send_multipart([b"", "intersection_reached".encode()])
                with aisle_condition:
                    while aisle_var == None:
                        aisle_condition.wait()
                    if aisle_var == "ignore":
                        logging.debug("Ignoring aisle")
                        car.set_velocity(car_speed,90,0)
                        # give enough time to clear the aisle
                        time.sleep(0.8)
                    elif aisle_var == "enter":
                        logging.debug("Entering aisle")
                        turn(turn_direction, 0.5, 4)
                        dealer_socket.send_multipart([b"", "aisle_entered".encode()])
                    elif aisle_var == "end":
                        turn(0, 1.5)
                
            case True, True, True, True:
                car.set_velocity(0,90,0)
                aisle_var = None
                dealer_socket.send_multipart([b"", "intersection_reached".encode()])
                with aisle_condition:
                    while aisle_var == None:
                        aisle_condition.wait()
                    if aisle_var == "ignore":
                        logging.debug("Ignoring aisle")
                        car.set_velocity(car_speed,90,0)
                        # give enough time to clear the aisle
                        time.sleep(0.8)
                    elif aisle_var == "enter":
                        logging.debug("Entering aisle")
                        turn(turn_direction, 0.5, 4)
                        dealer_socket.send_multipart([b"", "aisle_entered".encode()])
                    elif aisle_var == "end":
                        turn(0, 1.5)
            case _:
                car.set_velocity(0,90,0)
        time.sleep(0.02)
