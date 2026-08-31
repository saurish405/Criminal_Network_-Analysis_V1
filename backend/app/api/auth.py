import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

SECRET_KEY = "ncrb-nodespace-super-secret-tactical-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12

router = APIRouter(prefix="/auth", tags=["Authentication"])

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode('utf-8')[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode('utf-8'))

OFFICER_DB = {
    "officer@ncrb.gov.in": {
        "username": "officer@ncrb.gov.in",
        "full_name": "Devendra Pratap",
        "badge_id": "NCRB-IND-9041",
        "role": "Lead Investigating Officer (IO)",
        "station": "Special Cell, Crime Branch",
        "hashed_password": hash_password("ncrb@2026")
    },
    "analyst@ncrb.gov.in": {
        "username": "analyst@ncrb.gov.in",
        "full_name": "Rajeshwar Rao",
        "badge_id": "CYBER-HYD-102",
        "role": "Forensic Graph Intelligence Analyst",
        "station": "Cyber Intelligence Unit",
        "hashed_password": hash_password("analyst@2026")
    }
}

class Token(BaseModel):
    access_token: str
    token_type: str
    officer_name: str
    badge_id: str
    role: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    officer = OFFICER_DB.get(form_data.username)
    if not officer or not verify_password(form_data.password, officer["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Police Credentials or Unauthorized Badge ID",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": officer["username"], "role": officer["role"]})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "officer_name": officer["full_name"],
        "badge_id": officer["badge_id"],
        "role": officer["role"]
    }