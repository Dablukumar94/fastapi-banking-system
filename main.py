from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from datetime import datetime, timedelta
from starlette.middleware.sessions import SessionMiddleware
from models import UserInfo, Transaction
from sqlalchemy.orm import Session
from database import Base, engine, SessionLocal
import uvicorn
import random
import string

# ---------------- APP SETUP ----------------
app = FastAPI()


app.add_middleware(
    SessionMiddleware,
    secret_key=f"super-secret-key",
    max_age=60 * 10 # 10 minutes
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
Base.metadata.create_all(engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------- TEMP DATABASE ----------------
# users_db = {}      # user auth
user_data = {}     # transaction history

# ---------------- HELPERS ----------------
def generate_captcha():
    a = random.randint(1, 99)
    b = random.randint(1, 99)
    question = f"{a} + {b}"
    answer = str(a + b)
    return question, answer


def current_datetime():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)

def login_required(request: Request):
    return "user" in request.session


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- ROUTES ----------------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request}
    )

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    question, answer = generate_captcha()
    request.session["captcha_answer"] = answer

    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "captcha_question": question
        }
    )


@app.post("/register", response_class=HTMLResponse)
async def register_user(
    request: Request,
    firstname: str = Form(...),
    lastname: str = Form(...),
    emailid: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    captcha_input: str = Form(...),
    db: Session = Depends(get_db)
):
    captcha_answer = request.session.get("captcha_answer")

    # ❌ captcha mismatch
    if not captcha_answer or captcha_input.strip() != captcha_answer:
        question, answer = generate_captcha()
        request.session["captcha_answer"] = answer

        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Invalid captcha",
                "captcha_question": question
            }
        )

    # ❌ username exists
    user = db.query(UserInfo).filter(UserInfo.username == username).first()
    if user:
        question, answer = generate_captcha()
        request.session["captcha_answer"] = answer

        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "error": "Username already exists",
                "captcha_question": question
            }
        )

    # ✅ create user
    new_user = UserInfo(
        firstname=firstname,
        lastname=lastname,
        email=emailid,
        username=username,
        password=hash_password(password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # ✅ clear captcha after success
    request.session.pop("captcha_answer", None)

    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "success": "Registration successful! Please login."
        }
    )

# ---------------- LOGIN ----------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    question, answer = generate_captcha()
    request.session["captcha_answer"] = answer

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "captcha_question":question}
    )

@app.post("/login", response_class=HTMLResponse)
async def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    captcha_input = Form(...),
    db: Session=Depends(get_db)
):
    captcha_answer = request.session.get("captcha_answer")
    # ❌ captcha mismatch
    if not captcha_answer or captcha_input.strip() != captcha_answer:
        question, answer = generate_captcha()
        request.session["captcha_answer"] = answer

        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid captcha",
                "captcha_question": question
            }
        )

    user = db.query(UserInfo).filter(UserInfo.username == username).first()

    if not user or not verify_password(password, user.password):
        question, answer = generate_captcha()
        request.session["captcha_answer"] = answer
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password", "captcha_question": question}
        )

    request.session["user"] = username
    return RedirectResponse("/", status_code=303)


# ------------- FORGOR PASSWORD --------------
@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password(request: Request):
    question, answer = generate_captcha()
    request.session["captcha_answer"] = answer
    
    return templates.TemplateResponse(
        "forgot_password.html",
        {"request": request, "captcha_question": question}
    )

@app.post("/forgot-password")
async def forgot_password_post(
    request: Request,
    username: str = Form(...),
    new_password: str = Form(...),
    captcha_input = Form(...),
    db: Session = Depends(get_db)
):
    captcha_answer = request.session.get("captcha_answer")
    # ❌ captcha mismatch
    question, answer = generate_captcha()
    if not captcha_answer or captcha_input.strip() != captcha_answer:
        request.session["captcha_answer"] = answer
        return templates.TemplateResponse(
            "forgot_password.html",
            {
                "request": request,
                "error": "Invalid captcha",
                "captcha_question": question
            }
        )

    user = db.query(UserInfo).filter(UserInfo.username == username).first()
    if not user:
        request.session["captcha_answer"] = answer
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username not found", "captcha_question": question}
        )
    user.password = hash_password(new_password)
    db.commit()

    otp = random.randint(100000, 999999)

    print(f"{user.email} OTP:", otp)  # testing only
    return RedirectResponse("/login", status_code=303)

# -------- LOGOUT --------
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# -------- DEPOSITE --------
@app.get("/deposite", response_class=HTMLResponse)
async def deposite(request: Request):
    return templates.TemplateResponse(
        "deposite.html",
        {"request": request}
    )


@app.post("/deposite")
async def deposite(
    request: Request,
    amount: int = Form(...),
    db: Session = Depends(get_db)
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    username = request.session["user"]

    user = db.query(UserInfo).filter(UserInfo.username == username).first()
    if not user:
        return RedirectResponse("/login", status_code=303)

    last_txn = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id)
        .order_by(Transaction.created_at.desc())
        .first()
    )

    new_balance = last_txn.current_balance + amount if last_txn else amount

    new_txn = Transaction(
        user_id=user.id,
        username=user.username,
        transaction_type="Deposit",
        amount=amount,
        current_balance=new_balance
    )

    db.add(new_txn)
    db.commit()

    return templates.TemplateResponse(
        "deposite.html",
        {
            "request": request,
            "success": f"₹{amount} deposited successfully!"
        }
    )


    
# -------------- WITHDRAW -------------
@app.get("/withdraw", response_class=HTMLResponse)
async def withdraw(request: Request):
    return templates.TemplateResponse(
        "withdraw.html",
        {"request": request}
    )


@app.post("/withdraw")
async def withdraw(
    request: Request,
    amount: int = Form(...),
    db: Session = Depends(get_db)
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    username = request.session["user"]

    # 🔹 fetch logged-in user
    user = db.query(UserInfo).filter(UserInfo.username == username).first()
    if not user:
        return RedirectResponse("/login", status_code=303)

    # 🔹 get last transaction
    last_txn = (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id)
        .order_by(Transaction.created_at.desc())
        .first()
    )

    if not last_txn:
        return templates.TemplateResponse(
            "withdraw.html",
            {"request": request, "error": "No balance available"}
        )

    if amount <= 0:
        return templates.TemplateResponse(
            "withdraw.html",
            {"request": request, "error": "Invalid amount"}
        )

    if last_txn.current_balance < amount:
        return templates.TemplateResponse(
            "withdraw.html",
            {"request": request, "error": "Insufficient balance"}
        )

    new_balance = last_txn.current_balance - amount

    # 🔹 create withdraw transaction
    new_txn = Transaction(
        user_id=user.id,
        username=user.username,
        transaction_type="Withdraw",
        amount=amount,
        current_balance=new_balance
    )

    db.add(new_txn)
    db.commit()

    return templates.TemplateResponse(
        "withdraw.html",
        {
            "request": request,
            "success": f"₹{amount} withdrawn successfully!"
        }
    )


# ------------ BALANCE ------------

@app.get("/balance", response_class=HTMLResponse)
async def balance(request: Request, db: Session = Depends(get_db)):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    username = request.session["user"]

    last_txn = (
        db.query(Transaction)
        .filter(Transaction.username == username)
        .order_by(Transaction.created_at.desc())
        .first()
    )
    if last_txn:
        total_balance = last_txn.current_balance
    else:
        total_balance = 0

    return templates.TemplateResponse(
            "balance.html",
            {"request": request, "success": "Your Balance.", "balance": total_balance}
        )

# --------------- HISTORY ------------------

@app.get("/history", response_class=HTMLResponse)
async def transaction_history(request: Request, db: Session = Depends(get_db)):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    username = request.session["user"]
    user = db.query(UserInfo).filter(UserInfo.username == username).first()

    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "transactions": user.transactions
        }
    )

# -------------- PROFILE ---------------
@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, db: Session = Depends(get_db)):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    username = request.session["user"]

    user = db.query(UserInfo).filter(UserInfo.username == username).first()

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user
        }
    )



if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)