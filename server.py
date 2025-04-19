import logging
import threading
import time
from typing import override
import zmq
import json

from common import SERVER_PORT, OrderData

TEST_ORDERS_FILE = "messages.json"


class TestOrderData(OrderData):
    time: int


class ServerThread(threading.Thread):
    def __init__(self, port: int):
        super().__init__(name="SERVER")
        with open(TEST_ORDERS_FILE) as f:
            self.orders: list[TestOrderData] = json.load(f)
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.PUB)
        self.sock.bind(f"tcp://*:{port}")

    @override
    def run(self) -> None:
        start_time = time.time()
        for order in self.orders:
            time.sleep(order["time"] + start_time - time.time())
            msg: OrderData = {
                "deadline": order["deadline"],
                "packages": order["packages"],
            }
            self.sock.send_json(msg)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="[{threadName}]: {message}", style="{"
    )
    t = ServerThread(SERVER_PORT)
    t.start()
