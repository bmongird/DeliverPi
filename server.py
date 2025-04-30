import logging
import threading
import time
# from typing import override # can cause problems due to missing package
import zmq
import json

from common import SERVER_PORT, OrderData

# json file to use for test orders
TEST_ORDERS_FILE = "orders.json"


class TestOrderData(OrderData):
    """Struct representing the data of a single test order"""

    time: int  # the time from the thread start for the order to "arrive"


class ServerThread(threading.Thread):
    """
    Central Server thread used for testing
    Responsible for reading the order data from a json file and sending the orders to the delivery hub.
    """

    def __init__(self, port: int):
        super().__init__(name="SERVER")
        with open(TEST_ORDERS_FILE) as f:
            self.orders: list[TestOrderData] = json.load(f)
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.PUB)
        self.sock.bind(f"tcp://*:{port}")

    # @override
    def run(self) -> None:
        logging.info("starting")
        start_time = time.time()
        logging.debug(f"start time: {start_time}")
        for order in self.orders:
            # wait for the next order "arrival"
            sleep_time = order["time"] + start_time - time.time()
            if sleep_time > 0:
                logging.debug(f"sleeping for {sleep_time}")
                time.sleep(sleep_time)
            msg: OrderData = {
                "deadline": order["deadline"],
                "packages": order["packages"],
            }
            self.sock.send_json(msg)
            logging.info(f"published order: {msg}")
        logging.info("shutting down")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="[{threadName}]: {message}", style="{"
    )
    t = ServerThread(SERVER_PORT)
    t.start()
