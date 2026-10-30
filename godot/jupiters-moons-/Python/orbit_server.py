"""
Live dimensionless two-body simulation for Godot.

Requires Integrators.py in the same folder.

Godot sends:
    next\\n

Python returns a newline-terminated JSON array:
    [[time, x, y], [time, x, y], ...]

All times and positions are dimensionless.
Each new connection starts the orbit again.
"""

import argparse
import json
import socket

import numpy as np

from Integrators import initial_conditions, methods


# ------ Default settings ------
# Godot's command-line arguments override these values.

ECCENTRICITY = 0.0
METHOD = "Leapfrog"

STEPS_PER_ORBIT = 2000
STEPS_PER_SAMPLE = 4

HOST = "127.0.0.1"
PORT = 5050

# Must match the batch size expected by OrbitPlot.gd.
BATCH_SIZE = 128


# ------ Simulate and send data ------

def serve_client(connection):
    # Initial position and velocity, starting at apocentre.
    r, v = initial_conditions(ECCENTRICITY)

    method = methods[METHOD]

    # Dimensionless timestep.
    # These initial conditions have an exact orbital period of 2*pi.
    h = 2 * np.pi / STEPS_PER_ORBIT

    step = 0
    first_batch = True

    with connection.makefile("rb") as incoming:

        while True:
            # Wait for Godot to request another batch.
            # This only blocks Python, not the Godot process.
            line = incoming.readline(1024)

            if not line:
                return

            if line != b"next\n":
                raise ValueError(
                    "Expected 'next' followed by a newline."
                )

            samples = []

            # Include the initial state once, at time zero.
            if first_batch:
                samples.append([
                    0.0,
                    float(r[0]),
                    float(r[1])
                ])

                first_batch = False

            # Advance the simulation to produce the next batch.
            while len(samples) < BATCH_SIZE:

                for _ in range(STEPS_PER_SAMPLE):
                    r, v = method(r, v, h)
                    step += 1

                if not (
                    np.isfinite(r).all()
                    and np.isfinite(v).all()
                ):
                    raise ValueError(
                        "The simulation produced a non-finite state."
                    )

                simulation_time = step * h

                samples.append([
                    simulation_time,
                    float(r[0]),
                    float(r[1])
                ])

            # A newline marks the end of a complete message.
            payload = json.dumps(
                samples,
                allow_nan=False,
                separators=(",", ":")
            )

            connection.sendall(
                (payload + "\n").encode("utf-8")
            )


# ------ Local server ------

def main():
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    ) as server:

        server.bind((HOST, PORT))
        server.listen(1)

        print(
            f"Waiting for Godot at {HOST}:{PORT}",
            flush=True
        )

        print(
            f"Method: {METHOD}, "
            f"eccentricity: {ECCENTRICITY}, "
            f"steps per orbit: {STEPS_PER_ORBIT}, "
            f"steps per sample: {STEPS_PER_SAMPLE}",
            flush=True
        )

        while True:
            connection, address = server.accept()

            with connection:
                connection.setsockopt(
                    socket.IPPROTO_TCP,
                    socket.TCP_NODELAY,
                    1
                )

                print(
                    f"Godot connected from {address}. "
                    "Starting a new orbit.",
                    flush=True
                )

                try:
                    serve_client(connection)

                except (
                    OSError,
                    ValueError,
                    FloatingPointError
                ) as error:

                    print(
                        f"Session ended: {error}",
                        flush=True
                    )

                print(
                    "Waiting for another connection...",
                    flush=True
                )


# ------ Read settings supplied by Godot ------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stream dimensionless orbital positions to Godot."
    )

    parser.add_argument(
        "--eccentricity",
        type=float,
        default=ECCENTRICITY
    )

    parser.add_argument(
        "--method",
        choices=["Leapfrog", "RK4"],
        default=METHOD
    )

    parser.add_argument(
        "--steps-per-orbit",
        type=int,
        default=STEPS_PER_ORBIT
    )

    parser.add_argument(
        "--steps-per-sample",
        type=int,
        default=STEPS_PER_SAMPLE
    )

    args = parser.parse_args()

    if not 0 <= args.eccentricity < 1:
        parser.error(
            "Eccentricity must satisfy 0 <= e < 1."
        )

    if args.steps_per_orbit < 1:
        parser.error(
            "Steps per orbit must be positive."
        )

    if args.steps_per_sample < 1:
        parser.error(
            "Steps per sample must be positive."
        )

    ECCENTRICITY = args.eccentricity
    METHOD = args.method

    STEPS_PER_ORBIT = args.steps_per_orbit
    STEPS_PER_SAMPLE = args.steps_per_sample

    try:
        main()

    except KeyboardInterrupt:
        print("\nSimulation stopped.")