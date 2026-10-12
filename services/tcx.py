from datetime import timezone
import xml.etree.ElementTree as ET

NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
AX = "http://www.garmin.com/xmlschemas/ActivityExtension/v2"
ET.register_namespace("", NS)
ET.register_namespace("xsi", XSI)
ET.register_namespace("ae", AX)


def utc(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def element(parent, name, value=None, **attributes):
    node = ET.SubElement(parent, f"{{{NS}}}{name}", attributes)
    if value is not None:
        node.text = str(value)
    return node


def serialize(activity):
    root = ET.Element(f"{{{NS}}}TrainingCenterDatabase", {
        f"{{{XSI}}}schemaLocation": f"{NS} https://www8.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd"
    })
    activities = element(root, "Activities")
    running = element(activities, "Activity", Sport="Running")
    element(running, "Id", utc(activity.start))
    lap = element(running, "Lap", StartTime=utc(activity.start))
    element(lap, "TotalTimeSeconds", f"{activity.duration_s:.6f}")
    element(lap, "DistanceMeters", f"{activity.distance_m:.3f}")
    element(lap, "MaximumSpeed", f"{activity.max_speed:.6f}")
    summary = activity.summary()
    element(lap, "Calories", summary.get("calories_kcal",0))
    if summary["average_hr"] is not None:
        element(element(lap, "AverageHeartRateBpm"), "Value", summary["average_hr"])
        element(element(lap, "MaximumHeartRateBpm"), "Value", summary["max_hr"])
    element(lap, "Intensity", "Active")
    element(lap, "TriggerMethod", "Manual")
    track = element(lap, "Track")
    for point in activity.points:
        tp = element(track, "Trackpoint")
        element(tp, "Time", utc(point.time))
        pos = element(tp, "Position")
        element(pos, "LatitudeDegrees", f"{point.lat:.8f}")
        element(pos, "LongitudeDegrees", f"{point.lon:.8f}")
        if point.altitude_m is not None:
            element(tp,"AltitudeMeters",f"{point.altitude_m:.3f}")
        element(tp, "DistanceMeters", f"{point.distance_m:.3f}")
        if point.hr is not None:
            element(element(tp, "HeartRateBpm"), "Value", point.hr)
        element(tp,"SensorState","Absent" if point.paused else "Present")
        extension=ET.SubElement(element(tp,"Extensions"),f"{{{AX}}}TPX")
        ET.SubElement(extension,f"{{{AX}}}Speed").text=f"{point.speed_mps:.6f}"
        if point.cadence_spm is not None:
            # Running cadence in the Garmin profile is strides/min (two steps per stride).
            ET.SubElement(extension,f"{{{AX}}}RunCadence").text=str(round(point.cadence_spm/2))
        if point.power_w is not None:
            ET.SubElement(extension,f"{{{AX}}}Watts").text=str(round(point.power_w))
    if activity.params.simulate_metrics:
        lx=ET.SubElement(element(lap,"Extensions"),f"{{{AX}}}LX")
        for name,value in [('AvgSpeed',activity.distance_m/activity.duration_s),
                           ('AvgRunCadence',round(summary['average_cadence_spm']/2)),
                           ('MaxRunCadence',round(max(p.cadence_spm for p in activity.points)/2)),
                           ('Steps',summary['total_steps']),('AvgWatts',round(summary['average_power_w'])),
                           ('MaxWatts',round(max(p.power_w for p in activity.points)))]:
            if name=='Steps' and value>65535:
                continue
            ET.SubElement(lx,f"{{{AX}}}{name}").text=str(value)
    element(running, "Notes", "Synthetic activity for format testing. Not GPS-recorded. "
            "All physiological/dynamic metrics are simulated, not measured. "
            f"Elapsed seconds: {activity.elapsed_duration_s:.3f}; active seconds: {activity.duration_s:.3f}. "
            f"Synthetic metrics: {activity.metrics}. Coordinates: WGS84 approximation.")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
