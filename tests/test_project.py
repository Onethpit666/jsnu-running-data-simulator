import io
import math
import os
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from services.activity import parse_request, build_activity, position, distance_between
from services.tcx import NS, serialize

N = {"t": NS}
REQUEST = {"times": ["2020-01-01T10:00:00+08:00"]}


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_home_and_assets(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        for path in ("/static/css/style.css", "/static/js/main.js"):
            with self.client.get(path) as result:
                self.assertEqual(result.status_code, 200)

    def test_invalid_requests(self):
        cases = [None, [], {}, {"times": []}, {"times": [None]},
                 {"times": ["2026-02-30T10:00:00"]},
                 {"times": ["1999-01-01T10:00:00"]},
                 {"times": [{}]},
                 {"times": [dict(year=2026, month=10, day=12, hour=10.8, minute=0, second=0)]},
                 dict(REQUEST, options={"distance_m": float("nan")}),
                 dict(REQUEST, options={"distance_m": 0}),
                 dict(REQUEST, options={"sample_interval": 1}),
                 dict(REQUEST, options={"simulate_hr": "yes"}),
                 dict(REQUEST, options={"hr_min": 160, "hr_max": 150}),
                 dict(REQUEST, options={"hr_min": 100.5}),
                 dict(REQUEST, options={"unknown": 1}),
                 {"times": REQUEST["times"] * 21},
                 {"times": REQUEST["times"] * 20, "options": {"distance_m":20000,"pace_seconds_per_km":1200}}]
        for case in cases:
            with self.subTest(case=case):
                result = self.client.post("/generate", json=case)
                self.assertEqual(result.status_code, 400)
                self.assertIn("error", result.json)

    def test_bad_json_and_size_limit(self):
        self.assertEqual(self.client.post("/generate", data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/generate", data="{}", content_type="text/plain").status_code, 400)
        self.assertEqual(self.client.post("/generate", data=b" " * 65537, content_type="application/json").status_code, 413)

    def test_timezone_distance_and_time(self):
        starts, params = parse_request(REQUEST)
        activity = build_activity(starts[0], params)
        root = ET.fromstring(serialize(activity))
        self.assertEqual(root.find(".//t:Id", N).text, "2020-01-01T02:00:00.000000Z")
        self.assertLess(abs(activity.distance_m - 2000), 20)
        self.assertAlmostEqual(activity.duration_s / activity.distance_m * 1000, 360, places=5)
        accumulated = sum(distance_between((a.lat,a.lon),(b.lat,b.lon)) for a,b in zip(activity.points,activity.points[1:]))
        self.assertAlmostEqual(accumulated,activity.distance_m,places=9)
        for a,b in zip(activity.points,activity.points[1:]):
            self.assertGreater(b.time,a.time)
            self.assertGreaterEqual(b.distance_m,a.distance_m)
            if b.distance_m == a.distance_m:
                self.assertTrue(b.paused)
        track = root.findall(".//t:Trackpoint", N)
        self.assertEqual(root.find(".//t:Lap/t:DistanceMeters", N).text,track[-1].find("t:DistanceMeters", N).text)
        self.assertEqual(int(root.find(".//t:Calories", N).text), activity.metrics['calories_kcal'])
        self.assertIsNone(root.find(".//t:HeartRateBpm", N))

    def test_boundaries_rotation_and_closure(self):
        _, params = parse_request(REQUEST)
        self.assertEqual(position(0,params),position(params.lap_m,params))
        for edge in (100,200,300,400):
            self.assertLess(distance_between(position(edge-0.001,params),position(edge+0.001,params)),0.005)
        _, rotated = parse_request(dict(REQUEST, options={"rotation_deg":90,"straight_m":150,"radius_m":40}))
        self.assertAlmostEqual(rotated.lap_m,300+80*math.pi)
        self.assertNotEqual(position(0,params),position(0,rotated))

    def test_synthetic_hr_is_irregular_bounded_and_labelled(self):
        starts, params = parse_request(dict(REQUEST, options={"simulate_hr":True}))
        activity=build_activity(starts[0],params)
        heart=[p.hr for p in activity.points]
        self.assertTrue(all(100 <= x <= 190 for x in heart))
        self.assertLess(max(abs(b-a) for a,b in zip(heart,heart[1:])),20)
        self.assertGreater(len(set(heart)),10)
        self.assertGreater(max(abs(b-a) for a,b in zip(heart[100:],heart[101:])),3)
        root=ET.fromstring(serialize(activity))
        self.assertIn("Synthetic",root.find(".//t:Activity/t:Notes",N).text)

    def test_download_and_duplicate_filenames(self):
        response=self.client.post("/generate",json=REQUEST)
        self.assertEqual(response.status_code,200)
        self.assertIn(".tcx",response.headers["Content-Disposition"])
        response=self.client.post("/generate",json={"times":REQUEST["times"]*2})
        self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            names=archive.namelist()
            self.assertEqual(len(names),2)
            self.assertEqual(len(set(names)),2)
            for name in names:
                ET.fromstring(archive.read(name))

    def test_preview_export_agree(self):
        preview=self.client.post("/preview",json=REQUEST).json
        root=ET.fromstring(self.client.post("/generate",json=REQUEST).data)
        self.assertEqual(float(root.find(".//t:Lap/t:DistanceMeters",N).text),preview["summary"]["distance_m"])
        self.assertEqual(len(root.findall(".//t:Trackpoint",N)),len(preview["points"]))
        self.assertEqual(self.client.post("/preview",json={"times":REQUEST["times"]*2}).status_code,400)

    def test_variation_is_reproducible_and_can_be_disabled(self):
        starts,params=parse_request(REQUEST)
        a=build_activity(starts[0],params)
        self.assertEqual(serialize(a),serialize(build_activity(starts[0],params)))
        _,different=parse_request(dict(REQUEST,options={"random_seed":43}))
        self.assertNotEqual(serialize(a),serialize(build_activity(starts[0],different)))
        _,regular=parse_request(dict(REQUEST,options={"pace_variation_percent":0,"lane_variation_m":0}))
        b=build_activity(starts[0],regular)
        self.assertTrue(all(p.lateral_m == 0 for p in b.points))
        self.assertTrue(all(abs(p.pace_s_per_km-360)<0.0001 for p in b.points))

    def test_smooth_lane_changes_and_variable_pace(self):
        starts,params=parse_request(REQUEST)
        a=build_activity(starts[0],params)
        self.assertTrue(all(abs(p.lateral_m)<=1.5 for p in a.points))
        self.assertGreater(max(p.lateral_m for p in a.points)-min(p.lateral_m for p in a.points),1)
        self.assertLess(max(abs(b.lateral_m-p.lateral_m) for p,b in zip(a.points,a.points[1:])),0.7)
        self.assertGreater(max(p.pace_s_per_km for p in a.points)-min(p.pace_s_per_km for p in a.points),10)
        self.assertLess(max(abs(b.pace_s_per_km-p.pace_s_per_km) for p,b in zip(a.points,a.points[1:])),8)
        splits=a.splits()
        self.assertAlmostEqual(sum(x['distance_m'] for x in splits),a.distance_m,delta=.003)
        self.assertAlmostEqual(sum(x['duration_s'] for x in splits),a.duration_s,delta=.003)
        self.assertGreater(a.max_speed,1000/360)
        root=ET.fromstring(serialize(a))
        self.assertAlmostEqual(float(root.find('.//t:MaximumSpeed',N).text),a.max_speed,places=5)

    def test_finish_faster_is_more_likely_over_many_seeds(self):
        faster=0
        for seed in range(100):
            starts,params=parse_request(dict(REQUEST,options={"random_seed":seed}))
            a=build_activity(starts[0],params)
            self.assertAlmostEqual(a.duration_s/a.distance_m*1000,360,places=5)
            faster += a.splits()[-1]['pace_seconds_per_km'] < 360
        self.assertGreater(faster,60)
        self.assertLess(faster,95)

    @unittest.skipUnless(os.environ.get("TCX_SCHEMA"), "Set TCX_SCHEMA to official Garmin XSD for format validation")
    def test_official_xsd(self):
        from lxml import etree
        schema=etree.XMLSchema(etree.parse(os.environ["TCX_SCHEMA"]))
        for options in ({},{"simulate_hr":True},{"distance_m":2200,"rotation_deg":30}):
            starts,params=parse_request(dict(REQUEST,options=options))
            schema.assertValid(etree.fromstring(serialize(build_activity(starts[0],params))))
            extension=etree.XMLSchema(etree.parse(str(Path(os.environ['TCX_SCHEMA']).with_name('ActivityExtensionv2.xsd'))))
            root=etree.fromstring(serialize(build_activity(starts[0],params)))
            for element in root.xpath('//*[local-name()="TPX" or local-name()="LX"]'):
                extension.assertValid(element)

    def test_pause_and_metrics_consistency(self):
        from services.metrics import weighted
        starts,p=parse_request(dict(REQUEST,options={'ascent_m':31}))
        a=build_activity(starts[0],p)
        self.assertAlmostEqual(a.elapsed_duration_s-a.duration_s,3,places=5)
        self.assertEqual(sum(q.paused for q in a.points),1)
        self.assertAlmostEqual(weighted(a,'cadence_spm'),164,places=5)
        self.assertAlmostEqual(weighted(a,'power_w'),250,places=5)
        self.assertEqual(a.metrics['ascent_m'],31)
        self.assertAlmostEqual(a.metrics['average_stride_m'],a.distance_m/(164*a.duration_s/60),places=4)
        self.assertEqual(a.metrics['calories_kcal'],round(65*a.distance_m/1000))
        self.assertAlmostEqual(a.metrics['training_load_estimate'],a.duration_s/60*3,places=2)

    def test_metrics_disabled_and_flat_track(self):
        starts,p=parse_request(REQUEST)
        a=build_activity(starts[0],p)
        self.assertEqual(a.metrics['ascent_m'],0)
        _,p=parse_request(dict(REQUEST,options={'simulate_metrics':False,'pause_seconds':0}))
        a=build_activity(starts[0],p)
        self.assertEqual(a.metrics,{})
        self.assertEqual(a.elapsed_duration_s,round(a.duration_s,6))
        self.assertTrue(all(q.altitude_m is None for q in a.points))

    def test_hr_strength_controls_short_term_variation(self):
        def roughness(strength):
            starts,p=parse_request(dict(REQUEST,options={'simulate_hr':True,'hr_variation_bpm':strength}))
            heart=[q.hr for q in build_activity(starts[0],p).points][100:]
            return sum(abs(b-a) for a,b in zip(heart,heart[1:]))/len(heart)
        self.assertGreater(roughness(8),roughness(0)*4)

    def test_new_parameter_validation(self):
        for options in ({'pause_seconds':1.5},{'simulate_metrics':'yes'},{'ascent_m':-1},
                        {'hr_variation_bpm':16},{'simulate_hr':True,'hr_target':200}, {'weight_kg':0}):
            self.assertEqual(self.client.post('/generate',json=dict(REQUEST,options=options)).status_code,400)
        self.assertEqual(self.client.post('/generate',json=dict(REQUEST,export_format='gpx')).status_code,400)

    def test_fit_crc_native_fields_and_pause(self):
        from garmin_fit_sdk import Decoder,Stream
        response=self.client.post('/generate',json=dict(REQUEST,export_format='fit',options={'simulate_hr':True,'ascent_m':31}))
        self.assertEqual(response.status_code,200)
        decoder=Decoder(Stream.from_byte_array(bytearray(response.data)))
        self.assertTrue(decoder.check_integrity())
        decoder=Decoder(Stream.from_byte_array(bytearray(response.data)))
        messages,errors=decoder.read()
        self.assertEqual(errors,[])
        session=messages['session_mesgs'][0]
        self.assertAlmostEqual(session['total_elapsed_time']-session['total_timer_time'],3,places=3)
        self.assertEqual(session['total_ascent'],31)
        self.assertEqual(session['avg_power'],250)
        self.assertAlmostEqual(2*(session['avg_cadence']+session['avg_fractional_cadence']),164,places=2)
        self.assertGreater(session['avg_step_length'],900)
        self.assertGreater(session['total_calories'],100)
        self.assertNotIn('training_load_peak',session)
        self.assertEqual(session['developer_fields'][0],1)
        self.assertEqual(len(messages['event_mesgs']),4)

    def test_fit_batch(self):
        from garmin_fit_sdk import Decoder,Stream
        response=self.client.post('/generate',json={'times':REQUEST['times']*2,'export_format':'fit'})
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(len(archive.namelist()),2)
            for name in archive.namelist():
                self.assertTrue(name.endswith('.fit'))
                decoder=Decoder(Stream.from_byte_array(bytearray(archive.read(name))))
                self.assertTrue(decoder.check_integrity())
                decoder=Decoder(Stream.from_byte_array(bytearray(archive.read(name))))
                messages,errors=decoder.read()
                self.assertEqual(errors,[])
                self.assertEqual(len(messages['session_mesgs']),1)


if __name__ == "__main__":
    unittest.main()
