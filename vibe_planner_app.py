
# Ł Orkun Temeltaş - Haftalık Çalışma Planı Arayüzü (Colab uyumlu)
# Tam işlevli sürüm (arama, logo, ZIP, çoklu öğrenci destekli)

import streamlit as st
import os
import pdfplumber
import datetime
import json
import zipfile
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from collections import namedtuple
import re # Add this import statement for regular expressions

MAX_WEEKLY_KAZANIM = 6
OUTPUT_DIR = "output_plans"
HISTORY_FILE = "kazanım_history.json"
Kazanım = namedtuple("Kazanım", ["ders", "kazanım", "yüzde"])

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_pdf(pdf_bytes):
    students = []
    with pdfplumber.open(pdf_bytes) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                st.warning(f"Sayfa {page_idx + 1} boş görünüyor. İşlenemiyor.")
                print(f"DEBUG: Sayfa {page_idx + 1} boş görünüyor. İşlenemiyor.") # Added debug print
                continue

            lines = [l.strip() for l in text.split("
") if l.strip()]

            # Debug: Print extracted raw text and lines for the page - ACTIVATED
            print(f"DEBUG: --- Sayfa {page_idx + 1} --- Aday Metin:
{text}
")
            print(f"DEBUG: --- Sayfa {page_idx + 1} --- Ayrışturılmış Satırlar:
{lines}
")

            if not lines:
                st.warning(f"Sayfa {page_idx + 1} için okunabilir satır bulunamadı.")
                print(f"DEBUG: Sayfa {page_idx + 1} için okunabilir satır bulunamadı.") # Added debug print
                continue

            name_line = lines[0]
            if "(" in name_line and ")" in name_line:
                student_name = name_line.split("(")[0].strip()
                student_class = name_line.split("(")[1].replace(")", "").strip()
            else:
                student_name = name_line.strip()
                student_class = "Bilinmiyor"

            kazanımlar = []
            for line in lines[1:]:
                if "%" in line:
                    try:
                        ders = ""
                        # Adjusting keyword check to be more flexible, using 'in' for case-insensitivity and partial matches
                        if "matematik" in line.lower():
                            ders = "Matematik"
                        elif "türkçe" in line.lower():
                            ders = "Türkçe"
                        elif "fen" in line.lower():
                            ders = "Fen Bilimleri"
                        elif "sosyal" in line.lower():
                            ders = "Sosyal Bilgiler"
                        else:
                            # Debug: Log lines that contain '%' but don't match a recognized subject
                            print(f"DEBUG: Tanınmayan ders içeren satır (yüzde var): {line}")
                            continue

                        parts = line.split("%")
                        yuzde = int(parts[-1].strip())

                        # Find the start of the kazanım text after the subject
                        subject_index = line.lower().find(ders.lower())
                        if subject_index != -1:
                            kazanım_raw_text = line[subject_index + len(ders):parts[0].rfind('%')].strip() if parts[0].rfind('%') != -1 else line[subject_index + len(ders):].strip()
                        else:
                            kazanım_raw_text = parts[0].strip() # Fallback if subject not found explicitly

                        # Clean up any problematic PDF internal references like /PXXX or /'PXXX'
                        kazanım_text = re.sub(r"/'?P\d+'?", '', kazanım_raw_text).strip()
                        kazanım_text = re.sub(r"\s+", " ", kazanım_text).strip() # Normalize whitespace

                        kazanımlar.append({"ders": ders, "kazanım": kazanım_text, "yüzde": yuzde})
                    except Exception as e:
                        # Debug: Log parsing errors for kazanım lines
                        print(f"DEBUG: Kazanım satırı ayrışturılırken hata oluştu: {line} - Hata: {e}")
                        continue
            students.append({"isim": student_name, "sınıf": student_class, "kazanımlar": kazanımlar})

            # Debug: Print student and their extracted kazanımlar
            print(f"DEBUG: İşlenen ğrenci: {student_name} ({student_class}) - Kazanım Sayısı: {len(kazanımlar)}")
            for k in kazanımlar:
                print(f"  - Ders: {k['ders']}, Kazanım: {k['kazanım']}, Yüzde: {k['yüzde']}")

    if not students:
        st.error("PDF'den hiçbir öğrenci bilgisi veya kazanım çıkarılamadı. Lütfen PDF formatını kontrol edin.")
        print("DEBUG: PDF'den hiçbir öğrenci bilgisi veya kazanım çıkarılamadı.") # Added debug print

    return students

def get_activity_text(yuzde, second_time=False):
    if yuzde <= 50:
        if second_time:
            return "Ek kaynaklarındaki ilgili kazanım/konu ile ilgili bir test çöz. (10 Soru)"
        return "Vitamin online platformundan konu tekrarı videoları izle. Platformdaki etkinlikleri tamamla."
    if 51 <= yuzde <= 70:
        return "Vitamin online platformundaki konu tekrarı videolarını izle. Ek kaynaklarındaki ilgili kazanım/konu ile ilgili bir test çöz. (10 Soru). Hatalı sorularını defterine yaz."
    if 71 <= yuzde <= 85:
        return "Ek kaynaklarındaki ilgili kazanım/konu ile ilgili bir test çöz. (10 Soru). Yeni nesil 5 soru çöz. Hatalı sorularını defterine yaz."
    if 86 <= yuzde <= 99:
        return "Ek kaynaklarındaki ilgili kazanım/konu ile ilgili bir test çöz. (10 Soru). Yeni nesil 5 soru çöz. Hatalı sorularını defterine yaz."
    if yuzde == 100:
        return "Kendi belirleyeceğſ in konu ile ilgili 1 test çöz. Ardından yeni nesil 5 soru çöz."
    return ""

def build_plan(kazanımlar, student_id, history):
    today = datetime.date.today()
    student_hist = history.get(student_id, {})
    plan_slots = {"Pazartesi": [], "Salı": [], "Çarşamba": [], "Perşembe": []}
    kazanımlar.sort(key=lambda x: x["yüzde"])
    math_count = turkce_count = fen_count = sosyal_count = total = 0
    for k in kazanımlar:
        if total >= MAX_WEEKLY_KAZANIM:
            break
        d = k["ders"].lower()
        if "matematik" in d:
            if math_count < 2:
                if len(plan_slots["Pazartesi"]) < 1:
                    plan_slots["Pazartesi"].append(k)
                elif len(plan_slots["Perşembe"]) < 1:
                    plan_slots["Perşembe"].append(k)
                math_count += 1
                total += 1
        elif "türkçe" in d:
            if turkce_count < 2 and len(plan_slots["Salı"]) < 2:
                plan_slots["Salı"].append(k)
                turkce_count += 1
                total += 1
        elif "fen" in d:
            if fen_count < 2 and len(plan_slots["Çarşamba"]) < 2:
                plan_slots["Çarşamba"].append(k)
                fen_count += 1
                total += 1
        elif "sosyal" in d:
            if sosyal_count < 2 and len(plan_slots["Çarşamba"]) < 2:
                plan_slots["Çarşamba"].append(k)
                sosyal_count += 1
                total += 1
    plan_list = []
    for day in ["Pazartesi", "Salı", "Çarşamba", "Perşembe"]:
        for e in plan_slots[day]:
            second_time = e["kazanım"] in student_hist
            activity = get_activity_text(e["yüzde"], second_time)
            plan_list.append({"gün": day, "ders": e["ders"], "kazanım": e["kazanım"], "yüzde": e["yüzde"], "etkinlik": activity})
    plan_list.append({"gün": "Cuma", "ders": "Tüm Dersler", "kazanım": "Hafta boyunca çalış madığın tüm kazanımlar", "yüzde": "-", "etkinlik": "Hafta boyunca çalış madığın tüm kazanımlardan 2’ş er yeni nesil soru çöz."
})
    today_str = today.isoformat()
    for p in plan_list:
        if p["kazanım"]:
            student_hist[p["kazanım"]] = today_str
    history[student_id] = student_hist
    return plan_list, history

def create_pdf(student_name, student_class, plan_list, logo_path=None):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"{student_name.replace(' ', '_')}_{student_class.replace('/', '')}_Plan.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    if logo_path:
        try:
            logo = ImageReader(logo_path)
            c.drawImage(logo, 25 * mm, height - 35 * mm, width=25 * mm, height=25 * mm, mask='auto')
        except Exception:
            pass
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 30 * mm, f"{student_name} ({student_class}) – 1. Haftalık Çalışma Planı (Güncel)")
    c.line(20 * mm, height - 35 * mm, width - 20 * mm, height - 35 * mm)
    start_y = height - 45 * mm
    headers = ["Gün", "Ders", "Kazanım", "Baş arı %", "Çalışma Türü"]
    x_pos = [20 * mm, 45 * mm, 85 * mm, 145 * mm, 170 * mm]
    c.setFont("Helvetica-Bold", 9)
    for i, h in enumerate(headers):
        c.drawString(x_pos[i], start_y, h)
    y = start_y - 8 * mm
    line_height = 8 * mm
    c.setFont("Helvetica", 9)
    for item in plan_list:
        if y < 25 * mm:
            c.showPage()
            y = height - 30 * mm
        c.drawString(x_pos[0], y, item["gün"])
        c.drawString(x_pos[1], y, item["ders"])
        c.drawString(x_pos[2], y, item["kazanım"])
        c.drawString(x_pos[3], y, str(item["yüzde"]))
        text = c.beginText(x_pos[4], y)
        text.setFont("Helvetica", 8)
        desc = item["etkinlik"]
        while len(desc) > 45:
            cut = desc[:45]
            last_space = cut.rfind(" ")
            if last_space != -1:
                cut = desc[:last_space]
                desc = desc[last_space + 1:]
            else:
                desc = desc[45:]
            text.textLine(cut)
        text.textLine(desc)
        c.drawText(text)
        y -= line_height
    c.save()
    return filename

st.set_page_config(page_title="Haftalık Çalışma Planı", page_icon="Ł", layout="wide")
st.title("Ł Haftalık Kazanım Takip ve Çalışma Planı Oluşturucu")

logo_file = st.file_uploader("Okul logosunu yükleyin (isteğ e bağ lı)", type=["png", "jpg", "jpeg"])
uploaded_file = st.file_uploader("Sınav Sonuç PDF Dosyasını Yükleyin", type=["pdf"])

if uploaded_file:
    with st.spinner("PDF analiz ediliyor..."):
        students = parse_pdf(uploaded_file)
        history = load_history()
        outputs = []
        for s in students:
            if not s["kazanımlar"]:
                print(f"DEBUG: {s['isim']} ({s['sınıf']}) için hiç kazanım bulunamadı. Plan oluşturulmuyor.")
                continue
            student_id = f"{s['isim'].replace(' ', '_')}_{s['s['sınıf']}"
            plan_list, history = build_plan(s["kazanımlar"], student_id, history)
            logo_path = BytesIO(logo_file.read()) if logo_file else None
            pdf_path = create_pdf(s["isim"], s["sınıf"], plan_list, logo_path)
            outputs.append(pdf_path)
        save_history(history)

    if outputs:
        st.success(f"ł {len(outputs)} öğrenci için plan oluşturuldu!")
        student_names = [os.path.basename(out).replace("_Plan.pdf", "").replace("_", " ") for out in outputs]
        search_query = st.text_input("ł Bir öğrenci arayın (förneğ in 'Demir', '4A'):")
        filtered_outputs = [(n, o) for n, o in zip(student_names, outputs) if search_query.strip().lower() in n.lower()] or list(zip(student_names, outputs))
        for name, out in filtered_outputs:
            with open(out, "rb") as f:
                st.download_button(f"ł {name} - Planı indir", f, file_name=os.path.basename(out), mime="application/pdf")
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for fpath in outputs:
                zipf.write(fpath, os.path.basename(fpath))
        zip_buffer.seek(0)
        st.download_button("ł Tüm planları ZIP olarak indir", zip_buffer, file_name="Tum_Planlar.zip", mime="application/zip")
    else:
        st.warning("Hiçbir öğrenci için plan oluşturulamadı. Lütfen Colab çıktısını kontrol edin.")
