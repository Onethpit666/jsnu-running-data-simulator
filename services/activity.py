"""One model shared by preview, TCX export and the command-line example."""
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
import math
import random
from bisect import bisect_right

from config import DEFAULTS, LOCAL_TIMEZONE, MAX_BATCH, MAX_TOTAL_POINTS

EARTH_RADIUS = 6371008.8


def number(data, name, minimum, maximum):
    value = data.get(name, DEFAULTS[name])
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} 必须是数值")
    value = float(value)
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} 必须在 {minimum} 到 {maximum} 之间")
    return value


@dataclass(frozen=True)
class Parameters:
    distance_m: float
    pace_seconds_per_km: float
    sample_interval: float
    center_lat: float
    center_lon: float
    straight_m: float
    radius_m: float
    rotation_deg: float
    simulate_hr: bool
    hr_min: int
    hr_max: int
    pace_variation_percent: float
    lane_variation_m: float
    random_seed: int
    hr_target: float
    hr_variation_bpm: float
    hr_response_s: float
    hr_warmup_s: float
    simulate_metrics: bool
    pause_seconds: float
    weight_kg: float
    cadence_spm: float
    power_w: float
    base_altitude_m: float
    ascent_m: float
    rpe: float

    @property
    def lap_m(self):
        return 2 * self.straight_m + 2 * math.pi * self.radius_m


def parse_request(data):
    if not isinstance(data, dict):
        raise ValueError("请求必须是 JSON 对象")
    times = data.get("times")
    if not isinstance(times, list) or not 1 <= len(times) <= MAX_BATCH:
        raise ValueError(f"请提供 1 到 {MAX_BATCH} 个开始时间")
    starts = []
    for index, value in enumerate(times, 1):
        try:
            if isinstance(value, str):
                start = datetime.fromisoformat(value.replace("Z", "+00:00"))
            elif isinstance(value, dict):
                fields = []
                for key in ("year", "month", "day", "hour", "minute", "second"):
                    item = value.get(key)
                    if isinstance(item, bool) or not isinstance(item, int):
                        raise ValueError(f"{key} 必须是整数，且不能缺失")
                    fields.append(item)
                start = datetime(*fields)
            else:
                raise ValueError("时间必须是日期时间字符串或完整时间对象")
            if not 2000 <= start.year <= 2100:
                raise ValueError("年份必须在 2000 到 2100 之间")
            if start.tzinfo is None:
                start = start.replace(tzinfo=LOCAL_TIMEZONE)
            starts.append(start.astimezone(LOCAL_TIMEZONE))
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"第 {index} 个时间无效：{exc}") from exc
    options = data.get("options", {})
    if not isinstance(options, dict):
        raise ValueError("options 必须是对象")
    unknown = set(options) - set(DEFAULTS)
    if unknown:
        raise ValueError("不支持的参数：" + ", ".join(sorted(unknown)))
    hr = options.get("simulate_hr", False)
    if not isinstance(hr, bool):
        raise ValueError("simulate_hr 必须是布尔值")
    metrics = options.get("simulate_metrics", DEFAULTS["simulate_metrics"])
    if not isinstance(metrics, bool):
        raise ValueError("simulate_metrics 必须是布尔值")
    params = Parameters(
        number(options, "distance_m", 100, 20000),
        number(options, "pace_seconds_per_km", 180, 1200),
        number(options, "sample_interval", 2, 10),
        number(options, "center_lat", -80, 80),
        number(options, "center_lon", -179, 179),
        number(options, "straight_m", 10, 500),
        number(options, "radius_m", 10, 200),
        number(options, "rotation_deg", -360, 360),
        hr,
        number(options, "hr_min", 40, 220),
        number(options, "hr_max", 40, 220),
        number(options, "pace_variation_percent", 0, 20),
        number(options, "lane_variation_m", 0, 3),
        number(options, "random_seed", 0, 2147483647),
        number(options, "hr_target", 40, 220),
        number(options, "hr_variation_bpm", 0, 15),
        number(options, "hr_response_s", 5, 90),
        number(options, "hr_warmup_s", 0, 180),
        metrics,
        number(options, "pause_seconds", 0, 60),
        number(options, "weight_kg", 30, 180),
        number(options, "cadence_spm", 100, 220),
        number(options, "power_w", 50, 600),
        number(options, "base_altitude_m", -400, 5000),
        number(options, "ascent_m", 0, 200),
        number(options, "rpe", 1, 10),
    )
    if not params.hr_min.is_integer() or not params.hr_max.is_integer():
        raise ValueError("心率上下限必须是整数")
    if params.hr_min >= params.hr_max:
        raise ValueError("心率上限必须大于下限")
    if not params.random_seed.is_integer():
        raise ValueError("变化编号必须是整数")
    if hr and not params.hr_min <= params.hr_target <= params.hr_max:
        raise ValueError("心率目标值必须位于心率上下限之间")
    if not params.pause_seconds.is_integer():
        raise ValueError("暂停秒数必须是整数")
    count = point_count(params) + bool(params.pause_seconds)
    if count * len(starts) > MAX_TOTAL_POINTS:
        raise ValueError("本次批量轨迹点过多，请减少文件数量或增大采样间隔")
    return starts, params


def position(distance, params, lateral=0):
    """North-oriented stadium, then clockwise rotation. Coordinates are WGS84-like spherical approximation."""
    s, r = params.straight_m, params.radius_m
    arc = math.pi * r
    d = distance % params.lap_m
    if d < s:
        east, north = -r, -s / 2 + d
        normal = (-1, 0)
    elif d < s + arc:
        angle = math.pi - (d - s) / r
        east, north = r * math.cos(angle), s / 2 + r * math.sin(angle)
        normal = (math.cos(angle), math.sin(angle))
    elif d < 2 * s + arc:
        east, north = r, s / 2 - (d - s - arc)
        normal = (1, 0)
    else:
        angle = -(d - 2 * s - arc) / r
        east, north = r * math.cos(angle), -s / 2 + r * math.sin(angle)
        normal = (math.cos(angle), math.sin(angle))
    east += lateral * normal[0]
    north += lateral * normal[1]
    rotation = math.radians(params.rotation_deg)
    x = east * math.cos(rotation) + north * math.sin(rotation)
    y = -east * math.sin(rotation) + north * math.cos(rotation)
    lat = params.center_lat + math.degrees(y / EARTH_RADIUS)
    lon = params.center_lon + math.degrees(x / (EARTH_RADIUS * math.cos(math.radians(params.center_lat))))
    return round(lat, 8), round(lon, 8)


def distance_between(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS * math.asin(math.sqrt(min(1, max(0, h))))


@dataclass
class Point:
    time: datetime
    lat: float
    lon: float
    distance_m: float
    hr: int | None
    pace_s_per_km: float = 0
    lateral_m: float = 0
    active_s: float = 0
    speed_mps: float = 0
    cadence_spm: float | None = None
    power_w: float | None = None
    altitude_m: float | None = None
    stride_m: float | None = None
    paused: bool = False


@dataclass
class Activity:
    start: datetime
    params: Parameters
    points: list[Point]
    metrics: dict = field(default_factory=dict)

    @property
    def distance_m(self):
        return self.points[-1].distance_m

    @property
    def duration_s(self):
        return self.points[-1].active_s

    @property
    def elapsed_duration_s(self):
        return (self.points[-1].time-self.start).total_seconds()

    def summary(self):
        hearts = [p.hr for p in self.points if p.hr is not None]
        return {
            "start_local": self.start.isoformat(),
            "end_local": self.points[-1].time.isoformat(),
            "requested_distance_m": self.params.distance_m,
            "distance_m": round(self.distance_m, 3),
            "duration_s": round(self.duration_s, 3),
            "elapsed_duration_s": round(self.elapsed_duration_s,3),
            "pause_seconds": self.params.pause_seconds,
            "pace_seconds_per_km": round(self.duration_s / self.distance_m * 1000, 3),
            "lap_length_m": round(self.params.lap_m, 3),
            "laps": round(self.params.distance_m / self.params.lap_m, 3),
            "point_count": len(self.points),
            "average_hr": round(sum(hearts) / len(hearts)) if hearts else None,
            "max_hr": max(hearts) if hearts else None,
            "kilometer_splits": self.splits(),
            "pace_variation_percent": self.params.pace_variation_percent,
            "lane_variation_m": self.params.lane_variation_m,
            "source": "synthetic",
            "coordinate_system": "WGS84 (spherical local approximation)",
            **self.metrics,
        }

    @property
    def max_speed(self):
        return max((b.distance_m-a.distance_m)/(b.time-a.time).total_seconds()
                   for a,b in zip(self.points,self.points[1:]))

    def splits(self):
        boundaries = list(range(1000, math.floor(self.distance_m) + 1, 1000))
        if not boundaries or self.distance_m - boundaries[-1] > 0.001:
            boundaries.append(self.distance_m)
        elif boundaries:
            boundaries[-1] = self.distance_m
        result, previous_distance, previous_elapsed, index = [], 0, 0, 1
        for end in boundaries:
            while index < len(self.points)-1 and self.points[index].distance_m < end:
                index += 1
            a,b = self.points[index-1],self.points[index]
            fraction = (end-a.distance_m)/(b.distance_m-a.distance_m)
            elapsed = a.active_s + fraction*(b.active_s-a.active_s)
            length, duration = end-previous_distance, elapsed-previous_elapsed
            result.append(dict(distance_m=round(length,3), duration_s=round(duration,3),
                               pace_seconds_per_km=round(duration/length*1000,3)))
            previous_distance, previous_elapsed = end, elapsed
        return result

    def preview(self):
        return {
            "summary": self.summary(),
            "options": asdict(self.params),
            "points": [dict(time=p.time.isoformat(), lat=p.lat, lon=p.lon,
                            distance_m=round(p.distance_m, 3), hr=p.hr,
                            pace_seconds_per_km=round(p.pace_s_per_km,3),
                            lateral_m=round(p.lateral_m,3), active_s=round(p.active_s,3),
                            cadence_spm=p.cadence_spm, power_w=p.power_w,
                            altitude_m=p.altitude_m, stride_m=p.stride_m, paused=p.paused)
                       for p in self.points],
        }


def point_count(params):
    # Extra spatial samples keep variable-pace timestamps approximately within the requested interval.
    factor = 1 + 3 * params.pace_variation_percent / 100
    return math.ceil(params.distance_m * params.pace_seconds_per_km * factor / 1000 / params.sample_interval) + 1


def smoothstep(x):
    x = min(1, max(0, x))
    return x*x*(3-2*x)


def profile(rng, length, spacing, amplitude, close=False):
    distances, values = [0.0], [0.0 if close else rng.uniform(-amplitude, amplitude)]
    while distances[-1] < length:
        distances.append(min(length, distances[-1] + rng.uniform(*spacing)))
        values.append(rng.uniform(-amplitude, amplitude))
    if close:
        values[-1] = 0.0
    def sample(distance):
        index = min(len(distances)-2, max(0, bisect_right(distances,distance)-1))
        x = (distance-distances[index])/(distances[index+1]-distances[index])
        return values[index] + (values[index+1]-values[index])*smoothstep(x)
    return sample


def build_activity(start, params):
    intervals = point_count(params)-1
    # Stable across preview/export, different for different dates in a batch.
    rng = random.Random(f"{int(params.random_seed)}:{start.isoformat()}")
    lane = profile(rng,params.distance_m,(35,85),params.lane_variation_m,close=True)
    amplitude = params.pace_variation_percent / 100
    pace_noise = profile(rng,params.distance_m,(100,250),amplitude*.35)
    finish_sign = -1 if rng.random() < .75 else 1
    points = []
    cumulative = 0.0
    previous = None
    for i in range(intervals + 1):
        travelled = params.distance_m * i / intervals
        lateral = lane(travelled)
        coord = position(travelled, params, lateral)
        if previous is not None:
            cumulative += distance_between(previous, coord)
        # Smooth local variation, with a 75% draw favouring faster pace in the final 40%.
        finish = finish_sign * amplitude * 1.2 * smoothstep((i/intervals-.6)/.4)
        pace = params.pace_seconds_per_km * (1 + pace_noise(travelled) + finish)
        points.append(Point(start, *coord, cumulative, None, pace, lateral))
        previous = coord
    if abs(cumulative - params.distance_m) / params.distance_m > 0.01:
        raise ValueError("采样后距离误差超过 1%，请减小采样间隔、变道幅度或调整跑道参数")
    raw_times = [(b.distance_m-a.distance_m)*(a.pace_s_per_km+b.pace_s_per_km)/2000
                 for a,b in zip(points,points[1:])]
    # Distance-weighted normalization preserves the user's average pace exactly.
    scale = cumulative * params.pace_seconds_per_km / 1000 / sum(raw_times)
    elapsed = 0.0
    for i,point in enumerate(points):
        if i:
            elapsed += raw_times[i-1] * scale
        point.time = start + timedelta(seconds=elapsed)
        point.active_s = elapsed
        point.pace_s_per_km *= scale
    activity = Activity(start, params, points)
    from services.metrics import enrich
    enrich(activity)
    return activity
