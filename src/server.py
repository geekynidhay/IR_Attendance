import threading
import io
import time
import socket
from flask import Flask, send_file, jsonify, request
from PIL import Image

# Global state to share between UI and Server
current_image_bytes = None
current_pil_image = None
current_image_id = 0
server_thread = None
app = Flask(__name__)

# ── Mobile Attendance state ───────────────────────────────────────────────────
import threading as _threading
_mobile_lock = _threading.Lock()
_pending_mobile_id = None   # ID string waiting to be tapped on phone
_mobile_ack_event = _threading.Event()  # Set when phone acks completion
registered_phone_ip = None # IP of the connected smartphone

last_phone_access_time = 0 # Timestamp of last phone request

def is_phone_connected():
    """Return True if phone accessed server in the last 5 seconds"""
    return (time.time() - last_phone_access_time) < 5

_placeholder_image_bytes = None

def _generate_placeholder():
    global _placeholder_image_bytes
    if _placeholder_image_bytes is not None:
        return _placeholder_image_bytes
        
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (1080, 1920), color=(0, 0, 0))
        d = ImageDraw.Draw(img)
        text = "Start Attendance\nPhone is Connected"
        
        try:
            font = ImageFont.truetype("arial.ttf", 60)
        except:
            font = ImageFont.load_default()
            
        try:
            left, top, right, bottom = d.textbbox((0, 0), text, font=font, align="center")
            w = right - left
            h = bottom - top
        except:
            w, h = d.textsize(text, font=font)
            
        x = (1080 - w) / 2
        y = (1920 - h) / 2
        
        d.text((x, y), text, fill=(0, 255, 0), font=font, align="center")
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        _placeholder_image_bytes = img_byte_arr.getvalue()
        return _placeholder_image_bytes
    except Exception as e:
        print(f"Error generating placeholder: {e}")
        return None

def get_local_ip():
    """Get list of local IP addresses"""
    ip_list = []
    try:
        # Get all interfaces
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ip_list.append(ip)
                
        # Fallback if list is empty but we can connect to internet
        if not ip_list:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            ip_list.append(ip)
            
    except Exception:
        pass
        
    return ip_list if ip_list else ["127.0.0.1"]

@app.route('/status', methods=['GET'])
def get_status():
    """Return the current image ID to let client know if image changed"""
    global last_phone_access_time
    last_phone_access_time = time.time()
    return jsonify({
        'image_id': current_image_id,
        'timestamp': time.time()
    })

@app.route('/image', methods=['GET'])
def get_image():
    """Return the current image if available"""
    global current_image_bytes
    global last_phone_access_time
    last_phone_access_time = time.time()
    
    if current_image_bytes is None:
        placeholder = _generate_placeholder()
        if placeholder:
            return send_file(
                io.BytesIO(placeholder),
                mimetype='image/png',
                as_attachment=False,
                download_name='current.png'
            )
        return "No image loaded", 404
        
    return send_file(
        io.BytesIO(current_image_bytes),
        mimetype='image/png',
        as_attachment=False,
        download_name='current.png'
    )

def _find_pupil_center(gray):
    """
    Robust pupil detection using Hough Circles + Contour fallback.
    Finds the darkest point STRICTLY INSIDE the detected circle/contour to avoid eyelashes.
    Returns (x, y, confidence, method_name).
    """
    import cv2
    import numpy as np

    height, width = gray.shape

    # ── Stage 1: Preprocessing ─────────────────────────────────────────────
    filtered = cv2.bilateralFilter(gray, 9, 75, 75)
    blurred = cv2.GaussianBlur(filtered, (9, 9), 2)

    best_x, best_y = width // 2, height // 2
    best_score = -1
    method = "center_fallback"

    # ── Stage 2: Hough Circle Detection (primary) ──────────────────────────
    min_radius = max(int(min(width, height) * 0.04), 8)
    max_radius = int(min(width, height) * 0.25)

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.5,
        minDist=max(width, height) // 4,
        param1=50,
        param2=25,
        minRadius=min_radius,
        maxRadius=max_radius
    )

    if circles is not None:
        circles = np.uint16(np.around(circles))
        for c in circles[0, :]:
            cx, cy, r = int(c[0]), int(c[1]), int(c[2])

            mx = int(width * 0.12)
            my = int(height * 0.12)
            if cx < mx or cx > width - mx or cy < my or cy > height - my:
                continue

            # Measure mean darkness inside the circle
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.circle(mask, (cx, cy), r, 255, -1)
            mean_val = cv2.mean(blurred, mask=mask)[0]
            darkness = 255 - mean_val

            # Mild spatial preference toward image center
            dist = np.sqrt(((cx - width / 2) / width) ** 2 + ((cy - height / 2) / height) ** 2)
            spatial_w = 1.0 - dist * 0.4

            score = darkness * spatial_w
            if score > best_score:
                best_score = score
                # Geometric center of the circle is the most stable point.
                best_x, best_y = cx, cy
                method = "hough_geometric"

    # ── Stage 3: Contour-based fallback ────────────────────────────────────
    if best_score < 60:
        heavy = cv2.medianBlur(gray, 7)
        heavy = cv2.GaussianBlur(heavy, (11, 11), 0)

        min_val_global = int(np.min(heavy))
        p10 = int(np.percentile(heavy, 10))
        tv = max(int(min_val_global + (p10 - min_val_global) * 0.4), 5)
        _, thresh = cv2.threshold(heavy, tv, 255, cv2.THRESH_BINARY_INV)

        kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kern)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kern)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c_best = -1
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 500 or area > (width * height * 0.3):
                continue

            perim = cv2.arcLength(cnt, True)
            if perim == 0:
                continue
            circ = 4 * np.pi * area / (perim ** 2)
            if circ < 0.45:
                continue

            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            mx = int(width * 0.12)
            my = int(height * 0.12)
            if cx < mx or cx > width - mx or cy < my or cy > height - my:
                continue

            mask = np.zeros(gray.shape, dtype=np.uint8)
            # Draw slightly eroded contour mask
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            mask = cv2.erode(mask, np.ones((5,5), np.uint8), iterations=1)

            # Find darkest point inside contour
            min_val, _, min_loc, _ = cv2.minMaxLoc(heavy, mask=mask)
            darkest_x, darkest_y = min_loc
            
            # Use original mask for mean darkness calculation
            full_mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.drawContours(full_mask, [cnt], -1, 255, -1)
            darkness = 255 - cv2.mean(heavy, mask=full_mask)[0]

            dist = np.sqrt(((cx - width / 2) / width) ** 2 + ((cy - height / 2) / height) ** 2)
            spatial_w = 1.0 - dist * 0.3

            score = (circ ** 2) * darkness * spatial_w
            if score > c_best:
                c_best = score
                # Use darkest point inside contour
                best_x, best_y = darkest_x, darkest_y
                best_score = c_best
                method = "contour_darkest_inner"

    # ── Stage 4: Final sanity check ────────────────────────────────────────
    mx = int(width * 0.12)
    my = int(height * 0.12)
    if best_x < mx or best_x > width - mx or best_y < my or best_y > height - my:
        best_x, best_y = width // 2, height // 2
        best_score = 0
        method = "center_fallback"

    confidence = min(max(best_score, 0) / 200.0, 1.0)
    return best_x, best_y, confidence, method


@app.route('/darkest_point', methods=['GET'])
def get_darkest_point():
    """Find and return the pupil center in the current image."""
    global current_pil_image
    if current_pil_image is None:
        return jsonify({'ok': False, 'error': 'No image loaded'}), 404

    try:
        import cv2
        import numpy as np

        img_arr = np.array(current_pil_image)
        if len(img_arr.shape) == 3:
            gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_arr.copy()

        height, width = gray.shape
        px, py, confidence, method = _find_pupil_center(gray)

        return jsonify({
            'ok': True,
            'x_pct': px / width,
            'y_pct': py / height,
            'x': px,
            'y': py,
            'width': width,
            'height': height,
            'confidence': confidence,
            'method': method
        })
    except Exception as e:
        print(f"Error finding pupil: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/debug_preview', methods=['GET'])
def debug_preview():
    """Return the current image with detected pupil circled for debugging."""
    global current_pil_image
    if current_pil_image is None:
        return jsonify({'error': 'No image'}), 404
    try:
        import cv2
        import numpy as np

        img_arr = np.array(current_pil_image)
        if len(img_arr.shape) == 3:
            bgr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        else:
            bgr = cv2.cvtColor(img_arr, cv2.COLOR_GRAY2BGR)
            gray = img_arr.copy()

        height, width = gray.shape
        best_x, best_y, confidence, method = _find_pupil_center(gray)

        # Draw big crosshair + circle on the image
        cv2.circle(bgr, (best_x, best_y), 30, (0, 0, 255), 3)
        cv2.circle(bgr, (best_x, best_y), 5, (0, 255, 0), -1)
        cv2.line(bgr, (best_x - 50, best_y), (best_x + 50, best_y), (0, 0, 255), 2)
        cv2.line(bgr, (best_x, best_y - 50), (best_x, best_y + 50), (0, 0, 255), 2)
        label = f"({best_x},{best_y}) conf={confidence:.2f} [{method}]"
        cv2.putText(bgr, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        _, enc = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return send_file(io.BytesIO(enc.tobytes()), mimetype='image/jpeg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/mobile_input', methods=['POST'])
def mobile_input():
    """PC sends the ID to be tapped on the phone numpad."""
    global _pending_mobile_id
    data = request.get_json(force=True, silent=True) or {}
    id_str = str(data.get('id', '')).strip()
    if not id_str:
        return jsonify({'ok': False, 'error': 'missing id'}), 400
    with _mobile_lock:
        _pending_mobile_id = id_str
        _mobile_ack_event.clear()
    return jsonify({'ok': True})

@app.route('/mobile_status', methods=['GET'])
def mobile_status():
    """Phone polls this to get the next ID to tap."""
    with _mobile_lock:
        pid = _pending_mobile_id
    return jsonify({'pending_id': pid})

@app.route('/mobile_ack', methods=['POST'])
def mobile_ack():
    """Phone calls this after it finishes tapping all digits."""
    global _pending_mobile_id
    with _mobile_lock:
        _pending_mobile_id = None
        _mobile_ack_event.set()
    return jsonify({'ok': True})

@app.route('/register_phone', methods=['POST'])
def register_phone():
    """Phone calls this to announce its local IP to the PC."""
    global registered_phone_ip
    data = request.get_json(force=True, silent=True) or {}
    ip = data.get('ip')
    if ip:
        registered_phone_ip = ip
        global last_phone_access_time
        last_phone_access_time = time.time()
        print(f"[Server] Phone registered at IP: {ip}")
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'missing ip'}), 400

# ── Digit coordinate calibration ─────────────────────────────────────────────
_digit_coords = {}   # {'0': {'x': 540, 'y': 1200}, '1': ..., ...}
_digit_coords_lock = _threading.Lock()

@app.route('/digit_coords', methods=['POST'])
def set_digit_coords():
    """Phone sends calibrated {coords: {'0':{x,y}, '1':{x,y}, ...}} to PC."""
    global _digit_coords
    data = request.get_json(force=True, silent=True) or {}
    coords = data.get('coords', {})
    if not coords:
        return jsonify({'ok': False, 'error': 'missing coords'}), 400
    with _digit_coords_lock:
        _digit_coords = coords
    print(f"[Server] Digit coords calibrated: {list(coords.keys())}")
    return jsonify({'ok': True, 'digits': list(coords.keys())})

@app.route('/digit_coords', methods=['GET'])
def get_digit_coords():
    """Return stored calibration coords."""
    with _digit_coords_lock:
        return jsonify({'coords': _digit_coords, 'calibrated': bool(_digit_coords)})

def get_stored_digit_coords():
    """Helper for Python code to read stored coords."""
    with _digit_coords_lock:
        return dict(_digit_coords)

def update_image(pil_image):
    """
    Update the current image being served.
    This should be called by the main GUI thread whenever the image changes.
    """
    global current_image_bytes, current_image_id, current_pil_image
    current_pil_image = pil_image
    
    try:
        if pil_image:
            # Convert to JPEG bytes
            img_byte_arr = io.BytesIO()
            # Convert to RGB if RGBA (JPEG doesn't support alpha)
            if pil_image.mode == 'RGBA':
                pil_image = pil_image.convert('RGB')
                
            pil_image.save(img_byte_arr, format='PNG')
            current_image_bytes = img_byte_arr.getvalue()
            current_image_id += 1
        else:
            current_image_bytes = None
            current_image_id += 1 # Increment so phone fetches the placeholder
    except Exception as e:
        print(f"Error updating server image: {e}")

def run_server():
    """Run the Flask server"""
    try:
        # Run on 0.0.0.0 to be accessible from other devices
        app.run(host='0.0.0.0', port=5005, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Server error: {e}")

def start_server():
    """Start the server in a separate thread"""
    global server_thread
    if server_thread is None:
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        ip_list = get_local_ip()
        print(f"Server started on http://{ip_list[0]}:5005")
        
        # Publish IP to Firebase for Auto-Discovery by Mobile App
        try:
            import requests
            requests.put("https://attendance-68878-default-rtdb.asia-southeast1.firebasedatabase.app/active_pc_ip.json", json={"ip": ip_list[0]}, timeout=5)
            print(f"Published active PC IP {ip_list[0]} to Firebase for auto-discovery.")
        except Exception as e:
            print(f"Failed to publish IP to Firebase: {e}")
        return ip_list
    return get_local_ip()

def type_on_mobile(id_string, wait_timeout=15):
    """
    Tell the mobile app to tap the given ID on its numpad.
    Blocks until the phone acknowledges or times out.
    Returns True on success, False on timeout.
    """
    global _pending_mobile_id
    with _mobile_lock:
        _pending_mobile_id = str(id_string).strip()
        _mobile_ack_event.clear()
    return _mobile_ack_event.wait(timeout=wait_timeout)

def trigger_mobile_focus():
    global _trigger_focus
    with _mobile_lock:
        _trigger_focus = True
