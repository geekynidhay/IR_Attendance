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

@app.route('/darkest_point', methods=['GET'])
def get_darkest_point():
    """Find and return the darkest point in the current image"""
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
        
        # Stage 1: Median + Gaussian blur to remove IR noise / specular reflections
        blurred = cv2.medianBlur(gray, 7)
        blurred = cv2.GaussianBlur(blurred, (11, 11), 0)
        
        # Stage 2: Dynamic threshold — keep only pixels near the darkest region
        min_val = int(np.min(blurred))
        p10     = int(np.percentile(blurred, 10))
        thresh_val = max(int(min_val + (p10 - min_val) * 0.5), 5)
        
        _, thresh = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY_INV)
        
        # Stage 3: Morphological close+open to fill eyelash gaps and remove tiny specs
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        # Fallback: absolute darkest point
        min_loc = cv2.minMaxLoc(blurred)[2]
        best_x, best_y = min_loc[0], min_loc[1]
        best_score = -1
        
        # Stage 4: Score contours by circularity × darkness (the pupil wins)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 100 or area > (width * height * 0.5):
                continue
                
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter ** 2)
            
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Mean intensity inside contour (lower = darker = better)
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            mean_intensity = cv2.mean(blurred, mask=mask)[0]
            darkness = 255 - mean_intensity
            
            score = (circularity ** 2) * darkness
            if score > best_score:
                best_score = score
                best_x, best_y = cx, cy
        
        return jsonify({
            'ok': True,
            'x_pct': best_x / width,
            'y_pct': best_y / height,
            'x': best_x,
            'y': best_y,
            'width': width,
            'height': height
        })
    except Exception as e:
        print(f"Error finding darkest point: {e}")
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
        blurred = cv2.medianBlur(gray, 7)
        blurred = cv2.GaussianBlur(blurred, (11, 11), 0)

        min_val = int(np.min(blurred))
        p10 = int(np.percentile(blurred, 10))
        thresh_val = max(int(min_val + (p10 - min_val) * 0.5), 5)
        _, thresh = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        min_loc = cv2.minMaxLoc(blurred)[2]
        best_x, best_y = min_loc[0], min_loc[1]
        best_score = -1

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 100 or area > (width * height * 0.5):
                continue
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter ** 2)
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            mean_intensity = cv2.mean(blurred, mask=mask)[0]
            darkness = 255 - mean_intensity
            score = (circularity ** 2) * darkness
            if score > best_score:
                best_score = score
                best_x, best_y = cx, cy

        # Draw big crosshair + circle on the image
        cv2.circle(bgr, (best_x, best_y), 30, (0, 0, 255), 3)
        cv2.circle(bgr, (best_x, best_y), 5, (0, 255, 0), -1)
        cv2.line(bgr, (best_x - 50, best_y), (best_x + 50, best_y), (0, 0, 255), 2)
        cv2.line(bgr, (best_x, best_y - 50), (best_x, best_y + 50), (0, 0, 255), 2)
        label = f"({best_x},{best_y}) = {best_x/width:.2f},{best_y/height:.2f} | {width}x{height}"
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
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Server error: {e}")

def start_server():
    """Start the server in a separate thread"""
    global server_thread
    if server_thread is None:
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        ip_list = get_local_ip()
        print(f"Server started on http://{ip_list[0]}:5000")
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
