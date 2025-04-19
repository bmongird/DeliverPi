import heapq
import logging
import threading
from typing import cast, override
import zmq
from common import CONTROLLER_PORT, HUB_PORT, SERVER_PORT, OrderData

SERVER_HOST = "localhost"
CONTROLLER_HOST = "localhost"


class HubThread(threading.Thread):
    def __init__(self, server_host: str, server_port: int, hub_port: int):
        super().__init__(name="HUB")
        self.server_host: str = server_host
        self.server_port: int = server_port
        self.hub_port: int = hub_port
        self.orders: list[tuple[int, OrderData]] = []

        self.ctx = zmq.Context()
        self.server_sock = self.ctx.socket(zmq.SUB)  # TODO: add filters
        self.server_sock.connect(f"tcp://{self.server_host}:{self.server_port}")
        self.server_sock.setsockopt_string(zmq.SUBSCRIBE, "")
        self.hub_sock = self.ctx.socket(zmq.REP)
        self.hub_sock.bind(f"tcp://*:{self.hub_port}")
        self.controller_sock = self.ctx.socket(zmq.SUB)
        self.controller_sock.connect(f"tcp://{CONTROLLER_HOST}:{CONTROLLER_PORT}")
        self.controller_sock.setsockopt_string(zmq.SUBSCRIBE, "")

    @override
    def run(self):
        poller = zmq.Poller()
        poller.register(self.server_sock)
        poller.register(self.hub_sock)
        poller.register(self.controller_sock)

        logging.info("starting to receive")

        while True:
            try:
                socks = dict(poller.poll())
            except KeyboardInterrupt:
                break

            if self.server_sock in socks:
                data = cast(OrderData, self.server_sock.recv_json())
                heapq.heappush(self.orders, (data["deadline"], data))

            if self.hub_sock in socks:
                try:
                    self.hub_sock.recv()
                    data = heapq.heappop(self.orders)[1]
                    self.hub_sock.send_json(data)
                except IndexError:
                    self.hub_sock.send(b"")
            
            if self.controller_sock in socks:
                logging.info(f"Status update: {self.controller_sock.recv_string()}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="[{threadName}]: {message}", style="{"
    )
    t = HubThread(SERVER_HOST, SERVER_PORT, HUB_PORT)
    t.start()
