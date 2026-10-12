"""Synthetic metrics. Not device measurements or Keep's proprietary load model."""
from dataclasses import replace
from datetime import timedelta
import math
import random


def weighted(activity, name):
    total = 0.0
    for i,(a,b) in enumerate(zip(activity.points,activity.points[1:])):
        dt=b.active_s-a.active_s
        if a.paused:
            a=activity.points[i-1]
        av,bv=getattr(a,name),getattr(b,name)
        if av is not None and bv is not None:
            total += (av+bv)/2*dt
    return total/activity.duration_s


def enrich(activity):
    p=activity.params
    points=activity.points
    rng=random.Random(f"metrics:{int(p.random_seed)}:{activity.start.isoformat()}")
    avg_speed=activity.distance_m/activity.duration_s
    hr=p.hr_min+.1*(p.hr_target-p.hr_min)
    noise=0.0
    # Smooth altitude curve, scaled by positive increments to the requested cumulative ascent.
    cycles=max(1,round(p.distance_m/p.lap_m))
    heights=[math.sin(2*math.pi*cycles*q.distance_m/activity.distance_m) for q in points]
    ascent=sum(max(0,b-a) for a,b in zip(heights,heights[1:]))
    for i,q in enumerate(points):
        dt=q.active_s-points[i-1].active_s if i else 0
        q.speed_mps=1000/q.pace_s_per_km
        if p.simulate_hr:
            warmup=1-math.exp(-q.active_s/max(1,p.hr_warmup_s)) if p.hr_warmup_s else 1
            target=p.hr_min+(p.hr_target-p.hr_min)*warmup
            # Effort affects the target, while the response lags behind speed changes.
            target += (q.speed_mps/avg_speed-1)*35
            hr += (target-hr)*(1-math.exp(-dt/p.hr_response_s))
            rho=math.exp(-dt/7)
            noise=rho*noise+math.sqrt(max(0,1-rho*rho))*rng.uniform(-1.7,1.7)*p.hr_variation_bpm
            jitter=rng.uniform(-.25,.25)*p.hr_variation_bpm
            q.hr=round(min(p.hr_max,max(p.hr_min,hr+noise+jitter)))
        if p.simulate_metrics:
            q.cadence_spm=p.cadence_spm*(q.speed_mps/avg_speed)**.2 + rng.uniform(-1,1)
            q.power_w=p.power_w*(q.speed_mps/avg_speed)**1.15*(1+rng.uniform(-.015,.015))
            q.altitude_m=p.base_altitude_m+(heights[i]-heights[0])*p.ascent_m/ascent
    if p.simulate_metrics:
        # Normalize time-weighted means, then derive step length from speed/cadence.
        cadence_scale=p.cadence_spm/weighted(activity,'cadence_spm')
        power_scale=p.power_w/weighted(activity,'power_w')
        for q in points:
            q.cadence_spm *= cadence_scale
            q.power_w *= power_scale
            q.stride_m=q.speed_mps*60/q.cadence_spm
        steps=weighted(activity,'cadence_spm')*activity.duration_s/60
        activity.metrics.update(
            calories_kcal=round(p.weight_kg*activity.distance_m/1000),
            ascent_m=round(sum(max(0,b.altitude_m-a.altitude_m) for a,b in zip(points,points[1:])),3),
            average_cadence_spm=round(weighted(activity,'cadence_spm'),2),
            average_power_w=round(weighted(activity,'power_w'),2),
            total_steps=round(steps),
            average_stride_m=round(activity.distance_m/steps,4),
            training_load_estimate=round(activity.duration_s/60*p.rpe,2),
            training_load_method='session-RPE simulation; not Keep load',
        )
    # Explicit stationary interval, instead of inflating elapsed time without a pause.
    if p.pause_seconds:
        middle=len(points)//2
        paused=replace(points[middle],time=points[middle].time+timedelta(seconds=p.pause_seconds),
                       paused=True,speed_mps=0, cadence_spm=0 if p.simulate_metrics else None,
                       power_w=0 if p.simulate_metrics else None,stride_m=0 if p.simulate_metrics else None)
        for q in points[middle+1:]:
            q.time += timedelta(seconds=p.pause_seconds)
        points.insert(middle+1,paused)
