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
    - Semptomları Çin Tıbbı'na göre tanımla (örneğin Qi eksikliği, toprak element eksikliği, Nem birikimi, Karaciğer Yang fazlalığı gibi).
    - Klasik literatüre *atıfta bulunmadan*, bu kavramların anlamını açıkla ve klinik yorum yap.
    - "Akupunktur Noktaları" başlığı altında her bir semptom için özgül noktaları öner, özellikleri ve işlevlerini açıkla.
    - Gerekirse kupa, moxa, elektro-akupunktur gibi tamamlayıcı yöntemler öner.
    Kullanıcıdan gelen bilgiler:
    Semptomlar: {symptoms}
    Muayene Bulguları: {physical}
    Son olarak:
    - ICD-10 tanı kodlarını listele.
    - "Takip Planı" başlığı altında yaşam tarzı, seans sıklığı gibi öneriler sun.
    """

    api_key = os.environ.get("MY_OPENAI_KEY")
    if not api_key:
        raise ValueError("OpenAI API anahtarı bulunamadı. Ortam değişkeni 'MY_OPENAI_KEY' ayarlanmalıdır.")

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
        return f"❌ OpenAI yanıtı alınamadı. Detay: {str(e)}"

def answer_question(question):
    prompt = f"""
    Aşağıdaki soruya detaylı ve eğitici bir yanıt ver.
    - Eğer soru bir akupunktur noktasıysa (örneğin GB20 veya Fengchi gibi), şu başlıkları içeren detaylı açıklama yap:
        1. Anatomik konum
        2. Uygulama derinliği ve açısı
        3. Ana etkileri (örneğin: rüzgar dağıtma, baş ağrısı tedavisi)
        4. Klinik kullanımda hangi hastalıklarda öne çıkar
        5. Modern tıbbi açıklamalarla ilişkisi varsa ekle
    - Eğer genel bir kavramsal soruysa (örneğin Qi nedir?), sadeleştirilmiş ve öğretici bir yanıt ver.
    Soru: {question}
    Cevap:
    """
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
        return f"❌ Açıklama alınamadı: {str(e)}"

def get_image_path(query):
    filename = query.strip().upper() + ".jpg"
    path = f"images/{filename}"
    return path if os.path.exists(path) else None

with gr.Blocks(css="""
    .gr-box { background-color: #f9f9fb; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
    textarea, input { font-size: 17px !important; padding: 14px !important; border-radius: 12px !important; }
    button { font-size: 17px !important; padding: 12px 24px !important; border-radius: 10px !important; background: #3A86FF; color: white; border: none; }
    .gr-image { max-height: 280px; border-radius: 12px; margin-top: 10px; }
    .gr-markdown { font-size: 19px; line-height: 1.7; }
    .gr-textbox { resize: vertical; }
    .gr-file { height: 120px !important; min-height: 80px !important; }
""") as demo:
    gr.Markdown("""## ☯️🪡 **Akupunktur Uzmanı AI**
WHO verileri ve Çin Tıbbı Klasik Kitaplar;'' Huang Di Nei Jing'' ''Ben Cao Gang Mu'' ve diğer 22 kitap ile eğitilmiş donanımlı''Akupunktur Aİ Asistanı', Uygulama sahibine kişiselleştirilmiş öneriler üretir. Klasik bilgilerden esinlenilmiş ancak doğrudan alıntı içermeyen yorumlar sunar.""")

    with gr.Row():
        with gr.Column(scale=1, min_width=400):
            name = gr.Textbox(label="👤 Hasta Adı Soyadı", placeholder="Ad Soyad")
            pid = gr.Textbox(label="🆔 Hasta ID", placeholder="123456")
            symptoms = gr.Textbox(label="🔍 Semptomlar veya Tanı", placeholder="örn: bel ağrısı, baş dönmesi", lines=3)
            physical = gr.Textbox(label="🩺 Muayene Bulguları", placeholder="örn: palpasyonla hassasiyet, hareket kısıtlılığı", lines=3)

        with gr.Column(scale=1, min_width=400):
            output = gr.TextArea(label="📋 Klinik Özet ve Öneriler", lines=25, visible=True)

    def process(name, pid, symptoms, physical):
        try:
            summary = generate_summary(symptoms, physical)
            archive_patient_record(name, pid, symptoms, physical, summary)
            pdf = PDFReport(patient_name=name, patient_id=pid)
            pdf_path = pdf.create_pdf(summary)
            return summary, pdf_path
        except Exception as e:
            return f"❌ İşlem hatası: {str(e)}", None

    submit = gr.Button("🔎 Lütfen Araştır", variant="primary")
    file_output = gr.File(label="📄 İndirilebilir Rapor", visible=True)
    submit.click(process, [name, pid, symptoms, physical], [output, file_output])

    with gr.Accordion("🧠 Soru-Cevap & Mini Açıklama Modülü", open=False):
        with gr.Row():
            with gr.Column(scale=1):
                question_input = gr.Textbox(label="💡 Soru Sor", placeholder="örn: Qi eksikliği nedir?")
                explain_btn = gr.Button("📖 Açıkla")
            with gr.Column(scale=1):
                question_output = gr.Textbox(label="📘 Açıklama", lines=6)
                image_output = gr.Image(label="", type="filepath", visible=False, height=300, show_label=False)

        def explain_with_image(query):
            explanation = answer_question(query)
            image_path = get_image_path(query)
            from gradio import update
            if image_path:
                return explanation, update(value=image_path, visible=True)
            else:
                return explanation, update(visible=False)

        explain_btn.click(fn=explain_with_image, inputs=[question_input], outputs=[question_output, image_output])

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"✅ Uygulama başlatılıyor, port: {port}")
    demo.launch(server_name="0.0.0.0", server_port=port, share=False)





























