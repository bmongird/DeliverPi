import heapq
import logging
import threading
# from typing import override # can cause problems due to missing package
import zmq
from common import (
    CONTROLLER_PORT,
    HUB_PORT,
    SERVER_PORT,
    OrderData,
    validate_order_data,
)

# server and robot hostnames to connect to
SERVER_HOST = "localhost"
CONTROLLER_HOST = "localhost"


class HubThread(threading.Thread):
    """
    Delivery hub thread

    Responsible for keeping track of the orders received from the central server,
    scheduling the orders requested by the robot, and receiving status updates from it.
    """

    def __init__(self, server_host: str, server_port: int, hub_port: int):
        super().__init__(name="HUB")
        self.server_host: str = server_host
        self.server_port: int = server_port
        self.hub_port: int = hub_port
        self.orders: list[tuple[int, OrderData]] = []

        self.ctx = zmq.Context()
        self.server_sock = self.ctx.socket(zmq.SUB)
        self.server_sock.connect(f"tcp://{self.server_host}:{self.server_port}")
        self.server_sock.setsockopt_string(zmq.SUBSCRIBE, "")
        self.hub_sock = self.ctx.socket(zmq.REP)
        self.hub_sock.bind(f"tcp://*:{self.hub_port}")
        self.controller_sock = self.ctx.socket(zmq.SUB)
        self.controller_sock.connect(f"tcp://{CONTROLLER_HOST}:{CONTROLLER_PORT}")
        self.controller_sock.setsockopt_string(zmq.SUBSCRIBE, "")

    # @override
    def run(self):
        logging.info("starting")
        poller = zmq.Poller()
        poller.register(self.server_sock)
        poller.register(self.hub_sock)
        poller.register(self.controller_sock)

        while True:
            try:
                socks = dict(poller.poll())
            except KeyboardInterrupt:
                logging.debug("keyboard interrupt")
                break

            # receiving an order from the server
            if self.server_sock in socks:
                logging.debug("data from server")
                try:
                    data = self.server_sock.recv_json()
                    if validate_order_data(data):
                        # add the order to the internal min-heap based on its deadline
                        heapq.heappush(self.orders, (data["deadline"], data))
                        logging.info(f"order received: {data}")
                    else:
                        logging.error(f"invalid order received: {data}")
                except:
                    logging.error("invalid order received")

            # receiving an order request from the robot
            if self.hub_sock in socks:
                logging.debug("request from car")
                try:
                    self.hub_sock.recv()
                    # pop the next order and send it to the robot
                    data = heapq.heappop(self.orders)[1]
                    self.hub_sock.send_json(data)
                    logging.info(f"order sent: {data}")
                except IndexError:
                    self.hub_sock.send(b"")
                    logging.info("no orders available")

            # receiving a status update from the robot
            if self.controller_sock in socks:
                logging.debug("status update from car")
                logging.info(f"status update: {self.controller_sock.recv_string()}")
        logging.info("shutting down")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="[{threadName}]: {message}", style="{"
    )
    t = HubThread(SERVER_HOST, SERVER_PORT, HUB_PORT)
    t.start()
