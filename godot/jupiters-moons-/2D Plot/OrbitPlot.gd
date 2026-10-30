extends Node2D

# Canvas units per dimensionless length unit.
@export var pixels_per_unit: float = 200.0
# Dimensionless time units per real second.
@export_range(0.0, 20.0, 0.1) var playback_speed: float = 1.0

const HOST = "127.0.0.1"
const PORT = 5050
const MAX_READ_BYTES = 32768
const MAX_MESSAGE_BYTES = 65536
const REFILL_SAMPLES = 160
const MAX_BUFFER_SAMPLES = 512

var peer := StreamPeerTCP.new()
var received_text: String = ""
var samples: Array[Vector3] = []  # Each entry is (time, x, y).
var sample_index: int = 0
var request_pending: bool = false
var playing: bool = true
var playback_time: float = 0.0
var moon_position := Vector2.ZERO
var status_text: String = "Connecting to Python..."
var failed: bool = false


func _ready() -> void:
	var error = peer.connect_to_host(HOST, PORT)
	if error != OK:
		fail_connection("Could not start connection. Start Python, then rerun scene.")


func fail_connection(message: String) -> void:
	failed = true
	status_text = message
	peer.disconnect_from_host()


func read_stream() -> void:
	# Read only bytes already available: never wait for Python in this frame.
	var available = peer.get_available_bytes()
	if available > 0:
		var result = peer.get_partial_data(mini(available, MAX_READ_BYTES))
		if result[0] != OK:
			fail_connection("Read failed. Rerun scene to reconnect.")
			return
		var bytes: PackedByteArray = result[1]
		received_text += bytes.get_string_from_utf8()

	# Wait for the rest if TCP delivered only part of the JSON message.
	var newline = received_text.find("\n")
	if newline == -1:
		if received_text.length() > MAX_MESSAGE_BYTES:
			fail_connection("Message exceeded the receive limit.")
		return

	var decoded = JSON.parse_string(received_text.substr(0, newline))
	received_text = received_text.substr(newline + 1)
	if not decoded is Array:
		fail_connection("Python sent an invalid batch.")
		return
	if decoded.size() == 0 or decoded.size() > 128:
		fail_connection("Unexpected batch size.")
		return

	for row in decoded:
		if not row is Array:
			fail_connection("Invalid sample.")
			return
		if row.size() != 3:
			fail_connection("Expected [time, x, y].")
			return
		var sample = Vector3(float(row[0]), float(row[1]), float(row[2]))
		if not sample.is_finite():
			fail_connection("Non-finite simulation result.")
			return
		if not samples.is_empty() and sample.x <= samples[-1].x:
			fail_connection("Sample times must increase.")
			return
		samples.append(sample)
	request_pending = false
	if samples.size() > MAX_BUFFER_SAMPLES:
		fail_connection("Sample buffer exceeded its limit.")


func _process(delta: float) -> void:
	if not failed:
		peer.poll()
		var connection_status = peer.get_status()
		if connection_status == StreamPeerTCP.STATUS_CONNECTED:
			read_stream()
			if not failed:
				update_playback(delta)
				# Delete consumed samples, keeping the current interpolation endpoint.
				if sample_index > 0:
					samples = samples.slice(sample_index)
					sample_index = 0
				# Only one batch may be in flight, so pausing cannot grow memory.
				if samples.size() < REFILL_SAMPLES and not request_pending:
					var error = peer.put_data("next\n".to_utf8_buffer())
					if error != OK:
						fail_connection("Could not request data.")
					else:
						request_pending = true
		elif connection_status == StreamPeerTCP.STATUS_ERROR or connection_status == StreamPeerTCP.STATUS_NONE:
			fail_connection("Python disconnected/unavailable. Start it, then rerun scene.")
	queue_redraw()


func update_playback(delta: float) -> void:
	if samples.size() < 2:
		status_text = "Buffering..."
		return

	var target = playback_time
	if playing:
		# Avoid a large visual jump after dragging/debugging the window.
		target += minf(delta, 0.1) * maxf(playback_speed, 0.0)

	# Hold the clock at available data instead of extrapolating a false orbit.
	var waiting = target > samples[-1].x
	playback_time = minf(target, samples[-1].x)
	while sample_index + 1 < samples.size() - 1 and samples[sample_index + 1].x <= playback_time:
		sample_index += 1

	var a = samples[sample_index]
	var b = samples[sample_index + 1]
	var fraction = clampf((playback_time - a.x) / (b.x - a.x), 0.0, 1.0)
	moon_position = Vector2(a.y, a.z).lerp(Vector2(b.y, b.z), fraction)
	var mode = "Playing"
	if not playing:
		mode = "Paused"
	elif waiting:
		mode = "Buffering"
	status_text = "%s | t = %.3f (dimensionless) | speed = %.2f" % [mode, playback_time, playback_speed]


func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_SPACE:
			playing = not playing
		elif event.keycode == KEY_UP:
			playback_speed = minf(playback_speed * 2.0, 20.0)
		elif event.keycode == KEY_DOWN:
			playback_speed = maxf(playback_speed / 2.0, 0.0625)


func simulation_to_screen(simulation_position: Vector2) -> Vector2:
	return get_viewport_rect().size / 2.0 + Vector2(simulation_position.x, -simulation_position.y) * pixels_per_unit


func _draw() -> void:
	var size = get_viewport_rect().size
	var centre = simulation_to_screen(Vector2.ZERO)
	draw_line(Vector2(0, centre.y), Vector2(size.x, centre.y), Color.DIM_GRAY)
	draw_line(Vector2(centre.x, 0), Vector2(centre.x, size.y), Color.DIM_GRAY)
	draw_circle(centre, 15.0, Color.ORANGE)
	if not samples.is_empty():
		draw_circle(simulation_to_screen(moon_position), 6.0, Color.WHITE)
	draw_string(ThemeDB.fallback_font, Vector2(24, 36), status_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 22)
	draw_string(ThemeDB.fallback_font, Vector2(24, 66), "Space: pause/play    Up/Down: speed", HORIZONTAL_ALIGNMENT_LEFT, -1, 20)


func _exit_tree() -> void:
	peer.disconnect_from_host()
