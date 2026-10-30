extends Node2D

@export_group("Python")
@export var python_executable: String = "python"

@export_group("Initial orbit")
@export_range(0.0, 0.99, 0.01) var eccentricity: float = 0.0

@export_group("Numerical integration")
@export_enum("Leapfrog", "RK4") var integrator: String = "Leapfrog"
@export_range(100, 100000, 100) var steps_per_orbit: int = 2000
@export_range(1, 100, 1) var steps_per_sample: int = 4

@export_group("Display")
@export_range(0.0625, 20.0, 0.0625) var playback_speed: float = 1.0
@export_range(10.0, 500.0, 10.0) var plot_scale: float = 200.0

var python_pid: int = -1


func _ready() -> void:
	$OrbitPlot.playback_speed = playback_speed
	$OrbitPlot.pixels_per_unit = plot_scale

	var script_path = ProjectSettings.globalize_path(
		"res://python/orbit_server.py"
	)

	var arguments = PackedStringArray([
		script_path,
		"--eccentricity", str(eccentricity),
		"--method", integrator,
		"--steps-per-orbit", str(steps_per_orbit),
		"--steps-per-sample", str(steps_per_sample)
	])

	python_pid = OS.create_process(
		python_executable,
		arguments
	)

	if python_pid == -1:
		push_error("Could not launch Python.")


func _exit_tree() -> void:
	if python_pid > 0 and OS.is_process_running(python_pid):
		OS.kill(python_pid)
