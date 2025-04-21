import json
import os
import signal
import subprocess
import sys
from typing import Tuple, cast
import zmq
import time
import threading
import logging
from states import ControllerStateMachine, ControllerStates
from common import CONTROLLER_PORT, HUB_PORT, OrderData, validate_order_data

sys.path.append('/home/pi/TurboPi/')
import HiwonderSDK.mecanum as mecanum


logging.basicConfig(filename="logs.txt", level=logging.DEBUG, format=f'[CONTROLLER] %(asctime)s - %(levelname)s - %(message)s')
logging.info("Initializing controller program")

# instantiate all subprocesses
active_subprocesses = []
camera_process = subprocess.Popen(["python", os.path.join(os.getcwd(), "color_detect.py")])
active_subprocesses.append(camera_process)
ultrasonic_process = subprocess.Popen(["python", os.path.join(os.getcwd(), "ultrasonic.py")])
active_subprocesses.append(ultrasonic_process)
linefollower_process = subprocess.Popen(["python", os.path.join(os.getcwd(), "linefollower.py")])
active_subprocesses.append(linefollower_process)

car = mecanum.MecanumChassis()
import HiwonderSDK.ros_robot_controller_sdk as rrc
board = rrc.Board()

aisle_num = 0

HUB_HOST = "10.68.200.31"

class Controller():
    """Singleton class that controls robot execution
    """
    __initialized = False
    instance = None
    
    def __new__(cls): 
        if cls.instance == None:
            cls.instance = super().__new__(cls)
        return cls.instance
    
    def __init__(self):
        if not self.__initialized:
            self.state_machine = ControllerStateMachine()
            
            context = zmq.Context()
            self.router_socket = context.socket(zmq.ROUTER)
            self.router_socket.bind("tcp://*:5575")
            
            self.req_socket = context.socket(zmq.REQ)
            self.req_socket.connect(f"tcp://{HUB_HOST}:{HUB_PORT}")

            self.pub_socket = context.socket(zmq.PUB)
            self.pub_socket.bind(f"tcp://*:{CONTROLLER_PORT}")
            
            self.process_event_lock = threading.Lock()
            
            self.components = ["camera", "ultrasonic", "linefollower"]
            self.check_components()
            
            self.remaining_packages = []
            self.completed_packages = []
            
            self.__initialized = True
            self.state_machine.transition("init_done")
            self.exec_thread = threading.Thread(target=self.execution_thread)
            self.exec_thread.start()
        
    def _send_msg(self, identity: str, msg: str):
        """Send a message on the router socket

        :param identity: recipient identity 
        :param msg: message to send
        """
        msg = msg.encode()
        identity = identity.encode()
        self.router_socket.send_multipart([identity, b"", msg])

    def _recv_msg(self) -> Tuple[str, str]:
        """Receive a message on the router socket
        
        :return: tuple containing identity of the sender and message
        """
        
        identity, empty, message = self.router_socket.recv_multipart()
        identity = identity.decode()
        message = message.decode()
        print(f"Message received from from {identity}: {message}")
        return (identity, message)
        
    def listen_for_messages(self):
        """Thread that will listen for messages on the router socket
        """
        while True:
            # Receive identity and message
            identity, message = self._recv_msg()
            self.process_message(identity, message)
                        
    def process_message(self, identity: str, message: str):
        """Process a message received on the router socket

        :param message: message to process
        """
        match identity:
            case "camera":
                if "color_detected" in message:
                    # Trigger appropriate action
                    print("CONTROLLER: Color detected!")
                    self.process_event("color_detected")
                    logging.debug(f"Taking action for detected color: {message}")
                elif "STOPPED" in message:
                    logging.debug(f"Successfully stopped color detection")
                elif "ERROR" in message:
                    logging.error(f"{identity} {message}")
            case "ultrasonic":
                self.process_event(message)
            case "linefollower":
                self.process_event(message)
                    
    
    def check_components(self):
        """Verify that all components are available and online
        """
        self.router_socket.setsockopt(zmq.RCVTIMEO, 3000) # timeout on receives after 3s
        print("INITIATING COMPONENT CHECKS\n--------------------------------------")
        for component in self.components:
            print(f"Checking component {component}")
            for i in range(0,3):
                self._send_msg(component, '{"command": "check"}')
                
                try:
                    identity, response = self._recv_msg()
                except Exception as e:
                    print(e)
                    if i == 2:
                        print(f"Did not receive a response from component {component}. Aborting.")
                        self.exit(1)
                    print(f"Timeout occurred. Trying again ({i+1}/3)")
                    continue

                if response != "ONLINE":
                    if i == 2:
                        print(f"Component {identity} not online. Aborting.")
                        logging.error(f"Component {identity} not online")
                        self.exit(1)
                    print(f"Component {identity} not ready. Trying again ({i+1}/3)")
                    time.sleep(0.5)
                else:
                    print(f"Component {identity} online!")
                    break
        logging.info("All components online")
        print("ALL COMPONENTS ONLINE!\n--------------------------------------")
        self.router_socket.setsockopt(zmq.RCVTIMEO, -1)
        
    def process_event(self, event: str):
        """Process an event. Note that this function needs to run fairly quickly to avoid slowdown

        :param event: event to be processed
        """
        with self.process_event_lock:
            current_state = self.state_machine.state
            next_state = self.state_machine.get_next_state(event)
            match event:
                case "order_received":
                    # start line tracking thread to correct aisle
                    msg = {
                        "command": "start"
                    }
                    for component in self.components:
                        if component == "camera":
                            continue
                        self._send_msg(component, json.dumps(msg))
                case "order_grabbed":
                    self.remaining_packages[0]["picked"] = True
                    self.completed_packages.append(self.remaining_packages.pop(0))
                    logging.info(f"Successfully grabbed package {self.completed_packages[-1]}")
                    if len(self.remaining_packages) > 0:
                        if self.remaining_packages[0]["aisle"] == self.completed_packages[-1]["aisle"]:
                            # back up and picking init          
                            # implement this in line follower instead for robustness 
                            car.set_velocity(-20,90,0)
                            time.sleep(1)
                            color = self.remaining_packages[0]["color"]
                            msg = {
                                "command": "detect_color",
                                "color": color
                            }
                            self._send_msg("camera", json.dumps(msg))
                        else:
                            msg = {
                                "command": "start",
                                "param": 180
                            }
                            event = "exiting"
                            self._send_msg("linefollower", json.dumps(msg))
                    else:
                        print("all done!")
                        msg = {
                            "command": "stop"
                        }
                        for component in self.components:
                            if component == "ultrasonic":
                                continue
                            self._send_msg(component, json.dumps(msg))
                    # if no more items to grab in this aisle
                        # also, if no more orders period, should go back to hub

                    # else, back to start of aisle and find next item
                    # msg = {
                    #     "command": "detect_color",
                    #     "color": "red"
                    # }
                    # self._send_msg("camera", json.dumps(msg))
                case "movement_complete":
                    msg = {
                        "command": "stop"
                    }
                    self._send_msg("linefollower", json.dumps(msg))
                case "picking_init":
                    time.sleep(1) #give time to enter aisle
                    color = self.remaining_packages[0]["color"]
                    msg = {
                        "command": "detect_color",
                        "color": color
                    }
                    self._send_msg("camera", json.dumps(msg))
                case "color_detected":
                    msg = {
                        "command": "stop"
                    }
                    self._send_msg("linefollower", json.dumps(msg))
                case "path_blocked":
                    msg = {
                        "command": "stop"
                    }
                    for component in self.components:
                        if component == "ultrasonic":
                            continue
                        self._send_msg(component, json.dumps(msg))
                case "path_unblocked":
                    msg = {
                        "command": "resume"
                    }
                    for component in self.components:
                        self._send_msg(component, json.dumps(msg))
                case "blocked_timeout":
                    # still blocked after a timeout. move to next item and return to current one
                    pass
                case "intersection_reached":
                    # here, should check what aisle/lane we need to be in and react accordingly.
                    global aisle_num # replace w/ order status
                    if current_state == ControllerStates.ExitAisleState:
                        self._send_msg("linefollower", '{"command": "enter"}')
                    else:
                        print(self.remaining_packages[0])
                        if aisle_num == self.remaining_packages[0]["aisle"]:
                            self._send_msg("linefollower", '{"command": "enter"}')
                            self.process_event_lock.release()
                            self.process_event("picking_init") #override event
                            self.process_event_lock.acquire()
                            return
                        else:
                            self._send_msg("linefollower", '{"command": "ignore"}')
                        aisle_num += 1
            self.state_machine.transition(event)
            
    def execution_thread(self):
        """Main thread of execution for the controller.
        """
        # small delay to ensure sockets are connected
        time.sleep(1)
        
        listener = threading.Thread(target=controller.listen_for_messages, daemon=True)
        listener.start()
        self.__executing = True
        
        while self.__executing:
            match controller.state_machine.state:
                case ControllerStates.IdleState:
                    # block and wait for a msg from server here. server: router
                    logging.info("requesting a new order")
                    while True:
                        self.req_socket.send(b"")
                        data = self.req_socket.recv()
                        if not data:
                            logging.debug("no orders available")
                            time.sleep(1)
                            continue
                        order = json.loads(data)
                        if validate_order_data(order):
                            break
                        logging.error(f"invalid order received: {data}")
                    self.remaining_packages = sorted(order["packages"], key=lambda x: x["aisle"])
                    logging.info(f"order received: {order}")
                    self.process_event("order_received")
                case ControllerStates.MovingToAisleState:
                    pass
                case ControllerStates.PathBlockedState:
                    car.set_velocity(0,90,0)
                    time.sleep(0.1)
                case ControllerStates.PickingState:
                    # real meat and potatoes
                    pass                    
                case ControllerStates.GrabbingState:
                    r,g,b = 255, 255, 255
                    for i in range (0,5):
                        board.set_buzzer(1900, 0.1, 0.9, 1)
                        board.set_rgb([[1, r, g, b], [2, r, g, b]])
                        r -= 55
                        g -= 25
                        b -= 35
                        time.sleep(0.5)
                    self.process_event("order_grabbed")
                    
                    # order_grabbed

    def exit(self, code: int = 0, msg: str = None):
        """Clean up remaining resources and safely exit the program

        :param code: exit code, defaults to 0
        :param msg: exit message, defaults to None
        """
        print("Exiting" if msg == None else f"Exiting: {msg}")
        self.__executing = False
        
        # clean any running processes/threads
        logging.info("Attempting to cleanly exit controller program")
        
        for process in active_subprocesses:
            os.kill(process.pid, signal.SIGINT)
        for process in active_subprocesses:
            process.wait()
        
        logging.info("Successfully exiting controller program" if msg == None else f"Exiting controller program. Msg: {msg}")
        logging.shutdown()
        sys.exit(code)

if __name__ == "__main__":
    controller = Controller()

                