import os
import re
import csv
import argparse
from pathlib import Path
from typing import Dict, List, Optional

# --- CONFIGURACIÓN ---
# Puedes cambiar estos valores si tus cabeceras en el CSV son diferentes.
PROJECT_NAME_COL = 'PROJECT_NAME'
EMAIL_COL = 'BISO_TEAM'
# ---------------------

def format_email_for_label(email: str) -> str:
    """
    Formatea un correo electrónico para usarlo como valor de etiqueta en HCL.
    Reemplaza '@teco.com.ar' por '-teco_com_ar'.
    """
    return email.replace("@teco.com.ar", "-teco_com_ar")

def load_project_data(csv_path: Path) -> Optional[Dict[str, str]]:
    """
    Carga los datos del archivo CSV en un diccionario.
    Devuelve un diccionario {project_name: email} o None si hay un error.
    """
    if not csv_path.is_file():
        print(f"❌ Error: El archivo CSV no se encontró en la ruta: {csv_path}")
        return None

    project_data = {}
    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as infile:
            reader = csv.DictReader(infile, delimiter=';')
            # Verifica si las columnas necesarias existen
            if PROJECT_NAME_COL not in reader.fieldnames or EMAIL_COL not in reader.fieldnames:
                print(f"❌ Error: El archivo CSV debe contener las columnas '{PROJECT_NAME_COL}' y '{EMAIL_COL}'.")
                 # LÍNEA DE DIAGNÓSTICO AÑADIDA:
                print(f"   Columnas encontradas por el script: {reader.fieldnames}")
                return None
            
            for row in reader:
                project_name = row[PROJECT_NAME_COL].strip()
                email = row[EMAIL_COL].strip()
                if project_name and email:
                    project_data[project_name] = email
        print(f"✅ Se cargaron {len(project_data)} proyectos desde {csv_path}")
        return project_data
    except Exception as e:
        print(f"❌ Error al leer el archivo CSV: {e}")
        return None

def update_terragrunt_file(file_path: Path, project_name: str, email_to_add: str):
    """
    Actualiza un archivo terragrunt.hcl para añadir la etiqueta 'biso_team'.
    Busca el bloque de 'labels' y añade la nueva etiqueta al final.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        in_labels_block = False
        labels_block_found = False
        # Patrón para encontrar la última etiqueta antes del cierre del bloque '}'
        # Asume que la última línea con una etiqueta tiene un formato como 'key = "value",' o 'key = "value"'
        last_label_pattern = re.compile(r'^\s*([a-zA-Z0-9_-]+)\s*=\s*".*"')

        for i, line in enumerate(lines):
            # Añade la línea actual a la nueva lista
            new_lines.append(line)

            # Detecta el inicio del bloque de etiquetas
            if "labels = {" in line:
                in_labels_block = True
                labels_block_found = True
                continue
            
            # Detecta el final del bloque de etiquetas
            if in_labels_block and line.strip() == "}":
                # La línea anterior era la última etiqueta del bloque.
                # Inserta la nueva etiqueta 'biso_team' antes de la llave de cierre.
                
                # Busca la última línea que era una etiqueta para copiar su sangría
                indentation = "    " # Sangría por defecto
                for j in range(i - 1, 0, -1):
                    if last_label_pattern.match(lines[j]):
                        match = re.match(r'^(\s+)', lines[j])
                        if match:
                            indentation = match.group(1)
                        break

                formatted_email = format_email_for_label(email_to_add)
                biso_team_line = f'{indentation}biso_team                   = "{formatted_email}"\n'
                
                # Inserta la nueva línea en la posición correcta (antes del '}')
                new_lines.insert(-1, biso_team_line)
                
                print(f"    - Insertando etiqueta: biso_team = \"{formatted_email}\"")
                in_labels_block = False # Termina la búsqueda

        if not labels_block_found:
            print(f"    - ⚠️ Advertencia: No se encontró el bloque 'labels = {{...}}' en {file_path}. No se realizaron cambios.")
            return

        # Escribe el contenido modificado de nuevo en el archivo
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
            
        print(f"    - ✅ Archivo actualizado exitosamente.")

    except Exception as e:
        print(f"    - ❌ Error al procesar o escribir en el archivo {file_path}: {e}")

def main(iac_path: Path, project_data: Dict[str, str]):
    """
    Función principal que recorre los archivos y llama a la actualización.
    """
    if not iac_path.is_dir():
        print(f"❌ Error: La ruta '{iac_path}' no es un directorio válido.")
        return

    print(f"\n🚀 Iniciando búsqueda de archivos 'terragrunt.hcl' en: {iac_path}")
    
    # Patrón para encontrar el nombre del proyecto en el archivo HCL
    project_name_pattern = re.compile(r'name\s*=\s*"([^"]+)"')
    files_processed = 0
    files_modified = 0

    # Recorre el árbol de directorios de una manera más eficiente
    for hcl_path in iac_path.glob("**/project/terragrunt.hcl"):
        files_processed += 1
        try:
            content = hcl_path.read_text(encoding='utf-8')
            match = project_name_pattern.search(content)

            if not match:
                continue

            # Extrae el nombre del proyecto del archivo
            current_project_name = match.group(1)

            # Comprueba si este proyecto está en nuestra lista para actualizar
            if current_project_name in project_data:
                print(f"\n🔍 Coincidencia encontrada para el proyecto: '{current_project_name}'")
                print(f"  - Archivo: {hcl_path}")
                email = project_data[current_project_name]
                update_terragrunt_file(hcl_path, current_project_name, email)
                files_modified += 1

        except Exception as e:
            print(f"❌ Error al leer el archivo {hcl_path}: {e}")
            
    print("\n--- RESUMEN ---")
    print(f"📁 Archivos 'terragrunt.hcl' procesados: {files_processed}")
    print(f"✍️ Archivos modificados: {files_modified}")
    print("✨ Proceso completado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Actualiza archivos terragrunt.hcl añadiendo una etiqueta 'biso_team' a partir de un archivo CSV.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Ruta al archivo CSV con las columnas 'PROJECT_NAME' y 'BISO_TEAM'."
    )
    parser.add_argument(
        "--iac-path",
        required=True,
        help="Ruta a la carpeta raíz 'IAC_LIVE' que contiene los proyectos."
    )
    
    args = parser.parse_args()
    
    csv_file_path = Path(args.csv)
    iac_live_path = Path(args.iac_path)
    
    project_info = load_project_data(csv_file_path)
    
    if project_info:
        main(iac_live_path, project_info)