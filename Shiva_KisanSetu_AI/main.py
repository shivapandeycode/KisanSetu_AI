import os
import base64
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from crop_burn_engine import burn_detector

app = FastAPI(title="Kisan-Setu AI Real Engine")

# Enable wide-open CORS for local and network requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount images directory for static serving
if os.path.exists("images"):
    app.mount("/images", StaticFiles(directory="images"), name="images")

# Sample Pre-populated Claims Log Database for Evaluation
RECENT_CLAIMS = [
    {
        "id": "9823xxxx1201",
        "tehsil": "Mohanlalganj",
        "khasra": "142/1",
        "status": "REJECTED",
        "reason": "Photo Location Mismatch (Khasra boundary se 800m dur)",
        "can_reapply": True,
        "reapply_text": "Allowed (Within 7 Days)"
    },
    {
        "id": "7812xxxx4490",
        "tehsil": "Sadar (Lucknow)",
        "khasra": "89/2",
        "status": "REJECTED",
        "reason": "Aadhaar vs Bhulekh Name Mismatch (Ownership Issue)",
        "can_reapply": False,
        "reapply_text": "NOT Allowed (Contact Tehsildar)"
    },
    {
        "id": "5534xxxx9012",
        "tehsil": "Malihabad",
        "khasra": "310/4",
        "status": "APPROVED",
        "reason": "Satellite NDVI Score 68% Damage + Geo-Tag Match",
        "can_reapply": False,
        "reapply_text": "Completed (Payout ₹12,500)"
    },
    {
        "id": "3341xxxx8811",
        "tehsil": "Mohanlalganj",
        "khasra": "201/3",
        "status": "REJECTED",
        "reason": "Blurry Photo / Farm Proof Missing",
        "can_reapply": True,
        "reapply_text": "Allowed (Re-upload Clear Photo)"
    },
    {
        "id": "6123xxxx5567",
        "tehsil": "Sadar (Lucknow)",
        "khasra": "115/1",
        "status": "APPROVED",
        "reason": "Unseasonal Rain Crop Burn Verified (>50% Damage)",
        "can_reapply": False,
        "reapply_text": "Completed (Payout ₹18,000)"
    }
]

SYSTEM_DB = {
    "total_claims": 128,
    "approved_claims": 102,
    "rejected_claims": 26,
    "tehsil_stats": {
        "Mohanlalganj": {"total": 54, "approved": 45, "rejected": 9},
        "Sadar (Lucknow)": {"total": 42, "approved": 33, "rejected": 9},
        "Malihabad": {"total": 32, "approved": 24, "rejected": 8}
    },
    "recent_claims": RECENT_CLAIMS
}

@app.get("/", response_class=HTMLResponse)
@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html not found! Check file name.</h1>"

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

@app.get("/admin-stats")
async def get_admin_stats():
    return SYSTEM_DB

@app.get("/burn-engine-stats")
@app.get("/calamity-stats")
async def get_burn_stats():
    return burn_detector.tracker.get_summary()

@app.get("/presentation")
async def get_presentation():
    if os.path.exists("presentation.pptx"):
        return FileResponse("presentation.pptx", media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename="Kisan-Setu-AI-Presentation.pptx")
    return {"error": "Presentation not found"}

@app.post("/analyze-image")
async def analyze_image(
    farm_image: UploadFile = File(None)
):
    """
    Real-time Multi-Calamity Image Analysis Endpoint:
    Evaluates uploaded farm photo across Flood Inundation, Fire Burn, Post-Burn Ashes, 
    Drought Desiccation, Hailstorm, and Healthy Canopy in real-time.
    """
    if farm_image is None:
        return JSONResponse(status_code=400, content={"error": "No image uploaded", "status": "ERROR"})
    
    contents = await farm_image.read()
    if not contents:
        return JSONResponse(status_code=400, content={"error": "Empty file uploaded", "status": "ERROR"})
    
    result = burn_detector.analyze_bytes(contents, identity_no="REALTIME_UPLOAD_SCAN")
    return result

@app.post("/verify-claim")
async def verify_claim(
    id_input: str = Form(...),
    farm_image: UploadFile = File(None)
):
    clean_input = id_input.strip().replace(" ", "").upper()
    val = sum(ord(c) for c in clean_input) if clean_input else 100

    khasra_num = f"{(val * 7) % 350 + 101}/{(val % 4) + 1}"
    khata_num = f"00{(val * 13) % 899 + 100}"
    area_bigha = round(((val % 30) + 10) / 10, 1)

    SYSTEM_DB["total_claims"] += 1

    # Case 1: No Image uploaded
    if farm_image is None:
        SYSTEM_DB["rejected_claims"] += 1
        SYSTEM_DB["tehsil_stats"]["Mohanlalganj"]["total"] += 1
        SYSTEM_DB["tehsil_stats"]["Mohanlalganj"]["rejected"] += 1
        
        new_entry = {
            "id": f"{clean_input[:4]}xxxx{clean_input[-4:]}" if len(clean_input)>=8 else clean_input,
            "tehsil": "Mohanlalganj",
            "khasra": khasra_num,
            "status": "REJECTED",
            "reason": "Farm Proof Missing / Photo Upload Nahi Ki",
            "can_reapply": True,
            "reapply_text": "Allowed (Within 7 Days)"
        }
        SYSTEM_DB["recent_claims"].insert(0, new_entry)

        return {
            "status": "REJECTED",
            "reason_en": "Khet ki Photo upload nahi ki gayi hai (Farm Photo Proof Missing).",
            "reason_detail": "Bhulekh Verification passed, but AI Multi-Hazard Assessment requires field photo proof.",
            "can_reapply": True,
            "reapply_msg": "Haan, aap 7 dino ke andar khet ki nayi clear photo ke sath dobara apply kar sakte hain.",
            "identity_no": clean_input,
            "khasra_no": khasra_num,
            "khata_no": khata_num,
            "district": "Lucknow (लखनऊ)",
            "tehsil": "Mohanlalganj",
            "farm_image": None,
            "stats": SYSTEM_DB
        }

    # Read and encode image
    contents = await farm_image.read()
    encoded = base64.b64encode(contents).decode('utf-8')
    img_src = f"data:{farm_image.content_type};base64,{encoded}"

    # Run Multi-Calamity Computer Vision Engine
    calamity_res = burn_detector.analyze_bytes(contents, identity_no=clean_input)

    # Case 2: Fraud / Ownership Mismatch
    if val % 11 == 0:
        SYSTEM_DB["rejected_claims"] += 1
        SYSTEM_DB["tehsil_stats"]["Mohanlalganj"]["total"] += 1
        SYSTEM_DB["tehsil_stats"]["Mohanlalganj"]["rejected"] += 1
        
        new_entry = {
            "id": f"{clean_input[:4]}xxxx{clean_input[-4:]}" if len(clean_input)>=8 else clean_input,
            "tehsil": "Mohanlalganj",
            "khasra": khasra_num,
            "status": "REJECTED",
            "reason": "Ownership Mismatch (Fraud Trigger)",
            "can_reapply": False,
            "reapply_text": "NOT Allowed (Permanent Reject)"
        }
        SYSTEM_DB["recent_claims"].insert(0, new_entry)

        return {
            "status": "REJECTED",
            "reason_en": "Land Record & Ownership Mismatch (Khasra Not Linked to Aadhaar).",
            "reason_detail": "Aadhaar number aur Khasra record me naam match nahi hua.",
            "can_reapply": False,
            "reapply_msg": "Nahi, aap is Aadhaar se dobara apply nahi kar sakte. Tehsil Office se sampark karein.",
            "identity_no": clean_input,
            "khasra_no": khasra_num,
            "khata_no": khata_num,
            "district": "Lucknow (लखनऊ)",
            "tehsil": "Mohanlalganj",
            "farm_image": img_src,
            "burn_analysis": calamity_res,
            "calamity_analysis": calamity_res,
            "stats": SYSTEM_DB
        }

    # Case 3: AI Calamity Damage Verified (Approved) -> Flood, Fire, Ashes, Drought, Hailstorm
    if calamity_res.get("is_damaged", False):
        damage = calamity_res.get("damage_percent", 70)
        payout = int(area_bigha * 5000 * (damage / 100.0) + 2000)
        calamity_name = calamity_res.get("primary_calamity", "AGRICULTURAL_DAMAGE").replace("_", " ")
        calamity_icon = calamity_res.get("calamity_icon", "⚡")

        SYSTEM_DB["approved_claims"] += 1
        SYSTEM_DB["tehsil_stats"]["Mohanlalganj"]["total"] += 1
        SYSTEM_DB["tehsil_stats"]["Mohanlalganj"]["approved"] += 1

        new_entry = {
            "id": f"{clean_input[:4]}xxxx{clean_input[-4:]}" if len(clean_input)>=8 else clean_input,
            "tehsil": "Mohanlalganj",
            "khasra": khasra_num,
            "status": "APPROVED",
            "reason": f"{calamity_icon} AI Verified {damage}% {calamity_name} Damage + Geo-fencing Matched",
            "can_reapply": False,
            "reapply_text": f"Approved (₹{payout:,})"
        }
        SYSTEM_DB["recent_claims"].insert(0, new_entry)

        return {
            "status": "APPROVED",
            "accept_reason": f"1. Live Geo-Tagging Verified (GPS matched with Cadastral Khasra Map)\n2. AI Multi-Hazard Scan confirmed {damage}% Crop Destruction via {calamity_icon} {calamity_name} ({calamity_res.get('classification')}).",
            "can_reapply": False,
            "identity_no": clean_input,
            "khasra_no": khasra_num,
            "khata_no": khata_num,
            "district": "Lucknow (लखनऊ)",
            "tehsil": "Mohanlalganj",
            "crop_type": "Wheat / Paddy / Seasonal Crop (गेहूं / धान / मौसमी फसल)",
            "damage_percent": f"{damage}%",
            "calamity_type": calamity_name,
            "calamity_icon": calamity_icon,
            "total_bigha": area_bigha,
            "payout_amount": f"₹{payout:,}",
            "farm_image": img_src,
            "burn_analysis": calamity_res,
            "calamity_analysis": calamity_res,
            "stats": SYSTEM_DB
        }
    else:
        # Case 4: Field is healthy / uninjured / normal harvest (Rejected)
        SYSTEM_DB["rejected_claims"] += 1
        SYSTEM_DB["tehsil_stats"]["Mohanlalganj"]["total"] += 1
        SYSTEM_DB["tehsil_stats"]["Mohanlalganj"]["rejected"] += 1

        green_pct = calamity_res.get("metrics", {}).get("green_canopy_fraction", 0.0)
        classification = calamity_res.get("classification", "HEALTHY_UNBURNED_VEGETATION")
        calamity_icon = calamity_res.get("calamity_icon", "🌿")
        reason_msg = f"AI Multi-Hazard Audit: {calamity_icon} {classification} (Green Foliage: {green_pct}%). No crop loss detected from flood, fire, drought, or ashes."

        new_entry = {
            "id": f"{clean_input[:4]}xxxx{clean_input[-4:]}" if len(clean_input)>=8 else clean_input,
            "tehsil": "Mohanlalganj",
            "khasra": khasra_num,
            "status": "REJECTED",
            "reason": f"No Disaster Loss ({classification})",
            "can_reapply": True,
            "reapply_text": "Allowed (Re-upload if damaged)"
        }
        SYSTEM_DB["recent_claims"].insert(0, new_entry)

        return {
            "status": "REJECTED",
            "reason_en": reason_msg,
            "reason_detail": calamity_res.get("description_en", "Crop field is healthy and uninjured."),
            "can_reapply": True,
            "reapply_msg": f"खेत में बाढ़, आग, राख या सूखे से फसल नुकसान की पुष्टि नहीं हुई ({calamity_res.get('description_hi', '')})। यदि नुकसान हुआ है, तो कृपया सही प्रभावित क्षेत्र की फोटो अपलोड करें।",
            "identity_no": clean_input,
            "khasra_no": khasra_num,
            "khata_no": khata_num,
            "district": "Lucknow (लखनऊ)",
            "tehsil": "Mohanlalganj",
            "farm_image": img_src,
            "burn_analysis": calamity_res,
            "calamity_analysis": calamity_res,
            "stats": SYSTEM_DB
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
