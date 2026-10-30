"""Dimensionless planar orbit around a fixed central body.

Length unit: L (the initial orbit's semimajor axis).
Time unit: T = sqrt(L**3 / mu), where mu = G * central_mass.
Thus r_physical = L * r and t_physical = T * t.
The dimensionless acceleration is -r / |r|**3, with mu = 1.
These initial conditions have semimajor axis 1 and exact period 2*pi.
The orbit starts at apocentre, not pericentre.
"""

import numpy as np


# ------ Settings ------

eccentricity = 0.0
steps_per_orbit = 1000
number_of_orbits = 1
method_name = "Leapfrog"  # "Leapfrog" or "RK4"


# ------ Initial conditions ------

def initial_conditions(e):
    """Start at apocentre on the negative x-axis; require 0 <= e < 1."""
    if not 0 <= e < 1:
        raise ValueError("Eccentricity must satisfy 0 <= e < 1.")

    r = np.array([-(1.0 + e), 0.0])
    v = np.array([0.0, -np.sqrt((1.0 - e) / (1.0 + e))])
    return r, v


# ------ Acceleration ------

def acceleration(r):
    distance = np.linalg.norm(r)
    if distance == 0:
        raise ValueError("Gravity is undefined at the central body's position.")
    return -r / distance**3


# ------ Leapfrog: drift, kick, drift ------

def leapfrog_method(r, v, h):
    r = r + (h / 2) * v
    v = v + h * acceleration(r)
    r = r + (h / 2) * v
    return r, v


# ------ Fourth-order Runge-Kutta ------

def derivatives(w):
    r = w[:2]
    v = w[2:]
    return np.concatenate((v, acceleration(r)))


def rk4_method(r, v, h):
    w = np.concatenate((r, v))

    k1 = h * derivatives(w)
    k2 = h * derivatives(w + k1 / 2)
    k3 = h * derivatives(w + k2 / 2)
    k4 = h * derivatives(w + k3)

    w = w + (k1 + 2 * k2 + 2 * k3 + k4) / 6
    return w[:2], w[2:]


methods = {"Leapfrog": leapfrog_method, "RK4": rk4_method}


# ------ Simulation ------

def simulate_orbit(method, r, v, h, N):
    """Return N+1 dimensionless times, positions and velocities.

    positions[i] and velocities[i] correspond to times[i].
    The central body stays fixed at (0, 0).
    """
    if not isinstance(N, (int, np.integer)) or N < 1:
        raise ValueError("N must be a positive integer.")
    if not np.isfinite(h) or h <= 0:
        raise ValueError("h must be positive and finite.")

    r = np.array(r, dtype=float, copy=True)
    v = np.array(v, dtype=float, copy=True)

    positions = np.empty((N + 1, 2))
    velocities = np.empty((N + 1, 2))
    times = np.arange(N + 1) * h

    positions[0] = r
    velocities[0] = v

    for i in range(N):
        r, v = method(r, v, h)
        positions[i + 1] = r
        velocities[i + 1] = v

    return times, positions, velocities


if __name__ == "__main__":
    if not isinstance(steps_per_orbit, int) or steps_per_orbit < 1:
        raise ValueError("steps_per_orbit must be a positive integer.")
    if not isinstance(number_of_orbits, int) or number_of_orbits < 1:
        raise ValueError("number_of_orbits must be a positive integer.")

    h = 2 * np.pi / steps_per_orbit
    N = steps_per_orbit * number_of_orbits
    r, v = initial_conditions(eccentricity)

    times, positions, velocities = simulate_orbit(
        methods[method_name], r, v, h, N
    )

    print(f"Method: {method_name}")
    print(f"Samples: {len(times)}")
    print(f"Final dimensionless time: {times[-1]:.6f}")
    print(f"Final dimensionless position: {positions[-1]}")
