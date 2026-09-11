import os
import json
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds)

def get_sheet(name):
    sheet_id = os.environ.get("SPREADSHEET_ID")
    return get_client().open_by_key(sheet_id).worksheet(name)

def registrar_usuario(nombre, email, password_hash, telefono, rol="cliente"):
    ws = get_sheet("usuarios")
    records = ws.get_all_records()
    
    for row in records:
        if row.get("email") == email:
            return False
            
    nuevo_id = max([int(r.get("id", 0)) for r in records if str(r.get("id", "")).isdigit()] + [0]) + 1
    ws.append_row([nuevo_id, nombre, email, password_hash, telefono, rol])
    return True

def obtener_usuario_por_email(email):
    records = get_sheet("usuarios").get_all_records()
    for row in records:
        if row.get("email") == email:
            return row
    return None

def obtener_usuario_por_id(user_id):
    records = get_sheet("usuarios").get_all_records()
    for row in records:
        if str(row.get("id")) == str(user_id):
            return row
    return None

def obtener_catalogo():
    return get_sheet("catalogo").get_all_records()

def guardar_pedido(user_id, item_solicitado, cantidad, tipo_servicio, observaciones):
    ws = get_sheet("pedidos")
    records = ws.get_all_records()
    
    nuevo_id = max([int(r.get("id", 0)) for r in records if str(r.get("id", "")).isdigit()] + [0]) + 1
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    ws.append_row([
        nuevo_id, user_id, fecha, item_solicitado, cantidad, 
        tipo_servicio, observaciones, "Recibido en taller", ""
    ])

def obtener_pedidos_usuario(user_id):
    records = get_sheet("pedidos").get_all_records()
    return [r for r in records if str(r.get("user_id")) == str(user_id)]

def obtener_todos_pedidos():
    pedidos = get_sheet("pedidos").get_all_records()
    usuarios = get_sheet("usuarios").get_all_records()
    
    df_pedidos = pd.DataFrame(pedidos)
    df_usuarios = pd.DataFrame(usuarios)
    
    if df_pedidos.empty or df_usuarios.empty:
        return []
        
    merged = pd.merge(df_pedidos, df_usuarios, left_on='user_id', right_on='id', suffixes=('', '_user'))
    merged['id'] = pd.to_numeric(merged['id'], errors='coerce').fillna(0).astype(int)
    merged = merged.sort_values(by='id', ascending=False)
    
    return merged.to_dict('records')

def actualizar_pedido(pedido_id, nuevo_estado, link_descarga):
    ws = get_sheet("pedidos")
    data = ws.get_all_values()
    if not data:
        return
        
    headers = data[0]
    idx_id = headers.index("id")
    idx_estado = headers.index("estado")
    idx_link = headers.index("link_descarga")
    
    for i, row in enumerate(data[1:], start=2):
        if str(row[idx_id]) == str(pedido_id):
            ws.update_cell(i, idx_estado + 1, nuevo_estado)
            if link_descarga:
                ws.update_cell(i, idx_link + 1, link_descarga)
            break
