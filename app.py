from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer, Boolean, JSON, BigInteger, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import time

# Configuração do PostgreSQL (Neon)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@ep-cool-darkness-123.us-east-2.aws.neon.tech/dbname?sslmode=require")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# TABELAS DO BANCO DE DADOS
# ==========================================
class DBUser(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    cpf = Column(String)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    endereco = Column(String, nullable=True)
    cidade = Column(String, nullable=True)
    uf = Column(String, nullable=True)
    telefone = Column(String, nullable=True)
    role = Column(String, default="student")
    status = Column(String, default="pending")
    progress = Column(JSON, default=list) # IDs dos módulos concluídos
    examScore = Column(Integer, nullable=True)
    examPassed = Column(Boolean, default=False)
    examAnswers = Column(JSON, default=list)
    createdAt = Column(BigInteger)

class DBModule(Base):
    __tablename__ = "modules"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    desc = Column(String, nullable=True)
    videoUrl = Column(String, nullable=True)
    slidePath = Column(String, nullable=True)
    compPath = Column(String, nullable=True)
    glossary = Column(JSON, default=list)
    isExam = Column(Boolean, default=False)

class DBExamQuestion(Base):
    __tablename__ = "exam_questions"
    id = Column(Integer, primary_key=True, index=True)
    q = Column(String)
    options = Column(JSON, default=list)
    ans = Column(Integer)

class DBQA(Base):
    __tablename__ = "qa_forum"
    id = Column(String, primary_key=True, index=True)
    moduleId = Column(Integer)
    studentId = Column(String)
    questionText = Column(Text)
    replyText = Column(Text, nullable=True)
    status = Column(String, default="pending")

class DBCertificate(Base):
    __tablename__ = "certificates"
    id = Column(String, primary_key=True, index=True)
    studentId = Column(String)
    status = Column(String, default="pending")
    pdfData = Column(Text, nullable=True)
    isAvailable = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="GeoAgreste API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite acesso de qualquer frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# SCHEMAS (Pydantic)
# ==========================================
class UserAuth(BaseModel):
    email: str
    password: str

class UserCreate(UserAuth):
    name: str
    cpf: str
    endereco: str
    cidade: str
    uf: str
    telefone: str

class UserUpdate(BaseModel):
    email: str
    telefone: str
    endereco: str
    cidade: str
    uf: str

class ModuleData(BaseModel):
    id: Optional[int] = None
    title: str
    desc: str
    videoUrl: str
    slidePath: str
    compPath: str
    glossary: list
    isExam: bool

class ExamSubmit(BaseModel):
    answers: list
    score: int
    passed: bool

class QACreate(BaseModel):
    moduleId: int
    studentId: str
    questionText: str

class QAReply(BaseModel):
    replyText: str

# ==========================================
# ROTAS DE AUTENTICAÇÃO E USUÁRIOS
# ==========================================
@app.post("/auth/login")
def login(req: UserAuth, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.email == req.email, DBUser.password == req.password).first()
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    
    # Cria a diretoria padrão se não existir (apenas para garantir o acesso admin)
    if req.email == "admin" and not user:
        pass # Apenas ilustrativo, a rotina real de seed fica melhor em /init
    
    return user

@app.post("/auth/register")
def register(req: UserCreate, db: Session = Depends(get_db)):
    if db.query(DBUser).filter(DBUser.email == req.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")
    
    new_user = DBUser(
        id=f"u_{int(time.time() * 1000)}",
        name=req.name, cpf=req.cpf, email=req.email, password=req.password,
        endereco=req.endereco, cidade=req.cidade, uf=req.uf, telefone=req.telefone,
        role="student", status="pending", createdAt=int(time.time() * 1000)
    )
    db.add(new_user)
    db.commit()
    return {"message": "Sucesso"}

@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    return db.query(DBUser).all()

@app.put("/users/{user_id}/status")
def update_user_status(user_id: str, status: str, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if user:
        user.status = status
        db.commit()
    return {"message": "Status atualizado"}

@app.put("/users/{user_id}/profile")
def update_profile(user_id: str, data: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if user:
        user.email = data.email
        user.telefone = data.telefone
        user.endereco = data.endereco
        user.cidade = data.cidade
        user.uf = data.uf
        db.commit()
    return {"message": "Perfil atualizado"}

@app.put("/users/{user_id}/progress")
def update_progress(user_id: str, module_id: int, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if user:
        prog = list(user.progress)
        if module_id not in prog:
            prog.append(module_id)
            user.progress = prog
            db.commit()
    return {"message": "Progresso atualizado", "progress": user.progress}

@app.put("/users/{user_id}/exam")
def submit_user_exam(user_id: str, data: ExamSubmit, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if user:
        user.examScore = data.score
        user.examPassed = data.passed
        user.examAnswers = data.answers
        db.commit()
    return {"message": "Prova registrada"}

@app.delete("/users/{user_id}/exam")
def reset_user_exam(user_id: str, db: Session = Depends(get_db)):
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if user:
        user.examScore = None
        user.examPassed = False
        user.examAnswers = []
        db.commit()
    return {"message": "Prova resetada"}

# ==========================================
# ROTAS DE MÓDULOS
# ==========================================
@app.get("/modules")
def get_modules(db: Session = Depends(get_db)):
    return db.query(DBModule).all()

@app.post("/modules")
def save_module(data: ModuleData, db: Session = Depends(get_db)):
    if data.id:
        mod = db.query(DBModule).filter(DBModule.id == data.id).first()
        if mod:
            mod.title = data.title
            mod.desc = data.desc
            mod.videoUrl = data.videoUrl
            mod.slidePath = data.slidePath
            mod.compPath = data.compPath
            mod.glossary = data.glossary
            mod.isExam = data.isExam
    else:
        new_mod = DBModule(
            title=data.title, desc=data.desc, videoUrl=data.videoUrl,
            slidePath=data.slidePath, compPath=data.compPath,
            glossary=data.glossary, isExam=data.isExam
        )
        db.add(new_mod)
    db.commit()
    return {"message": "Aula salva"}

@app.delete("/modules/{module_id}")
def delete_module(module_id: int, db: Session = Depends(get_db)):
    db.query(DBModule).filter(DBModule.id == module_id).delete()
    db.commit()
    return {"message": "Aula apagada"}

# ==========================================
# ROTAS DA PROVA / EXAME
# ==========================================
@app.get("/exam")
def get_exam(db: Session = Depends(get_db)):
    return db.query(DBExamQuestion).all()

@app.post("/exam")
def replace_exam(questions: List[dict], db: Session = Depends(get_db)):
    db.query(DBExamQuestion).delete()
    for q in questions:
        new_q = DBExamQuestion(q=q['q'], options=q['options'], ans=q['ans'])
        db.add(new_q)
    db.commit()
    return {"message": "Banco de questões atualizado"}

@app.delete("/exam")
def clear_exam(db: Session = Depends(get_db)):
    db.query(DBExamQuestion).delete()
    db.commit()
    return {"message": "Banco apagado"}

# ==========================================
# ROTAS FÓRUM (QA) E CERTIFICADOS
# ==========================================
@app.get("/qa")
def get_all_qa(db: Session = Depends(get_db)):
    return db.query(DBQA).all()

@app.post("/qa")
def create_qa(data: QACreate, db: Session = Depends(get_db)):
    new_qa = DBQA(
        id=f"q_{int(time.time() * 1000)}",
        moduleId=data.moduleId,
        studentId=data.studentId,
        questionText=data.questionText
    )
    db.add(new_qa)
    db.commit()
    return {"message": "Dúvida enviada"}

@app.put("/qa/{qa_id}/reply")
def reply_qa(qa_id: str, data: QAReply, db: Session = Depends(get_db)):
    qa = db.query(DBQA).filter(DBQA.id == qa_id).first()
    if qa:
        qa.replyText = data.replyText
        qa.status = "answered"
        db.commit()
    return {"message": "Respondido"}

@app.get("/certs")
def get_certs(db: Session = Depends(get_db)):
    return db.query(DBCertificate).all()

@app.post("/certs")
def request_cert(studentId: str, db: Session = Depends(get_db)):
    new_cert = DBCertificate(id=f"cert_{int(time.time() * 1000)}", studentId=studentId)
    db.add(new_cert)
    db.commit()
    return {"message": "Certificado solicitado"}

@app.put("/certs/{cert_id}/status")
def update_cert_status(cert_id: str, status: str, db: Session = Depends(get_db)):
    cert = db.query(DBCertificate).filter(DBCertificate.id == cert_id).first()
    if cert:
        cert.status = status
        db.commit()
    return {"message": "Status atualizado"}

@app.put("/certs/{cert_id}/pdf")
def upload_cert_pdf(cert_id: str, data: dict, db: Session = Depends(get_db)):
    cert = db.query(DBCertificate).filter(DBCertificate.id == cert_id).first()
    if cert:
        cert.pdfData = data.get("pdfData")
        cert.isAvailable = data.get("isAvailable", False)
        db.commit()
    return {"message": "PDF salvo"}

# Rota para criar o usuário Admin inicial caso o banco esteja vazio
@app.post("/init-admin")
def init_admin(db: Session = Depends(get_db)):
    if not db.query(DBUser).filter(DBUser.email == "admin").first():
        admin = DBUser(id="u_admin", name="Diretoria Téc", email="admin", password="admin", role="admin", status="approved", createdAt=int(time.time() * 1000))
        db.add(admin)
        db.commit()
    return {"message": "Admin garantido"}