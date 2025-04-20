from common import PackageColor, PackageData
from server import TestOrderData
import random, json

TIME_PER_ORDER = 10
TIME_PER_PACKAGE = 10

if __name__ == "__main__":
    min_orders = int(input("Minimum number of orders: "))
    max_orders = int(input("Maximum number of orders: "))
    min_packages = int(input("Minimum number of packages: "))
    max_packages = int(input("Maximum number of packages: "))
    num_aisles = int(input("Number of aisles: "))
    if min_orders * min_packages > num_aisles * 3 or max_orders * max_packages < num_aisles * 3:
        print("Unsatisfiable constraints")
        exit(1)

    # packages = list[dict[PackageColor, int]]()
    # for i in range(num_aisles):
    #     aisle_packages = input(f"Packages in aisle {i+1} (R/G/B): ")
    #     packages.append({PackageColor.RED: 0, PackageColor.GREEN: 0, PackageColor.BLUE: 0})
    #     for package in aisle_packages:
    #         match package:
    #             case 'R':
    #                 packages[i][PackageColor.RED] += 1
    #             case 'G':
    #                 packages[i][PackageColor.GREEN] += 1
    #             case 'B':
    #                 packages[i][PackageColor.BLUE] += 1
    #             case _:
    #                 print(f"Invalid package color: {package}")
    #                 exit(1)

    # Assume that each aisle has one package of each color
    packages = [{PackageColor.RED, PackageColor.GREEN, PackageColor.BLUE} for _ in range(num_aisles)]
    min_spacing = int(input("Minimum spacing between packages (seconds): "))
    max_spacing = int(input("Maximum spacing between packages (seconds): "))
    orders = list[TestOrderData]()
    while any(packages):
        packages_left = sum([len(aisle_packages) for aisle_packages in packages])
        actual_min_packages = max(min_packages, packages_left - (max_orders - len(orders) - 1) * max_packages)
        actual_max_packages = min(max_packages, packages_left, packages_left - (min_orders - len(orders) - 1) * min_packages)
        num_packages = random.randint(actual_min_packages, actual_max_packages)
        order_packages = list[PackageData]()
        for _ in range(num_packages):
            available_packages = [(i, color) for i, aisle_packages in enumerate(packages) for color in aisle_packages]
            chosen_package = random.choice(available_packages)
            order_packages.append({"aisle": chosen_package[0], "color": chosen_package[1]})
            packages[chosen_package[0]].remove(chosen_package[1])
        timestamp = random.randint(min_spacing, max_spacing) + orders[-1]["time"] if orders else 0
        difficulty = TIME_PER_ORDER + TIME_PER_PACKAGE * num_packages
        # TODO: smarter deadline generation
        deadline = random.randint(timestamp + difficulty, timestamp + difficulty * 3)
        orders.append({"time": timestamp, "deadline": deadline, "packages": order_packages})
    filename = input("Output filename: ")
    with open(filename, "w") as f:
        json.dump(orders, f, indent=2)