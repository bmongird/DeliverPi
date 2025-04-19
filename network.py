import heapq
import json
import logging
import threading
from time import sleep
from typing import cast, override
import zmq
from common import HUB_PORT, OrderData

HUB_HOST = "localhost"


class NetworkThread(threading.Thread):
    def __init__(self, hub_host: str, hub_port: int, controller_host: int):
        super().__init__(name="NETWORK")
        self.hub_host: str = hub_host
        self.hub_port: int = hub_port
        self.controller_host: int = controller_host

        self.ctx = zmq.Context()
        self.hub_sock = self.ctx.socket(zmq.REQ)  # TODO: add filters
        self.hub_sock.connect(f"tcp://{self.hub_host}:{self.hub_port}")
        self.controller_sock = self.ctx.socket(zmq.PAIR)
        self.controller_sock.bind(f"inproc://{self.controller_host}")

    @override
    def run(self):
        logging.info("starting to receive")

        while True:
            # TODO: only do that when finished an order
            self.hub_sock.send(b"")
            raw_data = self.hub_sock.recv()
            if not raw_data:
                logging.info("no order received")
                sleep(1)
                continue
            logging.info(f"received order {raw_data}")
            data = cast(OrderData, json.loads(raw_data))
            self.controller_sock.send_json(data)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="[{threadName}]: {message}", style="{"
    )
    t = NetworkThread(HUB_HOST, HUB_PORT, 1234)  # TODO: controller host
    t.start()
