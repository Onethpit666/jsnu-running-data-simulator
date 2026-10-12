from datetime import timedelta, timezone

LOCAL_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
MAX_BATCH = 20
MAX_TOTAL_POINTS = 100_000
MAX_REQUEST_BYTES = 64 * 1024
DEFAULTS = {
    "distance_m": 2000,
    "pace_seconds_per_km": 360,
    "sample_interval": 2,
    "center_lat": 0.0,
    "center_lon": 0.0,
    "straight_m": 100,
    "radius_m": 100 / 3.141592653589793,
    "rotation_deg": 0,
    "simulate_hr": False,
    "hr_min": 100,
    "hr_max": 190,
    "pace_variation_percent": 8,
    "lane_variation_m": 1.5,
    "random_seed": 42,
    "hr_target": 155,
    "hr_variation_bpm": 4,
    "hr_response_s": 20,
    "hr_warmup_s": 45,
    "simulate_metrics": True,
    "pause_seconds": 3,
    "weight_kg": 65,
    "cadence_spm": 164,
    "power_w": 250,
    "base_altitude_m": 35,
    "ascent_m": 0,
    "rpe": 3,
}
