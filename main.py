import os
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import uuid4
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Profile, Userauth, Like

app = FastAPI(title="Matchmaking API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple token auth using userauth.token. In real apps, use JWT

def require_auth(token: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    user = db["userauth"].find_one({"token": token})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

@app.get("/")
def read_root():
    return {"message": "Matchmaking Backend Running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:20]
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# -------------------- Stripe-like payment flow (mock) --------------------
class CheckoutRequest(BaseModel):
    email: str

class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str

@app.post("/api/checkout", response_model=CheckoutResponse)
def create_checkout_session(payload: CheckoutRequest):
    token = uuid4().hex
    session_id = uuid4().hex
    doc = {
        "email": payload.email,
        "stripe_customer_id": None,
        "stripe_session_id": session_id,
        "paid": False,
        "token": token,
        "verified": False,
    }
    create_document("userauth", doc)
    return CheckoutResponse(checkout_url=f"/pay/success?session_id={session_id}", session_id=session_id)

class ConfirmRequest(BaseModel):
    session_id: str

class ConfirmResponse(BaseModel):
    token: str

@app.post("/api/confirm", response_model=ConfirmResponse)
def confirm_payment(payload: ConfirmRequest):
    ua = db["userauth"].find_one({"stripe_session_id": payload.session_id})
    if not ua:
        raise HTTPException(status_code=404, detail="Session not found")
    db["userauth"].update_one({"_id": ua["_id"]}, {"$set": {"paid": True}})
    return ConfirmResponse(token=ua["token"])  # return token for subsequent calls

# -------------------- Profile CRUD --------------------
@app.post("/api/profile")
def create_or_update_profile(profile: Profile, user=Depends(require_auth)):
    if not user.get("paid"):
        raise HTTPException(status_code=402, detail="Payment required")
    profile_dict = profile.model_dump()
    profile_dict["userauth_id"] = str(user["_id"])  # store as string
    existing = db["profile"].find_one({"userauth_id": str(user["_id"])})
    if existing:
        db["profile"].update_one({"_id": existing["_id"]}, {"$set": profile_dict})
        return {"status": "updated"}
    else:
        create_document("profile", profile_dict)
        return {"status": "created"}

@app.get("/api/me")
def get_my_profile(user=Depends(require_auth)):
    prof = db["profile"].find_one({"userauth_id": str(user["_id"])})
    if not prof:
        return {"profile": None, "user": {"email": user["email"], "verified": user.get("verified", False)}}
    prof["_id"] = str(prof["_id"])  # serialize
    return {"profile": prof, "user": {"email": user["email"], "verified": user.get("verified", False)}}

# -------------------- Search & Filters --------------------
@app.get("/api/search")
def search_profiles(
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    city: Optional[str] = None,
    religion: Optional[str] = None,
    religion_level: Optional[str] = None,
    education_level: Optional[str] = None,
    occupation: Optional[str] = None,
    income_range: Optional[str] = None,
    diet: Optional[str] = None,
    verified_only: bool = False,
    user=Depends(require_auth)
):
    match: Dict[str, Any] = {}
    if city:
        match["city"] = {"$regex": f"^{city}", "$options": "i"}
    if religion:
        match["religion"] = religion
    if religion_level:
        match["religion_level"] = religion_level
    if education_level:
        match["education_level"] = education_level
    if occupation:
        match["occupation"] = occupation
    if income_range:
        match["income_range"] = income_range
    if diet:
        match["diet"] = diet

    from datetime import date

    if age_min is not None or age_max is not None:
        today = date.today()
        date_filter: Dict[str, Any] = {}
        if age_min is not None:
            # min age -> birth date earlier than today - min_age
            min_birth = date(today.year - max(age_min, 0), today.month, today.day)
            date_filter["$lte"] = min_birth.isoformat()
        if age_max is not None:
            max_birth = date(today.year - max(age_max, 0), today.month, today.day)
            date_filter["$gte"] = max_birth.isoformat()
        if date_filter:
            match["birth_date"] = date_filter

    # query profiles
    profiles = list(db["profile"].find(match))

    # build cards and attach verified flag
    from datetime import datetime as dt
    cards = []
    for r in profiles:
        age = None
        try:
            age = int((dt.now() - dt.fromisoformat(r.get("birth_date"))).days / 365.25)
        except Exception:
            pass
        ua_verified = False
        ua = db["userauth"].find_one({"_id": ObjectId(r.get("userauth_id"))}) if r.get("userauth_id") else None
        if ua:
            ua_verified = bool(ua.get("verified", False))
        if verified_only and not ua_verified:
            continue
        cards.append({
            "name": r.get("full_name"),
            "age": age,
            "city": r.get("city"),
            "photo_url": r.get("photo_url"),
            "religion": r.get("religion"),
            "religion_level": r.get("religion_level"),
            "occupation": r.get("occupation"),
            "education_level": r.get("education_level"),
            "userauth_id": r.get("userauth_id"),
            "verified": ua_verified,
        })
    return {"results": cards}

# -------------------- Likes & Matches --------------------
@app.post("/api/like")
def like_user(payload: Like, user=Depends(require_auth)):
    if str(user["_id"]) == payload.to_userauth_id:
        raise HTTPException(status_code=400, detail="Cannot like yourself")
    create_document("like", {"from_userauth_id": str(user["_id"]), "to_userauth_id": payload.to_userauth_id})
    # check mutual like
    mutual = db["like"].find_one({"from_userauth_id": payload.to_userauth_id, "to_userauth_id": str(user["_id"])})
    if mutual:
        exists = db["match"].find_one({
            "$or": [
                {"userauth_a": str(user["_id"]), "userauth_b": payload.to_userauth_id},
                {"userauth_a": payload.to_userauth_id, "userauth_b": str(user["_id"])},
            ]
        })
        if not exists:
            create_document("match", {"userauth_a": str(user["_id"]), "userauth_b": payload.to_userauth_id})
        return {"status": "match"}
    return {"status": "liked"}

@app.get("/api/matches")
def get_matches(user=Depends(require_auth)):
    matches = list(db["match"].find({"$or": [{"userauth_a": str(user["_id"])}, {"userauth_b": str(user["_id"])}]}))
    for m in matches:
        m["_id"] = str(m["_id"])  # serialize
    return {"matches": matches}

# -------------------- Chat --------------------
class ChatMessage(BaseModel):
    match_id: str
    text: str

@app.post("/api/chat/send")
def send_message(msg: ChatMessage, user=Depends(require_auth)):
    try:
        match = db["match"].find_one({"_id": ObjectId(msg.match_id)})
    except Exception:
        match = None
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if str(user["_id"]) not in [match.get("userauth_a"), match.get("userauth_b")]:
        raise HTTPException(status_code=403, detail="Not allowed")
    create_document("message", {"match_id": msg.match_id, "from_userauth_id": str(user["_id"]), "text": msg.text})
    return {"status": "sent"}

@app.get("/api/chat/{match_id}")
def get_messages(match_id: str, user=Depends(require_auth)):
    try:
        match = db["match"].find_one({"_id": ObjectId(match_id)})
    except Exception:
        match = None
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if str(user["_id"]) not in [match.get("userauth_a"), match.get("userauth_b")]:
        raise HTTPException(status_code=403, detail="Not allowed")
    msgs = list(db["message"].find({"match_id": match_id}).sort("created_at", 1))
    for m in msgs:
        m["_id"] = str(m["_id"])  # serialize
    return {"messages": msgs}

# -------------------- Admin Panel APIs --------------------
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin-secret")

def require_admin(token: Optional[str] = Query(default=None)):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized admin")

@app.get("/api/admin/profiles")
def admin_list_profiles(_: Any = Depends(require_admin)):
    profiles = list(db["profile"].find({}))
    for p in profiles:
        p["_id"] = str(p["_id"])  # serialize
    return {"profiles": profiles}

@app.post("/api/admin/verify/{userauth_id}")
def admin_verify_user(userauth_id: str, _: Any = Depends(require_admin)):
    try:
        oid = ObjectId(userauth_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    res = db["userauth"].update_one({"_id": oid}, {"$set": {"verified": True}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "verified"}

@app.delete("/api/admin/user/{userauth_id}")
def admin_delete_user(userauth_id: str, _: Any = Depends(require_admin)):
    try:
        oid = ObjectId(userauth_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    db["profile"].delete_many({"userauth_id": userauth_id})
    db["like"].delete_many({"$or": [{"from_userauth_id": userauth_id}, {"to_userauth_id": userauth_id}]})
    db["match"].delete_many({"$or": [{"userauth_a": userauth_id}, {"userauth_b": userauth_id}]})
    db["message"].delete_many({"from_userauth_id": userauth_id})
    res = db["userauth"].delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted"}

@app.get("/api/admin/stats")
def admin_stats(_: Any = Depends(require_admin)):
    total_users = db["userauth"].count_documents({})
    total_matches = db["match"].count_documents({})
    verified_users = db["userauth"].count_documents({"verified": True})
    active_users = db["message"].distinct("from_userauth_id")
    return {
        "total_users": total_users,
        "total_matches": total_matches,
        "verified_users": verified_users,
        "active_users": len(active_users)
    }
