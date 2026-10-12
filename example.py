"""Example using exactly the same model and serializer as the web app."""
from pathlib import Path
from services.activity import parse_request, build_activity
from services.tcx import serialize

if __name__ == "__main__":
    starts, params = parse_request({"times": ["2020-01-01T10:00:00+08:00"]})
    activity = build_activity(starts[0], params)
    output = Path(__file__).resolve().parent / "samples" / "synthetic_2km.tcx"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(serialize(activity))
    print(activity.summary())
    print(output)
