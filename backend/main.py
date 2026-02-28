import os
import io
import base64
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

from PIL import Image, ImageDraw, ImageFont
import httpx
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config

# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── App setup ──────────────────────────────────────────────────
app = FastAPI(title="Khalq Certificate API", version="1.0.0")

app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "khalq-secret-key-change-in-prod"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Google OAuth ───────────────────────────────────────────────
config = Config(environ=os.environ)
oauth = OAuth(config)
oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

ALLOWED_EMAIL = "khalqq.pk@gmail.com"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# ── Auth helpers ───────────────────────────────────────────────
def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# ── Pydantic models ────────────────────────────────────────────
class Volunteer(BaseModel):
    name: str
    email: EmailStr

class NameStyle(BaseModel):
    font_size: int = 60
    font_weight: str = "bold"   # bold | regular
    color: str = "#2d3a8c"      # hex color
    pos_x: Optional[int] = None # None = center
    pos_y: int = 400
    center_align: bool = True

class SendRequest(BaseModel):
    certificate_base64: str          # the blank template as base64 PNG
    volunteers: List[Volunteer]
    name_style: NameStyle
    from_name: str = "Khalq Organization"
    subject: str = "Your Certificate of Appreciation — Khalq"
    body_template: str = "Dear {name},\n\nPlease find your Certificate of Appreciation attached.\n\nWarm regards,\nKhalq HR Team"

class PreviewRequest(BaseModel):
    certificate_base64: str
    volunteer_name: str
    name_style: NameStyle

# ── Auth routes ────────────────────────────────────────────────
@app.get("/auth/login")
async def login(request: Request):
    redirect_uri = str(request.base_url) + "auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/callback")
async def auth_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        if not user_info:
            raise HTTPException(status_code=400, detail="Could not fetch user info")

        email = user_info.get("email", "")
        if email != ALLOWED_EMAIL:
            logger.warning(f"Unauthorized login attempt: {email}")
            return RedirectResponse(url=f"{FRONTEND_URL}?error=unauthorized")

        request.session["user"] = {
            "email": email,
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
        }
        logger.info(f"Successful login: {email}")
        return RedirectResponse(url=f"{FRONTEND_URL}?auth=success")

    except Exception as e:
        logger.error(f"Auth error: {e}")
        return RedirectResponse(url=f"{FRONTEND_URL}?error=auth_failed")

@app.get("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url=FRONTEND_URL)

@app.get("/auth/me")
async def get_me(request: Request):
    user = request.session.get("user")
    if not user:
        return JSONResponse({"authenticated": False})
    return JSONResponse({"authenticated": True, "user": user})

# ── Certificate generation ─────────────────────────────────────
def generate_certificate(img_bytes: bytes, name: str, style: NameStyle) -> bytes:
    """Draw the volunteer's name onto the certificate image and return PNG bytes."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    width, height = img.size

    # Try to use a bundled font, fall back to default
    font = None
    font_size = style.font_size
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSerif-Bold.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    # Parse color
    color_hex = style.color.lstrip("#")
    r = int(color_hex[0:2], 16)
    g = int(color_hex[2:4], 16)
    b = int(color_hex[4:6], 16)
    fill = (r, g, b, 255)

    # Calculate position
    bbox = draw.textbbox((0, 0), name, font=font)
    text_width = bbox[2] - bbox[0]

    if style.center_align:
        x = (width - text_width) // 2
    else:
        x = style.pos_x if style.pos_x is not None else (width - text_width) // 2

    y = style.pos_y - font_size // 2  # center vertically around pos_y

    draw.text((x, y), name, font=font, fill=fill)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def send_certificate_email(
    to_email: str,
    to_name: str,
    cert_bytes: bytes,
    from_name: str,
    subject: str,
    body_template: str,
):
    """Send a certificate via Gmail SMTP."""
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        raise ValueError("Gmail credentials not configured")

    body = body_template.replace("{name}", to_name)

    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{gmail_user}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    img_attachment = MIMEImage(cert_bytes, name=f"Certificate_{to_name.replace(' ', '_')}.png")
    img_attachment.add_header("Content-Disposition", "attachment",
                               filename=f"Certificate_{to_name.replace(' ', '_')}.png")
    msg.attach(img_attachment)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, to_email, msg.as_string())


# ── API routes ─────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Khalq Certificate API"}

@app.post("/api/preview")
async def preview_certificate(req: PreviewRequest, user=Depends(get_current_user)):
    """Return a base64 preview of the certificate with the name applied."""
    try:
        img_bytes = base64.b64decode(req.certificate_base64.split(",")[-1])
        cert_bytes = generate_certificate(img_bytes, req.volunteer_name, req.name_style)
        encoded = base64.b64encode(cert_bytes).decode()
        return {"certificate_base64": f"data:image/png;base64,{encoded}"}
    except Exception as e:
        logger.error(f"Preview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send")
async def send_certificates(req: SendRequest, user=Depends(get_current_user)):
    """Generate and email certificates to all volunteers."""
    try:
        img_bytes = base64.b64decode(req.certificate_base64.split(",")[-1])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid certificate image data")

    results = []
    for volunteer in req.volunteers:
        try:
            cert_bytes = generate_certificate(img_bytes, volunteer.name, req.name_style)
            send_certificate_email(
                to_email=volunteer.email,
                to_name=volunteer.name,
                cert_bytes=cert_bytes,
                from_name=req.from_name,
                subject=req.subject,
                body_template=req.body_template,
            )
            results.append({"name": volunteer.name, "email": volunteer.email, "status": "sent"})
            logger.info(f"Certificate sent to {volunteer.name} <{volunteer.email}>")
        except Exception as e:
            logger.error(f"Failed to send to {volunteer.email}: {e}")
            results.append({"name": volunteer.name, "email": volunteer.email, "status": "failed", "error": str(e)})

    sent = sum(1 for r in results if r["status"] == "sent")
    failed = len(results) - sent
    return {
        "total": len(results),
        "sent": sent,
        "failed": failed,
        "results": results,
    }

@app.post("/api/download-single")
async def download_single(req: PreviewRequest, user=Depends(get_current_user)):
    """Return a single certificate as base64 for download."""
    try:
        img_bytes = base64.b64decode(req.certificate_base64.split(",")[-1])
        cert_bytes = generate_certificate(img_bytes, req.volunteer_name, req.name_style)
        encoded = base64.b64encode(cert_bytes).decode()
        return {"certificate_base64": f"data:image/png;base64,{encoded}", "filename": f"Certificate_{req.volunteer_name.replace(' ', '_')}.png"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
