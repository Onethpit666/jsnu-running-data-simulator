import io
from pathlib import Path
import sys
import threading
import webbrowser
import zipfile

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from config import DEFAULTS, MAX_REQUEST_BYTES
from services.activity import build_activity, parse_request
from services.tcx import serialize
from services.fit import serialize as serialize_fit

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
app = Flask(__name__, template_folder=str(BASE / "templates"), static_folder=str(BASE / "static"))
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES


@app.get("/")
def index():
    return render_template("index.html", defaults=DEFAULTS)


def activities_from_request():
    starts, params = parse_request(request.get_json())
    return [build_activity(start, params) for start in starts]


@app.post("/preview")
def preview():
    # Preview is single-record only, avoiding large JSON responses.
    starts, params = parse_request(request.get_json())
    if len(starts) != 1:
        raise ValueError("预览一次只能查看一个开始时间")
    return jsonify(build_activity(starts[0], params).preview())


@app.post("/generate")
def generate():
    export_format=request.get_json().get('export_format','tcx') if isinstance(request.get_json(),dict) else 'tcx'
    if export_format not in ('tcx','fit'):
        raise ValueError("导出格式必须为 TCX 或 FIT")
    exporter=serialize_fit if export_format=='fit' else serialize
    activities = activities_from_request()
    if len(activities) == 1:
        return send_file(io.BytesIO(exporter(activities[0])), mimetype="application/xml" if export_format=='tcx' else 'application/octet-stream',
                         as_attachment=True, download_name=filename(activities[0], 1,export_format))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for i, activity in enumerate(activities, 1):
            archive.writestr(filename(activity, i,export_format), exporter(activity))
    buffer.seek(0)
    return send_file(buffer, mimetype="application/zip", as_attachment=True, download_name="synthetic_runs.zip")


def filename(activity, index,export_format='tcx'):
    return f"synthetic_run_{activity.start:%Y%m%d_%H%M%S}_{index:02d}.{export_format}"


@app.errorhandler(ValueError)
def invalid_input(error):
    return jsonify(error=str(error)), 400


@app.errorhandler(BadRequest)
@app.errorhandler(UnsupportedMediaType)
def invalid_json(error):
    return jsonify(error="请发送完整、有效的 JSON 数据"), 400


@app.errorhandler(RequestEntityTooLarge)
def too_large(error):
    return jsonify(error="请求过大，请减少批量数量"), 413


@app.errorhandler(500)
def server_error(error):
    return jsonify(error="生成失败，请查看程序日志"), 500


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Local TCX file tool")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("端口必须在 1024 到 65535 之间")
    if not args.no_browser:
        threading.Timer(1, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
