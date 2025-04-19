from enum import StrEnum
from typing import TypedDict, TypeGuard

SERVER_PORT = 8000
HUB_PORT = 8001
CONTROLLER_PORT = 8002


class PackageColor(StrEnum):
    RED = "RED"
    BLUE = "BLUE"
    GREEN = "GREEN"


class PackageData(TypedDict):
    color: PackageColor
    aisle: int


class OrderData(TypedDict):
    deadline: int
    packages: list[PackageData]

def validate_order_data(data) -> TypeGuard[OrderData]:
    if not isinstance(data, dict):
        return False
    if len(data) != 2:
        return False
    if "deadline" not in data or not isinstance(data["deadline"], int):
        return False
    if "packages" not in data or not isinstance(data["packages"], list):
        return False
    if len(data["packages"]) == 0:
        return False
    for package in data["packages"]:
        if len(package) != 2:
            return False
        if "color" not in package or not isinstance(package["color"], str):
            return False
        if "aisle" not in package or not isinstance(package["aisle"], int):
            return False
    return True
