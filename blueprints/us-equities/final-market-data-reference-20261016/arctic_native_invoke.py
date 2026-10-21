"""ArcticDB 6.26.0 README LMDB example on explicitly SYNTHETIC input.

Native SDK diagnostic, not market-data, performance or comparative evidence.
Source: man-group/ArcticDB@e620d8572a1e62c9ec07df8cbc8f5c432cd84325
README.md:100-127. Fixed RNG; native data returned by read() is printed directly.
"""

from importlib.metadata import version
from pathlib import Path
import socket
import sys


def blocked(*args, **kwargs):
    raise RuntimeError("network is not authorized for the local LMDB invocation")


socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked

import arcticdb as adb
import numpy as np
import pandas as pd

destination = Path(sys.argv[1])
if destination.exists():
    raise ValueError("write-once scratch store already exists")
print(version("arcticdb"))
ac = adb.Arctic("lmdb://" + str(destination.resolve()))
ac.create_library("travel_data")
print(ac.list_libraries())
assert ac.list_libraries() == ["travel_data"]
rng = np.random.default_rng(0)
df = pd.DataFrame(
    rng.integers(0, 100, size=(100_000, 10)),
    columns=[f"COL_{i}" for i in range(10)],
    index=pd.date_range("2000", periods=100_000, freq="h"),
)
lib = ac["travel_data"]
lib.write("my_data", df)
data = lib.read("my_data")
print(data.data)
pd.testing.assert_frame_equal(data.data, df, check_freq=False)
assert version("arcticdb") == "6.26.0"
