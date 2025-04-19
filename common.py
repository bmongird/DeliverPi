from enum import StrEnum
from typing import TypedDict, override

SERVER_PORT = 8000
HUB_PORT = 8001

# main process
NETWORK_HOST = "network"


class PackageColor(StrEnum):
    RED = "RED"
    BLUE = "BLUE"
    GREEN = "GREEN"


class PackageData(TypedDict):
    color: PackageColor
    lane: int


class OrderData(TypedDict):
    deadline: int
    packages: list[PackageData]
