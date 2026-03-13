import json
import io
import os
from flask import Flask, render_template, request, send_file
from PyPDF2 import PdfReader
from groq import Groq 
from docxtpl import DocxTemplate

app = Flask(__name__)

# --- CONFIGURACIÓN DE GROQ ---
cliente_groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/generar', methods=['POST'])
def procesar_cv():
    nombre = request.form.get('nombre')
    cargo = request.form.get('cargo')
    experiencia = request.form.get('experiencia')
    archivo_pdf = request.files.get('cv_adjunto')

    if archivo_pdf:
        # 1. LEER PDF
        lector = PdfReader(archivo_pdf)
        texto_extraido = ""
        for pagina in lector.pages:
            texto_extraido += pagina.extract_text()

        print("\n" + "="*40)
        print(f"Enviando el CV de {nombre} a Groq...")
        
        # 2. EL AGENTE DE IA (Modo Sargento)
        mensaje_sistema = "Eres un sistema automático de RRHH. Tu única función es recibir texto y devolver un objeto JSON estrictamente formateado. NUNCA devuelvas texto fuera del JSON."

        prompt_ia = f"""
        Eres un experto en extracción de datos de RRHH. Tu tarea es analizar el texto de un CV y devolverlo estrictamente en formato JSON.

        REGLAS CRÍTICAS PARA HIGHLIGHTS Y SKILLS:
        - "highlights": Extrae EXACTAMENTE 3 logros.
        - "skills": Extrae EXACTAMENTE 3 habilidades. Deben ser palabras sueltas, NUNCA frases.

        ESTRUCTURA JSON OBLIGATORIA:
        {{
            "nombre_completo": "{nombre}",
            "educacion": ["Título - Institución (Fechas)"],
            "experiencia_profesional": [
                {{
                    "cargo": "Nombre del cargo",
                    "empresa": "NOMBRE DE LA EMPRESA",
                    "ubicacion_fechas": "Ciudad, País (Fechas)",
                    "tareas": ["Tarea 1", "Tarea 2"]
                }}
            ],
            "highlights": ["Logro 1", "Logro 2", "Logro 3"],
            "skills": ["Habilidad 1", "Habilidad 2", "Habilidad 3"],
            "idiomas": ["Idioma 1", "Idioma 2"]
        }}

        Reglas de contenido:
        - Si un dato no existe, déjalo en blanco.
        - Extrae la información en español.

        TEXTO BRUTO DEL CV:
        {texto_extraido}
        """

        try:
            # 3. LLAMADA ESTRICTA A GROQ (Aquí está la magia)
            respuesta = cliente_groq.chat.completions.create(
                messages=[
                    {"role": "system", "content": mensaje_sistema},
                    {"role": "user", "content": prompt_ia}
                ],
                model="llama-3.3-70b-versatile", 
                temperature=0.0, # Cero creatividad, solo obedece
                response_format={"type": "json_object"} # Fuerza bruta para que devuelva JSON
            )
            
            texto_respuesta = respuesta.choices[0].message.content
            
            # Convertir texto a JSON (Ya no hace falta limpiar backticks gracias al response_format)
            datos_cv = json.loads(texto_respuesta) 
            print("¡Datos extraídos con precisión militar por Groq!")

            # 4. PREPARAR LOS DATOS EXTRA
            lista_palabras = nombre.split()
            iniciales = "".join([palabra[0].upper() for palabra in lista_palabras])

            diccionario_puestos = {
                "ASSI": "ASSOCIATE",
                "CONS": "CONSULTANT",
                "SR CONS": "SENIOR CONSULTANT",
                "EXP SR CONS": "EXPERIENCE SENIOR CONSULTANT",
                "MNGR": "MANAGER",
                "SR MNGR": "SENIOR MANAGER",
                "SOCIO": "SOCIO"
            }
            puesto_completo = diccionario_puestos.get(cargo, "Puesto no definido")

            contexto_final = {
                "iniciales": iniciales,
                "puesto_abreviado": cargo,
                "puesto_completo": puesto_completo,
                "anios_experiencia": experiencia,
                **datos_cv 
            }

            # 5. INYECTAR EN WORD Y DESCARGAR
            doc = DocxTemplate("plantilla.docx")
            doc.render(contexto_final)
            
            archivo_salida = io.BytesIO()
            doc.save(archivo_salida)
            archivo_salida.seek(0)
            
            nombre_archivo = f"CV_{iniciales}_{puesto_completo.replace(' ', '_')}.docx"
            
            return send_file(
                archivo_salida, 
                as_attachment=True, 
                download_name=nombre_archivo,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        except Exception as e:
            print(f"\nError general: {e}")
            return f"Hubo un error: {e}"
    
    return "No se detectó archivo."

if __name__ == '__main__':
    app.run(debug=True)
