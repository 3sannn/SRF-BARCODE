from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
import fitz  # PyMuPDF
import barcode as bc
from barcode.writer import ImageWriter
import os, json
import re

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
BARCODE_FOLDER = os.path.join(app.root_path, 'barcodes')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BARCODE_FOLDER, exist_ok=True)
app.secret_key = 'nylon_secret_key'  # Needed for session

# ------------------- PDF Parser -------------------
def parse_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    all_data = []
    id_line_re = re.compile(r"^(\d+)\s+\S+")
    for page_num, page in enumerate(doc):
        lines = page.get_text("text").split("\n")
        if page_num == 0:
            print("--- DEBUG: First 50 lines of first page ---")
            for idx, line in enumerate(lines[:50]):
                print(f"{idx}: {repr(line)}")
            print("--- END DEBUG ---")
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
                    i += 9  # Move to next record
                except Exception as e:
                    print(f"Error parsing record at line {i}: {e}")
                    i += 1
            else:
                i += 1
    print(f"Total entries parsed: {len(all_data)}")
    return all_data

# ------------------- Routes -------------------

@app.route('/', methods=['GET'])
def home():
    entries = session.get('entries', [])
    return render_template('index.html', barcode=None, total=None, entries=entries)

@app.route('/connect')
def connect():
    pdf_path = os.path.join(UPLOAD_FOLDER, "machine_log.pdf")
    if not os.path.exists(pdf_path):
        return jsonify({"message": "PDF not found in uploads folder!"})
    entries = parse_pdf(pdf_path)
    with open("data.json", "w") as f:
        json.dump(entries, f)
    return jsonify({"message": f"✅ Server Connected. Data Loaded: {len(entries)} entries."})

@app.route('/add_entry', methods=['POST'])
def add_entry():
    user_id = request.form['user_id']
    shift = request.form['shift']
    timestamp = request.form['timestamp']
    entry = {'user_id': user_id, 'shift': shift, 'timestamp': timestamp}
    entries = session.get('entries', [])
    entries.append(entry)
    session['entries'] = entries
    return redirect(url_for('home'))

@app.route('/generate_barcode', methods=['POST'])
def generate_barcode():
    try:
        with open("data.json") as f:
            data = json.load(f)
    except FileNotFoundError:
        return "Data not loaded. Click Connect first."

    entries = session.get('entries', [])
    if not entries:
        return redirect(url_for('home'))

    total = 0

    for entry in entries:
        # Match records by timestamp and shift
        matches = [
            d for d in data
            if d["timestamp"] == entry['timestamp'] and d["shift"] == entry['shift']
        ]
        total += sum(d["actual_length"] for d in matches)

    # Only total value in barcode
    barcode_content = f"TOTAL : {total:.2f}"
    barcode_filename = f"total_{int(total)}.png"
    barcode_path = os.path.join('static', 'barcodes', barcode_filename)
    os.makedirs(os.path.dirname(barcode_path), exist_ok=True)

    # Generate barcode with no text printed under it
    code = bc.get('code128', barcode_content, writer=ImageWriter())
    code.save(barcode_path[:-4], options={
        "background": "white",
        "module_width": 0.2,
        "module_height": 10,
        "write_text": False  # Do not print text below the barcode
    })

    session['entries'] = []  # clear session after barcode generation
    return render_template("index.html", barcode=f"/static/barcodes/{barcode_filename}", total=total, entries=[])



# ------------------- Run App -------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)