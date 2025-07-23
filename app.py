from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import fitz  # PyMuPDF
import barcode as bc
from barcode.writer import ImageWriter
import os, json, re
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
BARCODE_FOLDER = os.path.join(app.root_path, 'static', 'barcodes')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BARCODE_FOLDER, exist_ok=True)
app.secret_key = 'nylon_secret_key'

# ------------------- PDF Parser -------------------
def parse_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    all_data = []
    id_line_re = re.compile(r"^(\d+)\s+\S+")
    for page_num, page in enumerate(doc):
        lines = page.get_text("text").split("\n")
        i = 0
        while i < len(lines):
            match = id_line_re.match(lines[i].strip())
            if match:
                try:
                    id_val = match.group(1)
                    timestamp = lines[i+2].strip()
                    shift = lines[i+3].strip()
                    actual_length = float(lines[i+8].strip())
                    entry = {
                        "id": id_val,
                        "timestamp": timestamp,
                        "shift": shift,
                        "actual_length": actual_length
                    }
                    all_data.append(entry)
                    i += 9
                except Exception as e:
                    print(f"Error parsing record at line {i}: {e}")
                    i += 1
            else:
                i += 1
    return all_data

# ------------------- Routes -------------------
@app.route('/')
def home():
    return render_template('index.html', barcode=None, total=None)

@app.route('/connect')
def connect():
    pdf_path = os.path.join(UPLOAD_FOLDER, "machine_log.pdf")
    if not os.path.exists(pdf_path):
        return jsonify({"message": "PDF not found in uploads folder!"})
    entries = parse_pdf(pdf_path)
    with open("data.json", "w") as f:
        json.dump(entries, f)
    return jsonify({"message": f"✅ Server Connected. Data Loaded: {len(entries)} entries."})

@app.route('/generate_barcode', methods=['POST'])
def generate_barcode():
    start_time = request.form['start_time']
    end_time = request.form['end_time']
    shift = request.form['shift']

    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "❌ Invalid time format. Use: YYYY-MM-DD HH:MM:SS"

    try:
        with open("data.json") as f:
            data = json.load(f)
    except FileNotFoundError:
        return "❌ Data not loaded. Click Connect first."

    total = 0
    for d in data:
        if d["shift"] != shift:
            continue
        try:
            record_dt = datetime.strptime(d["timestamp"], "%Y-%m-%d %H:%M:%S")
            if start_dt <= record_dt <= end_dt:
                total += d["actual_length"]
        except:
            continue

    if total == 0:
        return render_template("index.html", barcode=None, total=0, message="❌ No data in this time range.")

    barcode_text = f"TOTAL : {total:.2f}"
    barcode_filename = f"total_{int(total)}.png"
    barcode_path = os.path.join(BARCODE_FOLDER, barcode_filename)

    code = bc.get('code128', barcode_text, writer=ImageWriter())
    code.save(barcode_path[:-4], options={
        "background": "white",
        "module_width": 0.2,
        "module_height": 10,
        "write_text": False
    })

    return render_template("index.html", barcode=f"/static/barcodes/{barcode_filename}", total=total, message="✅ Barcode Generated")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
