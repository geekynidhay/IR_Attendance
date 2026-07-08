"""
Image processing utilities for IR Attendance application
Handles image splitting, cropping, and batch processing
"""
from PIL import Image, ImageEnhance
from pathlib import Path
import os
import re
import cv2
import numpy as np
import pytesseract

class ImageProcessor:
    """Handles all image processing operations"""
    
    @staticmethod
    def split_image(image_path, split_position_percent, crop_settings=None):
        """
        Split an image vertically at the specified position
        """
        try:
            img = Image.open(image_path)
            width, height = img.size
            
            # Apply crop if enabled
            if crop_settings and crop_settings.get('enabled', False):
                left_percent = crop_settings.get('left', 0)
                top_percent = crop_settings.get('top', 0)
                right_percent = crop_settings.get('right', 100)
                bottom_percent = crop_settings.get('bottom', 100)
                
                crop_left = int(width * left_percent / 100)
                crop_top = int(height * top_percent / 100)
                crop_right = int(width * right_percent / 100)
                crop_bottom = int(height * bottom_percent / 100)
                
                img = img.crop((crop_left, crop_top, crop_right, crop_bottom))
                width, height = img.size
            
            # Calculate split position
            split_x = int(width * split_position_percent / 100)
            
            # Split the image
            left_img = img.crop((0, 0, split_x, height))
            right_img = img.crop((split_x, 0, width, height))
            
            return left_img, right_img
        
        except Exception as e:
            print(f"Error splitting image {image_path}: {e}")
            return None, None
    
    @staticmethod
    def adjust_brightness(image, brightness_percent):
        """
        Adjust image brightness
        """
        try:
            enhancer = ImageEnhance.Brightness(image)
            # Apply quadratic mapping: UI 100->1.0, UI 101->1.02, UI 200->4.0
            factor = (brightness_percent / 100.0) ** 2
            return enhancer.enhance(factor)
        except Exception as e:
            print(f"Error adjusting brightness: {e}")
            return image
    
    @staticmethod
    def batch_split_images(raw_data_folder, output_base_folder, split_position_percent=50, 
                           crop_settings=None, progress_callback=None, visual_callback=None):
        """
        Batch process a folder of images, dividing them based on base folder names.
        """
        results = {
            'total': 0,
            'processed': 0,
            'candidates': 0,
            'errors': []
        }
        
        try:
            raw_path = Path(raw_data_folder)
            if not raw_path.exists():
                results['errors'].append(f"Raw data folder not found: {raw_data_folder}")
                return results
            
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
            image_files = []
            for ext in image_extensions:
                image_files.extend(list(raw_path.rglob(f"*{ext}")))
                image_files.extend(list(raw_path.rglob(f"*{ext.upper()}")))
            
            results['total'] = len(image_files)
            
            image_groups = {}
            for img_file in image_files:
                stem = img_file.stem
                match = re.match(r'^([^\s\-=(]+)', stem)
                base_name = match.group(1).strip() if match else stem.strip()
                if base_name not in image_groups:
                    image_groups[base_name] = []
                image_groups[base_name].append(img_file)
            
            current = 0
            for base_name, images in image_groups.items():
                output_folder = Path(output_base_folder) / base_name
                output_folder.mkdir(parents=True, exist_ok=True)
                
                for img_file in sorted(images):
                    current += 1
                    if progress_callback:
                        progress_callback(current, results['total'], f"Processing {img_file.name}...")
                    
                    try:
                        left_img, right_img = ImageProcessor.split_image(
                            img_file, split_position_percent, crop_settings
                        )
                        
                        if left_img and right_img:
                            base_filename = img_file.stem
                            extension = img_file.suffix
                            
                            save_args = {}
                            if extension.lower() in ['.jpg', '.jpeg']:
                                save_args = {'quality': 100, 'subsampling': 0}
                            
                            # Only save left image if it has non-zero size
                            if left_img.width > 0 and left_img.height > 0:
                                left_path = output_folder / f"{base_filename}-left{extension}"
                                left_img.save(left_path, **save_args)
                                
                            # Only save right image if it has non-zero size
                            if right_img.width > 0 and right_img.height > 0:
                                right_path = output_folder / f"{base_filename}-right{extension}"
                                right_img.save(right_path, **save_args)
                                
                            results['processed'] += 1
                            
                            if visual_callback:
                                visual_callback(base_name, left_img, right_img)
                        else:
                            results['errors'].append(f"Failed to split: {img_file.name}")
                    
                    except Exception as e:
                        results['errors'].append(f"Error processing {img_file.name}: {e}")
            
            results['candidates'] = len(image_groups)
            if progress_callback:
                progress_callback(current, results['total'], "Processing complete!")
        
        except Exception as e:
            results['errors'].append(f"Batch processing error: {e}")
            
        return results

    @staticmethod
    def trim_whitespace(image):
        """Trim whitespace from all 4 sides of a PIL image"""
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        _, thresh_i = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        v_sums = np.sum(thresh_i, axis=1)
        content_rows = np.where(v_sums > (255 * 2))[0]
        h_sums = np.sum(thresh_i, axis=0)
        content_cols = np.where(h_sums > (255 * 2))[0]
        if len(content_rows) > 0 and len(content_cols) > 0:
            t, b = content_rows[0], content_rows[-1]
            l, r = content_cols[0], content_cols[-1]
            t, b = max(0, t - 2), min(image.height, b + 2)
            l, r = max(0, l - 2), min(image.width, r + 2)
            return image.crop((l, t, r, b))
        return image

    @staticmethod
    def extract_from_pil_image(pil_img, output_base_folder, progress_callback=None, visual_callback=None, id_counters=None):
        """
        Extract sub-images from a single PIL image (e.g. a PDF page)
        Supports multiple IDs per row with automatic horizontal mapping.
        """
        results = {'processed': 0, 'errors': []}
        if id_counters is None:
            id_counters = {}
            
        try:
            tess_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            if os.path.exists(tess_path):
                pytesseract.pytesseract.tesseract_cmd = tess_path
            
            img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            img_gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            width, height = pil_img.size
            
            _, thresh = cv2.threshold(img_gray, 240, 255, cv2.THRESH_BINARY_INV)
            row_sums = np.sum(thresh, axis=1)
            
            content_mask = row_sums > (255 * 5)
            segments = []
            in_segment = False
            start_y = 0
            
            for y, has_content in enumerate(content_mask):
                if has_content and not in_segment:
                    start_y = y
                    in_segment = True
                elif not has_content and in_segment:
                    in_segment = False
                    if y - start_y > 10:
                        segments.append((start_y, y))
            if in_segment:
                segments.append((start_y, len(content_mask)))
                
            if len(segments) < 2:
                return results

            pairs = []
            i = 0
            while i < len(segments) - 1:
                h1 = segments[i][1] - segments[i][0]
                h2 = segments[i+1][1] - segments[i+1][0]
                if h1 < 150 and h2 >= 150:
                    pairs.append((segments[i], segments[i+1]))
                    i += 2
                else:
                    i += 1
            
            unknown_counter = 1
            for pair_idx, (header_seg, img_seg) in enumerate(pairs):
                try:
                    pad = 10
                    h_start = max(0, header_seg[0] - pad)
                    h_end = min(img_cv.shape[0], header_seg[1] + pad)
                    i_start = max(0, img_seg[0] - pad)
                    i_end = min(img_cv.shape[0], img_seg[1] + pad)
                    
                    # 1. Segment header row horizontally to find ID blocks with gap tolerance
                    h_row_thresh = thresh[h_start:h_end, :]
                    h_col_sums = np.sum(h_row_thresh, axis=0)
                    h_col_mask = h_col_sums > (255 * 2) 
                    
                    raw_id_segments = []
                    in_h_seg = False
                    sx = 0
                    for x, has_content in enumerate(h_col_mask):
                        if has_content and not in_h_seg:
                            sx = x; in_h_seg = True
                        elif not has_content and in_h_seg:
                            in_h_seg = False
                            raw_id_segments.append((sx, x))
                    if in_h_seg: raw_id_segments.append((sx, len(h_col_mask)))
                    
                    # Merge blocks that are close to each other (e.g. digits of the same ID)
                    id_h_segments = []
                    if raw_id_segments:
                        curr_s, curr_e = raw_id_segments[0]
                        for i in range(1, len(raw_id_segments)):
                            next_s, next_e = raw_id_segments[i]
                            if (next_s - curr_e) < 100: # Max gap between digits
                                curr_e = next_e
                            else:
                                id_h_segments.append((curr_s, curr_e))
                                curr_s, curr_e = next_s, next_e
                        id_h_segments.append((curr_s, curr_e))
                        
                    # 2. OCR each ID block and capture its visual
                    id_list = []
                    for sx_h, ex_h in id_h_segments:
                        sx_pad = max(0, sx_h - 10)
                        ex_pad = min(width, ex_h + 10)
                        
                        # Capture visual ID for the preview
                        id_img_crop = pil_img.crop((sx_pad, h_start, ex_pad, h_end))
                        
                        id_roi = img_gray[h_start:h_end, sx_pad:ex_pad]
                        id_roi_pad = cv2.copyMakeBorder(id_roi, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
                        scaled_id = cv2.resize(id_roi_pad, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                        blur_id = cv2.GaussianBlur(scaled_id, (5, 5), 0)
                        _, thresh_id = cv2.threshold(blur_id, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
                        text = pytesseract.image_to_string(thresh_id, config=custom_config).strip()
                        num = re.sub(r'\D', '', text)
                        if num: id_list.append({'id': num, 'center_x': (sx_h + ex_h) // 2, 'img': id_img_crop})
                    
                    if not id_list:
                        id_list = [{'id': f"unknown_{unknown_counter:03d}", 'center_x': width // 2, 'img': None}]
                        unknown_counter += 1
                        
                    # 3. Segment image row horizontally
                    i_row_thresh = thresh[i_start:i_end, :]
                    col_sums = np.sum(i_row_thresh, axis=0)
                    col_mask = col_sums > (255 * 5)
                    v_segments = []
                    in_v_seg = False
                    start_x = 0
                    for x, has_content in enumerate(col_mask):
                        if has_content and not in_v_seg:
                            start_x = x; in_v_seg = True
                        elif not has_content and in_v_seg:
                            in_v_seg = False
                            if x - start_x > 20: v_segments.append((start_x, x))
                    if in_v_seg: v_segments.append((start_x, len(col_mask)))
                    
                    # 4. Map Images to nearest ID
                    for isx, iex in v_segments:
                        img_center_x = (isx + iex) // 2
                        best_match = min(id_list, key=lambda x: abs(x['center_x'] - img_center_x))
                        extracted_number = best_match['id']
                        header_visual = best_match['img']
                        
                        output_folder = Path(output_base_folder) / extracted_number
                        output_folder.mkdir(parents=True, exist_ok=True)
                        
                        if extracted_number not in id_counters:
                            existing_files = list(output_folder.glob("img_*.jpg"))
                            id_counters[extracted_number] = len(existing_files)
                            
                        x_pad_start = max(0, isx - pad)
                        x_pad_end = min(width, iex + pad)
                        sub_img = pil_img.crop((x_pad_start, i_start, x_pad_end, i_end))
                        
                        # Split thin white line
                        sub_gray = cv2.cvtColor(np.array(sub_img), cv2.COLOR_RGB2GRAY)
                        w_s, h_s = sub_img.size
                        found_split = False
                        
                        crops_to_visualize = []
                        
                        if w_s > 120:
                            s_sums = np.sum(sub_gray, axis=0)
                            s_start = int(w_s * 0.3)
                            s_end = int(w_s * 0.7)
                            c_sums = s_sums[s_start:s_end]
                            bgx_rel = np.argmax(c_sums)
                            bgx = s_start + bgx_rel
                            mv = s_sums[bgx]
                            
                            if mv > (h_s * 230):
                                left = sub_img.crop((0, 0, bgx, h_s))
                                right = sub_img.crop((bgx+1, 0, w_s, h_s))
                                if left.width > 20 and right.width > 20:
                                    for eye in [left, right]:
                                        te = ImageProcessor.trim_whitespace(eye)
                                        id_counters[extracted_number] += 1
                                        te.save(output_folder / f"img_{id_counters[extracted_number]}.jpg", 'JPEG', quality=100)
                                        results['processed'] += 1
                                        crops_to_visualize.append(te)
                                    found_split = True
                                    
                        if not found_split:
                            ts = ImageProcessor.trim_whitespace(sub_img)
                            id_counters[extracted_number] += 1
                            ts.save(output_folder / f"img_{id_counters[extracted_number]}.jpg", 'JPEG', quality=100)
                            results['processed'] += 1
                            crops_to_visualize.append(ts)
                            
                        # Combined visual update (shows both eyes centered)
                        if visual_callback:
                            visual_callback(extracted_number, header_visual, crops_to_visualize)

                except Exception as pair_e:
                    results['errors'].append(str(pair_e))
                    
        except Exception as e:
            results['errors'].append(str(e))
            
        return results

    @staticmethod
    def batch_extract_images(raw_data_folder, output_base_folder, progress_callback=None, visual_callback=None):
        """Batch extract images from JPG files"""
        results = {'total': 0, 'processed': 0, 'candidates': 0, 'errors': []}
        try:
            raw_path = Path(raw_data_folder)
            if not raw_path.exists():
                results['errors'].append(f"Raw data folder not found: {raw_data_folder}")
                return results
                
            image_extensions = {'.jpg', '.jpeg', '.png'}
            image_files = []
            for ext in image_extensions:
                image_files.extend(list(raw_path.rglob(f"*{ext}")))
                image_files.extend(list(raw_path.rglob(f"*{ext.upper()}")))
                
            results['total'] = len(image_files)
            id_counters = {}
            
            for i, img_file in enumerate(image_files):
                if progress_callback:
                    progress_callback(i + 1, results['total'], f"Extracting {img_file.name}...")
                
                try:
                    pil_img = Image.open(img_file).convert("RGB")
                    sub_results = ImageProcessor.extract_from_pil_image(
                        pil_img, output_base_folder, None, visual_callback, id_counters
                    )
                    results['processed'] += sub_results['processed']
                    results['errors'].extend(sub_results['errors'])
                except Exception as e:
                    results['errors'].append(f"Error extracting {img_file.name}: {e}")
            
            results['candidates'] = len(id_counters)
            if progress_callback:
                progress_callback(results['total'], results['total'], "Extraction complete!")
                
        except Exception as e:
            results['errors'].append(str(e))
            
        return results
