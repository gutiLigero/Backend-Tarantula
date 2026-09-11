import os
from datetime import datetime, timedelta
from typing import List, Optional

import bcrypt
import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

import database

app = FastAPI(title="Tarántula Corp API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "LUMON_INDUSTRIES_MACRODATA_REFINEMENT_SECRET")
ALGORITHM = "HS256"
security = HTTPBearer()

class UserRegister(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    telefono: Optional[str] = ""

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class LabOrderCreate(BaseModel):
    tipo_servicio: str
    cantidad: int
    observaciones: Optional[str] = ""

class CartItem(BaseModel):
    id: int
    nombre: str
    cantidad: int
    precio: float

class CartOrderCreate(BaseModel):
    items: List[CartItem]

class OrderStatusUpdate(BaseModel):
    nuevo_estado: str
    link_descarga: Optional[str] = ""

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = database.obtener_usuario_por_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@app.post("/auth/register")
def register(user_data: UserRegister):
    hashed_pw = bcrypt.hashpw(user_data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    rol = "admin" if "admin@tarantula.com" in user_data.email else "cliente"
    
    success = database.registrar_usuario(
        user_data.nombre, user_data.email, hashed_pw, user_data.telefono, rol
    )
    if not success:
        raise HTTPException(status_code=400, detail="Employee designation already registered.")
    
    return {"message": "Orientation complete. Access granted."}

@app.post("/auth/login")
def login(credentials: UserLogin):
    user = database.obtener_usuario_por_email(credentials.email)
    if not user or not bcrypt.checkpw(credentials.password.encode("utf-8"), str(user["password"]).encode("utf-8")):
        raise HTTPException(status_code=400, detail="Authentication failed. Invalid credentials.")

    token = jwt.encode(
        {"sub": str(user["id"]), "exp": datetime.utcnow() + timedelta(days=7)},
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "nombre": user["nombre"], "email": user["email"], "rol": user["rol"]}
    }

@app.get("/catalog")
def get_catalog():
    items = database.obtener_catalogo()
    return [i for i in items if str(i.get("nombre_producto", "")).strip()]

@app.post("/orders/lab")
def create_lab_order(order: LabOrderCreate, user: dict = Depends(get_current_user)):
    database.guardar_pedido(
        user["id"],
        f"Revelado ({order.tipo_servicio})",
        order.cantidad,
        "Lab Service",
        order.observaciones
    )
    return {"message": "Request submitted to laboratory."}

@app.post("/orders/cart")
def create_cart_order(order: CartOrderCreate, user: dict = Depends(get_current_user)):
    for item in order.items:
        database.guardar_pedido(
            user["id"],
            item.nombre,
            item.cantidad,
            "Store Purchase",
            "WhatsApp Order"
        )
    return {"message": "Requisition recorded."}

@app.get("/orders/my-orders")
def get_user_orders(user: dict = Depends(get_current_user)):
    return database.obtener_pedidos_usuario(user["id"])

@app.get("/admin/orders")
def get_all_orders(user: dict = Depends(get_current_user)):
    if user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized.")
    
    pedidos = database.obtener_todos_pedidos()
    resultados = []
    for p in pedidos:
        resultados.append({
            "id": p.get("id"),
            "nombre": p.get("nombre"),
            "email": p.get("email"),
            "telefono": p.get("telefono"),
            "fecha": str(p.get("fecha", "")),
            "item_solicitado": p.get("item_solicitado"),
            "cantidad": p.get("cantidad"),
            "tipo_servicio": p.get("tipo_servicio"),
            "estado": p.get("estado"),
            "link_descarga": p.get("link_descarga")
        })
    return resultados

@app.patch("/admin/orders/{order_id}")
def update_order_status(order_id: int, payload: OrderStatusUpdate, user: dict = Depends(get_current_user)):
    if user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized.")
    
    database.actualizar_pedido(order_id, payload.nuevo_estado, payload.link_descarga)
    return {"message": "Directive updated."}
