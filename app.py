import json
import io
import os
from flask import Flask, render_template, request, send_file
from PyPDF2 import PdfReader
from groq import Groq 
from docxtpl import DocxTemplate # <-- Librería para el Word

app = Flask(__name__)

# --- CONFIGURACIÓN DE GROQ ---
# Ahora la clave está escondida. El servidor la buscará en sus variables secretas.
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
        
        # 2. EL AGENTE DE IA
        prompt_ia = f"""
        Eres un experto en extracción de datos de RRHH. Tu tarea es analizar el texto de un CV y devolverlo estrictamente en formato JSON plano.

        Sigue estas reglas de formato al pie de la letra:
        1. Formato: Devuelve ÚNICAMENTE el objeto JSON. Está prohibido incluir texto extra, explicaciones o bloques de código markdown (como ```json).
        2. Estructura exacta del JSON:
           - "nombre_completo": "{nombre}"
           - "educacion": (Array de Strings) Cada elemento debe seguir este formato: "[Título educativo] - [Nombre organización educativa] ([fechas])"
           - "experiencia_profesional": (Array de Strings) Cada elemento debe seguir este formato: "[Cargo] - [NOMBRE EMPRESA] - [Ciudad, País] ([fechas])\\n- [Tarea 1]\\n- [Tarea 2]\\n- [Tarea 3]\\n"
           - "highlights": (Array de Strings) Exactamente 3 bullet points con una breve descripción de logros.
           - "skills": (Array de Strings) Exactamente 3 palabras clave o conceptos sin descripción e ignorando los lenguajes de programación.
           - "lenguajes_programacion": (String) Todos los lenguajes dominados en una sola línea separados por comas, sin descripción.
           - "idiomas": (Array de Strings) Solo los idiomas con nivel profesional en una sola línea separados por comas, sin descripción.

        3. Reglas de contenido:
           - Si un dato no existe, déjalo en blanco.
           - Mantén las llaves del JSON en español tal como se indican arriba.
           - Extrae la información del CV en español (excepto las llaves).

        TEXTO BRUTO DEL CV:
        {texto_extraido}
        """

        try:
            # Llamamos a Groq
            respuesta = cliente_groq.chat.completions.create(
                messages=[{"role": "user", "content": prompt_ia}],
                model="llama-3.3-70b-versatile", 
                temperature=0.1 
            )
            
            texto_respuesta = respuesta.choices[0].message.content
            
            # 3. NODO CODE (Convertir texto a JSON)
            texto_limpio = texto_respuesta.replace("```json", "").replace("```", "").strip()
            datos_cv = json.loads(texto_limpio) 
            print("¡Datos extraídos con éxito por Groq!")

            # 4. PREPARAR LOS DATOS EXTRA
            # Iniciales
            lista_palabras = nombre.split()
            iniciales = "".join([palabra[0].upper() for palabra in lista_palabras])

            # Diccionario de convalidación
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

            # Empaquetamos todo
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

            print(f"Enviando archivo: {nombre_archivo}")
            
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
