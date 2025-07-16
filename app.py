import gradio as gr
import openai
from fpdf import FPDF
from datetime import datetime
import os
import re
import qrcode
from io import BytesIO
import json

# PDF rapor çıktısı için
class PDFReport(FPDF):
    def __init__(self, patient_name="", patient_id="", archive_link=""):
        super().__init__()
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.archive_link = archive_link

    def header(self):
        self.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True)
        self.set_font("DejaVu", size=16)
        self.cell(0, 10, "Akupunktur Klinik Raporu", ln=True, align='C')
        self.set_font("DejaVu", size=10)
        self.cell(0, 10, f"Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, align='R')
        if self.patient_name or self.patient_id:
            self.cell(0, 10, f"Hasta: {self.patient_name} | ID: {self.patient_id}", ln=True, align='L')
        self.ln(5)
        if self.archive_link:
            qr = qrcode.make(self.archive_link)
            buffer = BytesIO()
            qr.save(buffer)
            buffer.seek(0)
            self.image(buffer, x=170, y=10, w=25)

    def body(self, summary):
        self.set_font("DejaVu", size=11)
        self.ln(5)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 8, f"Hasta Adı Soyadı: {self.patient_name}\nHasta ID: {self.patient_id}")
        self.ln(3)
        self.set_text_color(0, 0, 0)
        self.set_font("DejaVu", size=12)
        lines = summary.split('\n')
        for line in lines:
            if line.strip():
                clean = re.sub(r"<[^>]+>", "", line)
                try:
                    self.multi_cell(0, 10, clean)
                except Exception as e:
                    self.multi_cell(0, 10, f"[Yazılamadı: {str(e)}]")
            else:
                self.ln(3)

    def create_pdf(self, summary, filename=f"/tmp/akupunktur_raporu.pdf"):
        self.add_page()
        self.body(summary)
        self.output(filename, "F")
        return filename

def archive_patient_record(name, pid, symptoms, physical, summary):
    record = {
        "ad": name,
        "id": pid,
        "semptomlar": symptoms,
        "muayene": physical,
        "ozet": summary,
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    archive_file = "hasta_gecmisi.json"
    if os.path.exists(archive_file):
        with open(archive_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []
    data.append(record)
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def generate_summary(symptoms, physical):
    prompt = f"""
    Aşağıdaki hasta bilgilerine dayanarak Çin Tıbbı prensiplerine göre bir değerlendirme yap:
    - Semptomları Çin Tıbbı'na göre tanımla
    - "Akupunktur Noktaları" başlığı altında her bir semptom için özgül noktaları öner
    - Gerekirse tamamlayıcı yöntemler öner
    - ICD-10 tanı kodlarını ve "Takip Planı"nı ver
    Kullanıcıdan gelen bilgiler:
    Semptomlar: {symptoms}
    Muayene Bulguları: {physical}
    """

    api_key = os.environ.get("MY_OPENAI_KEY")
    if not api_key:
        raise ValueError("OpenAI API anahtarı eksik. 'MY_OPENAI_KEY' ortam değişkenini ayarlayın.")

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Sen deneyimli bir akupunktur uzmanı yardımcı AI sistemisin."},
                {"role": "user", "content": prompt},
            ]
        )
        text = response.choices[0].message.content
        return re.sub(r"```html[\s\S]*?```", "", text)
    except Exception as e:
        return f"OpenAI hatası: {str(e)}"

def answer_question(question):
    prompt = f"Soru: {question}\nCevap:"
    try:
        client = openai.OpenAI(api_key=os.environ.get("MY_OPENAI_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Sen geleneksel Çin Tıbbı konusunda bilgi veren bir öğretici AI asistansın."},
                {"role": "user", "content": prompt},
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Açıklama hatası: {str(e)}"

def get_image_path(query):
    filename = query.strip().upper() + ".jpg"
    path = f"images/{filename}"
    return path if os.path.exists(path) else None

def explain_with_image(query):
    from gradio import update
    explanation = answer_question(query)
    image_path = get_image_path(query)
    if image_path:
        return explanation, update(value=image_path, visible=True)
    else:
        return explanation, update(visible=False)

def process(name, pid, symptoms, physical):
    try:
        summary = generate_summary(symptoms, physical)
        archive_patient_record(name, pid, symptoms, physical, summary)
        pdf = PDFReport(patient_name=name, patient_id=pid)
        pdf_path = pdf.create_pdf(summary)
        return summary, pdf_path
    except Exception as e:
        return f"Hata: {str(e)}", None

demo = gr.Blocks()
with demo:
    gr.Markdown("""
## ☯️ Akupunktur AI Asistanı

Semptomları girin, Çin Tıbbı prensiplerine göre değerlendirme ve tedavi önerisi alın.
""")































